from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Dict


def setup_logging(verbosity: int) -> None:
    """
    Настраивает логирование в зависимости от уровня подробности.

    Parameters
    ----------
    verbosity : int
        Количество флагов -v:
        0 - INFO,
        1 - DEBUG.
    """
    level = logging.INFO
    if verbosity >= 1:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )


def _cmd_stt(args: argparse.Namespace) -> int:
    # Ленивый импорт, чтобы "import speech_engine.cli" не требовал тяжёлых зависимостей.
    from .stt import SpeechToText

    stt = SpeechToText()
    language = None if args.lang == "auto" else args.lang

    try:
        result: Dict[str, Any] = stt.transcribe(args.input, language=language)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).error("Ошибка STT: %s", exc)
        return 1

    # Человеко-читаемый вывод
    print("=== STT RESULT ===")
    print(f"Language: {result.get('language')}")
    print("Text:\n")
    print(result.get("text", ""))

    print("\nSegments:")
    for seg in result.get("segments", []):
        start = seg.get("start")
        end = seg.get("end")
        text = seg.get("text")
        print(f"[{start:8.2f} - {end:8.2f}] {text}")

    return 0


def _cmd_tts(args: argparse.Namespace) -> int:
    # Ленивый импорт, чтобы не тянуть TTS, когда он не нужен
    from .tts import TextToSpeech

    tts = TextToSpeech()
    try:
        speaker = getattr(args, "speaker", None)
        output = tts.synthesize(text=args.text, language=args.lang, output_path=args.out, speaker=speaker)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).error("Ошибка TTS: %s", exc)
        return 1

    print("=== TTS RESULT ===")
    print(f"Output file: {output}")
    if args.lang == "ru" and speaker:
        print(f"Speaker: {speaker}")
    return 0


def _cmd_chat(args: argparse.Namespace) -> int:
    logger = logging.getLogger(__name__)

    # Ленивые импорты
    from .stt import SpeechToText
    from .tts import TextToSpeech

    stt = SpeechToText()
    tts = TextToSpeech()

    # 1. STT
    try:
        stt_result: Dict[str, Any] = stt.transcribe(args.input, language=None)
    except Exception as exc:  # noqa: BLE001
        logger.error("Ошибка STT в режиме chat: %s", exc)
        return 1

    recognized_text = stt_result.get("text", "").strip()
    language = stt_result.get("language", "en")

    if not recognized_text:
        logger.error("Распознан пустой текст, нечего озвучивать.")
        return 1

    # Нормализуем язык до ru/en для TTS, если возможно
    lang_for_tts = "en"
    lang_lower = str(language).lower()
    if lang_lower.startswith("ru"):
        lang_for_tts = "ru"
    elif lang_lower.startswith("en"):
        lang_for_tts = "en"

    print("=== CHAT (STT -> TTS) ===")
    print(f"Detected language: {language}")
    print("Recognized text:\n")
    print(recognized_text)
    print()

    # 2. TTS
    try:
        output = tts.synthesize(text=recognized_text, language=lang_for_tts, output_path=args.out)
    except Exception as exc:  # noqa: BLE001
        logger.error("Ошибка TTS в режиме chat: %s", exc)
        return 1

    print(f"Synthesized audio saved to: {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="speech_engine",
        description="Офлайн-движок STT <-> TTS (faster-whisper + Silero TTS для RU + Coqui TTS для EN)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Увеличить подробность логов (можно указать несколько раз).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # STT
    stt_parser = subparsers.add_parser(
        "stt",
        help="Распознать речь из аудиофайла.",
    )
    stt_parser.add_argument(
        "input",
        type=str,
        help="Путь к входному аудиофайлу.",
    )
    stt_parser.add_argument(
        "--lang",
        type=str,
        default="auto",
        choices=["ru", "en", "auto"],
        help="Язык распознавания: ru, en или auto (по умолчанию).",
    )
    stt_parser.set_defaults(func=_cmd_stt)

    # TTS
    tts_parser = subparsers.add_parser(
        "tts",
        help="Синтезировать речь из текста в WAV файл.",
    )
    tts_parser.add_argument(
        "text",
        type=str,
        help="Текст для озвучивания (в кавычках). Для русского языка можно использовать маркеры голосов: [aidar]текст[/aidar] или [aidar]текст[kseniya]другой текст. Доступны: aidar, baya, kseniya, xenia, eugene, random.",
    )
    tts_parser.add_argument(
        "--lang",
        type=str,
        required=True,
        choices=["ru", "en"],
        help="Язык синтеза: ru или en.",
    )
    tts_parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Путь для сохранения WAV-файла.",
    )
    tts_parser.add_argument(
        "--speaker",
        type=str,
        default=None,
        choices=["aidar", "baya", "kseniya", "xenia", "eugene", "random"],
        help="Голос для синтеза (только для ru): aidar (мужской, по умолчанию), baya/kseniya/xenia (женские), eugene (мужской), random (случайный).",
    )
    tts_parser.set_defaults(func=_cmd_tts)

    # CHAT (STT -> TTS)
    chat_parser = subparsers.add_parser(
        "chat",
        help="Распознать речь и озвучить её обратно (STT -> TTS).",
    )
    chat_parser.add_argument(
        "input",
        type=str,
        help="Путь к входному аудиофайлу для распознавания.",
    )
    chat_parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Путь для сохранения ответа в WAV.",
    )
    chat_parser.set_defaults(func=_cmd_chat)

    return parser


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(getattr(args, "verbose", 0))

    if hasattr(args, "func"):
        return args.func(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())