"""ASSMedia: your saved posts from X, Instagram and the like, as pages in an Obsidian vault.

    py -I <project>\\assmedia.py [--config <toml>] <x|instagram|relink> ...

README.md has every command. `py -I` doesn't put this script's folder on the import path, so it does that here.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from assmedia.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
