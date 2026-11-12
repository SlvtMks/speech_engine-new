from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

from .diarization import SpeakerDiarizer


AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".flac", ".ogg"
}

LOG_FIELDS = [
    "timestamp",
    "status",
    "source_audio",
    "processing_seconds",
    "speakers",
    "segments",
    "json_path",
    "rttm_path",
    "error",
]


def write_log(writer, log_file, **values):
    row = {field: values.get(field, "") for field in LOG_FIELDS}
    writer.writerow(row)
    log_file.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Batch speaker diarization"
    )

    parser.add_argument("input_dir")
    parser.add_argument(
        "--output-dir",
        default="data/diarization",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cuda", "cpu"],
        default="auto",
    )
    parser.add_argument(
        "--model",
        default="pyannote/speaker-diarization-community-1",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of pending files to process",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Reprocess files even when results already exist",
    )
    parser.add_argument(
        "--ffmpeg-bin",
        default=None,
    )

    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}")
        return 2

    if args.limit is not None and args.limit < 1:
        print("--limit must be greater than zero")
        return 2

    files = sorted(
        (
            path for path in input_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in AUDIO_EXTENSIONS
        ),
        key=lambda path: path.name.lower(),
    )

    print(f"Input directory: {input_dir}")
    print(f"Audio files found: {len(files)}")

    if not files:
        print("No supported audio files found.")
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)

    log_path = output_dir / "batch_log.csv"

    skipped = []
    pending = []

    for audio in files:
        json_path = output_dir / f"{audio.stem}.diarization.json"
        rttm_path = output_dir / f"{audio.stem}.rttm"

        if (
            json_path.is_file()
            and rttm_path.is_file()
            and not args.overwrite
        ):
            skipped.append((audio, json_path, rttm_path))
        else:
            pending.append(audio)

    if args.limit is not None:
        pending = pending[:args.limit]

    print(f"Already completed and skipped: {len(skipped)}")
    print(f"Files scheduled for processing: {len(pending)}")

    log_exists = log_path.exists() and log_path.stat().st_size > 0

    processed = 0
    errors = 0
    diarizer = None

    with log_path.open(
        "a",
        encoding="utf-8-sig",
        newline="",
    ) as log_file:

        writer = csv.DictWriter(
            log_file,
            fieldnames=LOG_FIELDS,
        )

        if not log_exists:
            writer.writeheader()
            log_file.flush()

        for audio, json_path, rttm_path in skipped:
            write_log(
                writer,
                log_file,
                timestamp=datetime.now(timezone.utc).isoformat(),
                status="SKIPPED",
                source_audio=str(audio),
                json_path=str(json_path),
                rttm_path=str(rttm_path),
            )

        if pending:
            print("\n=== LOADING MODEL ONCE ===", flush=True)

            try:
                diarizer = SpeakerDiarizer(
                    model_id=args.model,
                    device=args.device,
                    ffmpeg_bin=args.ffmpeg_bin,
                )
            except Exception as exc:
                message = f"Model initialization failed: {type(exc).__name__}: {exc}"
                print(message)

                for audio in pending:
                    write_log(
                        writer,
                        log_file,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        status="ERROR",
                        source_audio=str(audio),
                        error=message,
                    )

                return 2

            print("\n=== BATCH PROCESSING ===", flush=True)

        try:
            for index, audio in enumerate(pending, start=1):
                print(
                    f"\n[{index}/{len(pending)}] {audio.name}",
                    flush=True,
                )

                started = time.perf_counter()

                try:
                    result = diarizer.diarize(
                        audio_path=audio,
                        output_dir=output_dir,
                        overwrite=True,
                    )

                    elapsed = round(
                        time.perf_counter() - started, 2
                    )

                    processed += 1

                    write_log(
                        writer,
                        log_file,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        status="OK",
                        source_audio=str(audio),
                        processing_seconds=elapsed,
                        speakers=result["num_speakers"],
                        segments=result["num_segments"],
                        json_path=result["json_path"],
                        rttm_path=result["rttm_path"],
                    )

                    print(
                        f"OK | speakers={result['num_speakers']} "
                        f"| segments={result['num_segments']} "
                        f"| elapsed={elapsed}s",
                        flush=True,
                    )

                except Exception as exc:
                    elapsed = round(
                        time.perf_counter() - started, 2
                    )

                    errors += 1
                    message = f"{type(exc).__name__}: {exc}"

                    write_log(
                        writer,
                        log_file,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        status="ERROR",
                        source_audio=str(audio),
                        processing_seconds=elapsed,
                        error=message,
                    )

                    print(f"ERROR: {message}", flush=True)

        except KeyboardInterrupt:
            print(
                "\nInterrupted. Completed files are preserved. "
                "Run again to continue.",
                flush=True,
            )
            return 130

    print("\n=== BATCH SUMMARY ===")
    print("Processed successfully:", processed)
    print("Skipped:", len(skipped))
    print("Errors:", errors)
    print("Log:", log_path)
    print("Output directory:", output_dir)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())