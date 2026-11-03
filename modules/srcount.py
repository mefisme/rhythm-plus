"""A count-in before sample recording, set on pads 23 and 24 of the Sample Rec view (MIT; Circuit Rhythm 5706).

  * pad 23 (row 3, the Fixed Recording row's free 7th pad): count-in off (dim) or on (green), its clicks at the metronome's level (K5);
  * pad 24 (its 8th pad): start the sequencer with the recording (cyan) or not (dim);
  * with pad 23 on, Record in the Sample Rec view (the sampler ready, Shift up, no count running) starts clkci's count of one bar on the
    music's clock; with pad 24 on and the sequencer stopped it is a gated count (Play pressed at once, the music and the sampler both start on
    the bar's end), else the sampler alone starts there (threshold on waits for sound, off records at once).
    Record again, in any view, cancels the count (and stops a held start) and does nothing else.
The stock (read on the device): the view [ctrl + 0x7C] is 0x2004DC90 (vtable 0x08067A08) in the Sample Rec view; the sampler 0x200484F0
(vtable 0x08068B38), [+ 0x14] p0 = its state (0 cannot, 1 ready, 2 armed, 3 recording; 1 in the other views too); Record in the Sample Rec
view fires the sampler's event [+ 8], whose handler (vtable [0] 0x0803CABE) calls 0x0803CC2A(sampler) (ready -> armed); the Fixed Recording row
0x2004DE78 (vtable 0x080681B4: [0] = its pad press 0x080596C0(row, 0-7), 5-7 unused), its 8 LED codes at [[row + 4]], shown as pads 17-24.
RAM: our block's slot "srcount": + 0 pad 23's state, + 1 pad 24's.  Install after clkci.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, adds_imm8, b, b_cond, b_w, bl, cmp_imm, cmp_reg, eors_reg, ldr_imm, ldrb_imm, ldrb_w, mov_reg, movs_imm,  # noqa: E402
                   movt, movw, pop_list, push_list, raw, strb_imm, strh_imm, tst_reg)
import clkci as K  # noqa: E402
import countin as C  # noqa: E402
import rhstate  # noqa: E402

ID_REC = 16
SR_VIEW_VT = 0x08067A08
SAMPLER, O_SSTATE, REC_FN = K.SAMPLER, K.O_SSTATE, K.REC_FN
ROW, ROW_VT, ROW_PRESS = 0x2004DE78, 0x080681B4, 0x080596C0
PAD_MODE, PAD_PLAY = 6, 7                              # indexes in the row: pads 23, 24
MODE_COLS = (0x09, 0x1E)                               # off dim, on green
PLAY_COLS = (0x09, 0x4B)                               # off dim, on cyan
O_MODE, O_PLAY = (rhstate.OFF.get("srcount", (0, 0))[0] + k for k in (0, 1))   # no slot: a build without srcount


def arm_code(base, L):
    a = Asm(base)
    E = a.emit

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, v >> 16)

    # ---- c_srok() -> r0 = 1 in the Sample Rec view with the sampler ready; clobbers r1-r3
    a.label("c_srok")
    E(push_list, [3], lr=True)
    imm32(0, C.CTRL)
    E(ldr_imm, 0, 0, 0x7C)
    E(cmp_imm, 0, 0)
    E(b_cond, "ok_no", "eq")
    E(ldr_imm, 0, 0, 0)
    imm32(1, SR_VIEW_VT)
    E(cmp_reg, 0, 1)
    E(b_cond, "ok_no", "ne")
    E(bl, L["c_ckready"])
    E(pop_list, [3], pc=True)
    a.label("ok_no")
    E(movs_imm, 0, 0)
    E(pop_list, [3], pc=True)

    # ---- c_srpad (the row's pad press: r0 = row, r1 = 0-7): pads 23 / 24 ours, the rest the stock's
    a.label("c_srpad")
    E(cmp_imm, 1, PAD_MODE)
    E(b_cond, "sp_stock", "lo")
    E(push_list, [0, 1, 2, 3, 4], lr=True)
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    E(b_cond, "sp_f", "eq")
    E(mov_reg, 4, 0)
    E(raw, b"\x01\x99")                                # ldr r1, [sp, #4]: the pad
    E(cmp_imm, 1, PAD_MODE)
    E(b_cond, "sp_play", "ne")
    E(ldrb_imm, 0, 4, O_MODE)
    E(adds_imm8, 0, 1)
    E(cmp_imm, 0, len(MODE_COLS))
    E(b_cond, "sp_m", "lo")
    E(movs_imm, 0, 0)
    a.label("sp_m")
    E(strb_imm, 0, 4, O_MODE)
    E(b, "sp_x")
    a.label("sp_play")
    E(cmp_imm, 1, PAD_PLAY)
    E(b_cond, "sp_f", "ne")
    E(ldrb_imm, 0, 4, O_PLAY)
    E(movs_imm, 1, 1)
    E(eors_reg, 0, 1)
    E(strb_imm, 0, 4, O_PLAY)
    a.label("sp_x")
    E(pop_list, [0, 1, 2, 3, 4], pc=True)
    a.label("sp_f")
    E(raw, C.popw([0, 1, 2, 3, 4], lr=True))
    a.label("sp_stock")
    E(b_w, ROW_PRESS)

    # ---- c_srbtn (a head of the button chain: r0 = ctrl, r1 = id)
    a.label("c_srbtn")
    E(cmp_imm, 1, ID_REC)
    E(b_cond, "sb_g", "ne")
    E(push_list, [0, 1, 2, 4, 5], lr=True)
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    E(b_cond, "sb_f", "eq")
    E(mov_reg, 4, 0)
    E(ldrb_w, 5, 4, K.O_FL)
    E(movs_imm, 0, K.SAMP)
    E(tst_reg, 5, 0)
    E(b_cond, "sb_new", "eq")
    E(bl, L["c_ckcancel"])                             # Record during the count, in any view: cancelled, never the stock's
    E(b, "sb_x")
    a.label("sb_new")
    E(cmp_imm, 5, 0)
    E(b_cond, "sb_f", "ne")                            # the sequencer's count is running
    E(ldrb_imm, 0, 4, O_MODE)
    E(cmp_imm, 0, 0)
    E(b_cond, "sb_f", "eq")
    E(bl, L["c_ciok"])
    E(cmp_imm, 0, 0)
    E(b_cond, "sb_f", "eq")
    E(bl, "c_srok")
    E(cmp_imm, 0, 0)
    E(b_cond, "sb_f", "eq")
    E(bl, L["c_cishift"])
    E(cmp_imm, 0, 0)
    E(b_cond, "sb_f", "ne")                            # Shift + Record: the stock's
    E(movs_imm, 5, K.SAMP)
    E(ldrb_imm, 0, 4, O_PLAY)
    E(cmp_imm, 0, 0)
    E(b_cond, "sb_go", "eq")
    imm32(0, C.TRANSPORT)
    E(movs_imm, 1, 0)
    E(bl, L["c_cinew"])
    E(cmp_imm, 0, 0)
    E(b_cond, "sb_go", "ne")                           # playing already: the sampler alone
    E(movs_imm, 5, K.SAMP | K.GATE | K.PLAYQ)
    a.label("sb_go")
    E(mov_reg, 0, 5)
    E(bl, L["c_ckbegin"])
    a.label("sb_x")
    E(pop_list, [0, 1, 2, 4, 5], pc=True)
    a.label("sb_f")
    E(raw, C.popw([0, 1, 2, 4, 5], lr=True))
    a.label("sb_g")
    E(b_w, L["prev_btn"])

    # ---- c_srled (a new head of the LED task's chain: r0 = ctrl, r1 = frame): pads 23 and 24 in the row's codes (shown only in the Sample Rec view)
    a.label("c_srled")
    E(push_list, [4], lr=True)
    E(bl, L["prev_led"])
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    E(b_cond, "sl_x", "eq")
    E(mov_reg, 4, 0)
    imm32(0, ROW)
    E(ldr_imm, 1, 0, 0)
    imm32(2, ROW_VT)
    E(cmp_reg, 1, 2)
    E(b_cond, "sl_x", "ne")
    E(ldr_imm, 0, 0, 4)
    E(ldr_imm, 0, 0, 0)
    E(ldrb_imm, 1, 4, O_MODE)
    E(movs_imm, 2, MODE_COLS[0])
    E(cmp_imm, 1, 0)
    E(b_cond, "sl_m", "eq")
    E(movs_imm, 2, MODE_COLS[1])
    a.label("sl_m")
    E(strh_imm, 2, 0, 2 * PAD_MODE)
    E(ldrb_imm, 1, 4, O_PLAY)
    E(movs_imm, 2, PLAY_COLS[0])
    E(cmp_imm, 1, 0)
    E(b_cond, "sl_p", "eq")
    E(movs_imm, 2, PLAY_COLS[1])
    a.label("sl_p")
    E(strh_imm, 2, 0, 2 * PAD_PLAY)
    a.label("sl_x")
    E(pop_list, [4], pc=True)
    return a.assemble()


def install(img, report, base_addr):
    import rh_fw
    import rhbuild
    L = {k: int(v, 16) for k, v in report["countin"]["labels"].items()}
    L["c_rst"] = int(report["rhstate"]["labels"]["c_rst"], 16)
    L.update({k: int(v, 16) for k, v in report["clkci"]["labels"].items()})
    L["prev_btn"] = rhbuild.bw_target(img, C.BTN_ENTRY)
    L["prev_led"] = rhbuild.bl_target(img, C.LED_CALLS[0])
    assert all(rhbuild.bl_target(img, c) == L["prev_led"] for c in C.LED_CALLS)
    code, labels = arm_code(base_addr, L)
    img += bytes([0xFF]) * (base_addr - rh_fw.APP_BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    rhbuild.patch(img, C.BTN_ENTRY, f"b.w #{L['prev_btn']:#x}", b_w(C.BTN_ENTRY, labels["c_srbtn"]))
    for c in C.LED_CALLS:
        rhbuild.patch(img, c, f"bl #{L['prev_led']:#x}", bl(c, labels["c_srled"]))
    rhbuild.patch_word(img, ROW_VT, ROW_PRESS | 1, labels["c_srpad"] | 1)
    report["srcount"] = dict(slot=hex(rhstate.ST + rhstate.OFF["srcount"][0]), prev_btn=hex(L["prev_btn"]), prev_led=hex(L["prev_led"]),
                             labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
