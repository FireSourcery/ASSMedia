"""The mechanical pass before tagging: settle what has an exact answer, and suggest names for the rest.

It settles a field only when the tagging rules leave no choice (an account that isn't there, the user's
own account, a bookmark with no words to tag) or when earlier bookmarks already decided it for the same
account. Everything else stays for Claude, with the known names the bookmark's own text contains as
suggestions. Its history comes from the vault's source pages and tagging/creator-people.json, never from
an earlier batch's build files, which are safe to delete.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from assmedia.core import fsread
from assmedia.core.collection import collections_of
from assmedia.core.concepts import LINK_FIELDS, _as_list, _pages_in, _save_pages, link_target, wiki_dirs
from assmedia.core.tags import hub_names
from assmedia.core.yamlfm import split

ROLES = ("creator_person", "quoted_person", "source_person")
TAG_FIELDS = ("title", "description", "people", "subjects", "themes", "creator_person", "quoted_person",
              "source_person", "domain")
NO_WORDS_FIELDS = ("title", "description", "people", "subjects", "themes", "domain")  # Tagging.md, "Evidence"

# Fewest words a known name needs before it's suggested, per field. One-word subjects and themes are
# mostly ordinary words ("History", "Windows") that a bookmark uses without being about them.
MIN_WORDS = {"people": 1, "subjects": 2, "themes": 2}
MIN_CHARS = 3        # shorter names are never searched for
MIN_SQUASHED = 5     # a #hashtag or @mention matches a name with spaces removed only from this length

_URL = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://\S+")
_MENTION = re.compile(r"(?<![\w@])@(\w{2,})")
_WORD = re.compile(r"[^\W\d_]")  # any letter, any script: even ":D" gets a title ("Big smile")


def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).lower()


def squash(s: str) -> str:
    """"Claude Code", "#ClaudeCode" and "claude_code" all become "claudecode"."""
    return re.sub(r"[\W_]+", "", norm(s))


def word_count(name: str) -> int:
    return len([w for w in re.split(r"[\s\-_]+", name.strip()) if w])


def allowed_text(row: dict) -> str:
    """Every text the tagging rules allow as evidence (Tagging.md, "Evidence"); never bios or locations."""
    parts = [row.get("text"), " ".join(row.get("hashtags") or []), row.get("article_title"), row.get("article_text")]
    parts += [t.get("text") for t in row.get("above") or []]
    parts += list(row.get("below") or [])
    quoted = row.get("quoted") or {}
    parts += [quoted.get("text"), quoted.get("article_title"), quoted.get("article_text")]
    return "\n".join(p for p in parts if p)


def account_names(row: dict) -> str:
    """The display names the rules also allow."""
    names = [row.get("author_name")] + [t.get("author_name") for t in row.get("above") or []]
    names.append((row.get("quoted") or {}).get("author_name"))
    return "\n".join(n for n in names if n)


def has_words(row: dict) -> bool:
    """Whether any allowed text has words once links and @mentions are taken out."""
    return bool(_WORD.search(_MENTION.sub(" ", _URL.sub(" ", allowed_text(row)))))


@dataclass
class History:
    """What earlier batches settled, read from the vault and tagging/."""
    creators: dict[str, str] = field(default_factory=dict)      # username -> person
    unmapped: Counter = field(default_factory=Counter)          # lowercase username -> its pages with no person
    names: dict[str, tuple[str, str, bool]] = field(default_factory=dict)  # lowercase name or alias ->
    #                                                             (page spelling, field, linked from a bookmark)
    hubs: set[str] = field(default_factory=set)                 # lowercase domain hubs: never a tag
    own: frozenset[str] = frozenset()                           # the user's own usernames, lowercase

    def creator(self, user: str) -> str | None:
        return self.creators.get(user) or next((p for u, p in self.creators.items() if u.lower() == user.lower()),
                                               None)


def load_history(xp) -> History:
    """Build the History from the vault's source pages, wiki pages and tagging/creator-people.json."""
    core = xp.core
    path = core.tagging / "creator-people.json"
    creators = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    mapped = {u.lower() for u in creators}
    fields_of: dict[str, Counter] = defaultdict(Counter)
    spelling: dict[str, str] = {}
    unmapped: Counter = Counter()
    for c in collections_of(core):
        for _, meta in _save_pages(c.pages):
            for name in LINK_FIELDS:
                for value in _as_list(meta.get(name)):
                    target = link_target(str(value))
                    if target:
                        spelling.setdefault(norm(target), target)
                        fields_of[norm(target)][name] += 1
            if c.name == "X":
                user = str(meta.get("source_author") or "")
                if user and user.lower() not in mapped:
                    unmapped[user.lower()] += 1
    names: dict[str, tuple[str, str, bool]] = {}
    for key, counts in fields_of.items():
        names[key] = (spelling[key], counts.most_common(1)[0][0], True)
    wiki = list(_pages_in(wiki_dirs(core) + [core.people]).values())
    for md, text in zip(wiki, fsread.read_all(wiki)):
        meta = split(text)[0]
        key = norm(md.stem)
        linked = names.get(key)
        kind = "people" if str(meta.get("type") or "") == "person" else "subjects"
        entry = (md.stem, linked[1] if linked else kind, bool(linked))
        names.setdefault(key, entry)
        for alias in _as_list(meta.get("aliases")):
            names.setdefault(norm(str(alias)), entry)
    return History(creators=creators, unmapped=unmapped, names=names,
                   hubs={h.lower() for h in hub_names(core.domains).values()}, own=frozenset(xp.own_accounts))


def role_accounts(row: dict) -> dict[str, str | None]:
    return {"creator_person": row.get("author"), "quoted_person": (row.get("quoted") or {}).get("author"),
            "source_person": row.get("source_user")}


def settle_role(user: str | None, history: History) -> tuple[str | None, str] | None:
    """(value, reason) when the role has an exact answer, else None."""
    if not user:
        return None, "no such account"
    if user.lower() in history.own:
        return None, "your own account"
    if person := history.creator(user):
        return person, "already mapped in creator-people.json"
    if n := history.unmapped[user.lower()]:
        return None, (f"@{user}'s {n} earlier bookmark{'s' if n > 1 else ''} never got a person; "
                      "set one only if this bookmark shows it's an individual")
    return None


@dataclass
class _Needle:
    key: str
    rx: re.Pattern   # case-insensitive
    name: str
    field: str
    proper: bool     # a one-word name counts only where the text capitalizes it: "Cloud", not "the cloud"


def needles(history: History, min_words: dict[str, int] = MIN_WORDS) -> tuple[list[_Needle], dict[str, tuple]]:
    """Names to search for, longest first, and the #hashtag / @mention index (spaces removed)."""
    found, squashed = [], {}
    for key, (name, fld, linked) in history.names.items():
        if key in history.hubs or len(key) < MIN_CHARS or squash(key) in history.own:
            continue
        need = min_words.get(fld, 2) if linked else 2  # a name no bookmark links yet must be specific
        if word_count(key) >= need:
            rx = re.compile(r"(?<![\w-])" + re.escape(key) + r"(?![\w-]|\.\w)", re.IGNORECASE)
            found.append(_Needle(key, rx, name, fld, word_count(key) == 1))
        if len(squash(key)) >= MIN_SQUASHED:
            squashed.setdefault(squash(key), (name, fld))
    found.sort(key=lambda n: -len(n.key))
    return found, squashed


def suggest(row: dict, found: list[_Needle], squashed: dict[str, tuple]) -> dict[str, list[str]]:
    """Known names the bookmark's allowed text or display names contain, in order of appearance."""
    text = unicodedata.normalize("NFC", allowed_text(row) + "\n" + account_names(row))
    lowered = text.lower()
    taken: list[tuple[int, int]] = []
    hits: dict[str, tuple[int, str]] = {}
    for n in found:
        if n.key not in lowered:
            continue
        spans = [m.span() for m in n.rx.finditer(text)
                 if (not n.proper or m.group(0)[:1].isupper())
                 and not any(a <= m.start() and m.end() <= b for a, b in taken)]
        if spans:
            taken += spans
            hits.setdefault(n.name, (spans[0][0], n.field))
    tokens = list(row.get("hashtags") or []) + _MENTION.findall(allowed_text(row))
    for i, token in enumerate(tokens):
        if (match := squashed.get(squash(token))) and match[0] not in hits:
            hits[match[0]] = (len(text) + i, match[1])  # after the names found in the text
    out: dict[str, list[str]] = {f: [] for f in LINK_FIELDS}
    for name, (_, fld) in sorted(hits.items(), key=lambda kv: kv[1][0]):
        out[fld].append(name)
    return out


def empty_entry() -> dict:
    """One tags entry with exactly the fields Tagging.md requires, all empty."""
    return {"title": "", "description": "", "people": [], "subjects": [], "themes": [], "creator_person": None,
            "quoted_person": None, "source_person": None, "domain": []}


def prefill(rows: list[dict], history: History, min_words: dict[str, int] = MIN_WORDS
            ) -> tuple[dict[str, dict], Counter]:
    """Add a "prefill" block to each export row; return the starter tags and a summary.

    prefill = {"settled": {field: reason}, "to_tag": [fields], "suggestions": {people, subjects, themes}}.
    The starter tags hold every field of every bookmark, settled ones filled in and the rest empty.
    """
    found, squashed = needles(history, min_words)
    starter: dict[str, dict] = {}
    summary: Counter = Counter()
    for row in rows:
        entry = empty_entry()
        settled: dict[str, str] = {}
        for role, user in role_accounts(row).items():
            if (answer := settle_role(user, history)) is not None:
                entry[role], settled[role] = answer
        words = has_words(row)
        if not words:  # the entry's text fields are already empty; mark them settled
            settled.update({k: "no words to tag: text, thread, quote and article are empty or only links"
                            for k in NO_WORDS_FIELDS})
            summary["no_words"] += 1
        to_tag = [f for f in TAG_FIELDS if f not in settled]
        row["prefill"] = {"settled": settled, "to_tag": to_tag,
                          "suggestions": suggest(row, found, squashed) if words else {f: [] for f in LINK_FIELDS}}
        starter[row["tweet_id"]] = entry
        summary["roles_settled"] += sum(1 for r in ROLES if r in settled)
        summary["all_roles_settled"] += all(r in settled for r in ROLES)
        summary["nothing_to_tag"] += not to_tag
        summary["suggested_names"] += sum(len(v) for v in row["prefill"]["suggestions"].values())
    summary["bookmarks"] = len(rows)
    return starter, summary


def export_summary(rows: list[dict]) -> dict[str, int]:
    """Counts for the export report, read back from the rows' prefill blocks."""
    blocks = [r.get("prefill") or {} for r in rows]
    return {
        "nothing to tag": sum(1 for b in blocks if not b.get("to_tag")),
        "no words": sum(1 for b in blocks if "title" in (b.get("settled") or {})),
        "creators settled": sum(1 for b in blocks if all(r in (b.get("settled") or {}) for r in ROLES)),
        "names suggested": sum(len(v) for b in blocks for v in (b.get("suggestions") or {}).values()),
    }


def write_starter(path: Path, starter: dict[str, dict]) -> bool:
    """Write the starter tags file unless one exists already: never overwrite tagging work."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(starter, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return True
