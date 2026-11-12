import json
from pathlib import Path
from collections import Counter

ROOT = Path(r"F:\speech-engine\data\call_analysis")
files = list(ROOT.glob("*.json"))

stats = Counter()
problem_files = []

for path in files:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        stats["read_errors"] += 1
        continue

    words = data.get("words") or []
    duration = data.get("duration")

    if not isinstance(duration, (int, float)):
        duration = None

    stats["files"] += 1
    stats["total_words"] += len(words)

    zero = []
    repeated = Counter()
    invalid = []
    short = []
    low_probability = []
    near_end = []

    for word in words:
        start = word.get("start")
        end = word.get("end")

        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            invalid.append(word)
            continue

        if end <= start:
            zero.append(word)

        if end < start:
            stats["negative_duration_words"] += 1

        if end - start < 0.04:
            short.append(word)

        if start == end:
            repeated[round(start, 3)] += 1

        probability = word.get("probability")
        if isinstance(probability, (int, float)) and probability < 0.4:
            low_probability.append(word)

        if duration is not None and duration - start <= 1.0:
            near_end.append(word)

    repeated_groups = sum(1 for count in repeated.values() if count > 1)
    repeated_words = sum(count for count in repeated.values() if count > 1)

    stats["zero_words"] += len(zero)
    stats["short_words"] += len(short)
    stats["invalid_words"] += len(invalid)
    stats["low_probability_words"] += len(low_probability)
    stats["near_end_words"] += len(near_end)
    stats["repeated_timestamp_groups"] += repeated_groups
    stats["repeated_timestamp_words"] += repeated_words

    if zero or invalid or repeated_groups:
        problem_files.append({
            "file": path.name,
            "duration": duration,
            "words": len(words),
            "zero": len(zero),
            "repeated_groups": repeated_groups,
            "repeated_words": repeated_words,
            "short": len(short),
            "low_probability": len(low_probability),
            "near_end": len(near_end),
        })

print("\n=== FULL DATASET ===")
print(f"Files: {stats['files']}")
print(f"Read errors: {stats['read_errors']}")
print(f"Total words: {stats['total_words']}")

print("\n=== WORD QUALITY ===")
for key in (
    "zero_words",
    "negative_duration_words",
    "short_words",
    "invalid_words",
    "low_probability_words",
    "near_end_words",
    "repeated_timestamp_groups",
    "repeated_timestamp_words",
):
    print(f"{key}: {stats[key]}")

print("\n=== PROBLEM FILES ===")
print(f"Files with zero/invalid/repeated timestamps: {len(problem_files)}")

print("\n=== TOP 30 BY ZERO-DURATION WORDS ===")
for row in sorted(problem_files, key=lambda x: x["zero"], reverse=True)[:30]:
    print(
        f'{row["file"]} | duration={row["duration"]} | '
        f'words={row["words"]} | zero={row["zero"]} | '
        f'repeated_groups={row["repeated_groups"]} | '
        f'repeated_words={row["repeated_words"]} | '
        f'near_end={row["near_end"]}'
    )
