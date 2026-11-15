"""The user's one command: download new bookmarks, queue their thread lookups, run them, report what's ready.

Runs gallery-dl as a separate process (it lives in the user's site-packages, which `py -I` hides) with the one
config's `bookmark` block for the Bookmarks feed and its `tweet` block for the lookups. The lookup pass gets its own
log and failure list on the command line, so both keep their files from the two-config days.
"""
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from assmedia.core.config import Config, dirs

from .cli import PENDING_LIST, XPaths, cmd_pending
from .lookup import FAILED_LIST, lookup_state

BOOKMARKS_URL = "https://x.com/i/bookmarks"
TEMPLATE = Path(__file__).with_name("gallery-dl.conf")  # behaviour only; conf_values fills in the rest


def conf_values(cfg: Config) -> dict:
    """The paths and the browser X's gallery-dl config gets from the instance config, by key path."""
    d = dirs(cfg, "x")
    return {
        ("extractor", "base-directory"): d.items.as_posix() + "/",
        ("extractor", "twitter", "cookies"): [cfg.cookies],
        ("extractor", "twitter", "archive"): (d.crawl / "gallery-dl-archive.sqlite3").as_posix(),
        ("extractor", "twitter", "tweet", "postprocessors", 0, "directory"): d.threads.as_posix(),
        ("output", "logfile", "path"): (d.crawl / "gallery-dl.log").as_posix(),
        ("output", "errorfile"): (d.crawl / "failed-urls.txt").as_posix(),
    }


LOOKUP_LOG = "threads.log"
LOOKUP_FAILED = FAILED_LIST


def bookmark_args(conf: Path, full: bool) -> list[str]:
    """The bookmarks pass; it stops after 5 files in a row that the download record has, unless `full`."""
    return ["-c", conf.as_posix(), *([] if full else ["--abort", "5"]), BOOKMARKS_URL]


def lookup_args(conf: Path, crawl: Path, list_file: Path) -> list[str]:
    log = json.dumps({"path": (crawl / LOOKUP_LOG).as_posix(), "mode": "a", "level": "info"})
    return ["-c", conf.as_posix(),
            "-o", f"output.logfile={log}",
            "-o", f"output.errorfile={(crawl / LOOKUP_FAILED).as_posix()}",
            "-I", list_file.as_posix()]


def _urls(path: Path) -> int:
    """Lookup URLs still to run in a list (gallery-dl's -I comments out each one it has run)."""
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("https://"))


def has_lookups(list_file: Path) -> bool:
    return _urls(list_file) > 0


def run_gallery_dl(args: list[str]) -> int:
    return subprocess.run([sys.executable, "-m", "gallery_dl", *args]).returncode


def cmd_update(xp: XPaths, *, full: bool = False, lookups: Path | None = None,
               run: Callable[[list[str]], int] = run_gallery_dl) -> int:
    """Every step runs even when gallery-dl exits non-zero (one DMCA'd file is enough); only a gallery-dl that
    can't be started stops it. With `lookups`, only that lookup list is run (a retry)."""
    if lookups is not None:
        if not lookups.is_file():
            print(f"no lookup list at {lookups}")
            return 2
        if lookups.resolve() == (xp.crawl / LOOKUP_FAILED).resolve():
            print(f"{lookups.name} is the live failure list: rename it first (README, Failed lookups)")
            return 2
    try:
        if lookups is None:
            print(f"bookmarks pass: exit {run(bookmark_args(xp.gallery_conf, full))}")
            counts = cmd_pending(xp)
            print("pending: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
        list_file = lookups or xp.crawl / PENDING_LIST
        if has_lookups(list_file):
            print(f"lookup pass: exit {run(lookup_args(xp.gallery_conf, xp.crawl, list_file))}")
        else:
            print("lookup pass: nothing queued")
    except OSError as exc:
        print(f"gallery-dl could not be started: {exc}")
        return 2
    counts = cmd_pending(xp)
    state = lookup_state(xp.crawl)
    failed = len(state.failed - state.skip)
    line = (f"done: new {counts['new']}, ready {counts['ready']}, still waiting {counts['waiting_lookup']}, "
            f"failed lookups {failed}")
    if failed:
        line += f" (see {xp.crawl / LOOKUP_FAILED})"
    print(line)
    return 0
