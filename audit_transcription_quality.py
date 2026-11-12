import json
import csv
import re
from pathlib import Path
from collections import Counter

ROOT = Path(r"F:\speech-engine\data\call_analysis")
OUT = Path(r"F:\speech-engine\data\qc_timestamp_audit.csv")

rows = []
totals = Counter()
repeat_runs = []

def normalize(word):
    return re.sub(r"[^\w]+", "", word.lower(), flags=re.UNICODE)

for path in ROOT.glob("*.json"):
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        totals["read_errors"] += 1
        continue

    words = data.get("words") or []
    segments = data.get("transcription_segments") or []
    duration = data.get("audio_duration_seconds")

    zero = 0
    short = 0
    low_prob = 0
    outside_audio = 0
    last_5_sec = 0
    zero_last_5_sec = 0

    normalized_words = []

    for word in words:
        start = word.get("start")
        end = word.get("end")
        probability = word.get("probability")

        token = normalize(str(word.get("word", "")))
        normalized_words.append((token, word))

        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            if end == start:
                zero += 1

            if end - start < 0.04:
                short += 1

            if isinstance(duration, (int, float)):
                if start < 0 or end > duration + 0.1:
                    outside_audio += 1

                if duration - start <= 5:
                    last_5_sec += 1

                    if end == start:
                        zero_last_5_sec += 1

        if isinstance(probability, (int, float)) and probability < 0.4:
            low_prob += 1

    # Ищем подряд идущие повторы одного и того же слова
    runs = []
    i = 0

    while i < len(normalized_words):
        token = normalized_words[i][0]

        if not token:
            i += 1
            continue

        j = i + 1

        while j < len(normalized_words) and normalized_words[j][0] == token:
            j += 1

        run_length = j - i

        if run_length >= 5:
            run = normalized_words[i:j]
            runs.append((token, run_length))

            repeat_runs.append({
                "file": path.name,
                "word": token,
                "count": run_length,
                "start": run[0][1].get("start"),
                "end": run[-1][1].get("end"),
            })

        i = j

    segment_outside = 0

    if isinstance(duration, (int, float)):
        for segment in segments:
            end = segment.get("end")
            if isinstance(end, (int, float)) and end > duration + 0.1:
                segment_outside += 1

    totals["files"] += 1
    totals["words"] += len(words)
    totals["zero"] += zero
    totals["short"] += short
    totals["low_prob"] += low_prob
    totals["outside_audio"] += outside_audio
    totals["last_5_sec"] += last_5_sec
    totals["zero_last_5_sec"] += zero_last_5_sec
    totals["segment_outside"] += segment_outside
    totals["repeat_runs"] += len(runs)

    rows.append({
        "file": path.name,
        "duration": duration,
        "words": len(words),
        "zero": zero,
        "short": short,
        "low_probability": low_prob,
        "outside_audio": outside_audio,
        "last_5_sec_words": last_5_sec,
        "zero_last_5_sec": zero_last_5_sec,
        "repeat_runs_5plus": len(runs),
        "segment_outside_audio": segment_outside,
    })

with OUT.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print("\n=== DATASET SUMMARY ===")
for key, value in totals.items():
    print(f"{key}: {value}")

print("\n=== REPEATED WORD RUNS (5+ consecutive repetitions) ===")
print(f"Total runs: {len(repeat_runs)}")

for item in sorted(repeat_runs, key=lambda x: x["count"], reverse=True)[:30]:
    print(
        f'{item["file"]} | word="{item["word"]}" | '
        f'count={item["count"]} | '
        f'{item["start"]}–{item["end"]}'
    )

print("\n=== TOP 20 BY ZERO-DURATION WORDS ===")
for row in sorted(rows, key=lambda x: x["zero"], reverse=True)[:20]:
    print(
        f'{row["file"]} | zero={row["zero"]} | '
        f'last_5_sec={row["last_5_sec_words"]} | '
        f'zero_last_5_sec={row["zero_last_5_sec"]} | '
        f'repeats={row["repeat_runs_5plus"]} | '
        f'outside={row["outside_audio"]}'
    )

print(f"\nCSV saved: {OUT}")
