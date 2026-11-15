"""Claude-written tags per save (<state>/<Platform>/build/tags/<name>.json), tag-name rules and domain hubs."""
import json
from dataclasses import dataclass, field, fields
from pathlib import Path

ILLEGAL_CHARS = set('\\/:*?"<>|#^[]')


@dataclass
class Tags:
    title: str = ""
    description: str = ""
    people: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    creator_person: str | None = None
    domain: list[str] = field(default_factory=list)  # names of existing Domains/ hubs


_FIELDS = {f.name for f in fields(Tags)}
LIST_FIELDS = ("people", "subjects", "themes", "domain")
TEXT_FIELDS = ("title", "description", "creator_person")


def check_types(owner: str, entry: dict, list_fields, text_fields) -> None:
    """Raise ValueError unless list fields are lists of strings and text fields are strings or null."""
    for name in list_fields:
        value = entry.get(name)
        if value is not None and not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
            raise ValueError(f"{owner}: {name} must be a list of strings, got {value!r}")
    for name in text_fields:
        value = entry.get(name)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{owner}: {name} must be a string or null, got {value!r}")


def load_tags(path: Path) -> dict[str, Tags]:
    data = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for shortcode, entry in data.items():
        unknown = set(entry) - _FIELDS
        if unknown:
            raise ValueError(f"{shortcode}: unknown tag fields {sorted(unknown)}")
        check_types(shortcode, entry, LIST_FIELDS, TEXT_FIELDS)
        result[shortcode] = Tags(
            title=entry.get("title") or "",
            description=entry.get("description") or "",
            people=list(entry.get("people") or []),
            subjects=list(entry.get("subjects") or []),
            themes=list(entry.get("themes") or []),
            creator_person=entry.get("creator_person") or None,
            domain=list(entry.get("domain") or []),
        )
    return result


def validate_name(name: str) -> None:
    if not name.strip():
        raise ValueError("empty tag name")
    bad = sorted(set(name) & ILLEGAL_CHARS)
    if bad:
        raise ValueError(f"tag name {name!r} contains {' '.join(bad)}")


def canonicalize(name: str, index: dict[str, str]) -> str:
    name = name.strip()
    return index.get(name.lower(), name)


def hub_names(domains_dir: Path) -> dict[str, str]:
    """Lowercased hub name -> hub note name, from Domains/*.md."""
    if not domains_dir.exists():
        return {}
    return {md.stem.lower(): md.stem for md in domains_dir.glob("*.md")}


def canonical_domains(names: list[str], hubs: dict[str, str]) -> list[str]:
    result = []
    for name in names:
        hub = hubs.get(name.strip().lower())
        if hub is None:
            raise ValueError(f"unknown domain {name!r} (existing: {', '.join(sorted(hubs.values()))})")
        if hub not in result:
            result.append(hub)
    return result
