"""tools/uploader.html: the Rhythm Plus installer, with stable and one development build.

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
# Keep descriptions short: included features and key fixes; controls belong in the manual.
BUILDS = (
    ("A0213", "stable", HERE / "firmware" / "a0213",
     "Granular con ajuste fino, Freeze y Slice hasta 32 porciones; Pattern y Step Mutate; ajustes guardados en la tarjeta SD. Probada en el aparato.",
     "Granular with fine adjust, Freeze and Slice up to 32 slices; Pattern and Step Mutate; settings saved on the SD card. Tested on the unit."),
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
