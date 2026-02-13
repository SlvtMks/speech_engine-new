from __future__ import annotations

from typing import Any

__version__ = "0.1.0"
__all__ = ["SpeechToText", "TextToSpeech", "__version__"]


def SpeechToText(*args: Any, **kwargs: Any):
    """
    Лениво импортирует и возвращает экземпляр SpeechToText.
    """
    from .stt import SpeechToText as _SpeechToText

    return _SpeechToText(*args, **kwargs)


def TextToSpeech(*args: Any, **kwargs: Any):
    """
    Лениво импортирует и возвращает экземпляр TextToSpeech.
    """
    from .tts import TextToSpeech as _TextToSpeech

    return _TextToSpeech(*args, **kwargs)