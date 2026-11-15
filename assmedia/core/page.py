"""What every platform's pages share: their title limits and how a thumbnail is referenced."""
import re
from dataclasses import dataclass

from .tags import ILLEGAL_CHARS

MAX_TITLE = 80
MAX_TITLE_BYTES = 200  # Synology/SMB names are limited to 255 bytes; leave room for " - <id>.md"


@dataclass(frozen=True)
class ThumbRef:
    prop: str   # the page's `thumbnail` property
    embed: str  # the thumbnail as embedded in the page body


def safe_title(text: str, max_chars: int = MAX_TITLE, max_bytes: int = MAX_TITLE_BYTES) -> str:
    cleaned = "".join(" " if ch in ILLEGAL_CHARS else ch for ch in text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if len(cleaned) > max_chars or len(cleaned.encode("utf-8")) > max_bytes:
        cut = cleaned[:max_chars]
        while len(cut.encode("utf-8")) > max_bytes:
            cut = cut[:-1]
        if " " in cut and cleaned[len(cut):len(cut) + 1] not in ("", " "):
            cut = cut[:cut.rfind(" ")]
        cleaned = cut.strip(" .")
    return cleaned
