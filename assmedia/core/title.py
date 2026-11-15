"""Titles for untagged saves, from the caption (as X does): its first line with words, else the
names of its emoji, else nothing (the caller then uses the media kind).

Emoji names are CLDR short names, read from emoji_names.json (made by make_emoji_names.py from the `emoji`
package; the tools run with `py -I`, so the package itself isn't imported)."""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from .contact import has_contact

NAMES_FILE = Path(__file__).with_name("emoji_names.json")
_IGNORED = re.compile("[︎️\U0001f3fb-\U0001f3ff]")  # variation selectors, skin tones
_JOINERS = {"‍", "⃣"}
_URL = re.compile(r"https?://\S+|\b(?:www\.)?(?:x|twitter)\.com/\S+", re.IGNORECASE)
_MENTIONS = re.compile(r"^(?:@[\w.]+(?:\s+|$))+")
_HASHTAG = re.compile(r"#(\S+)")


@lru_cache(maxsize=1)
def _names() -> tuple[dict[str, str], int]:
    names = json.loads(NAMES_FILE.read_text(encoding="utf-8"))["names"]
    return names, max(len(k) for k in names)


def _emoji(text: str) -> list[tuple[int, int, str]]:
    """(start, end, name) for each emoji in `text` (already stripped of _IGNORED), longest match first."""
    names, longest = _names()
    found, i = [], 0
    while i < len(text):
        for size in range(min(longest, len(text) - i), 0, -1):
            name = names.get(text[i:i + size])
            if name:
                found.append((i, i + size, name))
                i += size
                break
        else:
            i += 1
    return found


def _without_emoji(text: str) -> str:
    text = _IGNORED.sub("", text)
    parts, last = [], 0
    for start, end, _ in _emoji(text):
        parts += [text[last:start], " "]
        last = end
    parts.append(text[last:])
    # joiners left over, and other symbols that aren't emoji (♡, ★), go too: page names keep words only
    return "".join(" " if ch in _JOINERS or unicodedata.category(ch) == "So" else ch for ch in "".join(parts))


def _has_words(text: str) -> bool:
    return any(unicodedata.category(ch)[0] in "LN" for ch in text)


def title_line(text: str | None) -> str:
    """The first caption line with words once links, leading @mentions, hashtags and emoji are dropped
    (a line of hashtags alone keeps their words); `$` is dropped too. Lines with contact details are skipped."""
    text = _MENTIONS.sub("", _URL.sub(" ", text or "").lstrip())
    for line in text.splitlines():
        line = _without_emoji(line)
        words = _HASHTAG.sub(" ", line)
        if not _has_words(words):
            words = _HASHTAG.sub(r"\1", line)
        words = words.replace("$", " ")
        if _has_words(words) and not has_contact(words):
            return words
    return ""


def emoji_title(text: str | None) -> str:
    """The names of the emoji in `text`, each once, in order, comma-separated, in sentence case."""
    seen: list[str] = []
    for _, _, name in _emoji(_IGNORED.sub("", text or "")):
        if name not in seen:
            seen.append(name)
    joined = ", ".join(seen)
    return joined[:1].upper() + joined[1:]
