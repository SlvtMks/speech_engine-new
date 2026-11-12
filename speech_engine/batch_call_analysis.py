from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

from .call_analysis import CallAnalyzer


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}

LOG_FIELDS = [
    "timestamp",
    "status",
    "audio",
    "speakers",
    "words",
    "assigned_words",
    "unknown_words",
    "dialogue_lines",
    "processing_seconds",
    "json_path",
    "txt_path",
    "error",
]


def write_log(writer, log_file, **values):
    row = {field: values.get(field, "") for field in LOG_FIELDS}
    writer.writerow(row)
    log_file.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Batch STT and speaker diarization analysis"
    )

    parser.add_argument("input_dir")
    parser.add_argument("--output-dir", default="data/call_analysis")
    parser.add_argument("--diarization-dir", default="data/diarization")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="cuda")
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument("--language", default="ru")
    parser.add_argument("--asr-model", default="large-v3")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    diarization_dir = Path(args.diarization_dir).resolve()

    if not input_dir.is_dir():
        raise NotADirectoryError(input_dir)

    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be greater than zero")

    audio_files = sorted(
        (
            path for path in input_dir.iterdir()
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
        ),
        key=lambda path: path.name.lower(),
    )

    print("Audio files found:", len(audio_files))

    output_dir.mkdir(parents=True, exist_ok=True)

    pending = []
    skipped = 0
    missing_diarization = 0
    conflicts = 0

    for audio in audio_files:
        diar_path = diarization_dir / f"{audio.stem}.diarization.json"

        json_path = output_dir / f"{audio.stem}.call-analysis.json"
        txt_path = output_dir / f"{audio.stem}.call-analysis.txt"

        if (
            json_path.is_file()
            and txt_path.is_file()
            and not args.overwrite
        ):
            skipped += 1
            continue

        if not diar_path.is_file():
            missing_diarization += 1
            continue

        if (json_path.exists() or txt_path.exists()) and not args.overwrite:
            conflicts += 1
            continue

        pending.append(audio)

    if args.limit is not None:
        pending = pending[:args.limit]

    print("Already completed:", skipped)
    print("Missing diarization:", missing_diarization)
    print("Incomplete output conflicts:", conflicts)
    print("Scheduled for analysis:", len(pending))

    log_path = output_dir / "batch_call_analysis.csv"
    log_exists = log_path.exists() and log_path.stat().st_size > 0

    processed = 0
    errors = 0

    with log_path.open("a", encoding="utf-8-sig", newline="") as log_file:
        writer = csv.DictWriter(log_file, fieldnames=LOG_FIELDS)

        if not log_exists:
            writer.writeheader()
            log_file.flush()

        if not pending:
            print("No eligible files to process.")
            print("Log:", log_path)
            return 0

        print("\n=== LOADING WHISPER ONCE ===", flush=True)

        try:
            analyzer = CallAnalyzer(
                asr_model=args.asr_model,
                device=args.device,
                compute_type=args.compute_type,
                language=args.language,
            )
        except Exception as exc:
            print(f"Whisper initialization failed: {exc}")
            return 2

        print("\n=== BATCH CALL ANALYSIS ===", flush=True)

        for index, audio in enumerate(pending, start=1):
            print(
                f"\n[{index}/{len(pending)}] {audio.name}",
                flush=True,
            )

            started = time.perf_counter()

            try:
                result = analyzer.analyze(
                    audio_path=audio,
                    output_dir=output_dir,
                    diarization_dir=diarization_dir,
                    overwrite=args.overwrite,
                )

                elapsed = round(time.perf_counter() - started, 2)
                processed += 1

                write_log(
                    writer,
                    log_file,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    status="OK",
                    audio=str(audio),
                    speakers=result["diarization"]["num_speakers"],
                    words=result["word_count"],
                    assigned_words=result["assigned_word_count"],
                    unknown_words=result["unassigned_word_count"],
                    dialogue_lines=len(result["dialogue"]),
                    processing_seconds=elapsed,
                    json_path=str(
                        output_dir / f"{audio.stem}.call-analysis.json"
                    ),
                    txt_path=str(
                        output_dir / f"{audio.stem}.call-analysis.txt"
                    ),
                )

                print(
                    f"OK | words={result['word_count']} "
                    f"| assigned={result['assigned_word_count']} "
                    f"| speakers={result['diarization']['num_speakers']} "
                    f"| elapsed={elapsed}s",
                    flush=True,
                )

            except Exception as exc:
                elapsed = round(time.perf_counter() - started, 2)
                errors += 1

                message = f"{type(exc).__name__}: {exc}"

                write_log(
                    writer,
                    log_file,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    status="ERROR",
                    audio=str(audio),
                    processing_seconds=elapsed,
                    error=message,
                )

                print("ERROR:", message, flush=True)

    print("\n=== BATCH CALL ANALYSIS SUMMARY ===")
    print("Processed:", processed)
    print("Skipped:", skipped)
    print("Missing diarization:", missing_diarization)
    print("Output conflicts:", conflicts)
    print("Errors:", errors)
    print("Log:", log_path)
    print("Output:", output_dir)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())