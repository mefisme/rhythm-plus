"""tools/rhythm_plus_app.html: the Rhythm Plus app (the installer, the SD card tools, backup and tidy), with the installer's builds.

    python tools/make_app.py         (needs the builds' .bin files and the stock image)
"""
import hashlib
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / d) for d in ("modules", "builds", "tests", "remix/tools")]
import make_rm_uploader as m  # noqa: E402
import rh_fw  # noqa: E402

APP = HERE / "tools" / "app"
OUT = HERE / "tools" / "rhythm_plus_app.html"
# (name, kind, folder, Spanish, English); the first one is picked when the page opens.
# Keep descriptions short: included features and key fixes; controls belong in the manual.
BUILDS = (
    ("A0256", "stable", HERE / "firmware" / "a0256",
     "A0213 con time stretch (modo Sample, pads 9-17), Clear + pista, ajustes Plus junto a cada proyecto y archivos Plus por USB. Cambios de proyecto rápidos y sin chasquidos con Granular y stretch.",
     "A0213 with time stretch (Sample mode pads 9-17), Clear + track, Plus settings next to each project and Plus files over USB. Fast project changes with no clicks from Granular or stretch."),
    ("A276", "test", HERE / "firmware" / "a276",
     "Copia proyectos y muestras, y borra packs, en la unidad. Sin Easy Start. Granular: sin blip al cambiar de modo, Scan centrado en 63-65, los pads de largo de Scan a tiempo con el reloj, también por muestra.",
     "Copy projects and samples, and delete packs, on the unit. No Easy Start. Granular: no blip on mode changes, Scan centred at 63-65, and the Scan length pads in time with the clock, per sample too."),
)

INSTALLER = APP / "installer.js"


def fill(template):
    """the page with the installer script and the builds: patches from the official image, each checked"""
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
    page = template.replace("__INSTALLER__", INSTALLER.read_text(encoding="utf-8"))
    for key, value in (("__PATCHES__", json.dumps(patches, separators=(",", ":"))), ("__BUILDS__", json.dumps(builds, ensure_ascii=False)),
                       ("__STOCK_SYX__", rh_fw.STOCK_5706["syx_sha256"]), ("__STOCK_IMG__", rh_fw.STOCK_5706["image_sha256"])):
        assert page.count(key) == 1, key
        page = page.replace(key, value)
    return page


def main():
    page = (APP / "template.html").read_text(encoding="utf-8")
    for key, value in (("__CORE__", (APP / "core.js").read_text(encoding="utf-8")),
                       ("__LICENSE__", html.escape((HERE / "remix" / "LICENSE").read_text(encoding="utf-8").strip()))):
        assert page.count(key) == 1, key
        page = page.replace(key, value)
    page = fill(page)
    assert "__" + "INSTALLER__" not in page and "</script" not in (APP / "core.js").read_text(encoding="utf-8")
    OUT.write_text(page, encoding="utf-8", newline="")
    print(OUT, len(page), "bytes")


if __name__ == "__main__":
    main()
