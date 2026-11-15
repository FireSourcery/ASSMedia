"""Rewrite the file:/// links in a folder of pages after a media folder moves.

    py -I relink.py <pages folder> <old folder> <new folder> [--dry-run]

Only links into the old folder change: its URI (Path.as_uri, plus "/") becomes the new folder's. Every other byte of
a page stays as it was, line endings included, and a page with no such link isn't written at all. Pages in
subfolders count too. It prints how many pages and links it changed (or would change, with --dry-run).
"""
import argparse
import os
import sys
from pathlib import Path


def _prefix(folder: Path) -> str:
    return folder.as_uri().rstrip("/") + "/"


def relink_text(text: str, old: Path, new: Path) -> tuple[str, int]:
    """The text with each link into `old` pointing into `new` instead, and how many links changed."""
    before, after = _prefix(old), _prefix(new)
    return text.replace(before, after), text.count(before)


def _replace(page: Path, data: bytes) -> None:
    """Write `data` over `page` without ever leaving it half-written: a temporary file beside it, then a rename."""
    tmp = page.with_name(page.name + ".relink-tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, page)
    finally:
        if tmp.exists():
            tmp.unlink()


def relink(pages: Path, old: Path, new: Path, dry_run: bool = False) -> dict[str, int]:
    files = links = 0
    for md in sorted(pages.rglob("*.md")):
        text = md.read_bytes().decode("utf-8")
        out, n = relink_text(text, old, new)
        if n:
            files, links = files + 1, links + n
            if not dry_run:
                _replace(md, out.encode("utf-8"))
    return {"files": files, "links": links}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Rewrite file:/// links in pages after a media folder moves.")
    ap.add_argument("pages", type=Path)
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not args.pages.is_dir():
        print(f"relink: no folder at {args.pages}", file=sys.stderr)
        return 2
    counts = relink(args.pages, args.old, args.new, args.dry_run)
    verb = "would change" if args.dry_run else "changed"
    print(f"{verb} {counts['links']} links in {counts['files']} pages: "
          f"{_prefix(args.old)} -> {_prefix(args.new)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
