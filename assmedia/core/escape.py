"""Escape caption text so Obsidian shows it exactly as written (no tags, math, links, lists or HTML)."""
import re

SPECIAL = "`#*_>[]|$~=%<&"
_LIST_DASH = re.compile(r"^(\s*)([-+])", re.MULTILINE)
_LIST_NUMBER = re.compile(r"^(\s*)(\d+)\.(\s|$)", re.MULTILINE)


def escape_caption(text: str) -> str:
    out = text.replace("\\", "\\\\")
    out = "".join("\\" + ch if ch in SPECIAL else ch for ch in out)
    out = _LIST_DASH.sub(lambda m: f"{m.group(1)}\\{m.group(2)}", out)
    out = _LIST_NUMBER.sub(lambda m: f"{m.group(1)}{m.group(2)}\\.{m.group(3)}", out)
    return out


def quote_block(text: str) -> str:
    return "\n".join(f"> {line}" if line.strip() else ">" for line in text.split("\n"))
