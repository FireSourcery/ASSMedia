"""Names a concepts plan proposed that got no page by choice, kept in tagging\\declined-names.json.

`concepts-apply` records every name in its batch's plan `new` list that the concepts file left out; `concepts-plan`
then moves those names out of `new` into `declined`, unless their link count has grown since. The record replaces
keeping old batch files around just to remember what was turned down.
"""
import json
from collections.abc import Callable
from pathlib import Path

DECLINED_FILE = "declined-names.json"


def load_declined(path: Path) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_declined(path: Path, declined: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(declined, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8",
                    newline="\n")


def _key(name: str, declined: dict[str, dict]) -> str | None:
    """The declined record's own spelling of `name`, matched case-insensitively."""
    low = name.lower()
    return next((k for k in declined if k.lower() == low), None)


def record_declined(declined: dict, plan: dict, applied: set[str], batch: str) -> list[str]:
    """Record the plan's `new` names that weren't applied; returns them in plan order."""
    taken = {a.lower() for a in applied}
    added = []
    for entry in plan.get("new", []):
        name = entry["name"]
        if name.lower() in taken:
            continue
        old = _key(name, declined)
        if old is not None:
            del declined[old]
        declined[name] = {"count": entry["count"], "batch": batch}
        added.append(name)
    return added


def filter_plan(plan: dict, declined: dict) -> dict:
    """Move declined names out of `new` into `declined`, unless their count has grown since."""
    new, moved = [], []
    for entry in plan.get("new", []):
        key = _key(entry["name"], declined)
        (moved if key is not None and entry["count"] <= declined[key]["count"] else new).append(entry)
    return {**plan, "new": new, "declined": moved}


def seed_declined(concepts_dir: Path, has_page: Callable[[str], bool]) -> dict[str, dict]:
    """Rebuild the record from old batches: each plan with a concepts file beside it, oldest plan first."""
    declined: dict[str, dict] = {}
    plans = sorted(concepts_dir.glob("*.plan.json"), key=lambda p: p.stat().st_mtime)
    for plan_path in plans:
        batch = plan_path.name.removesuffix(".plan.json")
        applied_path = plan_path.with_name(f"{batch}.json")
        if not applied_path.exists():
            continue  # planned but never applied: its names weren't turned down
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        applied = set(json.loads(applied_path.read_text(encoding="utf-8")))
        record_declined(declined, plan, applied, batch)
    return {name: rec for name, rec in declined.items() if not has_page(name)}
