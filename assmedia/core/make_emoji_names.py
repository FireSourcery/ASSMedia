"""Write assmedia/core/emoji_names.json: emoji -> CLDR short name, from the `emoji` package.

The tools run with `py -I`, which ignores user site-packages, so assmedia reads this table instead of importing
the package. Rerun after upgrading the package (plain `py`, not `py -I`, so the package can be found):

    py -m pip install --user --upgrade emoji
    py <project>\\assmedia\\core\\make_emoji_names.py

Keys are normalized the way assmedia.core.title reads text: variation selectors and skin-tone modifiers removed.
Flags get " flag" after the country name.
"""
import json
import re
from pathlib import Path

import emoji

OUT = Path(__file__).resolve().parent / "emoji_names.json"
IGNORED = re.compile("[\ufe0e\ufe0f\U0001f3fb-\U0001f3ff]")
SKIN = re.compile(r"_(?:light|medium-light|medium|medium-dark|dark)_skin_tone")


def is_flag(key: str) -> bool:
    return all("\U0001f1e6" <= ch <= "\U0001f1ff" for ch in key) or (key[:1] == "\U0001f3f4" and len(key) > 1)


def name_of(code: str) -> str:
    text = SKIN.sub("", code.strip(":")).replace("_", " ").strip(" ,")
    return re.sub(r"\s+", " ", text)


def main() -> None:
    names: dict[str, str] = {}
    # fully-qualified entries first, and entries without skin tones before those with them
    entries = sorted(emoji.EMOJI_DATA.items(), key=lambda kv: (kv[1].get("status", 9), "skin_tone" in kv[1]["en"]))
    for char, data in entries:
        key = IGNORED.sub("", char)
        if not key or key in names:
            continue
        name = name_of(data["en"])
        names[key] = f"{name} flag" if is_flag(key) else name
    OUT.write_text(json.dumps({"source": f"emoji {emoji.__version__} (CLDR short names)", "names": names},
                              ensure_ascii=False, sort_keys=True, indent=0), encoding="utf-8", newline="\n")
    print(f"wrote {len(names)} names to {OUT}")


if __name__ == "__main__":
    main()
