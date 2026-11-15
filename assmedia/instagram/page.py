"""Save page rendering: wiki/sources/Instagram/<title>.md."""
from datetime import date

from assmedia.core.contact import has_contact, phone_like  # noqa: F401  (re-exported for the tests)
from assmedia.core.escape import escape_caption, quote_block
from assmedia.core.page import MAX_TITLE, MAX_TITLE_BYTES, ThumbRef, safe_title

from .post import Post
from assmedia.core.tags import Tags
from assmedia.core.title import emoji_title, title_line
from assmedia.core.yamlfm import dump

VAULT_THUMBS = "raw/Instagram/_thumbs"
NO_CAPTION = "*(no caption)*"
_MEDIA_WORD = {"video": "Video", "photo": "Photo", "carousel": "Images"}


def thumb_ref(shortcode: str, mode: str, thumbs_url: str) -> ThumbRef:
    """`thumbs_url`: the thumbnails folder as a file:/// URI, without a trailing slash."""
    if mode == "external":
        url = f"{thumbs_url}/{shortcode}.jpg"
        return ThumbRef(url, f"![]({url})")
    if mode == "vault":
        path = f"{VAULT_THUMBS}/{shortcode}.jpg"
        return ThumbRef(f"[[{path}]]", f"![[{path}|360]]")
    raise ValueError(f"unknown thumb mode {mode!r}")


def fallback_title(post: Post, max_chars: int = MAX_TITLE, max_bytes: int = MAX_TITLE_BYTES) -> str:
    """For an untagged save: the caption's first line with words, else its emoji's names, else the media kind."""
    return (safe_title(title_line(post.caption), max_chars, max_bytes)
            or safe_title(emoji_title(post.caption), max_chars, max_bytes)
            or _MEDIA_WORD[post.media])


def choose_title(post: Post, tags: Tags, taken: set[str]) -> str:
    """`<title> (<username>)` always; a name already taken gets ` - <shortcode>`."""
    suffix = f" ({post.username})"
    limits = (MAX_TITLE - len(suffix), MAX_TITLE_BYTES - len(suffix.encode("utf-8")))
    base = (safe_title(tags.title, *limits) or fallback_title(post, *limits)) + suffix
    if base.lower() in taken:
        base = f"{base} - {post.shortcode}"
    return base


def _people(tags: Tags) -> list[str]:
    names = list(tags.people)
    if tags.creator_person and tags.creator_person.lower() not in {n.lower() for n in names}:
        names.append(tags.creator_person)
    return [f"[[{n}]]" for n in names]


def video_players(post: Post, items_url: str) -> list[str]:
    """Inline HTML players for the post's videos (Markdown embeds of files outside the vault don't play)."""
    return [f'<video controls preload="metadata" '
            f'src="{items_url}/{post.shortcode}/{path.name}"></video>'
            for path in post.media_files if path.suffix.lower() == ".mp4"]


def media_block(post: Post, items_url: str) -> list[str]:
    """The page's media, in post order: an inline player per video, an inline image per photo."""
    lines = []
    for path in post.media_files:
        url = f"{items_url}/{post.shortcode}/{path.name}"
        lines.append(f'<video controls preload="metadata" src="{url}"></video>'
                     if path.suffix.lower() == ".mp4" else f"![]({url})")
    return lines


def caption_block(post: Post) -> str:
    """The caption word for word, escaped so Obsidian shows it as written, as a quote block.
    Carriage returns (\\r\\n or a lone \\r) are line breaks, so every line stays inside the quote."""
    caption = post.caption.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    return quote_block(escape_caption(caption)) if caption.strip() else NO_CAPTION


def legacy_body_lines(post: Post, items_url: str, thumbs_url: str) -> set[str]:
    """Lines earlier versions of this tool wrote between the title and the caption."""
    lines = set(video_players(post, items_url)) | set(_media_lines(post, items_url))
    lines.add(f"- [View on Instagram]({post.url})")
    lines.add(f"![]({thumbs_url}/{post.shortcode}.jpg)")
    lines.add(f"![[{VAULT_THUMBS}/{post.shortcode}.jpg|360]]")
    return lines


def _media_lines(post: Post, items_url: str) -> list[str]:
    lines = []
    for path in post.media_files:
        number = int(path.stem.rsplit("_", 1)[1])
        kind = "video" if path.suffix.lower() == ".mp4" else "photo"
        lines.append(f"- [Open {kind} {number}]({items_url}/{post.shortcode}/{path.name})")
    return lines


def render_page(post: Post, tags: Tags, *, title: str, saved: date,
                thumb: ThumbRef | None, created: date, items_url: str) -> str:
    props = [
        ("type", "source"),
        ("source", "Instagram"),
        ("shortcode", post.shortcode),
        ("source_url", post.url),
        ("source_author", post.username),
        ("source_author_name", post.fullname),
        ("published", post.published),
        ("saved", saved),
        ("media", post.media),
        ("files", len(post.media_files)),
        ("people", _people(tags)),
        ("subjects", [f"[[{n}]]" for n in tags.subjects]),
        ("themes", [f"[[{n}]]" for n in tags.themes]),
        ("hashtags", [h.lstrip("#") for h in post.hashtags]),
        ("domain", [f"[[{n}]]" for n in tags.domain]),
        ("description", tags.description),
        ("online", True),
        ("thumbnail", thumb.prop if thumb else None),
        ("created", created),
        ("tags", ["source", "instagram"]),
        ("created_by", "claude"),
    ]
    body = [f"# {title}", ""]
    for line in media_block(post, items_url):
        body += [line, ""]
    body.append(caption_block(post))
    return dump(props) + "\n" + "\n".join(body) + "\n"
