"""Claude-written tags per X bookmark: the core's Tags plus the quoted tweet's and the reused media's creators."""
import json
from dataclasses import dataclass, fields
from pathlib import Path

from assmedia.core.tags import LIST_FIELDS, TEXT_FIELDS, Tags, check_types

ROLE_FIELDS = ("creator_person", "quoted_person", "source_person")


@dataclass
class XTags(Tags):
    quoted_person: str | None = None
    source_person: str | None = None


_FIELDS = {f.name for f in fields(XTags)}


def load_x_tags(path: Path) -> dict[str, XTags]:
    """<state>/X/build/tags/<name>.json: {tweet_id: {title, description, people, subjects, themes, domain, *_person}}."""
    data = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for tweet_id, entry in data.items():
        if not isinstance(entry, dict):
            raise ValueError(f"{tweet_id}: entry must be an object")
        unknown = set(entry) - _FIELDS
        if unknown:
            raise ValueError(f"{tweet_id}: unknown tag fields {sorted(unknown)}")
        check_types(tweet_id, entry, LIST_FIELDS, TEXT_FIELDS + ("quoted_person", "source_person"))
        result[str(tweet_id)] = XTags(
            title=entry.get("title") or "",
            description=entry.get("description") or "",
            people=list(entry.get("people") or []),
            subjects=list(entry.get("subjects") or []),
            themes=list(entry.get("themes") or []),
            creator_person=entry.get("creator_person") or None,
            domain=list(entry.get("domain") or []),
            quoted_person=entry.get("quoted_person") or None,
            source_person=entry.get("source_person") or None,
        )
    return result
