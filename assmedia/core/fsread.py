"""Bulk reads from slow disks (the NAS): each file open is a round trip, so open many at once.

Results come back in the order given. A file or folder that can't be read gives its exception in its place, so
each caller decides what that means, as it did when it read one file at a time. Callers use these through the
module (`fsread.read_texts(...)`), which lets tests count the reads.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Sequence

WORKERS = 16  # reads at once; the measurements stopped improving beyond this


def _read(path: Path) -> str | Exception:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        return exc


def _list(folder: Path) -> list[str] | OSError:
    try:
        with os.scandir(folder) as entries:
            return sorted(e.name for e in entries if e.is_file())
    except OSError as exc:
        return exc


def _map(fn, items: Sequence, workers: int) -> list:
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))


def read_texts(paths: Sequence[Path], workers: int = WORKERS) -> list[str | Exception]:
    """Each file's text as Path.read_text(encoding="utf-8") reads it, in the order given; an OSError or
    ValueError (a decode error) in place of a file that can't be read."""
    return _map(_read, list(paths), workers)


def read_all(paths: Sequence[Path], workers: int = WORKERS) -> list[str]:
    """read_texts, raising the first error in the order given."""
    texts = read_texts(paths, workers)
    for text in texts:
        if isinstance(text, Exception):
            raise text
    return texts


def list_files(folders: Sequence[Path], workers: int = WORKERS) -> list[list[str] | OSError]:
    """The names of each folder's regular files, sorted, in the order given; an OSError in place of a folder
    that can't be listed."""
    return _map(_list, list(folders), workers)
