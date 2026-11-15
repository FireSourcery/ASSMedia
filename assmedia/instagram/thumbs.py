"""Instagram's thumbnail: one frame or image of a post's first media file (core.thumbs makes it)."""
from pathlib import Path

from assmedia.core.thumbs import make_thumb_file

from .post import Post


def make_thumb(post: Post, out_path: Path, ffmpeg: Path) -> Path:
    return make_thumb_file(post.media_files[0], out_path, ffmpeg, post.shortcode)
