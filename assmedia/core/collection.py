"""Collections of source pages that share the wiki's entity and concept pages: Instagram saves, X bookmarks."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Collection:
    name: str           # "Instagram" | "X"
    pages: Path         # folder of this collection's source pages
    folder: str         # vault-relative folder, for the Base filter in embedded lists
    heading: str        # heading of the embedded list on entity and concept pages
    view_name: str      # name of the embedded cards view
    id_property: str    # page property holding the post id
    items: Path | None  # holds <id>/<id>.json from gallery-dl; None when known only from the vault
    caption_field: str  # JSON field with the post's text
    creators: Path | None  # this platform's username -> person mapping; None when there's none to read
    profile_url: str    # format string for a creator's profile


def instagram(pages: Path, items: Path | None = None, tagging: Path | None = None) -> Collection:
    """Instagram saves. Without `items` and `tagging` (no [instagram] section), known from the vault alone."""
    return Collection(name="Instagram", pages=pages, folder="wiki/sources/Instagram",
                      heading="## Instagram saves", view_name="Saves", id_property="shortcode",
                      items=items, caption_field="description",
                      creators=tagging / "creator-people.json" if tagging else None,
                      profile_url="https://www.instagram.com/{}/")


def x(pages: Path, items: Path | None = None, tagging: Path | None = None) -> Collection:
    """X bookmarks. Instagram's own runs pass only `pages`: they learn about X from the vault alone."""
    return Collection(name="X", pages=pages, folder="wiki/sources/X", heading="## X bookmarks",
                      view_name="Bookmarks", id_property="tweet_id", items=items, caption_field="content",
                      creators=tagging / "creator-people.json" if tagging else None,
                      profile_url="https://x.com/{}")


def collections_of(p) -> tuple[Collection, ...]:
    """The collections a Paths object carries; Instagram alone (from p.pages) when it carries none."""
    return tuple(getattr(p, "collections", ()) or ()) or (instagram(p.pages, p.items, p.tagging),)
