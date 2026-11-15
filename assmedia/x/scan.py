"""One scan of the downloads per command: each folder listed once, each tweet JSON read once, 16 at a time.

Over the NAS each file open and each folder listing is a round trip, so the scan lists `items\\` and then all
its folders, reads every JSON file in one batch (assmedia.core.fsread), and works from those results. What it gives is
what scan_bookmarks and known_tweets gave, read once instead of several times.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from assmedia.core import fsread

from .tweet import Tweet, TweetError, complete, media_from_names, merge_known, tweet_from_data


@dataclass(frozen=True)
class Scan:
    bookmarks: list[Tweet]   # complete bookmarks as their own <id>.json has them, newest bookmarked first
    incomplete: list[str]    # bookmark folder ids, sorted: download not complete, or its JSON can't be read
    known: dict[str, Tweet]  # every tweet on disk: bookmark copy > quoted copy > thread copy, article text merged


def _entries(folder: Path | None, want_dirs: bool) -> list[Path]:
    if folder is None or not folder.is_dir():
        return []
    with os.scandir(folder) as entries:
        return sorted(Path(e.path) for e in entries if (e.is_dir() if want_dirs else e.is_file()))


def scan(items_dir: Path, threads_dir: Path | None) -> Scan:
    folders = _entries(items_dir, want_dirs=True)
    names: dict[str, list[str]] = {}
    for folder, listed in zip(folders, fsread.list_files(folders)):
        if isinstance(listed, OSError):
            raise listed  # as before: a folder that can't be listed stops the command
        names[folder.name] = listed

    threads = [p for p in _entries(threads_dir, want_dirs=False) if p.name.lower().endswith(".json")]
    quoted = sorted(f / n for f in folders for n in names[f.name] if n.lower().endswith(".quoted.json"))
    bookmark_files = [f / f"{f.name}.json" for f in folders if f"{f.name}.json" in names[f.name]]
    paths = threads + quoted + bookmark_files

    def media_for(tweet_id: str) -> list[Path]:
        listed = names.get(tweet_id)
        return media_from_names(items_dir / tweet_id, tweet_id, listed) if listed is not None else []

    parsed: dict[Path, tuple[Tweet, dict] | None] = {}
    for path, text in zip(paths, fsread.read_texts(paths)):
        if isinstance(text, Exception):
            parsed[path] = None
            continue
        try:
            data = json.loads(text)
        except ValueError:
            parsed[path] = None
            continue
        try:
            parsed[path] = (tweet_from_data(data, path.name, media_for), data)
        except TweetError:
            parsed[path] = None

    bookmarks, incomplete = [], []
    for path in bookmark_files:
        folder = path.parent.name
        result = parsed[path]
        if result is not None and complete(names[folder], result[0], result[1].get("count")):
            bookmarks.append(result[0])
        else:
            incomplete.append(folder)
    bookmarks.sort(key=lambda t: (t.bookmarked or date.min, int(t.tweet_id)), reverse=True)

    known: dict[str, Tweet] = {}
    for path in paths:
        if parsed[path] is not None:
            merge_known(known, parsed[path][0])
    return Scan(bookmarks=bookmarks, incomplete=incomplete, known=known)
