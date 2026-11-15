"""The instance config, assmedia.toml: every path, account and program one setup needs.

Read before anything else, so this module imports only the standard library. Paths use forward slashes.
What the tool pulls goes under `raw`, what it keeps for itself under `state`, one folder per platform in each.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

PLATFORMS = {"x": "X", "instagram": "Instagram"}  # command name -> folder name under raw and state
PATH_KEYS = ("raw", "state", "vault", "ffmpeg")
TABLES = ("paths", "gallery-dl", *PLATFORMS)


@dataclass(frozen=True)
class XSettings:
    own_accounts: frozenset[str]  # the user's own X usernames, lowercase: never a creator person


@dataclass(frozen=True)
class InstagramSettings:
    saved_account: str | None     # whose Saved feed `update` downloads


@dataclass(frozen=True)
class Config:
    raw: Path                     # what the tool pulls: <raw>/<Platform>/items, threads, thumbs
    state: Path                   # what it keeps: <state>/<Platform>/_crawl, tagging, build
    vault: Path                   # the Obsidian vault the pages go into
    ffmpeg: Path                  # makes video thumbnails
    cookies: str                  # the browser gallery-dl reads the login cookies from
    x: XSettings | None           # None: no [x] section, so X isn't set up
    instagram: InstagramSettings | None


@dataclass(frozen=True)
class PlatformDirs:
    items: Path
    threads: Path
    thumbs: Path
    crawl: Path                   # download record, logs, failure and lookup lists
    tagging: Path                 # kept across batches: creator map (and X's declined names)
    build: Path                   # one batch's files; safe to delete


def dirs(cfg: Config, platform: str) -> PlatformDirs:
    folder = PLATFORMS[platform]
    raw, state = cfg.raw / folder, cfg.state / folder
    return PlatformDirs(items=raw / "items", threads=raw / "threads", thumbs=raw / "thumbs",
                        crawl=state / "_crawl", tagging=state / "tagging", build=state / "build")


def default_config_path() -> Path:
    """assmedia.toml in the project root, the folder above the assmedia package."""
    return Path(__file__).resolve().parents[2] / "assmedia.toml"


def _absolute(path: Path, key: str, value) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: {key} is missing")
    p = Path(value)
    if not p.is_absolute():
        raise ValueError(f"{path}: {key} must be an absolute path, not {value!r}")
    return p


def _x(path: Path, section: dict) -> XSettings:
    own = section.get("own", [])
    if not isinstance(own, list) or not all(isinstance(a, str) for a in own):
        raise ValueError(f"{path}: x.own must be a list of usernames")
    return XSettings(own_accounts=frozenset(a.strip().lower() for a in own if a.strip()))


def _instagram(path: Path, section: dict) -> InstagramSettings:
    saved = section.get("saved")
    if saved is not None and (not isinstance(saved, str) or not saved.strip()):
        raise ValueError(f"{path}: instagram.saved must be a username")
    return InstagramSettings(saved_account=saved.strip() if saved else None)


def load_config(path: Path) -> Config:
    if not path.is_file():
        raise FileNotFoundError(f"no instance config at {path}")
    try:
        text = path.read_text(encoding="utf-8-sig")  # -sig: a byte-order mark (PowerShell 5's UTF8) is fine
    except UnicodeDecodeError:
        raise ValueError(f"{path}: not UTF-8 text; save it as UTF-8 (PowerShell 5's `>` writes UTF-16)") from None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path}: {exc} (paths use forward slashes, as in D:/Media/raw)") from None
    for table in TABLES:
        if not isinstance(data.get(table, {}), dict):
            raise ValueError(f"{path}: [{table}] must be a table")
    section = data.get("paths") or {}
    paths = {key: _absolute(path, f"paths.{key}", section.get(key)) for key in PATH_KEYS}
    cookies = (data.get("gallery-dl") or {}).get("cookies")
    if not isinstance(cookies, str) or not cookies.strip():
        raise ValueError(f"{path}: gallery-dl.cookies is missing (the browser you're signed in with)")
    return Config(cookies=cookies.strip(),
                  x=_x(path, data["x"]) if "x" in data else None,
                  instagram=_instagram(path, data["instagram"]) if "instagram" in data else None,
                  **paths)


def problems(cfg: Config, platform: str | None = None) -> list[str]:
    """What's missing on disk for this config. `raw` and `state` may not exist yet: the tool makes them."""
    found = []
    if not cfg.vault.is_dir():
        found.append(f"paths.vault: no folder at {cfg.vault}")
    if not cfg.ffmpeg.is_file():
        found.append(f"paths.ffmpeg: no file at {cfg.ffmpeg}")
    return found


def split_config_arg(argv: list[str]) -> tuple[Path | None, list[str]]:
    """Take `--config PATH` out of the command line; the rest goes to the commands."""
    if "--config" not in argv:
        return None, list(argv)
    i = argv.index("--config")
    if i + 1 >= len(argv):
        raise ValueError("--config needs a path")
    return Path(argv[i + 1]), argv[:i] + argv[i + 2:]
