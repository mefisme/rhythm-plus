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
     "A0213 con time stretch (modo Sample, pads 9-17), Clear + pista, los ajustes de Rhythm Plus junto a cada proyecto, página 2 de la pista FX y archivos de Rhythm Plus por USB. Granular One Shot sigue el Scan; Granular suena al momento tras cualquier cambio de proyecto, sin chasquidos. Sin Drone. Cambio de proyecto rápido; Granular sigue sonando al recargar con la misma muestra, también con Retrigger, y se apaga sin chasquido al salir; ninguna pista suena a Granular sin tenerlo activado; un loop con stretch sigue sonando al cambiar de proyecto y pasa a Granular con un fundido.",
     "A0213 with time stretch (Sample mode pads 9-17), Clear + track, Rhythm Plus settings next to each project, FX track page 2 and Rhythm Plus files over USB. Granular One Shot follows the Scan; Granular plays at once after any project change, with no clicks. No Drone. Fast project change; Granular plays straight through a reload on the same sample, Retrigger too, and fades out when you leave; no track sounds Granular unless it is turned on; a stretched loop plays on through a project change and fades into Granular."),
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
