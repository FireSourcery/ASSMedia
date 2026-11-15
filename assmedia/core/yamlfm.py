"""Minimal YAML frontmatter writer/reader for the notes this tool writes and Obsidian edits.

Writes: strings JSON-quoted, dates/ints/bools plain, None as an empty value, lists as block lists.
Reads: that output, plus Obsidian property-editor output (block lists, single quotes, flow lists).
"""
import json
import re
from datetime import date

_KEY = re.compile(r"^([^\s:#-][^:]*):(?:\s+(.*)|)$")
_ITEM = re.compile(r"^\s*-(?:\s+(.*)|)$")
_FLOW_ITEM = re.compile(r"""\s*("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^,]+?)\s*(?:,|$)""")


def _scalar(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return json.dumps(str(value), ensure_ascii=False)


def dump(props: list[tuple[str, object]]) -> str:
    lines = ["---"]
    for key, value in props:
        if isinstance(value, (list, tuple)):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                lines.extend(f"  - {_scalar(item)}" for item in value)
        else:
            text = _scalar(value)
            lines.append(f"{key}: {text}" if text else f"{key}:")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _parse_scalar(text: str):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        try:
            return json.loads(text)
        except ValueError:
            return text[1:-1]
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1].replace("''", "'")
    if text in ("true", "false"):
        return text == "true"
    return text


def _parse_value(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]") and not raw.startswith("[["):
        inner = raw[1:-1].strip()
        return [_parse_scalar(m.group(1)) for m in _FLOW_ITEM.finditer(inner) if m.group(1)] if inner else []
    return _parse_scalar(raw)


def add_aliases(text: str, names: list[str]) -> str:
    """Add missing names (case-insensitive) to the note's `aliases`; every other line stays as it was."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 3)
    while end != -1 and text[end + 4:end + 5] not in ("\n", ""):
        end = text.find("\n---", end + 4)
    if end == -1:
        return text
    current = split(text)[0].get("aliases")
    current = [str(a) for a in current] if isinstance(current, list) else ([str(current)] if current else [])
    seen = {a.lower() for a in current}
    missing = []
    for name in names:
        if name.strip() and name.lower() not in seen:
            seen.add(name.lower())
            missing.append(name)
    if not missing:
        return text
    rows = text[4:end].split("\n")
    at = next((i for i, row in enumerate(rows) if (m := _KEY.match(row)) and m.group(1).strip() == "aliases"),
              None)
    if at is None:
        rows += ["aliases:"] + [f"  - {_scalar(n)}" for n in missing]
    elif (rows[at].split(":", 1)[1].strip()):  # flow list or a single value: rewrite as a block list
        rows[at:at + 1] = ["aliases:"] + [f"  - {_scalar(n)}" for n in current + missing]
    else:
        last = at
        while last + 1 < len(rows) and _ITEM.match(rows[last + 1]):
            last += 1
        rows[last + 1:last + 1] = [f"  - {_scalar(n)}" for n in missing]
    return "---\n" + "\n".join(rows) + text[end:]


def split(text: str) -> tuple[dict[str, object], str]:
    """Return (frontmatter, body). Text without a leading '---' block has empty frontmatter."""
    norm = text.replace("\r\n", "\n").removeprefix("﻿")
    if not norm.startswith("---\n"):
        return {}, text
    end = norm.find("\n---", 3)
    while end != -1 and norm[end + 4:end + 5] not in ("\n", ""):
        end = norm.find("\n---", end + 4)
    if end == -1:
        return {}, text
    block, body = norm[4:end], norm[end + 5:]
    meta: dict[str, object] = {}
    key = None
    for line in block.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = _ITEM.match(line)
        if item and key is not None and (meta[key] is None or isinstance(meta[key], list)):
            if meta[key] is None:
                meta[key] = []
            meta[key].append(_parse_scalar(item.group(1) or ""))
            continue
        kv = _KEY.match(line)
        if kv:
            key = kv.group(1).strip()
            raw = kv.group(2)
            meta[key] = None if raw is None or not raw.strip() else _parse_value(raw)
    return meta, body
