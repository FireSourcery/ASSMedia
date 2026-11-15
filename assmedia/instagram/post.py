"""Read gallery-dl post folders: <items>/<shortcode>/<shortcode>.json plus <shortcode>_NN.<ext> media."""
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

MEDIA_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "mp4")


@dataclass(frozen=True)
class Post:
    shortcode: str
    folder: Path
    url: str
    username: str
    fullname: str
    published: date
    caption: str
    hashtags: list[str]
    media_files: list[Path]
    media: str  # "video" | "photo" | "carousel"


def _media_files(folder: Path, shortcode: str) -> list[Path]:
    pattern = re.compile(rf"^{re.escape(shortcode)}_(\d{{2}})\.({'|'.join(MEDIA_EXTENSIONS)})$",
                         re.IGNORECASE)
    found = []
    for path in folder.iterdir():
        match = pattern.match(path.name)
        if match and path.is_file():
            found.append((int(match.group(1)), path))
    return [path for _, path in sorted(found)]


def _classify(files: list[Path]) -> str:
    if len(files) > 1:
        return "carousel"
    return "video" if files[0].suffix.lower() == ".mp4" else "photo"


def _expected_files(data: dict) -> int | None:
    """gallery-dl's `count` includes a skipped soundtrack file when the post has audio_* keys."""
    count = data.get("count")
    if not isinstance(count, int) or isinstance(count, bool):
        return None
    return count - (1 if any(key.startswith("audio_") for key in data) else 0)


def _load(folder: Path) -> Post | None:
    """A complete post: readable JSON with a post date, no *.part files, media numbered 1..n, all present."""
    shortcode = folder.name
    meta_path = folder / f"{shortcode}.json"
    if not meta_path.is_file() or any(p.name.endswith(".part") for p in folder.iterdir()):
        return None
    files = _media_files(folder, shortcode)
    numbers = [int(path.stem.rsplit("_", 1)[1]) for path in files]
    if not files or numbers != list(range(1, len(files) + 1)):
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        published = datetime.strptime(str(data["post_date"])[:10], "%Y-%m-%d").date()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    expected = _expected_files(data)
    if expected is not None and len(files) < expected:
        return None
    return Post(
        shortcode=shortcode,
        folder=folder,
        url=data.get("post_url") or f"https://www.instagram.com/p/{shortcode}/",
        username=data.get("username") or "",
        fullname=data.get("fullname") or "",
        published=published,
        caption=data.get("description") or "",
        hashtags=list(data.get("tags") or []),
        media_files=files,
        media=_classify(files),
    )


def scan_items(items_dir: Path) -> tuple[list[Post], list[str]]:
    """Return complete posts sorted by shortcode, and shortcodes of folders missing JSON or media."""
    posts, incomplete = [], []
    if not items_dir.is_dir():  # a new instance: no download has saved anything yet
        return posts, incomplete
    for folder in sorted(p for p in items_dir.iterdir() if p.is_dir()):
        post = _load(folder)
        if post is None:
            incomplete.append(folder.name)
        else:
            posts.append(post)
    return posts, incomplete

