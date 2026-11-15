"""Helpers shared by the core tests and the platforms' tests."""
import json
from pathlib import Path

from assmedia.core.config import Config, InstagramSettings, XSettings

_UNSET = object()


def config_with(raw="D:/m/raw", state="D:/m/state", vault="D:/v", ffmpeg="D:/tools/ffmpeg.exe",
                cookies="firefox", x=_UNSET, instagram=_UNSET) -> Config:
    """A Config with no file behind it: both platforms set up; pass x=None or instagram=None for no section."""
    return Config(raw=Path(raw), state=Path(state), vault=Path(vault), ffmpeg=Path(ffmpeg), cookies=cookies,
                  x=XSettings(own_accounts=frozenset({"me"})) if x is _UNSET else x,
                  instagram=(InstagramSettings(saved_account="me")
                             if instagram is _UNSET else instagram))


def write_note(folder: Path, name: str, props: dict, body: str = "") -> Path:
    """Write <folder>/<name>.md with simple frontmatter (lists as Obsidian-style block lists)."""
    lines = ["---"]
    for key, value in props.items():
        if isinstance(value, list):
            lines.append(f"{key}:" if value else f"{key}: []")
            lines.extend(f'  - "{item}"' for item in value)
        else:
            lines.append(f'{key}: "{value}"')
    lines.append("---")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.md"
    path.write_text("\n".join(lines) + "\n" + body, encoding="utf-8")
    return path


DEFAULT_POST = {
    "post_url": "https://www.instagram.com/p/{sc}/",
    "username": "someone",
    "fullname": "Some One",
    "post_date": "2026-11-06 20:02:52",
    "description": "a caption",
    "tags": ["#tag"],
}




def make_post_folder(root: Path, shortcode: str, files: list[str],
                     data: dict | None = None, drop: tuple[str, ...] = ()) -> Path:
    """Write <root>/<sc>/<sc>.json plus empty media files; `drop` removes default keys."""
    folder = root / shortcode
    folder.mkdir(parents=True, exist_ok=True)
    payload = {k: (v.format(sc=shortcode) if isinstance(v, str) else v)
               for k, v in DEFAULT_POST.items()}
    payload["post_shortcode"] = shortcode
    payload.update(data or {})
    for key in drop:
        payload.pop(key, None)
    (folder / f"{shortcode}.json").write_text(json.dumps(payload), encoding="utf-8")
    for name in files:
        (folder / name).write_bytes(b"")
    return folder


ITEMS_URL = "file:///D:/m/raw/Instagram/items"
THUMBS_URL = "file:///D:/m/raw/Instagram/thumbs"


def make_paths(root: Path, **overrides):
    """Paths for a temporary instance: the vault in root/vault, the instance folders in root."""
    from assmedia.core.paths import Paths
    vault = root / "vault"
    base = dict(vault=vault, wiki=vault / "wiki", items=root / "items", pages=vault / "pages",
                entities=vault / "entities", concepts=vault / "concepts", people=vault / "People",
                domains=vault / "Domains", index_md=vault / "index.md", thumbs_dir=root / "thumbs",
                tagging=root / "tagging", build=root / "build", ffmpeg=root / "no-ffmpeg.exe", thumb_mode="external",
                items_url=ITEMS_URL, thumbs_url=THUMBS_URL)
    return Paths(**{**base, **overrides})
