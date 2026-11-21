"""On-unit file tools: project and sample copies (Duplicate), pack delete (Clear). See filetools.c.

Placed in the first flash hole that dsppack leaves, so it runs after dsppack.install.
"""
import os
import struct
from pathlib import Path
import rhbuild
import rhstate
import tmenu
from stepmut import compile_c
from thumb import bl
ROOT = Path(__file__).resolve().parents[1]
SLOT_LEN = 64
VT = dict(PREV_PROJ=0x080679CC, PREV_SMP=0x08067A08, PREV_PACK=0x08067954)     # each view's vtable: [0] = its pad handler
STOCK = dict(PREV_PROJ=0x0804F09E, PREV_SMP=0x0804F9D8, PREV_PACK=0x0804E00A)
BUF, BUF_LDR = 0x20003F94, 0x0802EF94
USES = dict(USE_PROJ=0x0804F54A, USE_SMP=0x08069758, USE_PACK=0x0804E0A6)   # slot 8 (vtable +0x20): the buttons the view lights
USES_HOOK = dict(USE_PROJ="c_ft_projuse", USE_SMP="c_ft_smpuse", USE_PACK="c_ft_packuse")
USES_VT = dict(USE_PROJ=VT["PREV_PROJ"], USE_SMP=VT["PREV_SMP"], USE_PACK=VT["PREV_PACK"])


def install(img, report):
    assert "dsppack" in report and report["storageshadow"]["labels"].get("c_sh_pxmidi"), "filetools: after dsppack, with the Plus commands"
    assert rhstate.OFF["filetools"][1] == SLOT_LEN
    u = lambda a: struct.unpack_from("<I", img, a - rhbuild.BASE)[0]   # noqa: E731
    ins = struct.unpack_from("<H", img, BUF_LDR - rhbuild.BASE)[0]
    assert ins & 0xFF00 == 0x4800 and u(((BUF_LDR + 4) & ~3) + 4 * (ins & 0xFF)) == BUF   # the buffer the stock's lock hands out
    prev = {k: u(a) & ~1 for k, a in VT.items()}
    assert prev == STOCK, prev
    holes = report["dsppack"]["holes"]
    start, end = (int(x, 16) for x in holes[0][:2])
    base = (start + 3) & ~3
    defs = dict(prev, PREV_OUT=rhbuild.bl_target(img, tmenu.OUT_CALL), SLOT=rhstate.ST + rhstate.OFF["filetools"][0],
                C_RST=int(report["rhstate"]["labels"]["c_rst"], 16), C_PX=int(report["storageshadow"]["labels"]["c_sh_pxmidi"], 16))
    hold = os.environ.get("RH_FT_HOLD") == "1"
    if hold:
        defs["HOLD_SOURCE"] = 1
    buttons = os.environ.get("RH_FT_BUTTONS") == "1"
    if buttons:
        assert {k: u(a + 0x20) & ~1 for k, a in USES_VT.items()} == USES
        defs.update(USES, BUTTONS=1)
    code, labels = compile_c(base, defs, src=ROOT / "modules/filetools.c", name="filetools", prefix="c_ft_",
                             need=("c_ft_out", "c_ft_projpad", "c_ft_smppad", "c_ft_packpad") + (tuple(USES_HOOK.values()) if buttons else ()), max_code=end - base)
    o = base - rhbuild.BASE
    assert all(b == 0xFF for b in img[o:o + len(code)])
    img[o:o + len(code)] = code
    for k, a in VT.items():
        rhbuild.patch_word(img, a, prev[k] | 1, labels[{"PREV_PROJ": "c_ft_projpad", "PREV_SMP": "c_ft_smppad", "PREV_PACK": "c_ft_packpad"}[k]] | 1)
    if buttons:
        for k, a in USES_VT.items():
            rhbuild.patch_word(img, a + 0x20, USES[k] | 1, labels[USES_HOOK[k]] | 1)
    rhbuild.patch(img, tmenu.OUT_CALL, f"bl #{defs['PREV_OUT']:#x}", bl(tmenu.OUT_CALL, labels["c_ft_out"]))
    after = (base + len(code) + 3) & ~3
    holes[0] = [hex(after), holes[0][1], end - after]
    report["filetools"] = dict(at=hex(base), code=len(code), slot=hex(defs["SLOT"]), prev={k.lower(): hex(v) for k, v in prev.items()},
                               prev_out=hex(defs["PREV_OUT"]), labels={k: hex(v) for k, v in labels.items()}, internal_pack="read only", **({"hold_source": True} if hold else {}),
                               **({"buttons": "Duplicate lit on Projects and Sample Rec, Clear on Packs"} if buttons else {}))
    return labels, code
