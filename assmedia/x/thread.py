"""Put a bookmark's thread together: the chain above it, the author's continuation below, the quoted tweet."""
from dataclasses import dataclass
from pathlib import Path

from .tweet import Tweet


@dataclass(frozen=True)
class Thread:
    bookmark: Tweet
    above: list[Tweet]     # first tweet first, ending with the bookmark's parent
    below: list[Tweet]     # the author's own continuation, in order
    quoted: Tweet | None
    above_complete: bool   # False when a parent in the chain is unknown (deleted, protected, not looked up)
    quoted_missing: bool   # the bookmark quotes a tweet that isn't on disk


def assemble(bookmark: Tweet, known: dict[str, Tweet]) -> Thread:
    # known's copy of the bookmark carries the article text its lookup found; the Bookmarks feed's has none
    bookmark = known.get(bookmark.tweet_id) or bookmark
    above, seen = [], {bookmark.tweet_id}
    current, complete = bookmark, True
    while current.reply_id is not None:
        parent = known.get(current.reply_id)
        if parent is None:
            complete = False
            break
        if parent.tweet_id in seen:
            break
        seen.add(parent.tweet_id)
        above.append(parent)
        current = parent
    above.reverse()

    replies: dict[str, list[Tweet]] = {}
    for t in known.values():
        if t.reply_id is not None and t.author_id == bookmark.author_id:
            replies.setdefault(t.reply_id, []).append(t)
    below, current = [], bookmark
    while True:
        nxt = sorted((t for t in replies.get(current.tweet_id, []) if t.tweet_id not in seen),
                     key=lambda t: int(t.tweet_id))
        if not nxt:
            break
        current = nxt[0]
        seen.add(current.tweet_id)
        below.append(current)

    quoted = known.get(bookmark.quoted_id) if bookmark.quoted_id else None
    return Thread(bookmark=bookmark, above=above, below=below, quoted=quoted, above_complete=complete,
                  quoted_missing=bookmark.quoted_id is not None and quoted is None)


def page_media(thread: Thread) -> list[Path]:
    """The author's tweets above, the bookmark, the continuation, then the quoted tweet: their media in order."""
    author = thread.bookmark.author_id
    files = [f for t in thread.above if t.author_id == author for f in t.media_files]
    files += thread.bookmark.media_files
    files += [f for t in thread.below for f in t.media_files]
    if thread.quoted is not None:
        files += thread.quoted.media_files
    return files


def all_texts(thread: Thread) -> list[str]:
    """Every text on the page (tweets, article titles and bodies), for contact-detail checks."""
    tweets = thread.above + [thread.bookmark] + thread.below + ([thread.quoted] if thread.quoted else [])
    texts = []
    for t in tweets:
        texts += [s for s in (t.text, t.article_title, t.article_text) if s]
    return texts
