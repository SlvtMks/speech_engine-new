from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "pyannote/speaker-diarization-community-1"

DEFAULT_FFMPEG_BIN = Path(
    os.environ.get(
        "SPEECH_ENGINE_FFMPEG_BIN",
        r"C:\ffmpeg-8.0.1-full_build-shared\bin",
    )
)

_DLL_DIRECTORY_HANDLE: Any = None


def register_ffmpeg_dlls(ffmpeg_bin: str | Path | None = None) -> None:
    from .runtime import configure_native_libraries

    configure_native_libraries(ffmpeg_bin=ffmpeg_bin)

def annotation_to_segments(annotation: Any) -> list[dict[str, Any]]:
    """
    РџСЂРµРѕР±СЂР°Р·СѓРµС‚ pyannote Annotation РІ СЃРїРёСЃРѕРє РІСЂРµРјРµРЅРЅС‹С… СЃРµРіРјРµРЅС‚РѕРІ.
    РЎРѕС…СЂР°РЅСЏРµС‚ РїРµСЂРµРєСЂС‹С‚РёСЏ РјРµР¶РґСѓ РіРѕРІРѕСЂСЏС‰РёРјРё.
    """
    segments = []

    for turn, _, speaker in annotation.itertracks(yield_label=True):
        start = float(turn.start)
        end = float(turn.end)

        segments.append(
            {
                "speaker": str(speaker),
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
            }
        )

    segments.sort(
        key=lambda item: (
            item["start"],
            item["end"],
            item["speaker"],
        )
    )

    return segments


class SpeakerDiarizer:
    """
    РћР±СЂР°Р±РѕС‚С‡РёРє РґРёР°СЂРёР·Р°С†РёРё РЅР° Р±Р°Р·Рµ pyannote.audio.

    РњРѕРґРµР»СЊ Р·Р°РіСЂСѓР¶Р°РµС‚СЃСЏ РѕРґРёРЅ СЂР°Р· РїСЂРё СЃРѕР·РґР°РЅРёРё РѕР±СЉРµРєС‚Р°.
    Р”Р»СЏ MP3 РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ preload=True.
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL,
        device: str = "auto",
        ffmpeg_bin: str | Path | None = None,
    ) -> None:

        # РЎРЅР°С‡Р°Р»Р° СЂРµРіРёСЃС‚СЂРёСЂСѓРµРј FFmpeg DLL.
        # РўРѕР»СЊРєРѕ РїРѕСЃР»Рµ СЌС‚РѕРіРѕ РёРјРїРѕСЂС‚РёСЂСѓРµРј torch Рё pyannote.
        register_ffmpeg_dlls(ffmpeg_bin)

        import torch
        from pyannote.audio import Pipeline

        self.torch = torch
        self.model_id = model_id

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA requested, but PyTorch cannot access the GPU."
            )

        self.device = device

        print(f"Loading diarization model: {model_id}", flush=True)
        print(f"Device: {self.device}", flush=True)

        self.pipeline = Pipeline.from_pretrained(
            model_id,
            token=True,
        )

        self.pipeline.to(torch.device(self.device))

        print("Diarization model loaded.", flush=True)

    def diarize(
        self,
        audio_path: str | Path,
        output_dir: str | Path = "data/diarization",
        overwrite: bool = False,
    ) -> dict[str, Any]:

        source = Path(audio_path).expanduser().resolve()

        if not source.is_file():
            raise FileNotFoundError(
                f"Audio file not found: {source}"
            )

        destination = Path(output_dir).expanduser().resolve()

        json_path = destination / f"{source.stem}.diarization.json"
        rttm_path = destination / f"{source.stem}.rttm"

        existing = [
            path for path in (json_path, rttm_path)
            if path.exists()
        ]

        if existing and not overwrite:
            raise FileExistsError(
                "Output files already exist: "
                + ", ".join(str(path) for path in existing)
                + ". Use --overwrite to replace them."
            )

        print(f"Processing: {source.name}", flush=True)

        # Р’Р°Р¶РЅРѕ: preload=True СѓСЃС‚СЂР°РЅСЏРµС‚ РїСЂРѕР±Р»РµРјСѓ РІС‹Р±РѕСЂРѕС‡РЅРѕРіРѕ С‡С‚РµРЅРёСЏ
        # РєРѕСЂРѕС‚РєРёС… MP3-С„СЂР°РіРјРµРЅС‚РѕРІ, РѕР±РЅР°СЂСѓР¶РµРЅРЅСѓСЋ РїСЂРё РїРµСЂРІРѕРј С‚РµСЃС‚Рµ.
        output = self.pipeline(
            str(source),
            preload=True,
        )

        diarization = output.speaker_diarization
        exclusive = output.exclusive_speaker_diarization

        speakers = sorted(
            str(speaker) for speaker in diarization.labels()
        )

        segments = annotation_to_segments(diarization)
        exclusive_segments = annotation_to_segments(exclusive)

        result = {
            "schema_version": "1.0",
            "source_audio": str(source),
            "model": self.model_id,
            "device": self.device,
            "num_speakers": len(speakers),
            "speakers": speakers,
            "num_segments": len(segments),
            "segments": segments,
            "exclusive_num_segments": len(exclusive_segments),
            "exclusive_segments": exclusive_segments,
        }

        destination.mkdir(parents=True, exist_ok=True)

        # РђС‚РѕРјР°СЂРЅР°СЏ Р·Р°РїРёСЃСЊ JSON.
        json_temp = json_path.with_suffix(
            json_path.suffix + ".tmp"
        )

        with json_temp.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as file:
            json.dump(
                result,
                file,
                ensure_ascii=False,
                indent=2,
            )

        json_temp.replace(json_path)

        # Р¤РѕСЂРјРёСЂСѓРµРј RTTM РёР· РїРѕР»РЅРѕР№ РґРёР°СЂРёР·Р°С†РёРё.
        # РџРµСЂРµРєСЂС‹РІР°СЋС‰РёРµСЃСЏ РёРЅС‚РµСЂРІР°Р»С‹ РЅРµ СѓРґР°Р»СЏСЋС‚СЃСЏ.
        uri = source.stem.replace(" ", "_")
        rttm_temp = rttm_path.with_suffix(
            rttm_path.suffix + ".tmp"
        )

        with rttm_temp.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as file:
            for segment in segments:
                file.write(
                    f"SPEAKER {uri} 1 "
                    f"{segment['start']:.3f} "
                    f"{segment['duration']:.3f} "
                    f"<NA> <NA> "
                    f"{segment['speaker']} <NA> <NA>\n"
                )

        rttm_temp.replace(rttm_path)

        result["json_path"] = str(json_path)
        result["rttm_path"] = str(rttm_path)

        print("\n=== DIARIZATION RESULT ===")
        print("Speakers:", len(speakers), speakers)
        print("Segments:", len(segments))
        print("JSON:", json_path)
        print("RTTM:", rttm_path)

        for segment in segments:
            print(
                f"{segment['speaker']}: "
                f"{segment['start']:.3f} - "
                f"{segment['end']:.3f} "
                f"({segment['duration']:.3f} sec)"
            )

        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Speech Engine speaker diarization"
    )

    parser.add_argument(
        "audio",
        help="Path to the source audio file",
    )

    parser.add_argument(
        "--output-dir",
        default="data/diarization",
        help="Directory for JSON and RTTM output",
    )

    parser.add_argument(
        "--device",
        choices=["auto", "cuda", "cpu"],
        default="auto",
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
    )

    parser.add_argument(
        "--ffmpeg-bin",
        default=None,
        help="Path to FFmpeg Shared bin directory",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing output files",
    )

    args = parser.parse_args(argv)

    diarizer = SpeakerDiarizer(
        model_id=args.model,
        device=args.device,
        ffmpeg_bin=args.ffmpeg_bin,
    )

    diarizer.diarize(
        audio_path=args.audio,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())