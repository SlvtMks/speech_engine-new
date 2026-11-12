from pathlib import Path

from speech_engine.runtime import configure_native_libraries

runtime_info = configure_native_libraries(
    ffmpeg_bin=r"C:\ffmpeg-8.0.1-full_build-shared\bin"
)

print("=== NATIVE RUNTIME ===")
print(runtime_info)

from faster_whisper import WhisperModel

audio = Path(
    r"F:\speech-engine\data\stt_uploads\1537167506_+79690715333_15.09.2026_13_45_00m10s.mp3"
)

model = WhisperModel(
    "large-v3",
    device="cuda",
    compute_type="float16",
)

segments, info = model.transcribe(
    str(audio),
    language="ru",
    beam_size=5,
    temperature=0.0,
    vad_filter=True,
    word_timestamps=True,
)

print("\n=== AUDIO INFO ===")
print("Duration:", info.duration)
print("Language:", info.language)
print("Language probability:", info.language_probability)

print("\n=== RAW WHISPER SEGMENTS AND WORDS ===")

for segment in segments:
    print(f"\nSEGMENT: {segment.start:.4f} - {segment.end:.4f}")
    print("TEXT:", segment.text)

    for word in segment.words or []:
        print(
            f"WORD: {word.start!r} - {word.end!r} | "
            f"{word.word!r} | probability={word.probability}"
        )
