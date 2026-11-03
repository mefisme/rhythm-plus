"""Sample mode's pitch reset: Clear + pad 1 or 2 (MIT; Rhythm Plus, Circuit Rhythm 5706).

The stock (its pad handler 0x08057DA8 read in Ghidra): Sample mode (the Samples button twice, CONT's mode byte 9) hands each pad (index
0-31) to slot 0 of its subview (vtable 0x08067D8C); pads 1 / 2 fit the sample to the pattern by the pitch.  Each track has a fit object
(0x200469CC + 0xB4 t, vtable 0x0806847C): [+ 0x30] p0 = the pitch (64 = the sample's own, 1/5 semitone a step), [+ 0x14] / [+ 0x18] the
proxy and parameter id the stock writes the pitch through; 0x0803C1D4(fit) = the stock's «applied» on pads 1 / 2 back to none.

Ours: with Clear held, pad 1 or 2 sets the track's pitch to 64 and the stock's «applied» to none, in place of the stock's fit; without
Clear, and every other pad, the stock's.  The pads' LEDs stay the stock's.  No RAM.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import Asm, b, b_cond, b_w, bl, cmp_imm, cmp_reg, h, ldr_imm, ldrb_imm, ldrh_imm, lsls_imm, lsrs_imm, mov_reg, movs_imm, movt, movw, pop_list, push_list, raw  # noqa: E402
import countin as CI  # noqa: E402

SMP_VT, SMP_PAD = 0x08067D8C, 0x08057DA8
FIT_VT = 0x0806847C
F_PROXY, F_PID, F_TRACK = 0x14, 0x18, 0x30
SUB_NODE = 0x18
GET, UNAPPLY = 0x0803FC58, 0x0803C1D4
PAD_FIT0, PAD_FIT1 = 0, 1                                 # pads 1 / 2
PITCH_MID = 64
O_HELD, BIT_CLEAR = 0xA0, 23


def arm_code(base):
    a = Asm(base)
    E = a.emit

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, (v >> 16) & 0xFFFF)

    # ---- c_smpad (Sample mode's slot 0: r0 = subview, r1 = pad, r2 = velocity): Clear + pad 1 / 2 ours, the rest the stock's
    a.label("c_smpad")
    E(cmp_imm, 1, PAD_FIT1)
    E(b_cond, "pd_st", "hi")
    imm32(3, CI.CTRL + O_HELD)
    E(ldr_imm, 3, 3, 0)
    E(lsls_imm, 3, 3, 31 - BIT_CLEAR)
    E(b_cond, "pd_o", "mi")                                               # Clear held
    a.label("pd_st")
    E(b_w, SMP_PAD)
    a.label("pd_o")
    E(push_list, [4], lr=True)
    E(ldr_imm, 0, 0, SUB_NODE)
    E(ldr_imm, 4, 0, 0)                                                   # r4 = the fit object
    E(ldr_imm, 0, 4, 0)
    imm32(1, FIT_VT)
    E(cmp_reg, 0, 1)
    E(b_cond, "pd_x", "ne")
    E(ldrh_imm, 0, 4, F_PID)
    E(lsrs_imm, 0, 0, 4)                                                  # the track
    E(cmp_imm, 0, 8)
    E(b_cond, "pd_x", "hs")
    E(ldr_imm, 0, 4, F_TRACK)                                             # the pitch
    E(movs_imm, 1, 0)
    E(bl, GET)
    E(ldrb_imm, 0, 0, 0)
    E(cmp_imm, 0, PITCH_MID)
    E(b_cond, "pd_u", "eq")
    E(movs_imm, 2, PITCH_MID)                                             # the pitch 64 through the stock's proxy
    E(ldr_imm, 0, 4, F_PROXY)
    E(ldrh_imm, 1, 4, F_PID)
    E(ldr_imm, 3, 0, 0)
    E(ldr_imm, 3, 3, 0)
    E(raw, h(0x4798))                                                     # blx r3
    a.label("pd_u")
    E(mov_reg, 0, 4)
    E(bl, UNAPPLY)
    a.label("pd_x")
    E(pop_list, [4], pc=True)
    return a.assemble()


def install(img, report, base_addr):
    import rhbuild
    BASE = rhbuild.BASE
    assert int.from_bytes(img[SMP_VT - BASE:SMP_VT - BASE + 4], "little") == SMP_PAD | 1, "Sample mode's slot 0 is not the stock's"
    base_addr = (base_addr + 3) & ~3
    code, labels = arm_code(base_addr)
    img += bytes([0xFF]) * (base_addr - BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    rhbuild.patch_word(img, SMP_VT, SMP_PAD | 1, labels["c_smpad"] | 1)
    report["smpads"] = dict(clear_fit_reset=True, labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
