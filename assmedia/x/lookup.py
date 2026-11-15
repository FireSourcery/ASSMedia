"""Thread lookups: which tweets need one, which have run, and the -I lists the lookup pass works through.

A lookup is done only when its own URL has run: gallery-dl's -I comments it out in a `_crawl\\threads-*.txt`
list, it isn't in `threads-failed.txt`, and no list still has it uncommented (a renamed failure list waiting
for its retry). A thread JSON written by another bookmark's lookup doesn't count.
Ids in `threads-skip.txt` (lookups that failed for good) count as done.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .tweet import Tweet

FAILED_LIST = "threads-failed.txt"
SKIP_LIST = "threads-skip.txt"
_STATUS = re.compile(r"https://\S*/status/(\d+)")


@dataclass(frozen=True)
class LookupState:
    ran: frozenset[str]     # tweet ids whose lookup line was commented out by gallery-dl -I
    failed: frozenset[str]  # tweet ids listed in threads-failed.txt
    queued: frozenset[str]  # tweet ids still uncommented in a lookup list: not run yet
    skip: frozenset[str]    # tweet ids whose lookup failed for good


def needs_lookup(t: Tweet) -> bool:
    """A reply has tweets above it; a tweet with replies may have the author's continuation below it."""
    return t.reply_id is not None or t.reply_count > 0


def _ids(path: Path, commented_only: bool) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for row in path.read_text(encoding="utf-8").splitlines():
        row = row.strip()
        if commented_only and not row.startswith("#"):
            continue
        ids.update(_STATUS.findall(row))
    return ids


def lookup_state(crawl: Path) -> LookupState:
    ran: set[str] = set()
    queued: set[str] = set()
    if crawl.exists():
        for path in crawl.glob("threads-*.txt"):
            if path.name not in (FAILED_LIST, SKIP_LIST):
                commented = _ids(path, commented_only=True)
                ran |= commented
                queued |= _ids(path, commented_only=False) - commented
    return LookupState(ran=frozenset(ran), failed=frozenset(_ids(crawl / FAILED_LIST, commented_only=False)),
                       skip=frozenset(read_skip(crawl / SKIP_LIST)), queued=frozenset(queued))


def lookup_done(t: Tweet, state: LookupState) -> bool:
    if t.tweet_id in state.skip:
        return True
    return t.tweet_id in state.ran and t.tweet_id not in state.failed and t.tweet_id not in state.queued


def lookup_lines(t: Tweet) -> list[str]:
    """Per-URL options, then the URL: keep the tweets above, then the author's own; stop at anyone else.

    The author is matched by the bookmark's numeric id, so the filters still hold if X doesn't return the
    looked-up tweet (gallery-dl then leaves `user` unset)."""
    author = "author['id']"
    who = t.author_id if t.author_id.isdigit() else "user['id']"
    keep = f"{author} == {who} or tweet_id < {t.tweet_id} or abort()"
    lines = [f"-post-filter = {json.dumps(keep)}"]
    if t.author_id.isdigit():
        lines.append(f"-file-filter = {json.dumps(f'{author} == {who}')}")
    return lines + [t.url]


def add_lookups(list_file: Path, tweets: list[Tweet]) -> int:
    """Append lookups for tweets whose id isn't in the list yet (commented-out = already run)."""
    present = _ids(list_file, commented_only=False)
    new, seen = [], set()
    for t in tweets:
        if t.tweet_id not in present and t.tweet_id not in seen:
            seen.add(t.tweet_id)
            new.append(t)
    if not new:
        return 0
    list_file.parent.mkdir(parents=True, exist_ok=True)
    existing = list_file.read_text(encoding="utf-8") if list_file.exists() else ""
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    with list_file.open("a", encoding="utf-8", newline="\n") as fp:
        fp.write(prefix + "".join("\n".join(lookup_lines(t)) + "\n" for t in new))
    return len(new)


def read_skip(path: Path) -> set[str]:
    """Tweet ids whose lookup failed for good (deleted or protected); one per line, '#' comments."""
    if not path.exists():
        return set()
    ids = set()
    for row in path.read_text(encoding="utf-8").splitlines():
        row = row.split("#", 1)[0].strip()
        if row:
            ids.add(row)
    return ids
