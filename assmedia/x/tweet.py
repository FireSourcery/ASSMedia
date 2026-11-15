"""Read gallery-dl X JSON: items/<id>/<id>.json (bookmark), <id>.quoted.json (quoted copy), threads/<id>.json."""
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

MEDIA_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "gif", "mp4")
_BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre", "ul", "ol",
               "section", "article", "figure", "figcaption", "table", "tr"}


@dataclass(frozen=True)
class Tweet:
    tweet_id: str
    url: str
    author: str
    author_name: str
    author_id: str
    published: date
    bookmarked: date | None
    text: str
    hashtags: list[str]
    reply_id: str | None
    reply_to: str | None
    reply_count: int
    conversation_id: str
    quoted_id: str | None
    source_user: str | None
    article_title: str | None
    article_text: str | None
    media_files: list[Path]


class TweetError(ValueError):
    pass


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.parts.append("\n")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in _BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(html: str) -> str:
    """Plain text of an X Article's HTML: block elements become paragraphs, <br> a line break."""
    parser = _TextParser()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts)
    lines = [line.strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


_LIST_TYPES = ("ordered-list-item", "unordered-list-item")


def _entity_text(entity, block_text: str) -> str:
    """Text for an atomic block's entity: embedded tweet link, markdown/code, LaTeX, media caption, divider."""
    if not isinstance(entity, dict):
        return ""
    kind = entity.get("type")
    data = entity.get("data") if isinstance(entity.get("data"), dict) else {}
    if kind == "TWEET":
        tweet_id = data.get("tweetId") or data.get("tweet_id") or data.get("id")
        return f"https://x.com/i/status/{tweet_id}" if tweet_id else ""
    if kind == "MARKDOWN":
        return str(data.get("markdown") or data.get("text") or "")
    if kind == "LATEX":
        return block_text.strip()
    if kind == "MEDIA":
        return str(data.get("caption") or "")
    if kind == "DIVIDER":
        return "---"
    return ""


def article_text(state: dict) -> str:
    """Plain text of an X Article's raw content_state, every block type kept (gallery-dl's HTML drops some)."""
    raw_entities = state.get("entityMap") or []
    if isinstance(raw_entities, dict):
        raw_entities = [{"key": k, "value": v} for k, v in raw_entities.items()]
    entities = {str(e.get("key")): e.get("value") for e in raw_entities if isinstance(e, dict)}
    parts: list[tuple[str, str]] = []
    number = 0
    for block in state.get("blocks") or []:
        kind = block.get("type") or "unstyled"
        text = str(block.get("text") or "")
        number = number + 1 if kind == "ordered-list-item" else 0
        if kind == "atomic":
            text = "\n".join(t for t in (_entity_text(entities.get(str(r.get("key"))), text)
                                         for r in block.get("entityRanges") or []) if t)
        elif kind == "ordered-list-item":
            text = f"{number}. {text}"
        elif kind == "unordered-list-item":
            text = f"- {text}"
        if text.strip():
            parts.append((kind, text))
    out = ""
    for i, (kind, text) in enumerate(parts):
        if i:
            same_list = kind in _LIST_TYPES and parts[i - 1][0] == kind
            out += "\n" if same_list else "\n\n"
        out += text
    return out


def _article(data: dict) -> tuple[str | None, str | None]:
    """(title, text) from either gallery-dl article shape: raw `article_results`, or meta + html."""
    art = data.get("article")
    if not isinstance(art, dict):
        return None, None
    if "article_results" in art:
        result = (art.get("article_results") or {}).get("result") or {}
        state = result.get("content_state")
        text = article_text(state) if isinstance(state, dict) else ""
        return result.get("title") or None, text or None
    html = art.get("html")
    return art.get("title") or None, (html_to_text(html) or None) if isinstance(html, str) and html.strip() else None


def _id(value) -> str | None:
    """X ids as exact strings; 0 / missing -> None."""
    if value in (None, "", 0, "0"):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not str(value).isdigit():
        raise TweetError(f"bad id {value!r}")
    return str(value)


def _date(value, required: bool) -> date | None:
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        if required:
            raise TweetError(f"bad date {value!r}") from None
        return None


def media_from_names(folder: Path, tweet_id: str, names: list[str]) -> list[Path]:
    """The tweet's media files among a folder's file names (<id>_NN.<ext>), in number order."""
    pattern = re.compile(rf"^{re.escape(tweet_id)}_(\d{{2,}})\.({'|'.join(MEDIA_EXTENSIONS)})$", re.IGNORECASE)
    found = []
    for name in names:
        match = pattern.match(name)
        if match:
            found.append((int(match.group(1)), folder / name))
    return [path for _, path in sorted(found)]


def _media_files(folder: Path, tweet_id: str) -> list[Path]:
    if not folder.is_dir():
        return []
    return media_from_names(folder, tweet_id, [p.name for p in folder.iterdir() if p.is_file()])


def load_tweet(json_path: Path, items_dir: Path) -> Tweet:
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TweetError(f"{json_path.name}: {exc}") from None
    return tweet_from_data(data, json_path.name, lambda tweet_id: _media_files(items_dir / tweet_id, tweet_id))


def tweet_from_data(data, source: str, media_for: Callable[[str], list[Path]]) -> Tweet:
    """A Tweet from one gallery-dl JSON object read from the file named `source`. `media_for(tweet_id)` gives
    its media files: the folder is named by the id the JSON holds, known only once it's checked."""
    if not isinstance(data, dict):
        raise TweetError(f"{source}: not an object")
    tweet_id = _id(data.get("tweet_id"))
    who = data.get("author")
    if tweet_id is None or not isinstance(who, dict) or not who.get("name"):
        raise TweetError(f"{source}: missing tweet_id or author")
    article_title, article_body = _article(data)
    source = data.get("source_user")
    name = str(who["name"])
    return Tweet(
        tweet_id=tweet_id,
        url=f"https://x.com/{name}/status/{tweet_id}",
        author=name,
        author_name=str(who.get("nick") or ""),
        author_id=str(who.get("id") or ""),
        published=_date(data.get("date"), required=True),
        bookmarked=_date(data.get("date_bookmarked"), required=False),
        text=str(data.get("content") or ""),
        hashtags=[str(h) for h in data.get("hashtags") or []],
        reply_id=_id(data.get("reply_id")),
        reply_to=data.get("reply_to") or None,
        reply_count=int(data.get("reply_count") or 0),
        conversation_id=_id(data.get("conversation_id")) or tweet_id,
        quoted_id=_id(data.get("quoted_id")),
        source_user=str(source["name"]) if isinstance(source, dict) and source.get("name") else None,
        article_title=article_title,
        article_text=article_body,
        media_files=media_for(tweet_id),
    )


def complete(names: list[str], tweet: Tweet, data_count) -> bool:
    """Whether a bookmark's download is complete, from its folder's file names: no .part file, media numbered
    1..n, and at least as many files as the JSON's `count`."""
    if any(name.endswith(".part") for name in names):
        return False
    numbers = [int(p.stem.rsplit("_", 1)[1]) for p in tweet.media_files]
    if numbers != list(range(1, len(numbers) + 1)):
        return False
    return not (isinstance(data_count, int) and len(tweet.media_files) < data_count)


def merge_known(known: dict[str, Tweet], tweet: Tweet) -> None:
    """Add a tweet to `known`, over any earlier copy; a copy without article text keeps the earlier one's."""
    earlier = known.get(tweet.tweet_id)
    if earlier is not None and earlier.article_text and not tweet.article_text:
        # the Bookmarks feed has no article text; a thread lookup's copy may
        tweet = replace(tweet, article_text=earlier.article_text,
                        article_title=tweet.article_title or earlier.article_title)
    known[tweet.tweet_id] = tweet


def scan_bookmarks(items_dir: Path) -> tuple[list[Tweet], list[str]]:
    """Complete bookmarks (folders holding <id>.json), newest bookmarked first; ids of incomplete folders."""
    from .scan import scan
    s = scan(items_dir, None)
    return s.bookmarks, s.incomplete


def known_tweets(items_dir: Path, threads_dir: Path) -> dict[str, Tweet]:
    """Every tweet on disk by id; a bookmark copy beats a quoted copy, which beats a thread copy."""
    from .scan import scan
    return scan(items_dir, threads_dir).known
