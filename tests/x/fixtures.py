"""Test helpers: fake gallery-dl X JSON (the shape of <raw>\\X\\items\\*\\*.json) in temporary folders."""
import json
from pathlib import Path


def tweet_payload(tweet_id: str, **over) -> dict:
    tid = int(tweet_id)
    payload = {
        "tweet_id": tid, "retweet_id": 0, "quote_id": 0, "quoted_id": 0, "reply_id": 0,
        "conversation_id": tid, "source_id": 0, "date": "2026-11-10 12:00:00",
        "date_bookmarked": "2026-11-11 08:00:00",
        "author": {"id": 111, "name": "someone", "nick": "Some One", "description": "my bio",
                   "location": "somewhere"},
        "content": "tweet text", "hashtags": [], "count": 0, "reply_count": 0, "lang": "en",
    }
    payload.update(over)
    return payload


def make_xpaths(root: Path):
    """XPaths with every folder inside `root`; Instagram and X collections both present."""
    from assmedia.core.collection import instagram, x
    from assmedia.core.paths import Paths
    from assmedia.x.cli import XPaths
    vault = root / "vault"
    pages = vault / "wiki" / "sources" / "X"
    ig_pages = vault / "wiki" / "sources" / "Instagram"
    core = Paths(vault=vault, wiki=vault / "wiki", items=root / "items", pages=pages,
                 entities=vault / "wiki" / "entities", concepts=vault / "wiki" / "concepts",
                 people=vault / "People", domains=vault / "Domains", index_md=vault / "wiki" / "index.md",
                 thumbs_dir=root / "thumbs", tagging=root / "tagging", build=root / "build",
                 ffmpeg=root / "no-ffmpeg.exe", thumb_mode="external",
                 items_url=(root / "items").as_uri(), thumbs_url=(root / "thumbs").as_uri(),
                 collections=(instagram(ig_pages, root / "ig-items", root / "ig-data"),
                              x(pages, root / "items", root / "tagging")))
    for folder in (core.items, core.domains, root / "_crawl"):
        folder.mkdir(parents=True, exist_ok=True)
    for hub in ("AI", "Coding"):
        (core.domains / f"{hub}.md").write_text("", encoding="utf-8")
    return XPaths(core=core, threads=root / "threads", crawl=root / "_crawl", build=root / "build",
                  tagging=root / "tagging", gallery_conf=root / "_crawl" / "gallery-dl.conf",
                  own_accounts=frozenset({"ownaccount"}))


def author(user_id: int, name: str, nick: str = "") -> dict:
    return {"id": user_id, "name": name, "nick": nick or name.title(), "description": "bio", "location": ""}


def write_media(items: Path, tweet_id: str, names) -> Path:
    folder = items / tweet_id
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"")
    return folder


def write_tweet(root: Path, tweet_id: str, files=(), kind: str = "bookmark", **over) -> Path:
    """kind "bookmark" -> <root>/<id>/<id>.json, "quoted" -> <root>/<id>/<id>.quoted.json,
    "thread" -> <root>/<id>.json (root = the threads folder). `files` are empty media files next to the JSON."""
    data = tweet_payload(tweet_id, **over)
    data.setdefault("count", len(files))
    if "count" not in over:
        data["count"] = len(files)
    if kind == "quoted" and not data.get("quote_id"):
        data["quote_id"] = 1
    if kind == "thread":
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{tweet_id}.json"
    else:
        folder = write_media(root, tweet_id, files)
        path = folder / (f"{tweet_id}.quoted.json" if kind == "quoted" else f"{tweet_id}.json")
    path.write_text(json.dumps(data), encoding="utf-8")
    return path
