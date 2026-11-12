from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


DEFAULT_ASR_MODEL = "large-v3"
DEFAULT_DIARIZATION_MODEL = "pyannote/speaker-diarization-community-1"

MIN_OVERLAP_SECONDS = 0.04
MIN_WORD_COVERAGE = 0.20


def merge_speaker_intervals(
    segments: list[dict[str, Any]],
) -> dict[str, list[tuple[float, float]]]:
    """Объединяет пересекающиеся интервалы одного говорящего."""
    grouped: dict[str, list[tuple[float, float]]] = {}

    for segment in segments:
        speaker = str(segment["speaker"])
        start = float(segment["start"])
        end = float(segment["end"])

        if end <= start:
            continue

        grouped.setdefault(speaker, []).append((start, end))

    merged: dict[str, list[tuple[float, float]]] = {}

    for speaker, intervals in grouped.items():
        intervals.sort()
        speaker_intervals: list[list[float]] = []

        for start, end in intervals:
            if not speaker_intervals or start > speaker_intervals[-1][1]:
                speaker_intervals.append([start, end])
            else:
                speaker_intervals[-1][1] = max(
                    speaker_intervals[-1][1], end
                )

        merged[speaker] = [
            (start, end) for start, end in speaker_intervals
        ]

    return merged


def assign_speakers(
    words: list[dict[str, Any]],
    diarization_segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Назначает говорящего каждому слову по пересечению временных интервалов.

    При нескольких пересекающихся говорящих сохраняет всех кандидатов.
    Если пересечения недостаточно, speaker=None.
    """
    intervals = merge_speaker_intervals(diarization_segments)

    result = []

    for word in words:
        start = float(word["start"])
        end = float(word["end"])
        duration = end - start

        scores: list[dict[str, Any]] = []

        if duration > 0:
            for speaker, speaker_intervals in intervals.items():
                overlap = 0.0

                for interval_start, interval_end in speaker_intervals:
                    overlap += max(
                        0.0,
                        min(end, interval_end) - max(start, interval_start),
                    )

                coverage = min(1.0, overlap / duration)

                if (
                    overlap >= MIN_OVERLAP_SECONDS
                    and coverage >= MIN_WORD_COVERAGE
                ):
                    scores.append({
                        "speaker": speaker,
                        "overlap_seconds": round(overlap, 3),
                        "word_coverage": round(coverage, 3),
                    })

        scores.sort(
            key=lambda item: (
                -item["overlap_seconds"],
                item["speaker"],
            )
        )

        row = dict(word)
        row["speaker"] = scores[0]["speaker"] if scores else None
        row["speaker_candidates"] = scores

        result.append(row)

    return result


def build_dialogue(
    words: list[dict[str, Any]],
    max_gap: float = 1.0,
) -> list[dict[str, Any]]:
    """Объединяет последовательные слова одного говорящего в реплики."""
    dialogue: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current

        if current is None:
            return

        parts = [item["word"] for item in current["words"]]
        text = "".join(parts).strip()

        candidate_speakers = sorted({
            candidate["speaker"]
            for item in current["words"]
            for candidate in item["speaker_candidates"]
        })

        dialogue.append({
            "start": round(current["start"], 3),
            "end": round(current["end"], 3),
            "duration": round(
                current["end"] - current["start"], 3
            ),
            "speaker": current["speaker"],
            "speaker_candidates": candidate_speakers,
            "word_count": len(current["words"]),
            "text": text,
        })

        current = None

    for word in words:
        start = float(word["start"])
        end = float(word["end"])
        speaker = word["speaker"]

        can_append = False

        if current is not None and current["speaker"] == speaker:
            gap = start - current["end"]
            can_append = -0.08 <= gap <= max_gap

        if can_append:
            current["words"].append(word)
            current["end"] = max(current["end"], end)
        else:
            flush()
            current = {
                "start": start,
                "end": end,
                "speaker": speaker,
                "words": [word],
            }

    flush()
    return dialogue


def format_timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes:02d}:{remainder:05.2f}"


def write_results(
    result: dict[str, Any],
    json_path: Path,
    text_path: Path,
) -> None:
    """Сохраняет JSON и читаемый TXT через временные файлы."""
    json_temp = json_path.with_suffix(json_path.suffix + ".tmp")
    text_temp = text_path.with_suffix(text_path.suffix + ".tmp")

    try:
        json_temp.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        lines = [
            "SPEECH ENGINE — CALL ANALYSIS",
            f"Audio: {result['source_audio']}",
            f"ASR model: {result['asr_model']}",
            f"Diarization model: {result['diarization_model']}",
            f"Language: {result['language']}",
            f"Speakers: {result['diarization']['speakers']}",
            "",
            "=== DIALOGUE ===",
            "",
        ]

        for item in result["dialogue"]:
            speaker = item["speaker"] or "UNKNOWN"
            lines.append(
                f"[{format_timestamp(item['start'])} - "
                f"{format_timestamp(item['end'])}] "
                f"{speaker}: {item['text']}"
            )

        lines.extend([
            "",
            "=== FULL TRANSCRIPTION ===",
            "",
            result["text"],
        ])

        text_temp.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

        json_temp.replace(json_path)
        text_temp.replace(text_path)

    finally:
        if json_temp.exists():
            json_temp.unlink()

        if text_temp.exists():
            text_temp.unlink()


class CallAnalyzer:
    """
    Единый анализатор звонков.

    Whisper и Pyannote загружаются не чаще одного раза на экземпляр.
    Готовая диаризация переиспользуется из JSON-кэша.
    """

    def __init__(
        self,
        asr_model: str = DEFAULT_ASR_MODEL,
        diarization_model: str = DEFAULT_DIARIZATION_MODEL,
        device: str = "auto",
        compute_type: str = "auto",
        language: str | None = None,
        beam_size: int = 5,
        ffmpeg_bin: str | Path | None = None,
    ) -> None:

        # Настраиваем DLL до импорта Faster-Whisper и Torch.
        from .runtime import configure_native_libraries

        runtime_info = configure_native_libraries(
            ffmpeg_bin=ffmpeg_bin
        )

        import ctranslate2

        if device == "auto":
            device = (
                "cuda"
                if ctranslate2.get_cuda_device_count() > 0
                else "cpu"
            )

        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"

        if device == "cuda" and ctranslate2.get_cuda_device_count() == 0:
            raise RuntimeError(
                "CTranslate2 cannot access CUDA."
            )

        from faster_whisper import WhisperModel

        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.asr_model_name = asr_model
        self.diarization_model_name = diarization_model

        self.diarizer = None

        print("=== NATIVE RUNTIME ===")
        print(runtime_info)

        print("\n=== LOADING WHISPER ===", flush=True)

        self.whisper = WhisperModel(
            asr_model,
            device=device,
            compute_type=compute_type,
        )

        print("Whisper loaded.", flush=True)
        print(f"Device: {device}")
        print(f"Compute type: {compute_type}")

    def get_diarization(
        self,
        audio_path: Path,
        diarization_dir: Path,
        recompute: bool = False,
    ) -> dict[str, Any]:

        diarization_path = (
            diarization_dir
            / f"{audio_path.stem}.diarization.json"
        )

        if diarization_path.is_file() and not recompute:
            print(
                f"Using existing diarization: {diarization_path}",
                flush=True,
            )

            data = json.loads(
                diarization_path.read_text(encoding="utf-8")
            )

            if "segments" not in data:
                raise ValueError(
                    f"Invalid diarization JSON: {diarization_path}"
                )

            return data

        from .diarization import SpeakerDiarizer

        if self.diarizer is None:
            self.diarizer = SpeakerDiarizer(
                model_id=self.diarization_model_name,
                device=self.device,
            )

        return self.diarizer.diarize(
            audio_path=audio_path,
            output_dir=diarization_dir,
            overwrite=recompute,
        )

    def analyze(
        self,
        audio_path: str | Path,
        output_dir: str | Path = "data/call_analysis",
        diarization_dir: str | Path = "data/diarization",
        overwrite: bool = False,
        recompute_diarization: bool = False,
    ) -> dict[str, Any]:

        source = Path(audio_path).expanduser().resolve()

        if not source.is_file():
            raise FileNotFoundError(source)

        output_dir = Path(output_dir).expanduser().resolve()
        diarization_dir = Path(
            diarization_dir
        ).expanduser().resolve()

        json_path = (
            output_dir / f"{source.stem}.call-analysis.json"
        )

        text_path = (
            output_dir / f"{source.stem}.call-analysis.txt"
        )

        if not overwrite and (
            json_path.exists() or text_path.exists()
        ):
            raise FileExistsError(
                "Call analysis results already exist. "
                "Use --overwrite to replace them."
            )

        started = time.perf_counter()

        # 1. Получаем диаризацию из кэша или запускаем Pyannote.
        print("\n=== DIARIZATION ===", flush=True)

        diarization = self.get_diarization(
            source,
            diarization_dir,
            recompute=recompute_diarization,
        )

        diarization_segments = diarization["segments"]

        # 2. Распознаём исходный аудиофайл без добавления тишины.
        # Так обе модели работают на одной временной шкале.
        print("\n=== WHISPER TRANSCRIPTION ===", flush=True)

        segments_iter, info = self.whisper.transcribe(
            str(source),
            language=self.language,
            beam_size=self.beam_size,
            temperature=0.0,
            vad_filter=True,
            word_timestamps=True,
        )

        asr_segments = []
        words = []

        for segment in segments_iter:
            asr_segments.append({
                "start": float(segment.start),
                "end": float(segment.end),
                "text": segment.text.strip(),
            })

            for word in segment.words or []:
                if word.start is None or word.end is None:
                    continue

                probability = getattr(word, "probability", None)

                words.append({
                    "start": float(word.start),
                    "end": float(word.end),
                    "word": word.word,
                    "probability": (
                        float(probability)
                        if probability is not None
                        else None
                    ),
                })

        full_text = " ".join(
            segment["text"] for segment in asr_segments
        ).strip()

        # 3. Назначаем слова говорящим.
        print("\n=== WORD-LEVEL SPEAKER ALIGNMENT ===", flush=True)

        words = assign_speakers(
            words,
            diarization_segments,
        )

        # 4. Собираем слова в реплики.
        dialogue = build_dialogue(words)

        known_words = [
            word for word in words
            if word["speaker"] is not None
        ]

        speakers = sorted(
            str(speaker)
            for speaker in diarization.get(
                "speakers",
                sorted({
                    str(segment["speaker"])
                    for segment in diarization_segments
                }),
            )
        )

        elapsed = round(
            time.perf_counter() - started, 2
        )

        result = {
            "schema_version": "1.0",
            "source_audio": str(source),
            "asr_model": self.asr_model_name,
            "diarization_model": self.diarization_model_name,
            "device": self.device,
            "compute_type": self.compute_type,
            "language": info.language,
            "language_probability": float(
                info.language_probability
            ),
            "audio_duration_seconds": (
                float(info.duration)
                if getattr(info, "duration", None) is not None
                else None
            ),
            "processing_seconds": elapsed,
            "text": full_text,
            "transcription_segments": asr_segments,
            "diarization": {
                "speakers": speakers,
                "num_speakers": len(speakers),
                "num_segments": len(diarization_segments),
                "segments": diarization_segments,
            },
            "words": words,
            "word_count": len(words),
            "assigned_word_count": len(known_words),
            "unassigned_word_count": (
                len(words) - len(known_words)
            ),
            "dialogue": dialogue,
            "assignment_settings": {
                "minimum_overlap_seconds": MIN_OVERLAP_SECONDS,
                "minimum_word_coverage": MIN_WORD_COVERAGE,
            },
        }

        output_dir.mkdir(parents=True, exist_ok=True)

        write_results(
            result,
            json_path,
            text_path,
        )

        print("\n=== CALL ANALYSIS COMPLETE ===")
        print("Language:", info.language)
        print("Speakers:", speakers)
        print("Whisper segments:", len(asr_segments))
        print("Words:", len(words))
        print("Words with assigned speaker:", len(known_words))
        print(
            "Words without assigned speaker:",
            len(words) - len(known_words),
        )
        print("Dialogue lines:", len(dialogue))
        print("Elapsed:", elapsed, "sec")
        print("JSON:", json_path)
        print("TXT:", text_path)

        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Combined STT and speaker diarization"
    )

    parser.add_argument("audio")

    parser.add_argument(
        "--output-dir",
        default="data/call_analysis",
    )

    parser.add_argument(
        "--diarization-dir",
        default="data/diarization",
    )

    parser.add_argument(
        "--device",
        choices=["auto", "cuda", "cpu"],
        default="auto",
    )

    parser.add_argument(
        "--compute-type",
        default="auto",
        choices=["auto", "float16", "int8_float16", "int8", "float32"],
    )

    parser.add_argument(
        "--language",
        default="auto",
        help="Language code, e.g. ru, en, or auto",
    )

    parser.add_argument(
        "--asr-model",
        default=DEFAULT_ASR_MODEL,
    )

    parser.add_argument(
        "--diarization-model",
        default=DEFAULT_DIARIZATION_MODEL,
    )

    parser.add_argument(
        "--beam-size",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--ffmpeg-bin",
        default=None,
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    parser.add_argument(
        "--recompute-diarization",
        action="store_true",
    )

    args = parser.parse_args(argv)

    language = (
        None if args.language.lower() == "auto"
        else args.language
    )

    analyzer = CallAnalyzer(
        asr_model=args.asr_model,
        diarization_model=args.diarization_model,
        device=args.device,
        compute_type=args.compute_type,
        language=language,
        beam_size=args.beam_size,
        ffmpeg_bin=args.ffmpeg_bin,
    )

    analyzer.analyze(
        audio_path=args.audio,
        output_dir=args.output_dir,
        diarization_dir=args.diarization_dir,
        overwrite=args.overwrite,
        recompute_diarization=args.recompute_diarization,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())