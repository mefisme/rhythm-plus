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
# Keep the stable entry. When an in-development build passes hardware testing,
# replace the previous in-development entry with the new baseline.
BUILDS = (
    ("A276", "stable", HERE / "firmware" / "a276",
     "Copia proyectos y muestras en la unidad y sincroniza Granular Scan al reloj.",
     "Copy projects and samples on-device. Sync Granular Scan to the clock."),
    ("A329", "test", HERE / "firmware" / "a329",
     "Páginas Filter, Pitch y Extras (Ring Mod y Scan) en el editor de parámetros de pista. MIDI Merge, Filter y USB merge. Clear + Save guarda con los ajustes por defecto. Los proyectos del pack interno guardan sus ajustes en la tarjeta SD y se guardan también sin tarjeta. Pattern Settings, pad 25: cuantiza el patrón. Shift + Play muestra los pasos de la pista en cualquier pantalla. Mantén Shift + Play 0,5 s: 8 cues en los pads 25-32, los pads 17-24 y K4 fijan el tiempo del cue (salto y bucle), K2 la velocidad de K1, K3 explora la canción en silencio.",
     "Filter, Pitch and Extras (Ring Mod and Scan) pages in the Track Parameter Editor. MIDI Merge, Filter and USB merge. Clear + Save saves with the default settings. Internal pack projects keep their settings on the SD card and save without a card too. Pattern Settings pad 25 quantizes the pattern. Shift + Play shows the track's steps on every screen. Hold Shift + Play for 0.5 s: 8 cues on pads 25-32, pads 17-24 and K4 set the cue timing (jump and loop), K2 sets K1's speed, K3 scans the song silently."),
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
