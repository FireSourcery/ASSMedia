"""The thread's text for a bookmark page: earlier tweets, the bookmark, its continuation and the quoted tweet,
word for word. Contact details stay: the user allows them in the wiki for now (2026-11-11)."""
import re

from assmedia.core.escape import escape_caption, quote_block
from assmedia.core.contact import has_contact

from .thread import Thread
from .tweet import Tweet

NO_TEXT = "*(no text)*"
EARLIER_UNAVAILABLE = "*(earlier tweets unavailable)*"
QUOTED_UNAVAILABLE = "*(quoted tweet unavailable)*"

_URL = re.compile(r"https?://\S+|\b(?:www\.)?(?:x|twitter)\.com/\S+", re.IGNORECASE)


def contact_in(text: str) -> bool:
    """has_contact, ignoring links: 19-digit ids in x.com/.../status/<id> URLs aren't phone numbers.
    Used for page names and tagged descriptions, which stay free of contact details."""
    return has_contact(_URL.sub(" ", text))


def _clean(text: str) -> str:
    return escape_caption(text)


def _quoted_text(text: str) -> str:
    text = text.strip("\n")
    return quote_block(_clean(text)) if text.strip() else NO_TEXT


def tweet_block(t: Tweet) -> list[str]:
    name = f" ({_clean(t.author_name)})" if t.author_name else ""
    lines = [f"**@{escape_caption(t.author)}**{name} · {t.published.isoformat()} · [on X]({t.url})", "",
             _quoted_text(t.text)]
    if t.article_title or t.article_text:
        lines += ["", f"### Article: {_clean(t.article_title or '')}".rstrip()]
        if t.article_text:
            lines += ["", _quoted_text(t.article_text)]
    return lines


def _section(heading: str, parts: list[list[str]]) -> list[str]:
    lines = [heading]
    for part in parts:
        lines += [""] + part
    return lines + [""]


def thread_sections(thread: Thread) -> list[str]:
    """Page body lines after the media: ## Earlier in the thread, ## Bookmarked tweet, ## Continuation,
    ## Quoted tweet (only the ones that apply), each section followed by a blank line."""
    b = thread.bookmark
    body: list[str] = []
    if thread.above or not thread.above_complete:
        parts = ([[EARLIER_UNAVAILABLE]] if not thread.above_complete else []) + [tweet_block(t) for t in thread.above]
        body += _section("## Earlier in the thread", parts)
    body += _section("## Bookmarked tweet", [tweet_block(b)])
    if thread.below:
        body += _section("## Continuation", [tweet_block(t) for t in thread.below])
    if thread.quoted is not None:
        body += _section("## Quoted tweet", [tweet_block(thread.quoted)])
    elif thread.quoted_missing:
        body += _section("## Quoted tweet", [[f"{QUOTED_UNAVAILABLE} https://x.com/i/status/{b.quoted_id}"]])
    return body
