#!/usr/bin/env python3
"""
Audio Converter Helper Utility for STT Testing.
Converts mobile audio recordings (.m4a, .mp3, .mp4, etc.) into the strict
Linear PCM 16kHz, 16-bit, Mono WAV format required by GladiaService.
"""

import os
import sys
import shutil
import warnings
from pathlib import Path

try:
    warnings.filterwarnings(
        "ignore",
        message="Couldn't find ffmpeg or avconv.*",
        category=RuntimeWarning,
        module="pydub.utils",
    )
    warnings.filterwarnings(
        "ignore",
        message="Couldn't find ffprobe or avprobe.*",
        category=RuntimeWarning,
        module="pydub.utils",
    )
    from pydub import AudioSegment
except ImportError:
    print("Error: 'pydub' package not found. Run 'pip install pydub' first.")
    sys.exit(1)


def _ffmpeg_downloader_path(tool_name: str) -> str | None:
    """Return a ffmpeg-downloader binary path when that package is available."""

    try:
        import ffmpeg_downloader
    except ImportError:
        return None

    try:
        return ffmpeg_downloader.installed(tool_name, return_path=True)
    except Exception:
        return None


def _find_tool(tool_name: str, env_var: str) -> str | None:
    """Find an FFmpeg tool from env vars, PATH, common Windows locations, or ffmpeg-downloader."""

    candidates = [
        os.environ.get(env_var),
        shutil.which(tool_name),
        _ffmpeg_downloader_path(tool_name),
    ]

    if os.name == "nt":
        true_local_app_data = Path.home() / "AppData" / "Local"
        candidates.extend(
            [
                true_local_app_data / "Microsoft" / "WinGet" / "Links" / f"{tool_name}.exe",
                true_local_app_data / "ffmpegio" / "ffmpeg-downloader" / "cache" / f"{tool_name}.exe",
                true_local_app_data / "ffmpegio" / "ffmpeg-downloader" / "ffmpeg" / "bin" / f"{tool_name}.exe",
            ]
        )

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))

    return None


def _configure_ffmpeg() -> tuple[str | None, str | None]:
    """Point pydub at a local FFmpeg install if Windows PATH is not configured."""

    ffmpeg_path = _find_tool("ffmpeg", "FFMPEG_BINARY")
    ffprobe_path = _find_tool("ffprobe", "FFPROBE_BINARY")
    tool_dirs = {
        str(Path(tool_path).parent)
        for tool_path in (ffmpeg_path, ffprobe_path)
        if tool_path
    }

    for tool_dir in tool_dirs:
        path_entries = os.environ.get("PATH", "").split(os.pathsep)
        if tool_dir not in path_entries:
            os.environ["PATH"] = os.pathsep.join([tool_dir, os.environ.get("PATH", "")])

    if ffmpeg_path:
        AudioSegment.converter = ffmpeg_path
    if ffprobe_path:
        AudioSegment.ffprobe = ffprobe_path

    return ffmpeg_path, ffprobe_path


FFMPEG_PATH, FFPROBE_PATH = _configure_ffmpeg()


def _require_ffmpeg() -> None:
    missing = []
    if not FFMPEG_PATH:
        missing.append("ffmpeg")
    if not FFPROBE_PATH:
        missing.append("ffprobe")

    if not missing:
        return

    print(f"Missing required tool(s): {', '.join(missing)}")
    print("Install FFmpeg or download it for this Python environment:")
    print("  python -m ffmpeg_downloader install")
    print("Windows alternatives: 'winget install Gyan.FFmpeg' or 'choco install ffmpeg'")
    sys.exit(1)


def convert_mobile_audio(input_file_path: str | Path, output_file_name: str = "minglish_test.wav") -> Path | None:
    """
    Takes an input file path, forces the audio constraints to match our
    Phase 2 STT specifications, and saves it next to this test utility.
    """
    input_path = Path(input_file_path)
    if not input_path.is_file():
        input_path = Path.cwd() / input_path

    if not input_path.exists():
        raise FileNotFoundError(f"Source file not found at: {input_path.absolute()}")

    output_dir = Path(__file__).resolve().parent
    output_path = output_dir / output_file_name

    print(f"Processing file: {input_path.name}")

    try:
        _require_ffmpeg()

        # Load the mobile recording file (.m4a, .mp3, .mp4, .caf, etc.)
        audio = AudioSegment.from_file(input_path)

        # Apply strict Voice Agent specs:
        # 16000Hz frame rate, 2 bytes sample width (16-bit), 1 channel (Mono)
        optimized_audio = audio.set_frame_rate(16000).set_sample_width(2).set_channels(1)

        print("Applying Phase 2 constraints: 16kHz, 16-bit, Mono PCM...")

        # Export as a standard uncompressed WAV file.
        optimized_audio.export(output_path, format="wav")

        print(f"Success! Target output verified at: {output_path}")
        return output_path

    except Exception as e:
        print(f"Structural conversion failed: {e}")
        print(f"\nHint: Ensure FFmpeg is installed and can decode {input_path.suffix or 'this'} files.")
        print("Windows options: 'winget install Gyan.FFmpeg' or 'choco install ffmpeg'")
        print("Python-local option: 'python -m ffmpeg_downloader install'")
        sys.exit(1)


if __name__ == "__main__":
    # Local CLI capability: Allow dragging a file directly into the terminal execution.
    if len(sys.argv) < 2:
        print("Usage: python audio_converter.py <path_to_audio_file>")
        sys.exit(1)

    convert_mobile_audio(sys.argv[1], "minglish_test.wav")
