"""Commands: pending, export, build, vocab, concepts-plan, concepts-apply."""
import argparse
import json
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

from assmedia.core.config import Config, dirs
from assmedia.core.concepts import cmd_concepts_apply, cmd_concepts_plan, cmd_vocab
from assmedia.core.paths import Paths, build_index, clean_names, collections, page_index, taken_names, write_new

from .page import caption_block, choose_title, legacy_body_lines, media_block, render_page, thumb_ref
from .post import Post, scan_items
from .thumbs import make_thumb
from assmedia.core.tags import Tags, canonical_domains, canonicalize, hub_names, load_tags, validate_name
from assmedia.core.thumbs import ThumbError


def paths(cfg: Config, thumb_mode: str = "external") -> Paths:
    """Every Instagram path from the instance config: items and thumbnails under raw, the rest under state."""
    d, vault, ig = dirs(cfg, "instagram"), cfg.vault, cfg.instagram
    return Paths(
        vault=vault,
        wiki=vault / "wiki",
        items=d.items,
        pages=vault / "wiki" / "sources" / "Instagram",
        entities=vault / "wiki" / "entities",
        concepts=vault / "wiki" / "concepts",
        people=vault / "People",
        domains=vault / "Domains",
        index_md=vault / "wiki" / "index.md",
        thumbs_dir=d.thumbs if thumb_mode == "external" else vault / "raw" / "Instagram" / "_thumbs",
        tagging=d.tagging,
        build=d.build,
        ffmpeg=cfg.ffmpeg,
        thumb_mode=thumb_mode,
        items_url=d.items.as_uri(),
        thumbs_url=d.thumbs.as_uri(),
        collections=collections(cfg),
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def pending(p: Paths) -> tuple[list[Post], list[str]]:
    posts, incomplete = scan_items(p.items)
    done = page_index(p.pages)
    todo = [x for x in posts if x.shortcode not in done]
    todo.sort(key=lambda x: x.folder.stat().st_ctime)  # oldest download first
    return todo, incomplete


def cmd_export(p: Paths, name: str, limit: int) -> Path:
    todo, _ = pending(p)
    rows = [{"shortcode": x.shortcode, "username": x.username, "fullname": x.fullname,
             "caption": x.caption, "hashtags": x.hashtags, "media": x.media} for x in todo[:limit]]
    out = p.build / "export" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return out


def _clean(tags: Tags, index: dict[str, str], hubs: dict[str, str]) -> Tags:
    creator = None
    if tags.creator_person:
        validate_name(tags.creator_person)
        creator = canonicalize(tags.creator_person, index)
    return replace(tags, people=clean_names(tags.people, index),
                   subjects=clean_names(tags.subjects, index),
                   themes=clean_names(tags.themes, index), creator_person=creator,
                   domain=canonical_domains(tags.domain, hubs))


def _load_creators(p: Paths) -> dict[str, str]:
    path = p.tagging / "creator-people.json"
    return json.loads(_read(path)) if path.exists() else {}


def _save_creators(p: Paths, mapping: dict[str, str]) -> None:
    path = p.tagging / "creator-people.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=1, sort_keys=True),
                    encoding="utf-8", newline="\n")


def cmd_build(p: Paths, tags_file: Path, today: date) -> tuple[dict[str, int], list[str]]:
    all_tags = load_tags(tags_file)
    by_code = {x.shortcode: x for x in scan_items(p.items)[0]}
    done = page_index(p.pages)
    taken = taken_names(p)
    index = build_index(p)
    hubs = hub_names(p.domains)
    creators = _load_creators(p)
    counts = {"created": 0, "skipped": 0, "thumb_failed": 0}
    messages = []
    try:
        _build_posts(p, all_tags, by_code, done, taken, index, hubs, creators, counts,
                     messages, today)
    finally:
        if creators:
            _save_creators(p, creators)
    return counts, messages


def _resolve_creator(code: str, post: Post, tags: Tags, creators: dict[str, str],
                     messages: list[str]) -> Tags:
    """Keep one name per creator username: an earlier mapping wins over a different new name."""
    if not tags.creator_person:
        return tags
    mapped = creators.get(post.username)
    if mapped and mapped.lower() != tags.creator_person.strip().lower():
        messages.append(f"{code}: creator {post.username} is already mapped to {mapped!r}; "
                        f"used that instead of {tags.creator_person!r}")
        return replace(tags, creator_person=mapped)
    return tags


def _build_posts(p, all_tags, by_code, done, taken, index, hubs, creators, counts,
                 messages, today) -> None:
    for code, raw_tags in all_tags.items():
        post = by_code.get(code)
        if post is None:
            messages.append(f"{code}: no complete download in {p.items}")
            continue
        raw_tags = _resolve_creator(code, post, raw_tags, creators, messages)
        if code in done:
            if raw_tags.creator_person and post.username not in creators:
                creators[post.username] = raw_tags.creator_person.strip()
            counts["skipped"] += 1
            continue
        try:
            tags = _clean(raw_tags, index, hubs)
        except ValueError as exc:
            messages.append(f"{code}: {exc}")
            continue

        thumb = None
        try:
            make_thumb(post, p.thumbs_dir / f"{code}.jpg", p.ffmpeg)
            thumb = thumb_ref(code, p.thumb_mode, p.thumbs_url)
        except ThumbError as exc:
            counts["thumb_failed"] += 1
            messages.append(str(exc))

        title = choose_title(post, tags, taken)
        taken.add(title.lower())
        saved = date.fromtimestamp(post.folder.stat().st_ctime)
        write_new(p.pages / f"{title}.md",
                   render_page(post, tags, title=title, saved=saved,
                               thumb=thumb, created=today, items_url=p.items_url))
        for name in tags.people + tags.subjects + tags.themes + [tags.creator_person or ""]:
            if name:
                index.setdefault(name.lower(), name)
        if tags.creator_person:
            creators.setdefault(post.username, tags.creator_person)
        counts["created"] += 1


def cmd_update_media(p: Paths, dry_run: bool = False) -> dict[str, int]:
    """Bring save pages to the current body layout: title, then inline players/photos, then the caption.

    Replaces only the lines between the title and the caption line, and only when every one of them is
    a line an earlier version of this tool wrote (thumbnail embed, players, open/view links) or blank.
    Frontmatter, title and caption are never touched; a page with any other text there is skipped.
    """
    posts = {x.shortcode: x for x in scan_items(p.items)[0]}
    counts = {"updated": 0, "already": 0, "skipped_edited": 0, "missing_post": 0}
    for code, page in page_index(p.pages).items():
        post = posts.get(code)
        if post is None:
            counts["missing_post"] += 1
            continue
        rows = _read(page).split("\n")
        fences = [i for i, row in enumerate(rows) if row == "---"]
        caption = caption_block(post).split("\n")
        title_at = next((i for i in range(fences[1] + 1, len(rows)) if rows[i].startswith("# ")), None) \
            if len(fences) >= 2 else None
        caption_at = next((i for i in range(len(rows) - len(caption), -1, -1)
                           if rows[i:i + len(caption)] == caption), None)
        if title_at is None or caption_at is None or caption_at < title_at:
            counts["skipped_edited"] += 1
            continue
        block = rows[title_at + 1:caption_at]
        new_block = [""]
        for line in media_block(post, p.items_url):
            new_block += [line, ""]
        if block == new_block:
            counts["already"] += 1
            continue
        allowed = legacy_body_lines(post, p.items_url, p.thumbs_url) | set(media_block(post, p.items_url)) | {""}
        if any(row not in allowed for row in block):
            counts["skipped_edited"] += 1
            continue
        rows[title_at + 1:caption_at] = new_block
        if not dry_run:
            page.write_text("\n".join(rows), encoding="utf-8", newline="\n")
        counts["updated"] += 1
    return counts


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assmedia.py instagram")
    parser.add_argument("--thumb-mode", choices=["external", "vault"], default="external")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("pending")
    export = sub.add_parser("export")
    export.add_argument("name")
    export.add_argument("--limit", type=int, default=150)
    build = sub.add_parser("build")
    build.add_argument("tags_file", type=Path)
    sub.add_parser("vocab")
    update = sub.add_parser("update-media")
    update.add_argument("--dry-run", action="store_true")
    plan = sub.add_parser("concepts-plan")
    plan.add_argument("name")
    apply = sub.add_parser("concepts-apply")
    apply.add_argument("file", type=Path)
    update = sub.add_parser("update", help="download new saves (you run this: it uses your login)")
    update.add_argument("--full", action="store_true", help="no stop after 5 files already downloaded")
    return parser


def main(argv: list[str], config: Config) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    p = paths(config, args.thumb_mode)
    if args.command == "pending":
        todo, incomplete = pending(p)
        print(f"{len(todo)} pending, {len(incomplete)} incomplete: {', '.join(incomplete) or '-'}")
    elif args.command == "export":
        out = cmd_export(p, args.name, args.limit)
        print(f"exported {len(json.loads(_read(out)))} posts to {out}")
    elif args.command == "build":
        counts, messages = cmd_build(p, args.tags_file, date.today())
        for message in messages:
            print("  " + message)
        print(", ".join(f"{k} {v}" for k, v in counts.items()))
        handled = counts["created"] + counts["skipped"]
        return 0 if handled == len(load_tags(args.tags_file)) else 1
    elif args.command == "vocab":
        print(json.dumps(cmd_vocab(p), ensure_ascii=False, indent=1))
    elif args.command == "update-media":
        counts = cmd_update_media(p, dry_run=args.dry_run)
        print(("dry run: " if args.dry_run else "") + ", ".join(f"{k} {v}" for k, v in counts.items()))
    elif args.command == "concepts-plan":
        out = cmd_concepts_plan(p, args.name)
        plan = json.loads(_read(out))
        print(f"{len(plan['new'])} new pages, {len(plan['needs_embed'])} need the embed: {out}")
    elif args.command == "concepts-apply":
        counts = cmd_concepts_apply(p, args.file, date.today())
        print(", ".join(f"{k} {v}" for k, v in counts.items()))
    elif args.command == "update":
        from assmedia.core.gallerydl import write_conf
        from . import update  # update imports this module
        conf = write_conf(update.TEMPLATE, update.conf_values(config), dirs(config, "instagram").crawl / "gallery-dl.conf")
        return update.cmd_update(p, config.instagram.saved_account if config.instagram else None, full=args.full,
                                 conf=conf)
    return 0
