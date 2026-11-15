"""assmedia.py's dispatcher: `x <command>`, `instagram <command>`, or `relink <pages> <old> <new>`.

The platform commands read assmedia.toml (or --config <path>) first: a config problem, or a platform the config
doesn't set up, stops with one `assmedia:` line per problem and exit code 2. `relink` needs no config.
"""
from __future__ import annotations

import importlib
import sys

from assmedia.core.config import PLATFORMS, default_config_path, load_config, problems, split_config_arg

USAGE = "usage: assmedia.py [--config <toml>] <x|instagram|relink> ..."


def _fail(*lines: str) -> int:
    for line in lines:
        print(f"assmedia: {line}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    try:
        path, rest = split_config_arg(argv)
    except ValueError as exc:
        return _fail(str(exc))
    if not rest or rest[0] not in (*PLATFORMS, "relink"):
        print(USAGE, file=sys.stderr)
        return 2
    command, rest = rest[0], rest[1:]
    if command == "relink":
        from assmedia.core import relink
        return relink.main(rest)
    path = path or default_config_path()
    try:
        cfg = load_config(path)
    except (FileNotFoundError, ValueError) as exc:
        return _fail(str(exc))
    if getattr(cfg, command) is None:
        return _fail(f"[{command}] isn't set up in {path}")
    found = problems(cfg, command)
    if found:
        return _fail(*found)
    return importlib.import_module(f"assmedia.{command}.cli").main(rest, config=cfg)
