"""X bookmark commands: pending, export, build, vocab, concepts-plan, concepts-apply."""
import argparse
import json
import sys
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from assmedia.core.paths import (Paths, build_index, clean_names, collections, page_index, taken_names, write_new)
from assmedia.core.concepts import cmd_concepts_apply, cmd_concepts_plan, cmd_vocab
from assmedia.core.tags import canonical_domains, canonicalize, hub_names, validate_name
from assmedia.core.thumbs import ThumbError, make_thumb_file

from assmedia.core.config import Config, dirs
from .declined import DECLINED_FILE, filter_plan, load_declined, record_declined, save_declined, seed_declined
from .lookup import add_lookups, lookup_done, lookup_state, needs_lookup
from .page import choose_x_title, classify, contact_in, render_x_page, text_title, x_thumb_ref
from .prefill import export_summary, load_history, prefill, write_starter
from .tags import ROLE_FIELDS, XTags, load_x_tags
from .thread import Thread, assemble, page_media
from .scan import Scan, scan
from .tweet import Tweet

PENDING_LIST = "threads-pending.txt"


@dataclass
class XPaths:
    core: Paths    # the core paths, pointed at the X folders; carries every platform's collection
    threads: Path  # thread-lookup JSON
    crawl: Path    # download record, logs, lookup lists
    build: Path    # files used within one batch: export/, tags/, concepts/ (plans and concepts files)
    tagging: Path  # kept across batches: creator-people.json, declined-names.json
    gallery_conf: Path            # the one gallery-dl config (bookmark and tweet blocks)
    own_accounts: frozenset[str]  # the user's own X usernames, lowercase: never a creator person


def default_xpaths(cfg: Config) -> XPaths:
    """Every X path from the instance config: items, threads and thumbnails under raw, the rest under state."""
    d, vault = dirs(cfg, "x"), cfg.vault
    core = Paths(
        vault=vault,
        wiki=vault / "wiki",
        items=d.items,
        pages=vault / "wiki" / "sources" / "X",
        entities=vault / "wiki" / "entities",
        concepts=vault / "wiki" / "concepts",
        people=vault / "People",
        domains=vault / "Domains",
        index_md=vault / "wiki" / "index.md",
        thumbs_dir=d.thumbs,
        tagging=d.tagging,
        build=d.build,
        ffmpeg=cfg.ffmpeg,
        thumb_mode="external",
        items_url=d.items.as_uri(),
        thumbs_url=d.thumbs.as_uri(),
        collections=collections(cfg),
    )
    return XPaths(core=core, threads=d.threads, crawl=d.crawl, build=d.build, tagging=d.tagging,
                  gallery_conf=d.crawl / "gallery-dl.conf",
                  own_accounts=cfg.x.own_accounts if cfg.x else frozenset())


def lookup_targets(t: Tweet, known: dict[str, Tweet]) -> list[Tweet]:
    """Tweets that need their own lookup before bookmark t is built: t itself when it has a thread or is an
    X Article whose text isn't on disk yet (the Bookmarks feed carries only the title), and such a quoted
    article."""
    article_missing = bool(t.article_title) and not t.article_text
    targets = [t] if needs_lookup(t) or article_missing else []
    quoted = known.get(t.quoted_id) if t.quoted_id else None
    if quoted is not None and quoted.article_title and not quoted.article_text:
        targets.append(quoted)
    return targets


@dataclass
class PendingState:
    ready: list[Tweet]      # no page yet, every lookup done
    waiting: list[Tweet]    # no page yet, a lookup still to run
    lookups: list[Tweet]    # the lookups still to run
    incomplete: list[str]   # folder ids of incomplete downloads
    scan: Scan              # what it was worked out from; export and build reuse it


def pending_state(xp: XPaths) -> PendingState:
    """Bookmarks without a page, newest bookmarked first, split by whether their lookups have run."""
    s = scan(xp.core.items, xp.threads)
    bookmarks, incomplete, known = s.bookmarks, s.incomplete, s.known
    done = page_index(xp.core.pages, "tweet_id")
    state = lookup_state(xp.crawl)
    out = PendingState(ready=[], waiting=[], lookups=[], incomplete=incomplete, scan=s)
    for t in bookmarks:
        if t.tweet_id in done:
            continue
        todo = [x for x in lookup_targets(t, known) if not lookup_done(x, state)]
        (out.waiting if todo else out.ready).append(t)
        out.lookups += todo
    return out


def cmd_pending(xp: XPaths, state: PendingState | None = None) -> dict[str, int]:
    """Queue the missing lookups and count; `state` is reused when the caller already worked it out."""
    state = state or pending_state(xp)
    added = add_lookups(xp.crawl / PENDING_LIST, state.lookups)
    return {"new": len(state.ready) + len(state.waiting), "ready": len(state.ready),
            "waiting_lookup": len(state.waiting), "added_to_list": added, "incomplete": len(state.incomplete)}


def _tweet_row(t: Tweet) -> dict:
    return {"author": t.author, "author_name": t.author_name, "text": t.text,
            "article_title": t.article_title, "article_text": t.article_text}


def export_row(thread: Thread) -> dict:
    """What the tagger reads for one bookmark. Never the authors' bios or locations."""
    b = thread.bookmark
    return {
        "tweet_id": b.tweet_id, "author": b.author, "author_name": b.author_name, "text": b.text,
        "hashtags": b.hashtags, "media": classify(page_media(thread)),
        "article_title": b.article_title, "article_text": b.article_text, "source_user": b.source_user,
        "above": [{"author": t.author, "author_name": t.author_name, "text": t.text} for t in thread.above],
        "below": [t.text for t in thread.below],
        "quoted": _tweet_row(thread.quoted) if thread.quoted else None,
    }


def cmd_export(xp: XPaths, name: str, limit: int) -> Path:
    """Export the ready bookmarks after the mechanical pass (prefill.py): each row gets its `prefill` block,
    and build/tags/<name>.json gets the starter tags unless that file exists already."""
    state = pending_state(xp)
    ready, known = state.ready[:limit], state.scan.known
    rows = [export_row(assemble(t, known)) for t in ready]
    starter, _ = prefill(rows, load_history(xp))
    out = xp.build / "export" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    write_starter(tags_path(xp, name), starter)
    return out


def tags_path(xp: XPaths, name: str) -> Path:
    return xp.build / "tags" / f"{name}.json"


def _load_creators(xp: XPaths) -> dict[str, str]:
    path = xp.core.tagging / "creator-people.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save_creators(xp: XPaths, mapping: dict[str, str]) -> None:
    path = xp.core.tagging / "creator-people.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=1, sort_keys=True),
                    encoding="utf-8", newline="\n")


def role_accounts(thread: Thread) -> dict[str, str | None]:
    """The X username behind each creator role of a bookmark."""
    b = thread.bookmark
    return {"creator_person": b.author, "quoted_person": thread.quoted.author if thread.quoted else None,
            "source_person": b.source_user}


def _resolve_roles(code: str, thread: Thread, tags: XTags, creators: dict[str, str],
                   messages: list[str], own: frozenset[str]) -> XTags:
    """Drop roles with no account or the user's own; an earlier username -> name mapping wins."""
    changes = {}
    for role, user in role_accounts(thread).items():
        person = getattr(tags, role)
        if not person:
            continue
        if user is None:
            messages.append(f"{code}: {role} {person!r} dropped: the bookmark has no such account")
            changes[role] = None
        elif user.lower() in own:
            messages.append(f"{code}: {role} {person!r} dropped: @{user} is your own account")
            changes[role] = None
        elif (mapped := creators.get(user)) and mapped.lower() != person.strip().lower():
            messages.append(f"{code}: @{user} is already mapped to {mapped!r}; used that instead of {person!r}")
            changes[role] = mapped
    return replace(tags, **changes) if changes else tags


def _clean(tags: XTags, index: dict[str, str], hubs: dict[str, str]) -> XTags:
    for name, value in (("title", tags.title), ("description", tags.description)):
        if contact_in(value):
            raise ValueError(f"{name} contains contact details")
    roles = {}
    for role in ROLE_FIELDS:
        value = getattr(tags, role)
        if value:
            validate_name(value)
            roles[role] = canonicalize(value, index)
    return replace(tags, people=clean_names(tags.people, index), subjects=clean_names(tags.subjects, index),
                   themes=clean_names(tags.themes, index), domain=canonical_domains(tags.domain, hubs), **roles)


def _record_roles(thread: Thread, tags: XTags, creators: dict[str, str], own: frozenset[str]) -> None:
    for role, user in role_accounts(thread).items():
        person = getattr(tags, role)
        if person and user and user.lower() not in own:
            creators.setdefault(user, person.strip())


def cmd_build(xp: XPaths, tags_file: Path, today: date) -> tuple[dict[str, int], list[str]]:
    all_tags = load_x_tags(tags_file)
    state = pending_state(xp)
    ready = {t.tweet_id: t for t in state.ready}
    bookmarks = {t.tweet_id: t for t in state.scan.bookmarks}
    known = state.scan.known
    done = page_index(xp.core.pages, "tweet_id")
    pages = xp.core.pages
    taken = taken_names(xp.core)
    index = build_index(xp.core)
    hubs = hub_names(xp.core.domains)
    creators = _load_creators(xp)
    counts = {"created": 0, "skipped": 0, "not_ready": 0, "thumb_failed": 0}
    messages: list[str] = []
    try:
        for code, raw_tags in all_tags.items():
            tweet = bookmarks.get(code)
            if tweet is None:
                counts["not_ready"] += 1
                messages.append(f"{code}: no complete bookmark download in {xp.core.items}")
                continue
            thread = assemble(tweet, known)
            raw_tags = _resolve_roles(code, thread, raw_tags, creators, messages, xp.own_accounts)
            if code in done:
                _record_roles(thread, raw_tags, creators, xp.own_accounts)
                counts["skipped"] += 1
                continue
            if code not in ready:
                counts["not_ready"] += 1
                messages.append(f"{code}: thread lookup not done yet (see {PENDING_LIST})")
                continue
            try:
                tags = _clean(raw_tags, index, hubs)
            except ValueError as exc:
                messages.append(f"{code}: {exc}")
                continue
            thumb = None
            files = page_media(thread)
            if files:
                try:
                    make_thumb_file(files[0], xp.core.thumbs_dir / f"{code}.jpg", xp.core.ffmpeg, code)
                    thumb = x_thumb_ref(code, xp.core.thumbs_url)
                except ThumbError as exc:
                    counts["thumb_failed"] += 1
                    messages.append(str(exc))
            title = choose_x_title(thread, tags, taken)
            taken.add(title.lower())
            if not tags.title.strip() and text_title(thread):
                messages.append(f"{code}: no title in the tags; page named {title!r} from its text. "
                                "Give it an English title next time (Tagging.md).")
            write_new(pages / f"{title}.md", render_x_page(thread, tags, title=title, thumb=thumb, created=today,
                                                                items_url=xp.core.items_url))
            for name in tags.people + tags.subjects + tags.themes + [getattr(tags, r) or "" for r in ROLE_FIELDS]:
                if name:
                    index.setdefault(name.lower(), name)
            _record_roles(thread, tags, creators, xp.own_accounts)
            counts["created"] += 1
    finally:
        if creators:
            _save_creators(xp, creators)
    return counts, messages


def cmd_seed_declined(xp: XPaths) -> int:
    """One-time: fill tagging/declined-names.json from the old batches in build/concepts/."""
    path = xp.tagging / DECLINED_FILE
    if path.exists():
        print(f"{DECLINED_FILE} already exists")
        return 1
    pages = cmd_vocab(xp.core)["pages"]
    names = {n.lower() for n in pages} | {a.lower() for v in pages.values() for a in v.get("aliases", [])}
    seeded = seed_declined(xp.build / "concepts", has_page=lambda n: n.lower() in names)
    save_declined(path, seeded)
    print(f"seeded {len(seeded)} declined names: " + ", ".join(sorted(seeded, key=str.lower)))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assmedia.py x")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("pending")
    export = sub.add_parser("export")
    export.add_argument("name")
    export.add_argument("--limit", type=int, default=150)
    build = sub.add_parser("build")
    build.add_argument("tags_file", type=Path)
    sub.add_parser("vocab")
    plan = sub.add_parser("concepts-plan")
    plan.add_argument("name")
    apply = sub.add_parser("concepts-apply")
    apply.add_argument("file", type=Path)
    sub.add_parser("seed-declined")
    update = sub.add_parser("update", help="run by the user: it uses your browser login")
    which = update.add_mutually_exclusive_group()
    which.add_argument("--full", action="store_true", help="no --abort 5: the first run on a new instance")
    which.add_argument("--lookups", type=Path, help="run only this lookup list (a retry)")
    return parser


def main(argv: list[str], config: Config | None = None, xp: XPaths | None = None) -> int:
    """`xp` replaces the paths built from `config`, for tests."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    xp = xp or default_xpaths(config)
    if args.command == "pending":
        state = pending_state(xp)
        counts = cmd_pending(xp, state)
        incomplete = state.incomplete
        print(", ".join(f"{k} {v}" for k, v in counts.items()))
        if incomplete:
            print("incomplete: " + ", ".join(incomplete))
    elif args.command == "export":
        had_tags = tags_path(xp, args.name).exists()
        out = cmd_export(xp, args.name, args.limit)
        rows = json.loads(out.read_text(encoding="utf-8"))
        print(f"exported {len(rows)} bookmarks to {out}")
        print("mechanical pass: " + ", ".join(f"{k} {v}" for k, v in export_summary(rows).items()))
        print(f"kept the existing {tags_path(xp, args.name)}; no starter written" if had_tags
              else f"starter tags: {tags_path(xp, args.name)}")
    elif args.command == "build":
        counts, messages = cmd_build(xp, args.tags_file, date.today())
        for message in messages:
            print("  " + message)
        print(", ".join(f"{k} {v}" for k, v in counts.items()))
        return 0 if counts["created"] + counts["skipped"] == len(load_x_tags(args.tags_file)) else 1
    elif args.command == "vocab":
        print(json.dumps(cmd_vocab(xp.core), ensure_ascii=False, indent=1))
    elif args.command == "concepts-plan":
        out = cmd_concepts_plan(xp.core, args.name)
        plan = filter_plan(json.loads(out.read_text(encoding="utf-8")), load_declined(xp.tagging / DECLINED_FILE))
        out.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        print(f"{len(plan['new'])} new pages, {len(plan['declined'])} declined, "
              f"{len(plan['needs_embed'])} need a list appended: {out}")
    elif args.command == "concepts-apply":
        counts = cmd_concepts_apply(xp.core, args.file, date.today())
        plan_path = args.file.with_name(f"{args.file.stem}.plan.json")
        if plan_path.exists():
            declined_path = xp.tagging / DECLINED_FILE
            declined = load_declined(declined_path)
            entries = json.loads(args.file.read_text(encoding="utf-8"))
            added = record_declined(declined, json.loads(plan_path.read_text(encoding="utf-8")), set(entries),
                                    args.file.stem)
            save_declined(declined_path, declined)
            counts["declined"] = len(added)
        print(", ".join(f"{k} {v}" for k, v in counts.items()))
    elif args.command == "seed-declined":
        return cmd_seed_declined(xp)
    elif args.command == "update":
        from assmedia.core.gallerydl import write_conf
        from . import update  # update imports this module
        if config is not None:  # tests pass their own xp and no config
            write_conf(update.TEMPLATE, update.conf_values(config), xp.gallery_conf)
        return update.cmd_update(xp, full=args.full, lookups=args.lookups)
    return 0
