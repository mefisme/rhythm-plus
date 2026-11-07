"""Sample mode's pitch reset: Clear + pad 1 or 2 (MIT; Rhythm Plus, Circuit Rhythm 5706).

The stock (its pad handler 0x08057DA8 read in Ghidra): Sample mode (the Samples button twice, CONT's mode byte 9) hands each pad (index
0-31) to slot 0 of its subview (vtable 0x08067D8C); pads 1 / 2 fit the sample to the pattern by the pitch.  Each track has a fit object
(0x200469CC + 0xB4 t, vtable 0x0806847C): [+ 0x30] p0 = the pitch (64 = the sample's own, 1/5 semitone a step), [+ 0x14] / [+ 0x18] the
proxy and parameter id the stock writes the pitch through; 0x0803C1D4(fit) = the stock's «applied» on pads 1 / 2 back to none.

Ours: with Clear held, pad 1 or 2 sets the track's pitch to 64 and the stock's «applied» to none, in place of the stock's fit; without
Clear, and every other pad, the stock's.  The pads' LEDs stay the stock's.  No RAM.
(sm) pads 19-21 turn the selected track's switches on / off (fshape's value 29, saved with the project): 19 the loop crossfade, 20 the
retrigger de-click, 21 the end fade (sm = 1: pad 21; 2: pads 20, 21; 3: all three); c_smled, a head of the LED task's chain, lights
them while Sample mode is on the screen (the stock's colours for chosen / not chosen).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, b, b_cond, b_w, bl, cmp_imm, cmp_reg, eors_reg, h, ldr_imm, ldrb_imm, ldrb_w, ldrh_imm, lsls_imm, lsrs_imm,  # noqa: E402
                   mov_reg, movs_imm, movt, movw, pop_list, push_list, raw, strh_imm, subs_imm8)
import countin as CI  # noqa: E402

SMP_VT, SMP_PAD = 0x08067D8C, 0x08057DA8
FIT_VT = 0x0806847C
F_PROXY, F_PID, F_TRACK = 0x14, 0x18, 0x30
SUB_NODE = 0x18
GET, UNAPPLY = 0x0803FC58, 0x0803C1D4
PAD_FIT0, PAD_FIT1 = 0, 1                                 # pads 1 / 2
PITCH_MID = 64
O_HELD, BIT_CLEAR = 0xA0, 23
CONT, O_MODE, MODE_SMP, SELTRK = 0x20048B9C, 0x264, 9, 0x0805800E
O_VIEW = 0x7C                                             # the controller's view on the screen
PAD_XF, PAD_RD, PAD_EF = 18, 19, 20                       # (sm) pads 19, 20, 21
PAL, PAL_ON, PAL_OFF = 0x08062AB0, 0x408, 0x40A


def arm_code(base, sm=None, prev_led=None):
    """sm: fshape's c_fsval / c_fsput, its value 29's index, the pads with their bits"""
    a = Asm(base)
    E = a.emit

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, (v >> 16) & 0xFFFF)

    # ---- c_smpad (Sample mode's slot 0: r0 = subview, r1 = pad, r2 = velocity): Clear + pad 1 / 2 ours, the rest the stock's
    a.label("c_smpad")
    if sm:
        for pad, bit in sm["pads"]:
            E(movs_imm, 2, bit)
            E(cmp_imm, 1, pad)
            E(b_cond, "pe_go", "eq")
        E(b, "pd_n")
        a.label("pe_go")
        E(push_list, [4, 5, 6], lr=True)
        E(mov_reg, 5, 2)                                                  # r5 = the pad's bit
        imm32(0, CONT)
        E(bl, SELTRK)
        E(cmp_imm, 0, 8)
        E(b_cond, "pe_x", "hs")
        E(mov_reg, 4, 0)
        E(movs_imm, 1, sm["v"])
        E(bl, sm["val"])
        E(mov_reg, 2, 5)
        E(eors_reg, 2, 0)
        E(mov_reg, 0, 4)
        E(movs_imm, 1, sm["v"])
        E(bl, sm["put"])
        a.label("pe_x")
        E(pop_list, [4, 5, 6], pc=True)
        a.label("pd_n")
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
    if sm:
        # ---- c_smled(r0 = ctrl, r1 = frame): the chain, then pad 21 while Sample mode is on the screen
        a.label("c_smled")
        E(push_list, [3, 4, 5], lr=True)
        E(mov_reg, 5, 1)
        E(bl, prev_led)
        imm32(0, CI.CTRL)
        E(ldr_imm, 1, 0, O_VIEW)
        imm32(0, CONT)
        E(cmp_reg, 0, 1)
        E(b_cond, "sl_x", "ne")
        E(ldrb_w, 1, 0, O_MODE)
        E(cmp_imm, 1, MODE_SMP)
        E(b_cond, "sl_x", "ne")
        E(bl, SELTRK)
        E(cmp_imm, 0, 8)
        E(b_cond, "sl_x", "hs")
        E(movs_imm, 1, sm["v"])
        E(bl, sm["val"])
        E(mov_reg, 4, 0)
        for pad, bit in sm["pads"]:
            E(lsls_imm, 0, 4, 32 - bit.bit_length())
            imm32(1, PAL + PAL_OFF)
            E(b_cond, f"sl_c{pad}", "pl")
            E(subs_imm8, 1, PAL_OFF - PAL_ON)
            a.label(f"sl_c{pad}")
            E(ldrh_imm, 0, 1, 0)
            E(strh_imm, 0, 5, 2 * pad)
        a.label("sl_x")
        E(pop_list, [3, 4, 5], pc=True)
    return a.assemble()


def install(img, report, base_addr, sm=0):
    """sm: after fshape with sm; 1 = pad 21 (the end fade), 2 = + pad 20 (fshape's drone, else its de-click), 3 = + pad 19 (the crossfade)"""
    import rhbuild
    BASE = rhbuild.BASE
    assert int.from_bytes(img[SMP_VT - BASE:SMP_VT - BASE + 4], "little") == SMP_PAD | 1, "Sample mode's slot 0 is not the stock's"
    base_addr = (base_addr + 3) & ~3
    smd, prev = None, None
    if sm:
        import fshape
        fs = report["fshape"]
        assert fs.get("sm"), "sm: fshape with sm"
        pads = ((PAD_XF, fshape.SM_XF), (PAD_RD, fshape.SM_DR if fs.get("drone") else fshape.SM_RD), (PAD_EF, fshape.SM_EF))[3 - sm:]
        assert sm < 2 or fs.get("declick") or fs.get("drone"), "sm=2: fshape with declick or drone"
        assert sm < 3 or fs.get("loopxf"), "sm=3: fshape with loopxf"
        smd = dict(v=fs["sm0"], pads=pads, val=int(fs["labels"]["c_fsval"], 16), put=int(fs["labels"]["c_fsput"], 16))
        prev = rhbuild.bl_target(img, CI.LED_CALLS[0])
        assert all(rhbuild.bl_target(img, c) == prev for c in CI.LED_CALLS)
    code, labels = arm_code(base_addr, smd, prev)
    img += bytes([0xFF]) * (base_addr - BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    rhbuild.patch_word(img, SMP_VT, SMP_PAD | 1, labels["c_smpad"] | 1)
    if sm:
        for c in CI.LED_CALLS:
            rhbuild.patch(img, c, f"bl #{prev:#x}", bl(c, labels["c_smled"]))
    report["smpads"] = dict(clear_fit_reset=True, labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")},
                            **(dict(sm=True, pads={str(p): b for p, b in smd["pads"]}, prev_led=hex(prev)) if sm else {}))
    return labels, code
