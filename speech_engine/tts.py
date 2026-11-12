from __future__ import annotations

import logging
import os
import re
import tempfile
from typing import Any, Dict, List, Tuple

import numpy as np
import soundfile as sf
import torch
from pydub import AudioSegment

logger = logging.getLogger(__name__)

# Максимальная длина текста для Silero TTS (безопасный лимит)
SILERO_MAX_TEXT_LENGTH = 900

# Доступные голоса для русского языка
AVAILABLE_RU_SPEAKERS = ["aidar", "baya", "kseniya", "xenia", "eugene", "random"]


class TextToSpeech:
    """
    Обёртка для офлайн синтеза речи (TTS).

    Поддерживаемые языки:
    - ru → Silero TTS (MIT лицензия)
    - en → Coqui TTS (MPL-2.0 лицензия)

    Модели кэшируются внутри класса и загружаются только один раз.
    """

    def __init__(self) -> None:
        # Позволяем управлять устройством через SPEECH_ENGINE_DEVICE.
        env_device = os.getenv("SPEECH_ENGINE_DEVICE")
        if env_device in {"cpu", "cuda"}:
            device = env_device
        else:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self.device = device
        self._models: Dict[str, Any] = {}
        logger.info("Инициализация TextToSpeech на устройстве '%s'.", self.device)

    def _get_silero_model(self) -> Any:
        """Загружает модель Silero TTS для русского языка."""
        if "ru" in self._models:
            return self._models["ru"]

        logger.info("Загрузка Silero TTS модели для русского языка.")
        try:
            # Silero TTS v3.1_ru - русская модель, MIT лицензия
            model, example_text = torch.hub.load(
                repo_or_dir="snakers4/silero-models",
                model="silero_tts",
                language="ru",
                speaker="v3_1_ru",
            )
            model.to(self.device)
        except Exception as exc:  # noqa: BLE001
            msg = f"Не удалось загрузить модель Silero TTS: {exc}"
            logger.exception(msg)
            raise RuntimeError(msg) from exc

        self._models["ru"] = model
        return model

    def _get_coqui_model(self) -> Any:
        """Загружает модель Coqui TTS для английского языка."""
        if "en" in self._models:
            return self._models["en"]

        # Ленивый импорт Coqui TTS только для английского
        from TTS.api import TTS

        logger.info("Загрузка Coqui TTS модели 'tts_models/en/ljspeech/tacotron2-DDC' для английского языка.")
        try:
            tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC").to(self.device)
        except Exception as exc:  # noqa: BLE001
            msg = f"Не удалось загрузить модель Coqui TTS: {exc}"
            logger.exception(msg)
            raise RuntimeError(msg) from exc

        self._models["en"] = tts
        return tts

    def _split_text_for_silero(self, text: str) -> List[str]:
        """
        Разбивает длинный текст на части для Silero TTS.

        Parameters
        ----------
        text : str
            Исходный текст.

        Returns
        -------
        List[str]
            Список частей текста, каждая не длиннее SILERO_MAX_TEXT_LENGTH.
        """
        if len(text) <= SILERO_MAX_TEXT_LENGTH:
            return [text]

        # Разбиваем по предложениям (точка, восклицательный знак, вопросительный знак)
        sentences = []
        current_sentence = ""

        for char in text:
            current_sentence += char
            if char in ".!?":
                sentences.append(current_sentence.strip())
                current_sentence = ""

        if current_sentence.strip():
            sentences.append(current_sentence.strip())

        # Группируем предложения в части не длиннее лимита
        parts: List[str] = []
        current_part = ""

        for sentence in sentences:
            if len(current_part) + len(sentence) + 1 <= SILERO_MAX_TEXT_LENGTH:
                if current_part:
                    current_part += " " + sentence
                else:
                    current_part = sentence
            else:
                if current_part:
                    parts.append(current_part)
                current_part = sentence

        if current_part:
            parts.append(current_part)

        return parts if parts else [text]

    def _parse_multi_speaker_text(self, text: str) -> List[Tuple[str, str]]:
        """
        Парсит текст с маркерами голосов и возвращает список (текст, голос).

        Поддерживаемые форматы:
        - [aidar]текст[/aidar] - явное указание начала и конца
        - [aidar]текст[kseniya]другой текст - переход к другому голосу
        - [aidar]текст - до следующего маркера или конца текста

        Если маркеров нет, возвращает весь текст с голосом None.

        Parameters
        ----------
        text : str
            Текст с маркерами голосов.

        Returns
        -------
        List[Tuple[str, str | None]]
            Список кортежей (текст, голос). Если голос None, используется дефолтный.
        """
        # Паттерн для поиска маркеров: [speaker_name] или [/speaker_name]
        pattern = r"\[(/)?([a-z_]+)\]"
        matches = list(re.finditer(pattern, text, re.IGNORECASE))

        if not matches:
            # Маркеров нет - возвращаем весь текст без указания голоса
            return [(text, None)]

        segments: List[Tuple[str, str | None]] = []
        current_pos = 0
        current_speaker: str | None = None

        for match in matches:
            is_closing = match.group(1) == "/"
            speaker_name = match.group(2).lower()

            # Текст до маркера
            text_before = text[current_pos : match.start()].strip()
            if text_before and current_speaker is not None:
                segments.append((text_before, current_speaker))
            elif text_before:
                segments.append((text_before, None))

            if is_closing:
                # Закрывающий маркер - сбрасываем текущий голос
                current_speaker = None
            else:
                # Открывающий маркер - устанавливаем голос
                if speaker_name in AVAILABLE_RU_SPEAKERS:
                    current_speaker = speaker_name
                else:
                    logger.warning(
                        "Неизвестный голос '%s' в маркере, игнорируем. Доступны: %s",
                        speaker_name,
                        ", ".join(AVAILABLE_RU_SPEAKERS),
                    )
                    current_speaker = None

            current_pos = match.end()

        # Остаток текста после последнего маркера
        text_after = text[current_pos:].strip()
        if text_after:
            segments.append((text_after, current_speaker))

        return segments if segments else [(text, None)]

    def _auto_alternate_speakers(self, text: str, speakers: List[str]) -> List[Tuple[str, str]]:
        """
        Автоматически чередует голоса по предложениям.

        Parameters
        ----------
        text : str
            Исходный текст.
        speakers : List[str]
            Список голосов для чередования.

        Returns
        -------
        List[Tuple[str, str]]
            Список кортежей (текст, голос).
        """
        # Разбиваем по предложениям
        sentences = re.split(r"([.!?]+)", text)
        # Склеиваем предложения с их знаками препинания
        parts: List[str] = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                parts.append(sentences[i] + sentences[i + 1])
            else:
                parts.append(sentences[i])

        # Убираем пустые части
        parts = [p.strip() for p in parts if p.strip()]

        # Чередуем голоса
        result: List[Tuple[str, str]] = []
        for i, part in enumerate(parts):
            speaker = speakers[i % len(speakers)]
            result.append((part, speaker))

        return result if result else [(text, speakers[0])]

    def synthesize(self, text: str, language: str, output_path: str, speaker: str | None = None) -> str:
        """
        Синтезирует речь из текста и сохраняет в WAV файл.

        Parameters
        ----------
        text : str
            Исходный текст.
        language : str
            Язык ("ru" или "en").
        output_path : str
            Путь к результирующему WAV файлу.
        speaker : str | None, optional
            Голос для синтеза (только для ru):
            - "aidar" (мужской, по умолчанию)
            - "baya" (женский)
            - "kseniya" (женский)
            - "xenia" (женский)
            - "eugene" (мужской)
            - "random" (случайный)
            Если None, используется "aidar".

        Returns
        -------
        str
            Путь к созданному аудиофайлу.

        Raises
        ------
        ValueError
            При неподдерживаемом языке или голосе.
        RuntimeError
            При ошибках синтеза.
        """
        text = text.strip()
        if not text:
            raise ValueError("Пустой текст для синтеза речи.")

        if language not in ("ru", "en"):
            raise ValueError(f"Неподдерживаемый язык для TTS: {language}. Поддерживаются: ru, en")

        # Определяем голос для русского языка
        if language == "ru":
            if speaker is None:
                speaker = "aidar"
            elif speaker not in AVAILABLE_RU_SPEAKERS:
                raise ValueError(
                    f"Неподдерживаемый голос '{speaker}' для русского языка. "
                    f"Доступны: {', '.join(AVAILABLE_RU_SPEAKERS)}"
                )

        output_dir = os.path.dirname(os.path.abspath(output_path))
        if output_dir and not os.path.isdir(output_dir):
            logger.info("Создание директории для TTS вывода: %s", output_dir)
            os.makedirs(output_dir, exist_ok=True)

        logger.info("Запуск TTS синтеза (%s) -> %s", language, output_path)
        if language == "ru" and speaker:
            logger.info("Используется голос: %s", speaker)

        try:
            if language == "ru":
                # Silero TTS для русского
                model = self._get_silero_model()

                # Парсим текст на сегменты с указанием голосов
                segments = self._parse_multi_speaker_text(text)

                # Если маркеров не было, используем один голос для всего текста
                if len(segments) == 1 and segments[0][1] is None:
                    # Один сегмент без указания голоса - используем дефолтный
                    text_to_synthesize = segments[0][0]
                    text_parts = self._split_text_for_silero(text_to_synthesize)

                    if len(text_parts) == 1:
                        audio = model.apply_tts(
                            text=text_parts[0],
                            speaker=speaker or "aidar",
                            sample_rate=48000,
                        )
                        sf.write(output_path, audio, 48000)
                    else:
                        logger.info(
                            "Текст слишком длинный (%d символов), разбиваем на %d частей для синтеза.",
                            len(text_to_synthesize),
                            len(text_parts),
                        )
                        audio_parts: List[np.ndarray] = []
                        for i, part in enumerate(text_parts):
                            logger.debug(
                                "Синтез части %d/%d (длина: %d символов)", i + 1, len(text_parts), len(part)
                            )
                            part_audio = model.apply_tts(
                                text=part,
                                speaker=speaker or "aidar",
                                sample_rate=48000,
                            )
                            audio_parts.append(part_audio)
                        full_audio = np.concatenate(audio_parts)
                        sf.write(output_path, full_audio, 48000)
                else:
                    # Несколько сегментов с разными голосами
                    logger.info("Обнаружено %d сегментов с разными голосами", len(segments))
                    audio_parts: List[np.ndarray] = []

                    for i, (segment_text, segment_speaker) in enumerate(segments):
                        # Используем голос из маркера или дефолтный
                        final_speaker = segment_speaker if segment_speaker else (speaker or "aidar")
                        logger.info("Сегмент %d/%d: голос '%s', длина %d символов", i + 1, len(segments), final_speaker, len(segment_text))

                        # Разбиваем длинные сегменты
                        text_parts = self._split_text_for_silero(segment_text)

                        for j, part in enumerate(text_parts):
                            if len(text_parts) > 1:
                                logger.debug("  Подсегмент %d/%d", j + 1, len(text_parts))
                            part_audio = model.apply_tts(
                                text=part,
                                speaker=final_speaker,
                                sample_rate=48000,
                            )
                            audio_parts.append(part_audio)

                    # Склеиваем все части
                    full_audio = np.concatenate(audio_parts)
                    sf.write(output_path, full_audio, 48000)
            else:
                # Coqui TTS для английского
                tts = self._get_coqui_model()
                tts.tts_to_file(text=text, file_path=output_path)
        except Exception as exc:  # noqa: BLE001
            msg = f"Ошибка во время синтеза речи: {exc}"
            logger.exception(msg)
            raise RuntimeError(msg) from exc

        logger.info("TTS синтез завершён: %s", output_path)
        return output_path