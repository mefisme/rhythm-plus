"""The paused playhead: while stopped, the step it will continue from fades between its colour and white (MIT; Circuit Rhythm 5706).

As the Tracks' synth step views: one white peak every 510 ms (the stock fade codes, 0x0803E3A4 with the triangle tables 0x08066D30 /
0x08066D90).  Not before the first Play since power-on (step 1 then says nothing).
The stock (read on the device and in the firmware):
  * the view manager [ctrl + 0x7C] (vtable 0x080678DC): byte + 0x264 = the mode; in modes 0-3, 5, 6 the top 16 pads are the step view
    [mgr + 0x74 + 4 * track] of the selected track (0x0804DC50; the track = 0x0805800E(mgr));
  * a step view (vtable 0x080682CC): [obj + 0x1C] p1 = the track's current step 0-31, kept after Stop (what Shift + Play continues from);
    [obj + 0x60] p0 = the page shown (steps 17-32); [[obj + 4]] = its 32 pad codes;
  * 0x0803E8E6(ctrl, out, frame) turns the frame's codes into the LEDs' RGB words (pads 0-59 dimmed by 0x8D00 / 2^16 when bit 10 of
    [ctrl + 0x88] p2 is set).
c_phconv takes the conversion's call (0x0803E802): after it, while stopped, when the top pads are that step view's page and the step is on
it, the pad's RGB is mixed with white (dimmed as the pads).  While playing it marks our RAM block's slot "pausehd".
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, adds_imm8, adds_reg, ands_reg, b, b_cond, bl, cmp_imm, cmp_reg, ldr_imm, ldrb_imm, ldrb_w, ldrh_reg, lsls_imm,  # noqa: E402
                   lsrs_imm, lsrs_reg, mov_reg, movs_imm, movt, movw, muls, pop_list, push_list, raw, strb_imm, subs_reg)
import countin as C  # noqa: E402
import rhstate  # noqa: E402

CONV, CONV_CALL = 0x0803E8E6, 0x0803E802
MGR_VT, STEP_VT, CUR_TRACK = 0x080678DC, 0x080682CC, 0x0805800E
O_VIEW, O_MODE, O_STEPVIEWS = 0x7C, 0x264, 0x74
O_BUF, O_STEP, O_PAGE = 4, 0x1C, 0x60
MODES = 0x6F                                           # bit m: mode m shows the step view on the top pads
DIM_STORE, DIM_BIT, DIM_WHITE = 0x88, 10, 0xFF * 0x8D00 >> 16
FADE_MS = 510                                          # one white peak per FADE_MS


def arm_code(base):
    slot = rhstate.OFF["pausehd"][0]
    a = Asm(base)
    E = a.emit

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, v >> 16)

    a.label("c_phconv")                                # (r0 = ctrl, r1 = out, r2 = frame): the stock conversion, then the paused step
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    E(mov_reg, 5, 1)
    E(mov_reg, 6, 2)
    E(bl, CONV)
    imm32(7, rhstate.ST)                               # r7 = our block, set up
    imm32(1, rhstate.HEAP_LIMIT_PTR)
    E(ldr_imm, 1, 1, 0)
    E(cmp_reg, 1, 7)
    E(b_cond, "ph_x", "ne")
    E(ldr_imm, 1, 7, 0)
    imm32(2, rhstate.MAGIC)
    E(cmp_reg, 1, 2)
    E(b_cond, "ph_x", "ne")
    imm32(0, C.TRANSPORT)
    E(movs_imm, 1, 0)
    E(bl, C.PARAM_NEW)
    E(ldrb_imm, 0, 0, 0)
    E(cmp_imm, 0, 0)
    E(b_cond, "ph_stop", "eq")
    E(movs_imm, 0, 1)
    E(strb_imm, 0, 7, slot)                            # played since power-on
    E(b, "ph_x")
    a.label("ph_stop")
    E(ldrb_imm, 0, 7, slot)
    E(cmp_imm, 0, 0)
    E(b_cond, "ph_x", "eq")
    imm32(4, C.CTRL)                                   # r4 = the view manager
    E(ldr_imm, 4, 4, O_VIEW)
    E(cmp_imm, 4, 0)
    E(b_cond, "ph_x", "eq")
    E(ldr_imm, 0, 4, 0)
    imm32(1, MGR_VT)
    E(cmp_reg, 0, 1)
    E(b_cond, "ph_x", "ne")
    E(ldrb_w, 1, 4, O_MODE)
    E(cmp_imm, 1, 6)
    E(b_cond, "ph_x", "hi")
    E(movs_imm, 0, MODES)
    E(lsrs_reg, 0, 1)
    E(lsls_imm, 0, 0, 31)
    E(b_cond, "ph_x", "pl")                            # the top pads are not a step view
    E(mov_reg, 0, 4)
    E(bl, CUR_TRACK)
    E(cmp_imm, 0, 7)
    E(b_cond, "ph_x", "hi")
    E(lsls_imm, 0, 0, 2)
    E(adds_reg, 0, 0, 4)
    E(ldr_imm, 4, 0, O_STEPVIEWS)                      # r4 = the track's step view
    E(ldr_imm, 0, 4, 0)
    imm32(1, STEP_VT)
    E(cmp_reg, 0, 1)
    E(b_cond, "ph_x", "ne")
    E(ldr_imm, 0, 4, O_PAGE)
    E(movs_imm, 1, 0)
    E(bl, C.PARAM_GET)
    E(ldrb_imm, 7, 0, 0)
    E(cmp_imm, 7, 0)
    E(b_cond, "ph_pg", "eq")
    E(movs_imm, 7, 1)
    a.label("ph_pg")                                   # r7 = the page, 0 / 1
    E(ldr_imm, 0, 4, O_STEP)
    E(movs_imm, 1, 1)
    E(bl, C.PARAM_GET)
    E(ldrb_imm, 3, 0, 0)                               # r3 = the step
    E(cmp_imm, 3, 31)
    E(b_cond, "ph_x", "hi")
    E(lsrs_imm, 0, 3, 4)
    E(cmp_reg, 0, 7)
    E(b_cond, "ph_x", "ne")                            # on the other page
    E(ldr_imm, 0, 4, O_BUF)
    E(ldr_imm, 0, 0, 0)
    E(lsls_imm, 7, 7, 5)
    E(adds_reg, 0, 0, 7)                               # r0 = the page's 16 codes
    E(movs_imm, 1, 0)
    a.label("ph_cmp")
    E(ldrh_reg, 2, 0, 1)
    E(ldrh_reg, 7, 6, 1)
    E(cmp_reg, 2, 7)
    E(b_cond, "ph_x", "ne")                            # the top pads show something else
    E(adds_imm8, 1, 2)
    E(cmp_imm, 1, 32)
    E(b_cond, "ph_cmp", "lo")
    E(b, "ph_mix")
    a.label("ph_x")
    E(pop_list, [3, 4, 5, 6, 7], pc=True)
    a.label("ph_mix")
    E(movs_imm, 0, 15)
    E(ands_reg, 3, 0)
    E(lsls_imm, 3, 3, 2)
    E(adds_reg, 5, 5, 3)                               # r5 = the pad's RGB word
    imm32(0, C.HAL_TICK)                               # r7 = the white weight 0..255..0 over FADE_MS
    E(ldr_imm, 0, 0, 0)
    E(movw, 1, FADE_MS)
    E(raw, C.udiv(2, 0, 1))
    E(muls, 2, 1)
    E(subs_reg, 0, 0, 2)
    E(cmp_imm, 0, 255)
    E(b_cond, "ph_f", "ls")
    E(subs_reg, 0, 1, 0)
    a.label("ph_f")
    E(mov_reg, 7, 0)
    E(movs_imm, 6, 0xFF)                               # r6 = white, dimmed as the pads
    imm32(0, C.CTRL + DIM_STORE)
    E(ldr_imm, 0, 0, 0)
    E(movs_imm, 1, 2)
    E(bl, C.PARAM_GET)
    E(ldr_imm, 0, 0, 0)
    E(lsls_imm, 0, 0, 31 - DIM_BIT)
    E(b_cond, "ph_w", "pl")
    E(movs_imm, 6, DIM_WHITE)
    a.label("ph_w")
    E(movs_imm, 3, 0xFF)
    E(subs_reg, 3, 3, 7)                               # r3 = the colour's weight
    for k in range(3):                                 # channel = (colour * (255 - w) + white * w) / 255
        E(ldrb_imm, 0, 5, k)
        E(muls, 0, 3)
        E(mov_reg, 1, 6)
        E(muls, 1, 7)
        E(adds_reg, 0, 0, 1)
        E(lsrs_imm, 1, 0, 8)
        E(adds_reg, 0, 0, 1)
        E(adds_imm8, 0, 1)
        E(lsrs_imm, 0, 0, 8)
        E(strb_imm, 0, 5, k)
    E(b, "ph_x")
    return a.assemble()


def install(img, report, base_addr):
    import rh_fw
    import rhbuild
    code, labels = arm_code(base_addr)
    img += bytes([0xFF]) * (base_addr - rh_fw.APP_BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    rhbuild.patch(img, CONV_CALL, f"bl #{CONV:#x}", bl(CONV_CALL, labels["c_phconv"]))
    report["pausehead"] = dict(slot=hex(rhstate.ST + rhstate.OFF["pausehd"][0]), labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
