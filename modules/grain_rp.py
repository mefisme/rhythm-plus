"""Circuit Remix's granular (tools/granular0.py on DSP core 0, unchanged) driven from Track + (MIT; Circuit Rhythm 5706).

One granular track at a time.  Its 12 values (14 bits, as the stock's knobs) and the track travel with the project in the record's
tail, in Circuit Remix's own block (rhrec "granpage": "GP", a check byte, the track + 1 (0 = off), 0, 0, 12 halfwords), so a project
moves between the two firmwares with its granular.  Values 0-7 = K1-K8 (size, density, position, scan, pitch, position spray, pitch
spray, window), 8-11 = Shift + K5-K8 (fine pitch, zone, reverse chance, gate).

  * c_grval(r0 = track, r1 = k) -> the value; c_grput(r0 = track, r1 = k, r2 = value); c_grdirty(r0 = track): Stock+'s
    signatures (the track is not used: one set of values), so Track +'s own-value page code serves both;
  * c_grtrk() -> the track + 1 (0 = off); c_grset(r0 = track + 1); c_grreset(): the 12 defaults;
  * c_grframe() (the LED task, each frame): while core 0 holds the mode 0 program (dspready's READY), the engine's words to core 0
    (X:$1400 + its control: the 12 values, the key, the track, the note last), all of them after a change or after a new upload,
    else two a frame in turn;
  * c_grnote (in place of the DSP note-on's bl TRIG): the granular track's note to the engine at once, then TRIG.
RAM: rhstate "grain": + 0 pending (1 = all words), + 1 the round's next word, + 2 1 = READY seen since the last upload.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, adds_imm8, adds_reg, b, b_cond, bl, b_w, cmp_imm, cmp_reg, eors_reg, h, ldrb_imm, ldrb_reg, ldrh_imm,  # noqa: E402
                   lsls_imm, lsrs_imm, mov_reg, movs_imm, movt, movw, muls, orrs_reg, pop_list, push_list, raw, strb_imm, strh_imm,
                   subs_imm8, subs_reg)
import countin as CI  # noqa: E402
import granular0 as G  # noqa: E402
import rhrec  # noqa: E402
import rhstate  # noqa: E402

WR16, READY = 0x08031200, 0xA0                             # cthresh's (core, value << 8, address); dspready's READY
NOTE_ON_BL, TRIG = 0x080407E6, 0x080406A8                  # the DSP note-on 0x08040778: its trigger {w0, w1} (w0 & 7 = the track,
CUR_NOTE = 0x20006D90                                      #   w1 = (note - 60) << 16); the track's current note at + t (0xFF = none)
BLK, BLK_LEN = rhrec.OFF["granpage"]
MARK0, MARK1, CHECK = ord("G"), ord("P"), 0x5A
NK = 12
#        size  dens  pos  scan pitch  spr  pspr  win | fine  zone  rev  gate
DEF = (8192, 6528, 0, 9216, 8192, 0, 0, 8192, 8192, 16256, 0, 16383)
MUL = (128, 101, 128, 128, 48, 128, 128, 101, 128, 128, 128, 2)   # the engine's value = (v >> 7) x MUL >> 7 - OFFS
OFFS = (0, 0, 0, 64, 24, 0, 0, 0, 64, 0, 0, 0)
IDX = (G.P_SIZE, G.P_DENS, G.P_POS, G.P_SCAN, G.P_PITCH, G.P_SPR, G.P_PSPR, G.P_WIN, G.P_FINE, G.P_ZONE, G.P_REV, G.P_GATE)
BIP = (0, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 0)                 # shown from the middle
NW = NK + 3                                                # the words: 12 values, the key, the track, the note
W_KEY, W_TRK, W_NOTE = NK, NK + 1, NK + 2
O_PEND, O_ROUND, O_SEEN = 0, 1, 2


def model_engine(v, k):
    """the engine's value of value k at the 14-bit v (as c_grw computes it)"""
    return (((v >> 7) * MUL[k]) >> 7) - OFFS[k]


def model_block(trk1, vals):
    """the project's block for the track + 1 and the 12 values (the tests')"""
    b_ = bytearray(BLK_LEN)
    b_[0], b_[1], b_[3] = MARK0, MARK1, trk1
    for k, v in enumerate(vals):
        b_[6 + 2 * k:8 + 2 * k] = v.to_bytes(2, "little")
    c = CHECK
    for x in b_[3:]:
        c ^= x
    b_[2] = c
    return bytes(b_)


def arm_code(base, L):
    O = rhstate.OFF["grain"][0]
    O_TH = rhstate.OFF["cthresh"][0] + 1
    a = Asm(base)
    E = a.emit
    zc = [0]

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, (v >> 16) & 0xFFFF)

    def local():
        zc[0] += 1
        return f"_r{zc[0]}"

    t_def = base
    E(raw, b"".join(v.to_bytes(2, "little") for v in DEF))
    t_mul = t_def + 2 * NK
    E(raw, bytes(MUL) + bytes(OFFS) + bytes(IDX))
    t_off, t_idx = t_mul + NK, t_mul + 2 * NK                # 24 + 36 B: the code stays half-word aligned

    # ---- c_grst() -> r0 = our state, 0 without our RAM; clobbers r1-r3
    a.label("c_grst")
    E(push_list, [4], lr=True)
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    E(b_cond, "gs_x", "eq")
    E(movw, 1, O)
    E(adds_reg, 0, 0, 1)
    a.label("gs_x")
    E(pop_list, [4], pc=True)

    # ---- c_grblk() -> r0 = the block's place in the record's tail, 0 without the record; clobbers r1-r3
    a.label("c_grblk")
    E(push_list, [4], lr=True)
    E(bl, L["c_rrt"])
    E(cmp_imm, 0, 0)
    E(b_cond, "gb_x", "eq")
    E(movw, 1, BLK)
    E(adds_reg, 0, 0, 1)
    a.label("gb_x")
    E(pop_list, [4], pc=True)

    # ---- c_grsum(r0 = block) -> r0 = its check byte (bytes 3 .. BLK_LEN - 1); clobbers r1-r3
    a.label("c_grsum")
    E(adds_imm8, 0, 3)
    E(movs_imm, 1, BLK_LEN - 3)
    E(movs_imm, 2, CHECK)
    a.label("gu_l")
    E(ldrb_imm, 3, 0, 0)
    E(eors_reg, 2, 3)
    E(adds_imm8, 0, 1)
    E(subs_imm8, 1, 1)
    E(b_cond, "gu_l", "ne")
    E(mov_reg, 0, 2)
    E(raw, h(0x4770))

    # ---- c_grb() -> r0 = the block when it holds granular values, else 0; clobbers r1-r3
    a.label("c_grb")
    E(push_list, [4], lr=True)
    E(bl, "c_grblk")
    E(cmp_imm, 0, 0)
    E(b_cond, "gk_x", "eq")
    E(mov_reg, 4, 0)
    E(ldrb_imm, 1, 4, 0)
    E(cmp_imm, 1, MARK0)
    E(b_cond, "gk_0", "ne")
    E(ldrb_imm, 1, 4, 1)
    E(cmp_imm, 1, MARK1)
    E(b_cond, "gk_0", "ne")
    E(bl, "c_grsum")
    E(ldrb_imm, 1, 4, 2)
    E(cmp_reg, 0, 1)
    E(b_cond, "gk_0", "ne")
    E(mov_reg, 0, 4)
    E(pop_list, [4], pc=True)
    a.label("gk_0")
    E(movs_imm, 0, 0)
    a.label("gk_x")
    E(pop_list, [4], pc=True)

    # ---- c_grfix(r0 = block): its check byte again; clobbers r0-r3
    a.label("c_grfix")
    E(push_list, [4], lr=True)
    E(mov_reg, 4, 0)
    E(bl, "c_grsum")
    E(strb_imm, 0, 4, 2)
    E(pop_list, [4], pc=True)

    # ---- c_grinit() -> r0 = the block, made with the defaults (off) if missing; 0 without the record; clobbers r1-r3
    a.label("c_grinit")
    E(push_list, [4, 5, 6], lr=True)
    E(bl, "c_grb")
    E(cmp_imm, 0, 0)
    E(b_cond, "gi_x", "ne")
    E(bl, "c_grblk")
    E(cmp_imm, 0, 0)
    E(b_cond, "gi_x", "eq")
    E(mov_reg, 4, 0)
    E(movs_imm, 0, MARK0)
    E(strb_imm, 0, 4, 0)
    E(movs_imm, 0, MARK1)
    E(strb_imm, 0, 4, 1)
    E(movs_imm, 0, 0)
    E(strb_imm, 0, 4, 3)
    E(strb_imm, 0, 4, 4)
    E(strb_imm, 0, 4, 5)
    E(bl, "c_grdefs")
    E(mov_reg, 0, 4)
    a.label("gi_x")
    E(pop_list, [4, 5, 6], pc=True)

    # ---- c_grdefs(r4 = block): the 12 defaults into it, its check byte; clobbers r0-r3, r5
    a.label("c_grdefs")
    E(push_list, [4, 5], lr=True)
    E(movs_imm, 5, 0)
    a.label("gf_l")
    imm32(0, t_def)
    E(lsls_imm, 1, 5, 1)
    E(adds_reg, 0, 0, 1)
    E(ldrh_imm, 0, 0, 0)
    E(adds_reg, 1, 4, 1)
    E(strh_imm, 0, 1, 6)
    E(adds_imm8, 5, 1)
    E(cmp_imm, 5, NK)
    E(b_cond, "gf_l", "lo")
    E(mov_reg, 0, 4)
    E(bl, "c_grfix")
    E(pop_list, [4, 5], pc=True)

    # ---- c_grreset(): the 12 defaults (the track kept), all words pushed; clobbers r0-r3
    a.label("c_grreset")
    E(push_list, [4], lr=True)
    E(bl, "c_grinit")
    E(cmp_imm, 0, 0)
    E(b_cond, "gr_x", "eq")
    E(mov_reg, 4, 0)
    E(bl, "c_grdefs")
    E(bl, "c_grdirty")
    a.label("gr_x")
    E(pop_list, [4], pc=True)

    # ---- c_grval(r0 = track, unused; r1 = k) -> r0 = its value (the default without the block); clobbers r1-r3
    a.label("c_grval")
    E(push_list, [4, 5], lr=True)
    E(mov_reg, 5, 1)
    E(bl, "c_grb")
    E(lsls_imm, 1, 5, 1)
    E(cmp_imm, 0, 0)
    E(b_cond, "gv_d", "eq")
    E(adds_reg, 0, 0, 1)
    E(ldrh_imm, 0, 0, 6)
    E(pop_list, [4, 5], pc=True)
    a.label("gv_d")
    imm32(0, t_def)
    E(adds_reg, 0, 0, 1)
    E(ldrh_imm, 0, 0, 0)
    E(pop_list, [4, 5], pc=True)

    # ---- c_grput(r0 = track, unused; r1 = k, r2 = value); clobbers r0-r3
    a.label("c_grput")
    E(push_list, [4, 5, 6], lr=True)
    E(mov_reg, 5, 1)
    E(mov_reg, 6, 2)
    E(bl, "c_grinit")
    E(cmp_imm, 0, 0)
    E(b_cond, "gp_x", "eq")
    E(mov_reg, 4, 0)
    E(lsls_imm, 1, 5, 1)
    E(adds_reg, 1, 4, 1)
    E(strh_imm, 6, 1, 6)
    E(mov_reg, 0, 4)
    E(bl, "c_grfix")
    a.label("gp_x")
    E(pop_list, [4, 5, 6], pc=True)

    # ---- c_grtrk() -> r0 = the granular track + 1 (0 = off, also without the block); clobbers r1-r3
    a.label("c_grtrk")
    E(push_list, [4], lr=True)
    E(bl, "c_grb")
    E(cmp_imm, 0, 0)
    E(b_cond, "gt_x", "eq")
    E(ldrb_imm, 0, 0, 3)
    E(cmp_imm, 0, 8)
    E(b_cond, "gt_x", "ls")
    E(movs_imm, 0, 0)
    a.label("gt_x")
    E(pop_list, [4], pc=True)

    # ---- c_grset(r0 = track + 1, 0 = off): the granular track, all words pushed; clobbers r0-r3
    a.label("c_grset")
    E(push_list, [4, 5], lr=True)
    E(mov_reg, 5, 0)
    E(bl, "c_grinit")
    E(cmp_imm, 0, 0)
    E(b_cond, "ge_x", "eq")
    E(mov_reg, 4, 0)
    E(strb_imm, 5, 4, 3)
    E(bl, "c_grfix")
    E(bl, "c_grdirty")
    a.label("ge_x")
    E(pop_list, [4, 5], pc=True)

    # ---- c_grdirty(r0 = track, unused): all words pushed at the next frame; clobbers r0-r3
    a.label("c_grdirty")
    E(push_list, [4], lr=True)
    E(bl, "c_grst")
    E(cmp_imm, 0, 0)
    E(b_cond, "gd_x", "eq")
    E(movs_imm, 1, 1)
    E(strb_imm, 1, 0, O_PEND)
    a.label("gd_x")
    E(pop_list, [4], pc=True)

    # ---- c_grw(r0 = i 0 .. NW - 1): the engine's word i to core 0; clobbers r0-r3
    a.label("c_grw")
    E(push_list, [4], lr=True)
    E(mov_reg, 4, 0)
    E(cmp_imm, 4, NK)
    E(b_cond, "gw_k", "hs")
    E(mov_reg, 1, 4)
    E(bl, "c_grval")
    E(lsrs_imm, 0, 0, 7)
    imm32(1, t_mul)
    E(ldrb_reg, 1, 1, 4)
    E(muls, 0, 1)
    E(lsrs_imm, 0, 0, 7)
    imm32(1, t_off)
    E(ldrb_reg, 1, 1, 4)
    E(subs_reg, 0, 0, 1)
    imm32(1, t_idx)
    E(ldrb_reg, 1, 1, 4)
    E(movw, 2, G.GB)
    E(adds_reg, 1, 1, 2)
    E(b, "gw_w")
    a.label("gw_k")
    E(cmp_imm, 4, W_KEY)
    E(b_cond, "gw_t", "ne")
    imm32(0, G.KEY)
    E(movw, 1, G.GB + G.P_KEY)
    E(b, "gw_w")
    a.label("gw_t")
    E(cmp_imm, 4, W_TRK)
    E(b_cond, "gw_n", "ne")
    E(bl, "c_grtrk")
    E(movw, 1, G.GB + G.P_TRK)
    E(b, "gw_w")
    a.label("gw_n")                                          # the granular track's current note - 60 (no note now: the engine keeps its last)
    E(bl, "c_grtrk")
    E(cmp_imm, 0, 0)
    E(b_cond, "gw_x", "eq")
    imm32(1, CUR_NOTE - 1)
    E(ldrb_reg, 0, 1, 0)
    E(cmp_imm, 0, 0x80)
    E(b_cond, "gw_x", "hs")
    E(subs_imm8, 0, 60)
    E(movw, 1, G.GB + G.P_NOTE)
    a.label("gw_w")                                          # WR16(core 0, word << 8, X address)
    E(lsls_imm, 0, 0, 8)
    E(mov_reg, 2, 1)
    E(mov_reg, 1, 0)
    E(movs_imm, 0, 0)
    E(bl, WR16)
    a.label("gw_x")
    E(pop_list, [4], pc=True)

    # ---- c_grframe(): the engine's words to core 0 (the mode 0 program only); clobbers r0-r3
    a.label("c_grframe")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(bl, L["c_ciok"])
    E(cmp_imm, 0, 0)
    E(b_cond, "gl_xx", "eq")
    E(bl, "c_grst")
    E(cmp_imm, 0, 0)
    E(b_cond, "gl_xx", "eq")
    E(mov_reg, 6, 0)                                         # r6 = our state
    E(bl, L["c_rst"])
    E(movw, 1, O_TH)
    E(adds_reg, 0, 0, 1)
    E(ldrb_imm, 0, 0, 0)
    E(cmp_imm, 0, READY)
    E(b_cond, "gl_up", "eq")
    E(movs_imm, 0, 0)                                        # not the mode 0 program: no words; all of them once it is back
    E(strb_imm, 0, 6, O_SEEN)
    E(b, "gl_xx")
    a.label("gl_up")
    E(ldrb_imm, 0, 6, O_SEEN)
    E(cmp_imm, 0, 0)
    E(b_cond, "gl_sn", "ne")
    E(movs_imm, 0, 1)
    E(strb_imm, 0, 6, O_SEEN)
    E(strb_imm, 0, 6, O_PEND)
    a.label("gl_sn")
    E(ldrb_imm, 0, 6, O_PEND)
    E(cmp_imm, 0, 0)
    E(b_cond, "gl_rd", "eq")
    E(movs_imm, 0, 0)
    E(strb_imm, 0, 6, O_PEND)
    E(movs_imm, 4, 0)                                        # a change: all the words, the track and the note last
    a.label("gl_al")
    E(mov_reg, 0, 4)
    E(bl, "c_grw")
    E(adds_imm8, 4, 1)
    E(cmp_imm, 4, NW)
    E(b_cond, "gl_al", "lo")
    E(b, "gl_xx")
    a.label("gl_rd")
    for _ in range(2):                                       # else two a frame in turn
        E(ldrb_imm, 4, 6, O_ROUND)
        E(mov_reg, 0, 4)
        E(bl, "c_grw")
        E(adds_imm8, 4, 1)
        E(cmp_imm, 4, NW)
        n = local()
        E(b_cond, n, "lo")
        E(movs_imm, 4, 0)
        a.label(n)
        E(strb_imm, 4, 6, O_ROUND)
    a.label("gl_xx")
    E(pop_list, [4, 5, 6, 7], pc=True)

    # ---- c_grnote (in place of the DSP note-on's bl TRIG: r0 = {w0, w1}): the granular track's note to the engine at once, then TRIG
    a.label("c_grnote")
    E(push_list, [0, 4, 5], lr=True)
    E(raw, h(0x6804))                                        # ldr r4, [r0]: w0
    E(raw, h(0x6845))                                        # ldr r5, [r0, #4]: w1 = (note - 60) << 16
    E(bl, "c_grtrk")
    E(subs_imm8, 0, 1)
    E(movs_imm, 1, 7)
    E(raw, h(0x400C))                                        # ands r4, r1
    E(cmp_reg, 0, 4)
    E(b_cond, "gn_x", "ne")
    E(raw, h(0x1428))                                        # asrs r0, r5, #16
    E(lsls_imm, 0, 0, 8)
    E(movw, 2, G.GB + G.P_NOTE)
    E(mov_reg, 1, 0)
    E(movs_imm, 0, 0)
    E(bl, WR16)
    a.label("gn_x")
    E(raw, h(0xE8BD) + h((1 << 0) | (1 << 4) | (1 << 5) | (1 << 14)))   # pop.w {r0, r4, r5, lr}
    E(b_w, TRIG)
    return a.assemble()


def install(img, report, base_addr):
    """After granular0 (core 0's engine, note), dspready (cthresh's READY byte), rhrec and countin; before tmenu (its gran page)."""
    import rhbuild
    lab = lambda m, k: int(report[m]["labels"][k], 16)                         # noqa: E731
    for need in ("granular0", "cthresh", "rhrec", "countin", "rhstate"):
        assert need in report, f"grain_rp needs {need}"
    assert report["granular0"].get("note"), "grain_rp needs granular0 note"
    assert "grain" in rhstate.OFF, "grain_rp needs ourram's slot (RH_GRAIN=1)"
    assert rhbuild.bl_target(img, NOTE_ON_BL) == TRIG, "the DSP note-on's bl TRIG moved"
    L = dict(c_rst=lab("rhstate", "c_rst"), c_rrt=lab("rhrec", "c_rrt"), c_ciok=lab("countin", "c_ciok"))
    code, labels = arm_code(base_addr, L)
    img += bytes([0xFF]) * (base_addr - rhbuild.BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    rhbuild.patch(img, NOTE_ON_BL, f"bl #{TRIG:#x}", bl(NOTE_ON_BL, labels["c_grnote"]))
    report["grain"] = dict(tables=hex(base_addr), slot=hex(rhstate.ST + rhstate.OFF["grain"][0]), block=BLK,
                           labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
