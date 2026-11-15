"""The gallery-dl configs, filled in before each run.

Each platform's committed config holds only behaviour: per-subcategory blocks, filters, file names and
post-processors. Its paths and the browser come from assmedia.toml: the tool fills them in by key path and writes
the result to <state>/<Platform>/_crawl/gallery-dl.conf, which gallery-dl then runs with. gallery-dl's own {...}
format fields are values like any other, so they come through untouched.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

KeyPath = tuple[str | int, ...]


def fill(template: dict, values: dict[KeyPath, object]) -> dict:
    """A deep copy of `template` with each key path set. A missing dict on the way is made; a list index must exist."""
    out = copy.deepcopy(template)
    for path, value in values.items():
        node = out
        for key in path[:-1]:
            if isinstance(key, int):
                node = node[key]
            else:
                node = node.setdefault(key, {})
        node[path[-1]] = value
    return out


def write_conf(template_path: Path, values: dict[KeyPath, object], out: Path) -> Path:
    """Fill in the template at `template_path` and write it to `out`; returns `out`."""
    conf = fill(json.loads(template_path.read_text(encoding="utf-8")), values)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(conf, indent=4, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return out
