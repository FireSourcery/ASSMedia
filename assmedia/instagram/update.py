"""`update`, which you run: download new saves from your Saved feed, then report what's waiting.

gallery-dl is started as its own process without -I: it lives in the user site-packages, which `py -I` hides.
"""
import subprocess
import sys
from pathlib import Path

from assmedia.core.config import Config, dirs

SAVED_URL = "https://www.instagram.com/{}/saved/"
TEMPLATE = Path(__file__).with_name("gallery-dl.conf")  # behaviour only; conf_values fills in the rest


def conf_values(cfg: Config) -> dict:
    """The paths and the browser Instagram's gallery-dl config gets from the instance config, by key path."""
    d = dirs(cfg, "instagram")
    return {
        ("extractor", "base-directory"): d.items.as_posix() + "/",
        ("extractor", "instagram", "cookies"): [cfg.cookies],
        ("extractor", "instagram", "archive"): (d.crawl / "gallery-dl-archive.sqlite3").as_posix(),
        ("output", "logfile", "path"): (d.crawl / "gallery-dl.log").as_posix(),
        ("output", "errorfile"): (d.crawl / "failed-urls.txt").as_posix(),
    }


def download_args(conf: Path, account: str, full: bool) -> list[str]:
    """gallery-dl's arguments for the Saved feed; without `full`, it stops after 5 files it already has."""
    return ["-c", str(conf), *([] if full else ["--abort", "5"]), SAVED_URL.format(account)]


def run_gallery_dl(args: list[str]) -> int:
    return subprocess.run([sys.executable, "-m", "gallery_dl", *args]).returncode


def cmd_update(p, account: str | None, *, full: bool, conf: Path, run=run_gallery_dl) -> int:
    """The download with the filled-in gallery-dl config `conf`, then `pending`'s summary. A failed file doesn't stop the summary; a missing gallery-dl does."""
    if not account:
        print("update: no account to download from; set [instagram] saved in assmedia.toml", flush=True)
        return 2
    try:
        code = run(download_args(conf, account, full))
    except OSError as exc:
        print(f"update: gallery-dl could not be started: {exc}", flush=True)
        return 2
    print(f"download: exit {code}", flush=True)
    from .cli import pending  # cli imports this module for the `update` command
    todo, incomplete = pending(p)
    print(f"done: new {len(todo)}, incomplete {len(incomplete)}" + (f" ({', '.join(incomplete)})" if incomplete else ""),
          flush=True)
    return 0
