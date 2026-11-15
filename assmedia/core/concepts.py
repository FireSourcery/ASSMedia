"""Entity pages (wiki/entities/) and concept pages (wiki/concepts/) for names linked from saves."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from . import fsread
from .collection import Collection, collections_of
from .escape import escape_caption
from .contact import has_contact
from .tags import canonical_domains, check_types, hub_names, validate_name
from .yamlfm import add_aliases, dump, split

if TYPE_CHECKING:
    from .paths import Paths

LINK_FIELDS = ("people", "subjects", "themes")
ENTITY_KINDS = ("person", "organization", "tool", "product", "channel")
KINDS = ENTITY_KINDS + ("concept",)
THRESHOLD = 2
EMBED_HEADING = "## Instagram saves"
MY_TAKE_COMMENT = ("%% Links only, to my own notes. "
                   "Never paraphrase my views into the sections above. %%")
_LINK = re.compile(r"^\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]$")


def link_target(value: str) -> str | None:
    match = _LINK.match(str(value).strip())
    return match.group(1).strip() if match else None


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _save_pages(pages: Path):
    if pages.exists():
        mds = sorted(pages.glob("*.md"))
        for md, text in zip(mds, fsread.read_all(mds)):
            yield md, split(text)[0]


def collect_links(pages: Path) -> dict[str, list[Path]]:
    """Name (first-seen spelling) -> save pages linking it from people/subjects/themes."""
    spelling: dict[str, str] = {}
    found: dict[str, list[Path]] = {}
    for md, meta in _save_pages(pages):
        for field_name in LINK_FIELDS:
            for value in _as_list(meta.get(field_name)):
                target = link_target(value)
                if target:
                    spelling.setdefault(target.lower(), target)
                    bucket = found.setdefault(target.lower(), [])
                    if md not in bucket:
                        bucket.append(md)
    return {spelling[key]: paths for key, paths in found.items()}


def collect_all(cols) -> dict[str, list[Path]]:
    """collect_links over every collection's pages: one entry per name (case-insensitive, first spelling)."""
    spelling: dict[str, str] = {}
    found: dict[str, list[Path]] = {}
    for c in cols:
        for name, paths in collect_links(c.pages).items():
            spelling.setdefault(name.lower(), name)
            bucket = found.setdefault(name.lower(), [])
            bucket += [path for path in paths if path not in bucket]
    return {spelling[key]: paths for key, paths in found.items()}


def _link_fields(cols) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for c in cols:
        for _, meta in _save_pages(c.pages):
            for field_name in LINK_FIELDS:
                for value in _as_list(meta.get(field_name)):
                    target = link_target(value)
                    if target and field_name not in fields.setdefault(target.lower(), []):
                        fields[target.lower()].append(field_name)
    return {k: sorted(v, key=LINK_FIELDS.index) for k, v in fields.items()}


def _pages_in(folders: list[Path]) -> dict[str, Path]:
    found = {}
    for folder in folders:
        if folder.exists():
            for md in folder.rglob("*.md"):
                found.setdefault(md.stem.lower(), md)
    return found


SKIP_DIRS = {".obsidian", ".trash", ".git"}


def vault_notes(vault: Path) -> dict[str, Path]:
    """Every note name in the vault (lowercased) -> path, except settings, trash and Instagram/X raw copies."""
    notes = {}
    if vault.exists():
        for md in vault.rglob("*.md"):
            parts = md.relative_to(vault).parts
            if SKIP_DIRS & set(parts) or parts[:2] in (("raw", "Instagram"), ("raw", "X")):
                continue
            notes.setdefault(md.stem.lower(), md)
    return notes


def concept_index(folders: list[Path]) -> dict[str, str]:
    """Lowercased page name and each alias -> page name, across the given folders."""
    index = {}
    pages = list(_pages_in(folders).values())
    for md, text in zip(pages, fsread.read_all(pages)):
        index.setdefault(md.stem.lower(), md.stem)
        for alias in _as_list(split(text)[0].get("aliases")):
            if str(alias).strip():
                index.setdefault(str(alias).strip().lower(), md.stem)
    return index


def embed_block(c: Collection | None = None) -> str:
    """The embedded cards list of a collection's pages linking here; Instagram's when no collection is given."""
    heading, folder, view = ((c.heading, c.folder, c.view_name) if c else
                             (EMBED_HEADING, "wiki/sources/Instagram", "Saves"))
    return "\n".join([
        heading, "",
        "```base",
        "filters:",
        "  and:",
        f'    - file.inFolder("{folder}")',
        "    - file.hasLink(this.file)",
        "views:",
        "  - type: cards",
        f"    name: {view}",
        "    image: note.thumbnail",
        "    order:",
        "      - file.name",
        "      - description",
        "```", "",
    ])


def _block_end(rows: list[str], heading: str) -> int | None:
    """Index of the closing fence of the embedded list under `heading`, or None."""
    start = next((i for i, row in enumerate(rows) if row.strip() == heading), None)
    if start is None:
        return None
    fence = next((i for i in range(start + 1, len(rows)) if rows[i].strip().startswith("```base")), None)
    if fence is None:
        return None
    return next((i for i in range(fence + 1, len(rows)) if rows[i].strip() == "```"), None)


def ensure_embed(text: str, c: Collection | None = None, cols=()) -> str:
    """Add c's embedded list once: right after the list of an earlier collection in `cols`, else at the end."""
    heading = c.heading if c else EMBED_HEADING
    rows = text.split("\n")
    if any(row.strip() == heading for row in rows):
        return text
    block = embed_block(c)
    cols = list(cols)
    for earlier in reversed(cols[:cols.index(c)] if c in cols else []):
        end = _block_end(rows, earlier.heading)
        if end is not None:
            return "\n".join(rows[:end + 1] + [""] + block.rstrip("\n").split("\n") + rows[end + 1:])
    return text + ("" if text.endswith("\n") else "\n") + "\n" + block


def _embeds(embeds) -> str:
    return "\n".join(embed_block(c) for c in embeds) if embeds else embed_block()


def _norm_sources(sources) -> list[tuple[str, str | None]]:
    """Sources as (page, quote) pairs; plain strings have no quote."""
    return [(s, None) if isinstance(s, str) else (s[0], s[1]) for s in sources]


def _sources_section(sources) -> list[str]:
    lines = []
    for page, quote in _norm_sources(sources):
        lines.append(f'- [[{page}]]: "{escape_caption(quote)}"' if quote else f"- [[{page}]]")
    return ["## Sources"] + (lines or ["- "])


def _source_links(sources) -> list[str]:
    return [f"[[{page}]]" for page, _ in _norm_sources(sources)]


def render_concept(name: str, sentence: str, aliases: list[str], sources,
                   domain: list[str], created: date, embeds=None) -> str:
    props = [("type", "concept"), ("created", created), ("aliases", aliases),
             ("domain", [f"[[{d}]]" for d in domain]), ("sources", _source_links(sources)),
             ("tags", ["concept"]), ("created_by", "claude")]
    body = [f"# {name}", "", "> [!note] In one sentence", f"> {sentence}", "",
            "## Explanation", "", _embeds(embeds),
            "## Connections", "- Related:", "- Contrasts with:", "",
            "## My take", MY_TAKE_COMMENT, "- ", ""] + _sources_section(sources)
    return dump(props) + "\n" + "\n".join(body) + "\n"


def render_entity(name: str, kind: str, sentence: str, aliases: list[str], sources,
                  domain: list[str], url: str | None, created: date, embeds=None) -> str:
    props = [("type", kind), ("created", created), ("aliases", aliases),
             ("domain", [f"[[{d}]]" for d in domain]), ("url", url),
             ("sources", _source_links(sources)), ("tags", ["entity"]),
             ("created_by", "claude")]
    body = [f"# {name}", "", "> [!note] In one sentence", f"> {sentence}", "",
            "## Overview",
            "%% Sourced facts only: link the source page next to each claim. Never cite wiki/analyses/. %%",
            "", _embeds(embeds),
            "## Connections", "- Concepts:", "- Related entities:", "",
            "## My take", MY_TAKE_COMMENT, "- ", ""] + _sources_section(sources)
    return dump(props) + "\n" + "\n".join(body) + "\n"


def add_index_lines(index_md: Path, heading: str, lines: list[str]) -> int:
    """Append lines under `heading` in wiki/index.md, dropping its '*None yet' placeholder."""
    if not lines or not index_md.exists():
        return 0
    rows = _read(index_md).replace("\r\n", "\n").split("\n")
    if heading not in rows:
        rows += ["", heading, ""]
    start = rows.index(heading)
    end = next((i for i in range(start + 1, len(rows)) if rows[i].startswith("## ")), len(rows))
    section = rows[start + 1:end]
    existing = "\n".join(section)
    new = []
    for line in lines:
        match = re.search(r"\[\[[^\]]+\]\]", line)
        if match and match.group(0) not in existing and line not in new:
            new.append(line)
    if not new:
        return 0
    section = [row for row in section if not row.strip().startswith("*None yet")]
    while section and not section[-1].strip():
        section.pop()
    section += new + [""]
    rows = rows[:start + 1] + section + rows[end:]
    index_md.write_text("\n".join(rows), encoding="utf-8", newline="\n")
    return len(new)


def _captions(pairs: list[tuple[Collection, dict]]) -> list[str]:
    """Each save's caption from its item JSON, all read in one batch. "" when there's no such file, or when the
    collection is known only from the vault and has no item JSON to quote."""
    paths = []
    for c, meta in pairs:
        code = meta.get(c.id_property)
        paths.append(c.items / str(code) / f"{code}.json" if code and c.items is not None else None)
    wanted = list(dict.fromkeys(p for p in paths if p is not None))
    texts = dict(zip(wanted, fsread.read_texts(wanted)))
    out = []
    for (c, _), path in zip(pairs, paths):
        text = texts.get(path) if path is not None else None
        if text is None or isinstance(text, FileNotFoundError):
            out.append("")
        elif isinstance(text, Exception):
            raise text
        else:
            out.append(json.loads(text).get(c.caption_field) or "")
    return out


def _owners(cols) -> dict[Path, Collection]:
    """Each collection page -> its collection."""
    return {md: c for c in cols if c.pages.exists() for md in c.pages.glob("*.md")}


def layers(p: Paths) -> dict[str, Path]:
    """Domain hubs with a domain folder of their own: hub -> <vault>/<Domain>/wiki/ (CLAUDE.md "Domain folders")."""
    return {hub: p.vault / hub / "wiki" for hub in hub_names(p.domains).values()
            if (p.vault / hub / "wiki").is_dir()}


def wiki_dirs(p: Paths) -> list[Path]:
    """Every entities/ and concepts/ folder: the shared ones plus each domain folder's."""
    dirs = [p.entities, p.concepts]
    for layer in layers(p).values():
        dirs += [layer / "entities", layer / "concepts"]
    return dirs


def _index_for(p: Paths, page: Path) -> Path:
    for hub, layer in layers(p).items():
        if page.is_relative_to(layer):
            return layer / f"{hub} index.md"
    return p.index_md


def _wiki_pages(p: Paths) -> dict[str, Path]:
    return _pages_in(wiki_dirs(p))


def _needs_embed(p: Paths, cols) -> list[tuple[Path, Collection]]:
    """Existing wiki pages linked from a collection's pages that lack that collection's embedded list."""
    wiki = _wiki_pages(p)
    index = concept_index(wiki_dirs(p))
    candidates = []
    for c in cols:
        for name in collect_links(c.pages):
            canonical = index.get(name.lower())
            path = wiki.get(canonical.lower()) if canonical else None
            if path and (path, c) not in candidates:
                candidates.append((path, c))
    unique = list(dict.fromkeys(path for path, _ in candidates))
    texts = dict(zip(unique, fsread.read_all(unique)))
    return [(path, c) for path, c in candidates if c.heading not in texts[path]]


def _suggest(fields: list[str]) -> str | None:
    if "people" in fields:
        return "person"
    if fields == ["themes"]:
        return "concept"
    return None


def _conflicts(p: Paths, names) -> dict[str, Path]:
    """Names that would duplicate a note elsewhere in the vault (Domains/, Dashboards/, wiki/index ...)."""
    existing = concept_index(wiki_dirs(p) + [p.people])
    notes = vault_notes(p.vault)
    return {name.lower(): notes[name.lower()] for name in names
            if name.lower() not in existing and name.lower() in notes}


def cmd_concepts_plan(p: Paths, name: str) -> Path:
    cols = collections_of(p)
    links = collect_all(cols)
    fields = _link_fields(cols)
    owners = _owners(cols)
    existing = concept_index(wiki_dirs(p) + [p.people])
    candidates = [c for c, pages in links.items() if len(pages) >= THRESHOLD and c.lower() not in existing]
    clashes = _conflicts(p, candidates)
    wanted = list(dict.fromkeys(page for c in candidates if c.lower() not in clashes for page in links[c]))
    metas = {page: split(text)[0] for page, text in zip(wanted, fsread.read_all(wanted))}
    captions = dict(zip(wanted, _captions([(owners[page], metas[page]) for page in wanted])))
    new, conflicts = [], []
    for concept in candidates:
        pages = links[concept]
        if concept.lower() in clashes:
            conflicts.append({"name": concept, "count": len(pages), "path": str(clashes[concept.lower()])})
            continue
        saves = []
        for page in pages:
            meta = metas[page]
            owner = owners[page]
            saves.append({"page": page.stem, "collection": owner.name,
                          "description": meta.get("description") or "", "caption": captions[page]})
        entry_fields = fields.get(concept.lower(), [])
        new.append({"name": concept, "count": len(pages), "fields": entry_fields,
                    "suggested_kind": _suggest(entry_fields), "saves": saves})
    new.sort(key=lambda entry: (-entry["count"], entry["name"].lower()))
    out = p.build / "concepts" / f"{name}.plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    needs = _needs_embed(p, cols)
    plan = {"new": new, "conflicts": conflicts,
            "needs_embed": list(dict.fromkeys(str(path) for path, _ in needs)),
            "needs_embed_detail": [{"path": str(path), "collection": c.name} for path, c in needs],
            "domains": sorted(hub_names(p.domains).values())}
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return out


def _domain_union(pages: list[Path]) -> list[str]:
    """Domains of the linking saves, most common first (the first one picks the domain folder)."""
    counts: dict[str, int] = {}
    for text in fsread.read_all(pages):
        for value in _as_list(split(text)[0].get("domain")):
            target = link_target(value)
            if target:
                counts[target] = counts.get(target, 0) + 1
    return sorted(counts, key=lambda name: (-counts[name], name.lower()))


def _check_entry(name: str, entry: dict) -> list[tuple[str, str | None]]:
    """Validate one apply entry's types; return its sources as (page, quote) pairs."""
    if not isinstance(entry, dict):
        raise ValueError(f"{name}: entry must be an object")
    check_types(name, entry, ("aliases", "domain"), ("kind", "sentence", "url"))
    sentence = entry.get("sentence") or ""
    if "\n" in sentence or "\r" in sentence:
        raise ValueError(f"{name}: sentence must be a single line")
    if has_contact(sentence):
        raise ValueError(f"{name}: sentence contains contact details")
    sources = entry.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError(f"{name}: sources must be a list")
    pairs = []
    for source in sources:
        if isinstance(source, str):
            pairs.append((source, None))
        elif isinstance(source, dict) and isinstance(source.get("page"), str) and \
                isinstance(source.get("quote", ""), str):
            quote = (source.get("quote") or "").strip()
            if "\n" in quote:
                raise ValueError(f"{name}: quote from {source['page']} must be a single line")
            if has_contact(quote):
                raise ValueError(f"{name}: quote from {source['page']} contains contact details")
            pairs.append((source["page"], quote or None))
        else:
            raise ValueError(f"{name}: each source must be a page name or an object with page and quote, "
                             f"got {source!r}")
    return pairs


def cmd_concepts_apply(p: Paths, file: Path, today: date) -> dict[str, int]:
    entries = json.loads(_read(file))
    cols = collections_of(p)
    links = {name.lower(): pages for name, pages in collect_all(cols).items()}
    linked_by = {c.name: {n.lower() for n in collect_links(c.pages)} for c in cols}
    existing = concept_index(wiki_dirs(p) + [p.people])
    wiki = _wiki_pages(p)
    clashes = _conflicts(p, entries)
    hubs = hub_names(p.domains)
    creator_maps = _creator_maps(cols)

    seen: dict[str, str] = {}
    planned, repairs = [], []
    for name, entry in entries.items():
        validate_name(name)
        if name.lower() in seen:
            raise ValueError(f"{name}: duplicate of {seen[name.lower()]!r} (names differ only in case)")
        seen[name.lower()] = name
        sources = _check_entry(name, entry)
        sentence = (entry.get("sentence") or "").strip()
        if name.lower() in existing:
            path = wiki.get(existing[name.lower()].lower())
            if path is not None and sentence:  # existing wiki page: make sure it has an index line
                heading = "## Concepts" if path.parent.name == "concepts" else "## Entities"
                repairs.append((_index_for(p, path), heading, f"- [[{path.stem}]] — {sentence}"))
            continue  # People/ notes are never touched
        if name.lower() in clashes:
            raise ValueError(f"{name}: a note with this name already exists at {clashes[name.lower()]}")
        kind = entry.get("kind")
        if kind not in KINDS:
            raise ValueError(f"{name}: kind {kind!r} is not one of {', '.join(KINDS)}")
        pages = links.get(name.lower(), [])
        linking = {page.stem for page in pages}
        if len(linking) < THRESHOLD:
            raise ValueError(f"{name}: linked from {len(linking)} save(s), needs {THRESHOLD}")
        bad = [page for page, _ in sources if page not in linking]
        if bad:
            raise ValueError(f"{name}: sources {bad} do not link to it")
        domain = canonical_domains(entry["domain"], hubs) if "domain" in entry else \
            canonical_domains(_domain_union(pages), hubs)
        users = _users_for(name, creator_maps)
        aliases = list(dict.fromkeys(list(entry.get("aliases") or []) + [user for _, user in users]))
        url = entry.get("url") or (users[0][0].profile_url.format(users[0][1]) if users else None)
        planned.append((name, kind, sentence, aliases, sources, domain, url))

    counts = {"created": 0, "embedded": 0, "index_lines": 0}
    layer_dirs = layers(p)
    for name, kind, sentence, aliases, sources, domain, url in planned:
        layer = layer_dirs.get(domain[0]) if domain else None
        root = layer if layer else None
        embeds = [c for c in cols if name.lower() in linked_by[c.name]]
        if kind == "concept":
            folder, heading = (root / "concepts") if root else p.concepts, "## Concepts"
            text = render_concept(name, sentence, aliases, sources, domain, today, embeds)
        else:
            folder, heading = (root / "entities") if root else p.entities, "## Entities"
            text = render_entity(name, kind, sentence, aliases, sources, domain, url, today, embeds)
        index_md = root / f"{domain[0]} index.md" if root else p.index_md
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / f"{name}.md").open("x", encoding="utf-8", newline="\n") as fp:
            fp.write(text)
        counts["created"] += 1
        counts["index_lines"] += add_index_lines(index_md, heading, [f"- [[{name}]] — {sentence}"])
    for index_md, heading, line in repairs:
        counts["index_lines"] += add_index_lines(index_md, heading, [line])
    for path, c in _needs_embed(p, cols):
        path.write_text(ensure_embed(_read(path), c, cols), encoding="utf-8", newline="\n")
        counts["embedded"] += 1
    counts["aliased"] = _alias_existing(p, creator_maps)
    return counts


def _creator_maps(cols) -> list[tuple[Collection, dict[str, str]]]:
    """Each collection's username -> person mapping (a shared file is read once)."""
    maps, seen = [], set()
    for c in cols:
        if c.creators is None or c.creators in seen:
            continue
        seen.add(c.creators)
        maps.append((c, json.loads(_read(c.creators)) if c.creators.exists() else {}))
    return maps


def _users_for(name: str, creator_maps) -> list[tuple[Collection, str]]:
    return [(c, user) for c, mapping in creator_maps for user, person in mapping.items()
            if str(person).lower() == name.lower()]


def _alias_existing(p: Paths, creator_maps) -> int:
    """Give existing wiki pages the usernames creators map to them; People/ notes are never touched."""
    index = concept_index(wiki_dirs(p))
    wiki = _wiki_pages(p)
    wanted: dict[Path, list[str]] = {}
    for _, mapping in creator_maps:
        for user, person in mapping.items():
            canonical = index.get(str(person).lower())
            path = wiki.get(canonical.lower()) if canonical else None
            if path is not None:
                wanted.setdefault(path, []).append(user)
    changed = 0
    for path, users in wanted.items():
        text = _read(path)
        updated = add_aliases(text, users)
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed += 1
    return changed


def cmd_vocab(p: Paths) -> dict:
    pages = {}
    wiki = list(_pages_in(wiki_dirs(p) + [p.people]).values())
    for md, text in zip(wiki, fsread.read_all(wiki)):
        meta = split(text)[0]
        pages[md.stem] = {"type": str(meta.get("type") or ""),
                          "aliases": [str(a) for a in _as_list(meta.get("aliases"))]}
    linked = {name: len(paths) for name, paths in collect_all(collections_of(p)).items()}
    creators_path = p.tagging / "creator-people.json"
    creators = json.loads(_read(creators_path)) if creators_path.exists() else {}
    return {"pages": pages, "linked": linked, "domains": sorted(hub_names(p.domains).values()),
            "creators": creators}
