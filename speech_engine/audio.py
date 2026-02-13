from __future__ import annotations

import logging
import os
from typing import Final

from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE: Final[int] = 16_000
TARGET_CHANNELS: Final[int] = 1
TARGET_SAMPLE_WIDTH: Final[int] = 2  # bytes (16-bit)
LEADING_SILENCE_SECONDS: Final[float] = 1.0


def preprocess_audio(input_path: str, output_path: str) -> str:
    """
    Преобразует любой поддерживаемый формат аудио в:
    - WAV
    - 16 kHz
    - mono
    - pcm_s16le
    - с 1 секундой тишины в начале
    - с нормализацией громкости

    Parameters
    ----------
    input_path : str
        Путь к исходному аудио файлу.
    output_path : str
        Путь к результирующему WAV файлу.

    Returns
    -------
    str
        Путь к обработанному файлу (output_path).

    Raises
    ------
    FileNotFoundError
        Если входной файл не существует.
    RuntimeError
        При ошибках декодирования или обработки аудио.
    """
    if not os.path.isfile(input_path):
        msg = f"Входной аудиофайл не найден: {input_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    try:
        logger.info("Загрузка аудио: %s", input_path)
        audio = AudioSegment.from_file(input_path)
    except CouldntDecodeError as exc:
        msg = f"Не удалось декодировать аудиофайл: {input_path}. Убедитесь, что установлен ffmpeg."
        logger.exception(msg)
        raise RuntimeError(msg) from exc
    except Exception as exc:  # noqa: BLE001
        msg = f"Неизвестная ошибка при загрузке аудио: {exc}"
        logger.exception(msg)
        raise RuntimeError(msg) from exc

    # Приведение к требуемым параметрам
    logger.info("Преобразование аудио к %d Hz, mono, 16-bit PCM", TARGET_SAMPLE_RATE)
    audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)
    audio = audio.set_channels(TARGET_CHANNELS)
    audio = audio.set_sample_width(TARGET_SAMPLE_WIDTH)

    # Нормализация громкости (простая: выравнивание по peak)
    try:
        peak_sample = audio.max
        if peak_sample > 0:
            # максимальное значение для 16-битного PCM
            max_possible = float(2 ** (8 * TARGET_SAMPLE_WIDTH - 1) - 1)
            factor = max_possible / peak_sample
            logger.info("Нормализация громкости, коэффициент: %.3f", factor)
            audio = audio.apply_gain(20.0 * (factor ** 0.5).bit_length() if False else 0)  # no-op, см. ниже
            # Более корректно - нормализация через встроенный normalize
            audio = audio.normalize()
        else:
            logger.info("Аудио уже на минимальном уровне, нормализация не требуется.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ошибка при нормализации громкости: %s. Продолжаем без нормализации.", exc)

    # Добавление тишины в начало
    logger.info("Добавление %.1f секунд тишины в начало.", LEADING_SILENCE_SECONDS)
    silence = AudioSegment.silent(duration=int(LEADING_SILENCE_SECONDS * 1000), frame_rate=TARGET_SAMPLE_RATE)
    processed_audio = silence + audio

    # Экспорт
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir and not os.path.isdir(output_dir):
        logger.info("Создание директории для вывода: %s", output_dir)
        os.makedirs(output_dir, exist_ok=True)

    logger.info("Сохранение обработанного аудио: %s", output_path)
    try:
        processed_audio.export(
            output_path,
            format="wav",
            parameters=[
                "-acodec",
                "pcm_s16le",
                "-ac",
                str(TARGET_CHANNELS),
                "-ar",
                str(TARGET_SAMPLE_RATE),
            ],
        )
    except Exception as exc:  # noqa: BLE001
        msg = f"Ошибка при сохранении обработанного аудио: {exc}"
        logger.exception(msg)
        raise RuntimeError(msg) from exc

    return output_path