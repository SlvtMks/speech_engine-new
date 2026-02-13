from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

import torch
from faster_whisper import WhisperModel

from .audio import preprocess_audio

logger = logging.getLogger(__name__)


class SpeechToText:
    """
    Обёртка над faster-whisper для офлайн распознавания речи (STT).

    Поддерживает:
    - автоопределение устройства (CPU / GPU);
    - автоопределение языка;
    - VAD фильтр;
    - возврат сегментов с таймкодами.
    """

    def __init__(self, model_size: str = "large-v3") -> None:
        """
        Parameters
        ----------
        model_size : str, optional
            Размер / имя модели faster-whisper. По умолчанию "large-v3".
        """
        self.model_size = model_size

        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"

        logger.info(
            "Инициализация SpeechToText с моделью '%s' на устройстве '%s' (%s).",
            self.model_size,
            device,
            compute_type,
        )

        try:
            self.model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
            )
        except Exception as exc:  # noqa: BLE001
            msg = f"Не удалось загрузить модель faster-whisper '{self.model_size}': {exc}"
            logger.exception(msg)
            raise RuntimeError(msg) from exc

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Распознаёт речь из файла.

        Parameters
        ----------
        audio_path : str
            Путь к аудиофайлу.
        language : str | None, optional
            Язык распознавания ("ru", "en") или None для автоопределения.

        Returns
        -------
        dict
            {
                "text": str,  # полный текст
                "segments": list[{"start": float, "end": float, "text": str}],
                "language": str  # определённый язык (ISO код)
            }

        Raises
        ------
        FileNotFoundError
            Если аудиофайл не найден.
        RuntimeError
            При ошибках распознавания.
        """
        if not os.path.isfile(audio_path):
            msg = f"Аудиофайл для распознавания не найден: {audio_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)

        logger.info("Начало препроцессинга аудио для STT: %s", audio_path)
        with tempfile.TemporaryDirectory() as tmpdir:
            preprocessed_path = os.path.join(tmpdir, "preprocessed.wav")
            preprocess_audio(audio_path, preprocessed_path)

            logger.info(
                "Запуск распознавания (VAD включён, beam_size=5, temperature=0.0, language=%s)",
                language or "auto",
            )
            try:
                segments_iter, info = self.model.transcribe(
                    preprocessed_path,
                    language=language,
                    beam_size=5,
                    temperature=0.0,
                    vad_filter=True,
                )
            except Exception as exc:  # noqa: BLE001
                msg = f"Ошибка при распознавании аудио: {exc}"
                logger.exception(msg)
                raise RuntimeError(msg) from exc

            detected_language = info.language if info is not None else (language or "unknown")
            logger.info("Определённый язык: %s (prob=%.3f)", getattr(info, "language", "n/a"), getattr(info, "language_probability", 0.0))

            segments: List[Dict[str, Any]] = []
            full_text_parts: List[str] = []

            for seg in segments_iter:
                seg_text = seg.text.strip()
                segments.append(
                    {
                        "start": float(seg.start),
                        "end": float(seg.end),
                        "text": seg_text,
                    },
                )
                full_text_parts.append(seg_text)

            full_text = " ".join(full_text_parts).strip()

            logger.info("Распознавание завершено. Кол-во сегментов: %d", len(segments))

            result: Dict[str, Any] = {
                "text": full_text,
                "segments": segments,
                "language": detected_language,
            }
            return result