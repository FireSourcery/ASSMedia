"""ASSMedia's tests. A guard makes any write outside the system temp folder fail, so no test can touch real data.

The guard is an audit hook, installed when this package is imported, so it covers every test the suite runs. Reads
anywhere are fine (the instance tests read assmedia.toml and a few files under `state`). Python's own bytecode cache
(`__pycache__`) is allowed. Child processes (git, ffmpeg) aren't seen by the hook; the tests point them at temp.
"""
import os
import sys
import tempfile
from pathlib import Path


def _forms(path: str) -> set[str]:
    """The ways a path may be spelled: as given and fully resolved (8.3 short names expand to long ones)."""
    forms = {os.path.normcase(os.path.abspath(path))}
    try:
        forms.add(os.path.normcase(str(Path(path).resolve())))
    except OSError:
        pass
    return forms


_TEMP = tuple(f.rstrip("\\/") + os.sep for f in _forms(tempfile.gettempdir()))
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_ONE_PATH = {"os.mkdir", "os.makedirs", "os.remove", "os.rmdir", "os.truncate", "os.chmod", "os.utime",
             "shutil.rmtree"}
_TWO_PATHS = {"os.rename", "os.replace", "os.link", "os.symlink", "shutil.copyfile", "shutil.copytree",
              "shutil.move", "shutil.copymode", "shutil.copystat"}


def _allowed(path) -> bool:
    if path is None or isinstance(path, int):  # a file descriptor: its open was already checked
        return True
    text = os.fsdecode(path)
    if text == os.devnull or "__pycache__" in text:
        return True
    return any(form.startswith(_TEMP) for form in _forms(text))


def _guard(event: str, args: tuple) -> None:
    if event == "open":
        path, mode, flags = args
        writing = ((isinstance(mode, str) and any(c in mode for c in "wax+"))
                   or (mode is None and isinstance(flags, int) and flags & _WRITE_FLAGS))
        targets = [path] if writing else []
    elif event in _ONE_PATH:
        targets = [args[0]]
    elif event in _TWO_PATHS:
        targets = [args[1]] if event.startswith("shutil.copy") else [args[0], args[1]]
    else:
        return
    for target in targets:
        if not _allowed(target):
            raise PermissionError(f"tests may write only under {tempfile.gettempdir()}, not {os.fsdecode(target)}")


sys.addaudithook(_guard)
