from __future__ import annotations

import os
import sysconfig
from pathlib import Path

_DLL_HANDLES: dict[str, object] = {}

DEFAULT_FFMPEG_BIN = Path(
    os.environ.get(
        "SPEECH_ENGINE_FFMPEG_BIN",
        r"C:\ffmpeg-8.0.1-full_build-shared\bin",
    )
)


def _register_directory(directory: Path) -> None:
    directory = directory.resolve()

    if not directory.is_dir():
        raise FileNotFoundError(
            f"Native library directory not found: {directory}"
        )

    normalized = os.path.normcase(str(directory))

    # CTranslate2 ищет CUDA DLL через PATH.
    entries = [
        entry.strip().strip('"')
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry.strip()
    ]

    existing = {
        os.path.normcase(os.path.abspath(entry))
        for entry in entries
    }

    if normalized not in existing:
        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = (
            str(directory)
            + (os.pathsep + current_path if current_path else "")
        )

    # Python использует отдельный механизм поиска зависимых DLL.
    if normalized not in _DLL_HANDLES and os.name == "nt":
        _DLL_HANDLES[normalized] = os.add_dll_directory(
            str(directory)
        )


def configure_native_libraries(
    ffmpeg_bin: str | Path | None = None,
) -> dict[str, str]:
    """
    Подключает CUDA DLL и FFmpeg Shared в текущем процессе.

    Не изменяет системный или пользовательский PATH.
    Не требует запуска от имени администратора.
    """

    if os.name != "nt":
        return {"platform": os.name}

    purelib = Path(sysconfig.get_paths()["purelib"])
    torch_lib = purelib / "torch" / "lib"

    nvidia_root = purelib / "nvidia"
    nvidia_bin_dirs = (
        sorted(p for p in nvidia_root.glob("*/bin") if p.is_dir())
        if nvidia_root.is_dir()
        else []
    )

    if not torch_lib.is_dir():
        raise FileNotFoundError(
            f"PyTorch native libraries not found: {torch_lib}"
        )

    ffmpeg_dir = (
        Path(ffmpeg_bin)
        if ffmpeg_bin is not None
        else DEFAULT_FFMPEG_BIN
    )

    # Сначала CUDA, затем FFmpeg.
    _register_directory(torch_lib)

    for directory in nvidia_bin_dirs:
        _register_directory(directory)

    _register_directory(ffmpeg_dir)

    return {
        "torch_lib": str(torch_lib.resolve()),
        "ffmpeg_bin": str(ffmpeg_dir.resolve()),
        "status": "OK",
    }