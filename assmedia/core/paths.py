"""The paths every platform's commands work from, the collections sharing the wiki, and the page indexes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import fsread
from .collection import Collection, collections_of, instagram, x
from .concepts import collect_all, concept_index, vault_notes, wiki_dirs
from .config import Config, dirs
from .tags import canonicalize, validate_name
from .yamlfm import split


@dataclass
class Paths:
    vault: Path
    wiki: Path
    items: Path
    pages: Path
    entities: Path
    concepts: Path
    people: Path
    domains: Path
    index_md: Path
    thumbs_dir: Path
    tagging: Path                 # kept across batches: creator-people.json
    build: Path                   # files used within one batch: export/, concepts/ (plans)
    ffmpeg: Path
    thumb_mode: str  # "external" or "vault"
    items_url: str   # items folder as a file:/// URI, no trailing slash: page media links
    thumbs_url: str  # thumbnails folder, the same way: page thumbnails
    collections: tuple = ()  # every collection sharing the wiki pages; empty = Instagram only


def collections(cfg: Config) -> tuple[Collection, ...]:
    """Every platform's source pages, which share the wiki's entity and concept pages: Instagram, then X. A
    platform with a config section brings its item JSON and creator map; one without, its pages alone."""
    sources = cfg.vault / "wiki" / "sources"
    ig, xd = dirs(cfg, "instagram"), dirs(cfg, "x")
    return (instagram(sources / "Instagram", ig.items, ig.tagging) if cfg.instagram is not None
            else instagram(sources / "Instagram", None, None),
            x(sources / "X", xd.items, xd.tagging) if cfg.x is not None else x(sources / "X"))


def write_new(path: Path, text: str) -> None:
    """Create `path` with `text`; an existing file is never overwritten."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as fp:
        fp.write(text)


def page_index(pages: Path, id_property: str = "shortcode") -> dict[str, Path]:
    """Post id (the page's `id_property`) -> its page."""
    index = {}
    if pages.exists():
        mds = list(pages.glob("*.md"))
        for md, text in zip(mds, fsread.read_all(mds)):
            code = split(text)[0].get(id_property)
            if code:
                index[str(code)] = md
    return index


def clean_names(names: list[str], index: dict[str, str]) -> list[str]:
    seen, result = set(), []
    for name in names:
        validate_name(name)
        canonical = canonicalize(name, index)
        if canonical.lower() not in seen:
            seen.add(canonical.lower())
            result.append(canonical)
    return result


def taken_names(p: Paths) -> set[str]:
    """Lowercased note names a new page must not reuse: file names are unique across the vault (CLAUDE.md)."""
    taken = {md.stem.lower() for md in p.pages.glob("*.md")} if p.pages.exists() else set()
    return taken | set(vault_notes(p.vault))


def build_index(p: Paths) -> dict[str, str]:
    """Names to canonicalize against: earlier link spellings, overridden by existing pages and aliases."""
    linked = {name.lower(): name for name in collect_all(collections_of(p))}
    return {**linked, **concept_index(wiki_dirs(p) + [p.people])}
