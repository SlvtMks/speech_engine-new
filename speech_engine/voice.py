from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

XTTS_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
XTTS_LANGUAGE = "ru"


class PremiumTTSUnavailable(RuntimeError):
    pass


def synthesize_premium_tts(
    text: str,
    output_path: str,
    instructions: Optional[str] = None,
) -> str:
    """Synthesize natural speech with a local open-source voice model.

    The `instructions` argument is accepted for API compatibility with the
    call-agent UI. XTTS v2 is not an instruction-following TTS model, so style is
    controlled mostly by the reference voice and by how the scenario text is
    written.
    """
    provider = _resolve_provider()
    if provider in {"", "silero", "local"}:
        raise PremiumTTSUnavailable("Local neural TTS provider is not enabled.")

    if provider == "xtts":
        return _synthesize_xtts(text=text, output_path=output_path)

    raise PremiumTTSUnavailable(f"Unsupported local TTS provider: {provider}")


def get_voice_status() -> dict[str, str | bool]:
    configured_provider = _configured_provider()
    reference_path = _resolve_xtts_reference_path()
    active_provider = _resolve_provider()

    return {
        "configured_provider": configured_provider,
        "active_provider": active_provider,
        "premium_available": active_provider == "xtts" and reference_path is not None,
        "xtts_reference_present": reference_path is not None,
        "xtts_reference_wav": str(reference_path) if reference_path else "",
        "xtts_model": os.getenv("SPEECH_ENGINE_XTTS_MODEL", XTTS_MODEL_NAME),
        "xtts_language": os.getenv("SPEECH_ENGINE_XTTS_LANGUAGE", XTTS_LANGUAGE),
        "fallback_provider": "silero",
    }


def _configured_provider() -> str:
    return os.getenv("SPEECH_ENGINE_TTS_PROVIDER", "auto").strip().lower()


def _resolve_provider() -> str:
    provider = _configured_provider()
    if provider == "auto":
        return "xtts" if _resolve_xtts_reference_path() else "silero"
    if provider in {"coqui", "coqui-xtts", "xtts-v2"}:
        return "xtts"
    return provider


def _resolve_xtts_reference_path() -> Path | None:
    candidates = [
        os.getenv("SPEECH_ENGINE_XTTS_SPEAKER_WAV"),
        "data/voices/reference_ru.wav",
        "elena.wav",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file():
            return path
    return None


def _get_device() -> str:
    env_device = os.getenv("SPEECH_ENGINE_DEVICE")
    if env_device in {"cpu", "cuda"}:
        return env_device

    try:
        import torch
    except ImportError:
        return "cpu"

    return "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=1)
def _get_xtts_model() -> object:
    model_name = os.getenv("SPEECH_ENGINE_XTTS_MODEL", XTTS_MODEL_NAME)
    device = _get_device()

    try:
        from TTS.api import TTS

        logger.info("Loading XTTS model '%s' on %s.", model_name, device)
        return TTS(model_name=model_name).to(device)
    except Exception as exc:  # noqa: BLE001
        raise PremiumTTSUnavailable(f"Failed to load XTTS model: {exc}") from exc


def _synthesize_xtts(text: str, output_path: str) -> str:
    speaker_wav = _resolve_xtts_reference_path()
    if speaker_wav is None:
        raise PremiumTTSUnavailable(
            "XTTS requires a reference WAV. Set SPEECH_ENGINE_XTTS_SPEAKER_WAV "
            "or put a file at data/voices/reference_ru.wav."
        )

    clean_text = text.strip()
    if not clean_text:
        raise PremiumTTSUnavailable("Text for XTTS synthesis is empty.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    language = os.getenv("SPEECH_ENGINE_XTTS_LANGUAGE", XTTS_LANGUAGE)
    tts = _get_xtts_model()

    try:
        tts.tts_to_file(
            text=clean_text,
            file_path=str(output),
            speaker_wav=str(speaker_wav),
            language=language,
        )
    except Exception as exc:  # noqa: BLE001
        raise PremiumTTSUnavailable(f"XTTS synthesis failed: {exc}") from exc

    return str(output)
