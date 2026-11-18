"""tools/rhythm_plus_app.html: the Rhythm Plus app (the installer, the SD card tools, backup and tidy), with the installer's builds.

    python tools/make_app.py         (needs the builds' .bin files and the stock image, as make_uploader.py)
"""
import html
from pathlib import Path

import make_uploader as u

HERE = Path(__file__).resolve().parents[1]
APP = HERE / "tools" / "app"
OUT = HERE / "tools" / "rhythm_plus_app.html"


def main():
    page = (APP / "template.html").read_text(encoding="utf-8")
    for key, value in (("__CORE__", (APP / "core.js").read_text(encoding="utf-8")),
                       ("__LICENSE__", html.escape((HERE / "remix" / "LICENSE").read_text(encoding="utf-8").strip()))):
        assert page.count(key) == 1, key
        page = page.replace(key, value)
    page = u.fill(page)
    assert "__" + "INSTALLER__" not in page and "</script" not in (APP / "core.js").read_text(encoding="utf-8")
    OUT.write_text(page, encoding="utf-8", newline="")
    print(OUT, len(page), "bytes")


if __name__ == "__main__":
    main()
