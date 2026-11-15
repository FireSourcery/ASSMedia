"""Bookmark page rendering: wiki/sources/X/<title>.md, with the media and the thread's text."""
import re
from datetime import date
from pathlib import Path

from assmedia.core.page import MAX_TITLE, MAX_TITLE_BYTES, ThumbRef, safe_title
from assmedia.core.yamlfm import dump

from .tags import XTags
from .text import _URL, contact_in, thread_sections
from .thread import Thread, page_media

__all__ = ["classify", "x_thumb_ref", "media_lines", "contact_in", "choose_x_title", "render_x_page"]


def classify(files: list[Path]) -> str:
    if not files:
        return "text"
    if any(f.suffix.lower() == ".mp4" for f in files):
        return "video"
    return "carousel" if len(files) > 1 else "photo"


def x_thumb_ref(tweet_id: str, thumbs_url: str) -> ThumbRef:
    """`thumbs_url` is the thumbnail folder as a file URL (Path.as_uri(), so a space becomes %20)."""
    url = f"{thumbs_url}/{tweet_id}.jpg"
    return ThumbRef(url, f"![]({url})")


def media_lines(thread: Thread, items_url: str) -> list[str]:
    """An inline player per video (no width: Obsidian caps it at the pane width), an inline image per photo,
    in page order (files live in items/<their id>/; `items_url` is that folder as a file URL)."""
    lines = []
    for f in page_media(thread):
        url = f"{items_url}/{f.parent.name}/{f.name}"
        lines.append(f'<video controls preload="metadata" src="{url}"></video>'
                     if f.suffix.lower() == ".mp4" else f"![]({url})")
    return lines


_MENTIONS = re.compile(r"^(?:@\w+(?:\s+|$))+")
_HASHTAG = re.compile(r"#(\S+)")
_MEDIA_WORD = {"video": "Video", "photo": "Photo", "carousel": "Images", "text": "Tweet"}


def _title_line(text: str | None) -> str:
    """The first line of a text that has words once links, leading @mentions and hashtags are dropped
    (a line of hashtags alone keeps their words); `$` is dropped too, as in tagged titles."""
    text = _MENTIONS.sub("", _URL.sub(" ", text or "").lstrip())
    for line in text.splitlines():
        words = _HASHTAG.sub(" ", line)
        if not words.strip():
            words = _HASHTAG.sub(r"\1", line)
        words = words.replace("$", " ")
        if any(ch.isalnum() for ch in words):  # emoji and punctuation alone aren't words
            return words
    return ""


def text_title(thread: Thread, max_chars: int = MAX_TITLE, max_bytes: int = MAX_TITLE_BYTES) -> str:
    """A title from the words of an untagged bookmark: its article title or text, then the quoted tweet's;
    never a line with contact details. Empty when there are no words to use."""
    b, q = thread.bookmark, thread.quoted
    for text in (b.article_title, b.text, q.article_title if q else None, q.text if q else None):
        part = safe_title(_title_line(text), max_chars, max_bytes)
        if part and not contact_in(part):
            return part
    return ""


def _fallback_title(thread: Thread, max_chars: int, max_bytes: int) -> str:
    """text_title, else the media kind (Video, Photo, Images, Tweet)."""
    return text_title(thread, max_chars, max_bytes) or _MEDIA_WORD[classify(page_media(thread))]


def choose_x_title(thread: Thread, tags: XTags, taken: set[str]) -> str:
    """`<title> (<author>)` always; a name already taken gets ` - <tweet_id>`."""
    b = thread.bookmark
    suffix = f" ({b.author})"
    limits = (MAX_TITLE - len(suffix), MAX_TITLE_BYTES - len(suffix.encode("utf-8")))
    base = (safe_title(tags.title, *limits) or _fallback_title(thread, *limits)) + suffix
    if base.lower() in taken:
        base = f"{base} - {b.tweet_id}"
    return base


def _people(tags: XTags) -> list[str]:
    names, seen = [], set()
    for name in list(tags.people) + [tags.creator_person, tags.quoted_person, tags.source_person]:
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return [f"[[{n}]]" for n in names]


def render_x_page(thread: Thread, tags: XTags, *, title: str, thumb: ThumbRef | None, created: date,
                  items_url: str) -> str:
    b = thread.bookmark
    files = page_media(thread)
    props = [
        ("type", "source"),
        ("source", "X"),
        ("tweet_id", b.tweet_id),
        ("source_url", b.url),
        ("source_author", b.author),
        ("source_author_name", b.author_name),
        ("published", b.published),
        ("saved", b.bookmarked or b.published),
        ("media", classify(files)),
        ("files", len(files)),
        ("people", _people(tags)),
        ("subjects", [f"[[{n}]]" for n in tags.subjects]),
        ("themes", [f"[[{n}]]" for n in tags.themes]),
        ("hashtags", list(b.hashtags)),
        ("domain", [f"[[{n}]]" for n in tags.domain]),
        ("description", tags.description),
        ("online", True),
        ("thumbnail", thumb.prop if thumb else None),
        ("created", created),
        ("tags", ["source", "x"]),
        ("created_by", "claude"),
    ]
    body = [f"# {title}", ""]
    for line in media_lines(thread, items_url):
        body += [line, ""]
    body += thread_sections(thread)
    return dump(props) + "\n" + "\n".join(body).rstrip("\n") + "\n"
