"""Thumbnails made locally with ffmpeg: a frame at 1 s for videos, a scaled copy for images."""
import subprocess
from pathlib import Path


WIDTH_FILTER = "scale=360:-2"


class ThumbError(Exception):
    pass


def _run(ffmpeg: Path, source: Path, target: Path, seek: bool) -> str:
    args = [str(ffmpeg), "-y", "-loglevel", "error"]
    if seek:
        args += ["-ss", "1"]
    args += ["-i", str(source), "-frames:v", "1", "-vf", WIDTH_FILTER, "-q:v", "5", str(target)]
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"cannot run ffmpeg: {exc}"
    return result.stderr.strip()


def _ok(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def make_thumb_file(source: Path, out_path: Path, ffmpeg: Path, label: str) -> Path:
    """Thumbnail of one media file; an existing thumbnail is kept. `label` names the post in errors."""
    if _ok(out_path):
        return out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.stem + ".tmp.jpg")
    is_video = source.suffix.lower() == ".mp4"
    error = _run(ffmpeg, source, tmp, seek=is_video)
    if is_video and not _ok(tmp):
        error = _run(ffmpeg, source, tmp, seek=False)
    if not _ok(tmp):
        tmp.unlink(missing_ok=True)
        raise ThumbError(f"{label}: ffmpeg made no thumbnail ({error[-200:]})")
    tmp.replace(out_path)
    return out_path
