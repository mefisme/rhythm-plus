"""tools/uploader.html: the Rhythm Plus installer, from tools/uploader_template.html, with the stable build and the newest test build.

    python tools/make_uploader.py         (needs the builds' .bin files and the stock image)
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / d) for d in ("modules", "builds", "tests", "remix/tools")]
import make_rm_uploader as m  # noqa: E402
import rh_fw  # noqa: E402

# (name, kind, folder, Spanish, English); the first one is picked when the page opens.
BUILDS = (
    ("A0120", "stable", HERE / "firmware" / "a0120",
     "Pattern Mutate y Track +: Parameter Editor, Filter, Mix, Pitch y FX. Probada en el aparato.",
     "Pattern Mutate and Track +: Parameter Editor, Filter, Mix, Pitch and FX. Tested on the unit."),
    ("AG015", "test", HERE / "buildtmp" / "granular-hardware-ag015",
     "La página Granular en el pad 30, con Slice y Lock. Sin las páginas Filter y Mix. Versión de prueba.",
     "The Granular page on pad 30, with Slice and Lock. No Filter or Mix pages. Test build."),
)
TEMPLATE = HERE / "tools" / "uploader_template.html"
OUT = HERE / "tools" / "uploader.html"


def main():
    stock = m.STOCK_BIN.read_bytes()
    assert hashlib.sha256(stock).hexdigest() == rh_fw.STOCK_5706["image_sha256"]
    patches, builds = {}, []
    for v, kind, d, es, en in BUILDS:
        man = json.loads((d / "manifest.json").read_text())
        img = next(d.glob("*.bin")).read_bytes()
        assert hashlib.sha256(img).hexdigest() == man["image_sha256"], v
        ops = m.make_patch(stock, img)
        assert m.apply(stock, ops) == img
        m.check_add(stock, ops)
        assert hashlib.sha256(rh_fw.encode(img)).hexdigest() == man["syx_sha256"], v
        patches[v] = dict(image_sha256=man["image_sha256"], syx_sha256=man["syx_sha256"], ops=ops)
        builds.append(dict(v=v, kind=kind, es=es, en=en))
        print(v, len(ops), "ops")
    page = TEMPLATE.read_text(encoding="utf-8")
    for key, value in (("__PATCHES__", json.dumps(patches, separators=(",", ":"))), ("__BUILDS__", json.dumps(builds, ensure_ascii=False)),
                       ("__STOCK_SYX__", rh_fw.STOCK_5706["syx_sha256"]), ("__STOCK_IMG__", rh_fw.STOCK_5706["image_sha256"])):
        assert page.count(key) == 1, key
        page = page.replace(key, value)
    assert "remix" not in page.lower()
    OUT.write_text(page, encoding="utf-8", newline="")
    print(OUT, len(page), "bytes")


if __name__ == "__main__":
    main()
