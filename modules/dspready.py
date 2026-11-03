"""Whether the voices' DSP program is loaded, for Stock+ (MIT; Circuit Rhythm 5706).

tools/stockplus.py writes to core 1 only after the mode 0 program was seen uploaded: it reads byte + 1 of rhstate's "cthresh" slot (READY /
BLOCKED).  In Circuit Remix tools/cthresh.py (the master compressor's threshold on Sidechain K5) keeps that byte; here only the byte is kept,
without the threshold feature.  The slot and the report key keep cthresh's name, as stockplus reads them under it.

  * the two program uploads (0x080278CC mode 0 at power-up, 0x080278A8 mode 1, both bl 0x08031110 after movs r0, #mode): the upload, then
    + 1 = READY (mode 0) or BLOCKED (mode 1); without our RAM block nothing is written (0 = no upload seen: Stock+ writes nothing).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import Asm, b_cond, bl, cmp_imm, mov_reg, movs_imm, pop_list, push_list, strb_w  # noqa: E402
import cthresh as TH  # noqa: E402
import rhstate  # noqa: E402

O_ST = rhstate.OFF["cthresh"][0]


def arm_code(base, L):
    a = Asm(base)
    E = a.emit
    for mode in (0, 1):
        a.label(f"c_drup{mode}")                         # in place of the upload call (r0 = the mode)
        E(push_list, [4], lr=True)
        E(bl, TH.UPLOAD)
        E(mov_reg, 4, 0)                                  # (its result kept)
        E(bl, L["c_rst"])
        E(cmp_imm, 0, 0)
        E(b_cond, f"du{mode}_x", "eq")
        E(movs_imm, 1, TH.READY if mode == 0 else TH.BLOCKED)
        E(strb_w, 1, 0, O_ST + 1)
        a.label(f"du{mode}_x")
        E(mov_reg, 0, 4)
        E(pop_list, [4], pc=True)
    return a.assemble()


def install(img, report, base_addr):
    import rhbuild
    from thumb import bl as bl_enc
    BASE = rhbuild.BASE
    L = dict(c_rst=int(report["rhstate"]["labels"]["c_rst"], 16))
    for c, mode in TH.UPLOAD_CALLS.items():
        assert rhbuild.bl_target(img, c) == TH.UPLOAD, hex(c)
        assert bytes(img[c - 2 - BASE:c - BASE]) == bytes([mode, 0x20]), hex(c)          # movs r0, #mode
    code, labels = arm_code(base_addr, L)
    img += bytes([0xFF]) * (base_addr - BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    for c, mode in TH.UPLOAD_CALLS.items():
        rhbuild.patch(img, c, f"bl #{TH.UPLOAD:#x}", bl_enc(c, labels[f"c_drup{mode}"]))
    report["cthresh"] = dict(ready_only=True, slot=hex(rhstate.ST + O_ST), labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
