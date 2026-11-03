"""The filter page's envelope and LFO (MIT; Rhythm Plus, Circuit Rhythm 5706): pshape's shapes on each track's low-pass cutoff.

  * core 1: RR (pshape's, built with FILT) runs a second timeline T += S and a second LFO phase per track and keeps
    FM = (A x ENV[shape](T) + L x LFO[shape](phase / 2)) >> 16 in semitones; TRIG sets T = 0; voicefilt's LPIDX adds FM to the low-pass
    index before its clamp to 0..128 (the comb keeps the stock's index);
  * the values: 6 a track in the record's tail (block "FL", stored XOR their defaults, so a new project = the defaults), values 12..17
    of c_fsval / c_fsput (0..11 are Stock+'s, through pshape's c_shval / c_shput);
  * c_flframe (the LED task): with core 1 READY and Stock+'s wait done, a changed track's words (else every 8th frame one track in
    turn), and the synced LFOs' phase at each tick.
  * (move) LVL first runs the move LFO of values 21 / 22 (shape, rate): phase += MR at shared Y:SH + 8 + t, M = shape(phase / 2) at
    shared Y:SH + t (0 while MR = 0) for mixmove's core 0 hooks; c_fldsp writes MR, its table, and the depths 23..25 to core 0's
    Y:YD (pan, reverb, delay; 0 while the move's rate is off).
  * (px) value 26, the random pitch's depth (block "PX"): each TRIG takes the next number r of an LCG at Y:RSEED and keeps the note's
    offset r x RD at Y:RO + t; RR adds it to the pitch before the clamp; c_fldsp writes RD = (d x d >> 10) x 3 (at most 12 semitones).
  * (glide) value 27, the glide time: RR keeps the glided pitch G at Y:GP + t, G = y0 + K x (G - y0) with K at Y:GK + t (0 = none),
    then the envelope, the LFO and the random offset on top; c_fldsp writes K from the glide table (GL_MIN .. GL_MAX to 95 %).
  * (fade) value 28, the LFO's fade-in (block "FI"): TRIG sets the mute W = 1 at Y:FW + t; RR takes W -= FR (at least 0) and the LFO
    x (1 - W); c_fldsp writes FR from the fade table (1 = none, else a full fade in FD_MIN .. FD_MAX).
RAM: rhstate "fshape" + 0 the tracks to write (bit t), + 1 the frame counter, + 4 the tick last seen.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, adds_imm8, adds_reg, b, b_cond, b_w, bl, cmp_imm, cmp_reg, eors_reg, h, ldr_imm, ldrb_imm, ldrh_reg, lsls_imm,  # noqa: E402
                   lsls_reg, lsrs_imm, mov_reg, movs_imm, movt, movw, muls, orrs_reg, pop_list, push_list, raw, str_imm, strb_imm, strh_reg,
                   subs_imm8, subs_reg, tst_reg, bics_reg)
import countin as CI  # noqa: E402
import pshape as PS  # noqa: E402
import rhstate  # noqa: E402

FB = 0x1E00                                              # core 1's Y, + t: free above pshape's LFO tables, cleared at core 1's start
O_T, O_S, O_A, O_E, O_P, O_R, O_L, O_Q, O_M = 0, 8, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40
assert PS.LFO_Y + PS.NL * PS.STRIDE <= FB and FB + O_M + 8 <= 0x1F80   # $1F80: emu_pshape's stub word
V0, NV = 12, 6                                           # values 12..17: env shape, amount, decay, LFO shape, rate, depth
DEF = (0, 8192, 8192, 0, 14080, 0)
NAMES = ("env shape", "env amount", "env decay", "LFO shape", "LFO rate", "LFO depth")
A_SCALE, L_SCALE = 1024, 256                             # (v - 8192) x 1024: +- 128 semitones; v x 256: 64 at the top
BLK_OFF, BLK_LEN = 420, 4 + 2 * NV * 8                   # in the record's tail: "FL", the check byte, 0, 8 tracks x 6 halfwords
MARK0, MARK1, CHECK = ord("F"), ord("L"), 0xA5
DEAD, DIV_SHIFT, X7 = 128, 9, 8192                       # stockplus's: the LFO rate's middle, 4 clicks a division
K3_MIDPH = 0x400000
SEQ, TEMPO = 0x2003C380, 0x20012788
UPD = 1500 / 8
DIVS = (4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768)
KQ = tuple(round((1 << 24) * 24 * 256 / (60 * UPD * d)) for d in DIVS)
PHQ = tuple(round((1 << 24) / d) for d in DIVS)
ROUND = 8                                                # frames a track in the round
DSP_LABELS = {}                                          # voicefilt's labels in core 1, as pitchmod placed them
VB = 0x1E48                                              # (vol) core 1's Y, + t: the volume LFO
O_VP, O_VR, O_VD, O_VQ, O_VX = 0, 8, 0x10, 0x18, 0x20    # phase, rate (a block), depth, the shape's table, the cut it gives (0 = full level)
assert FB + O_M + 8 <= VB and VB + O_VX + 8 <= PS.VOL_Y
V1, NV2 = 18, 8                                          # (vol) values 18..25: vol shape, rate, depth; 21..25 the movement's (not used yet)
VDEF = (0, 14080, 0, 0, 14080, 0, 0, 0)
VNAMES = ("vol shape", "vol rate", "vol depth", "move shape", "move rate", "pan depth", "reverb depth", "delay depth")
VBLK_OFF, VBLK_LEN = 2, 4 + 2 * NV2 * 8                  # "VL", the check byte, 0, 8 tracks x 8 halfwords; in Remix's granmulti / patchain room
VMARK0, VMARK1 = ord("V"), ord("L")
D_SHIFT, R_SHIFT = 9, 3                                  # depth v << 9; the rate >> 3: LVL runs every block, RR every 8th
NVS = PS.NL + PS.NG                                      # 16 volume shapes: the 10 LFOs, the 6 gates
LVL_R0 = 0x16E1                                          # LVL's copy of r0 (the voice loop's)
MB = 0x1E70                                              # (move) core 1's Y: the move LFO's rate + t, its table + 8 + t
VDEF_M = (0, 14080, 0, 0, 14080, 0, 8192, 8192)          # (move) the sends' depths from the middle
WR16 = 0x08031200                                        # (core, word << 8, address: core 1 / core 0's Y $8000 | it; shared: as it is)
MOVE = [False]                                           # set by strip(move=True)
PX0, NPX = 26, 2                                         # (px) values 26, 27: the random pitch's depth; 27 kept for the pitch page
PXDEF = (0, 0)
PXBLK_OFF, PXBLK_LEN = 136, 4 + 2 * NPX * 8              # "PX", the check byte, 0, 8 tracks x 2 halfwords; in Remix's patchain room
PXMARK0, PXMARK1 = ord("P"), ord("X")
RD, RSEED, RO = 0x16E2, 0x16F7, 0x16F8                   # (px) core 1's Y: the random depth + t, the seed, the note's offset + t
LCG_A, LCG_C = 0xC64E6D, 0x3039                          # seed = seed x A + C, mod 2^24
PX = [False]                                             # set by strip(px=True)
GK, GP = PS.ENV_Y + 0x30, PS.ENV_Y + 0x38               # (glide) core 1's Y, + t: the glide's factor, the glided pitch (past envelope 0's points)
GL_MIN, GL_MAX = 0.01, 1.0                               # (glide) seconds to 95 % of the jump, at the knob's first step and its top
GLIDE = [False]                                          # set by strip(glide=True)
FI0, NFI = 28, 1                                         # (fade) value 28: the pitch LFO's fade-in time
FIDEF = (0,)
FIBLK_OFF, FIBLK_LEN = 172, 4 + 2 * NFI * 8              # "FI", the check byte, 0, 8 tracks x 1 halfword; after "PX", in Remix's patchain room
FIMARK0, FIMARK1 = ord("F"), ord("I")
FR, FW = PS.ENV_Y + PS.STRIDE + 0x30, PS.ENV_Y + PS.STRIDE + 0x38   # (fade) core 1's Y, + t: the fade's step, the LFO's mute (past envelope 1's points)
FD_MIN, FD_MAX = 0.02, 2.0                               # (fade) seconds of a full fade at the knob's first step and its top
FADE = [False]                                           # set by strip(fade=True)
assert VB + O_VX + 8 <= MB and MB + 16 <= PS.VOL_Y
STOCK_LVL, LVL_CALL = 0x244, 0x241                       # core 1's level ramp, its jsr in the voice loop


def block_bytes(vals):
    """the record block for vals[t][k] (for the tests)"""
    data = b"".join((vals[t][k] ^ DEF[k]).to_bytes(2, "little") for t in range(8) for k in range(NV))
    return bytes([MARK0, MARK1, (sum(data) & 0xFF) ^ CHECK, 0]) + data


def vblock_bytes(vals):
    """the "VL" block for vals[t][k], 8 values a track (for the tests)"""
    data = b"".join((vals[t][k] ^ VDEF[k]).to_bytes(2, "little") for t in range(8) for k in range(NV2))
    return bytes([VMARK0, VMARK1, (sum(data) & 0xFF) ^ CHECK, 0]) + data


def vwords(v, t, bpm=120):
    """{core 1 Y address: word} c_fldsp writes for the volume of track t with its values v[0..2] (for the tests)"""
    import stockplus as SP
    r = (SP.k3_rate(v[1], bpm) & 0xFFFFFF) >> R_SHIFT
    s = v[0] * NVS >> 14
    q = PS.LFO_Y + PS.STRIDE * s if s < PS.NL else PS.VOL_Y + PS.STRIDE * (s - PS.NL)
    return {VB + O_VR + t: r, VB + O_VQ + t: q, VB + O_VD + t: v[2] << D_SHIFT if r else 0}


def mwords(v, t, bpm=120):
    """(move) {(core, address): word} c_fldsp writes for the move of track t with its values v[0..7] (18..25): core 1's rate and table,
    core 0's Y depths (0 while the rate is off)"""
    import mixmove as MM
    import stockplus as SP
    r = (SP.k3_rate(v[4], bpm) & 0xFFFFFF) >> R_SHIFT
    s = v[3] * NVS >> 14
    q = PS.LFO_Y + PS.STRIDE * s if s < PS.NL else PS.VOL_Y + PS.STRIDE * (s - PS.NL)
    d = [v[5] << D_SHIFT, ((v[6] - 8192) << 10) & 0xFFFFFF, ((v[7] - 8192) << 10) & 0xFFFFFF]
    out = {(1, MB + t): r, (1, MB + 8 + t): q}
    for off, w in zip((MM.O_PD, MM.O_RD, MM.O_DD), d):
        out[(0, MM.YD + off + t)] = w if r else 0
    return out


def words(v, t, bpm=120):
    """{core 1 Y address: word} c_fldsp writes for track t with its 6 values v (for the tests; the phase only for R = 0)"""
    import stockplus as SP
    steps = PS.step_table()
    i, f = v[2] >> 7, v[2] & 127
    out = {FB + O_S + t: steps[i] + ((steps[i + 1] - steps[i]) * f >> 7),
           FB + O_A + t: ((v[1] - 8192) * A_SCALE) & 0xFFFFFF,
           FB + O_E + t: PS.shape_index(v[0], PS.NE),
           FB + O_Q + t: PS.shape_index(v[3], PS.NL),
           FB + O_L + t: v[5] * L_SCALE,
           FB + O_R + t: SP.k3_rate(v[4], bpm) & 0xFFFFFF}
    if not out[FB + O_R + t]:
        out[FB + O_P + t] = K3_MIDPH
    return out


# ---------------------------------------------------------------- core 1
def rr_part():
    """RR's filter half (n1 = the track; keeps y0; r1 changed)"""
    return [f"move #>${FB:x},r1", "lua (r1)+n1,r1",
            "move y:(r1),a", f"move y:(r1+${O_S:x}),x0", "add x0,a", "move #>$7fffff,x0", "cmp x0,a", "tgt x0,a", "move a1,y:(r1)",
            f"move y:(r1+${O_E:x}),b", "asl #6,b,b", f"add #>${PS.ENV_Y:x},b", "move b1,r0",
            ("jsr", "lk"),
            "move a,x0", f"move y:(r1+${O_A:x}),x1", "mpy x1,x0,a", f"move a,y:>${PS.SCR:x}",
            f"move y:(r1+${O_P:x}),a", f"move y:(r1+${O_R:x}),x0", "add x0,a", f"move a1,y:(r1+${O_P:x})",
            "lsr #1,a",
            f"move y:(r1+${O_Q:x}),b", "asl #6,b,b", f"add #>${PS.LFO_Y:x},b", "move b1,r0",
            ("jsr", "lk"),
            "move a,x0", f"move y:(r1+${O_L:x}),x1", "mpy x1,x0,b", f"move y:>${PS.SCR:x},a", "add a,b",
            "asr #16,b,b", f"move b1,y:(r1+${O_M:x})"]


def trig_part():
    """TRIG: x0 = 0, n1 = the track; (px) the note's random offset, a = the track again"""
    rnd = [f"move y:>${RSEED:x},x0", f"move #>${LCG_A:x},x1", "mpy x1,x0,a", "asr a", "move a0,x0", "move x0,a", f"add #>${LCG_C:x},a",
           "move a1,x0", f"move x0,y:>${RSEED:x}",
           f"move #>${RD:x},r1", "lua (r1)+n1,r1", "move y:(r1),x1", "mpy x1,x0,a", f"move a,y:(r1+${RO - RD:x})",
           "move n1,a"] if PX[0] else []
    fd = [f"move #>${FW:x},r1", "move #>$7fffff,x0", "move x0,y:(r1+n1)"] if FADE[0] else []
    return [f"move #>${FB + O_T:x},r1", "move x0,y:(r1+n1)", *fd, *rnd]


def fade_part():
    """(fade) RR, b = L x LFO (r1 = pitchmod's base + the track): W -= FR, at least 0; b x (1 - W)"""
    o_w, o_r = FW - PS.YB, FR - PS.YB
    return ["move b,y1", "clr b", f"move y:(r1+${o_w:x}),a", f"move y:(r1+${o_r:x}),x0", "sub x0,a", "tlt b,a", f"move a1,y:(r1+${o_w:x})",
            "move a1,x0", "move #>$7fffff,a", "sub x0,a", "move a1,x1", "mpy y1,x1,b"]


def fade_table():
    """the fade's step for the knob's 129 points: 1 = none, then a full fade in FD_MIN .. FD_MAX"""
    out = [0x7FFFFF]
    for i in range(1, 129):
        t = FD_MIN * (FD_MAX / FD_MIN) ** ((i - 1) / 127)
        out.append(min(0x7FFFFF, round(0x7FFFFF / (t * UPD))))
    return out


def px_part():
    """(px) RR, after the pitch's sum in a (r1 = pitchmod's base + the track, b = the envelope + the LFO): (glide) a = G + b,
    + the note's random offset"""
    gl = [f"move y:(r1+${GP - PS.YB:x}),a", "sub y0,a", "move a,y1", f"move y:(r1+${GK - PS.YB:x}),x1", "mpy y1,x1,a", "add y0,a",
          f"move a,y:(r1+${GP - PS.YB:x})", "add b,a"] if GLIDE[0] else []
    return [*gl, f"move y:(r1+${RO - PS.YB:x}),x0", "add x0,a"]


def glide_table():
    """the glide's K for the knob's 129 points: 0 = none, then GL_MIN .. GL_MAX to 95 % of the jump (3 time constants)"""
    out = [0]
    for i in range(1, 129):
        t = GL_MIN * (GL_MAX / GL_MIN) ** ((i - 1) / 127)
        out.append(min(0x7FFFFF, round(math.exp(-3 / (t * UPD)) * (1 << 23))))
    return out


def lvl_part():
    """LVL (in place of the stock's level ramp, after RR's lk): the volume LFO of voice v = y:$1405 (phase += R, VX = D x (1 - shape) / 2),
    then the stock's ramp toward the target x (1 - VX); r0 kept; r1, n1 changed"""
    import mixmove as MM
    mv = ["move y:>$1405,n1", f"move #>${MB:x},r1", "lua (r1)+n1,r1",
          "move y:(r1),x0", "move y:(r1+$8),r0",                                         # MR, the table
          f"move #>${MM.SH:x},r1", "lua (r1)+n1,r1",
          "clr b", "move x0,a", "tst a", ("jcc", "eq", "mv_0"),
          "move y:(r1+$8),a", "add x0,a", "move a1,y:(r1+$8)", "lsr #1,a",
          ("jsr", "lk"), "move a,b",
          ("label", "mv_0"), "move b,y:(r1)"] if MOVE[0] else []
    return [("label", "lvl"),
            f"move r0,y:>${LVL_R0:x}",
            *mv,
            "move y:>$1405,n1", f"move #>${VB:x},r1", "lua (r1)+n1,r1",
            f"move y:(r1+${O_VD:x}),b", "tst b", ("jcc", "eq", "lv_0"),
            f"move y:(r1+${O_VP:x}),a", f"move y:(r1+${O_VR:x}),x0", "add x0,a", f"move a1,y:(r1+${O_VP:x})",
            "lsr #1,a",
            f"move y:(r1+${O_VQ:x}),r0",
            ("jsr", "lk"),
            "move a,x0", "move #>$7fffff,a", "sub x0,a", "asr a", "move a,x0", f"move y:(r1+${O_VD:x}),x1", "mpy x1,x0,b",
            ("label", "lv_0"),
            f"move b,y:(r1+${O_VX:x})", "move b,y1",
            f"move y:>${LVL_R0:x},r0",
            "move #>$2a02,r2",
            "move y:>$1405,a", "asl #1,a,a", "move #>$37301,x1", "add x1,a", "move a,r5",
            "move y:(r5)+,b", "move b,x1", "mac -y1,x1,b", "move b,x1",                       # the target x (1 - VX)
            "move y:(r5)-,x0",
            ("do", "lv_e"),
            "move x1,b", "sub x0,b", "asr #6,b,b", "add x0,b", "move b,x0", "move x:(r2),y1", "mpy x0,y1,a", "move a,x:(r2)+",
            ("label", "lv_e"),
            "move (r5)+", "move x0,x:(r5)", "rts"]


def strip(vol=False, move=False, px=False, glide=False, fade=False):
    """from now on pshape's RR / TRIG carry the filter's half and voicefilt's LPIDX adds FM; vol: LVL after RR; move: the move LFO in LVL;
    px: the random pitch in TRIG and RR; glide: the glide in RR; fade: the pitch LFO's fade-in in TRIG and RR"""
    import voicefilt as F
    assert vol or not move
    assert move or not px
    assert px or not glide
    assert PS.ENV_Y + PS.NPT + 1 <= GK and GP + 8 <= PS.ENV_Y + PS.STRIDE
    assert px or not fade
    assert PS.ENV_Y + PS.STRIDE + PS.NPT + 1 <= FR and FW + 8 <= PS.ENV_Y + 2 * PS.STRIDE
    GLIDE[0], FADE[0] = glide, fade
    PS.PLFO = fade_part if fade else None
    assert F.TMP + 7 <= RSEED and RD + 8 <= F.TMP and RO + 8 <= F.STATE2
    MOVE[0], PX[0] = move, px
    PS.PADD = px_part if px else None
    PS.FILT = (rr_part, trig_part, lvl_part) if vol else (rr_part, trig_part)
    items0 = F.items

    def items():
        L = items0()
        at = L.index(("label", "lpidx"))
        k = next(i for i in range(at, len(L) - 1) if L[i] == "mpyr y0,x0,b" and L[i + 1] == "add b,a") + 2
        return L[:k] + [f"move #>${FB + O_M:x},r1", "move y:(r1+n1),x0", "add x0,a"] + L[k:]
    F.items = items
    code0 = F.code

    def code(at):
        w, labels = code0(at)
        DSP_LABELS.update(labels)
        return w, labels
    F.code = code


# ---------------------------------------------------------------- the ARM
def arm_code(base, L, vol=False, move=False, px=False, glide=False, fade=False):
    a = Asm(base)
    E = a.emit
    O = rhstate.OFF["fshape"][0]
    O_TH = rhstate.OFF["cthresh"][0] + 1
    O_W = rhstate.OFF["spwait"][0]

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, (v >> 16) & 0xFFFF)
    t_def = base
    E(raw, b"".join(v.to_bytes(2, "little") for v in DEF))
    t_tabs = base + 2 * NV
    E(raw, b"".join(x.to_bytes(4, "little") for x in DIVS + KQ + PHQ))
    t_divs, t_kq, t_phq = t_tabs, t_tabs + 4 * len(DIVS), t_tabs + 8 * len(DIVS)
    t_vdef = t_tabs + 12 * len(DIVS)
    if vol:
        E(raw, b"".join(v.to_bytes(2, "little") for v in (VDEF_M if move else VDEF)))
    t_pxdef = t_vdef + 2 * NV2
    if px:
        E(raw, b"".join(v.to_bytes(2, "little") for v in PXDEF))
    t_glide = t_pxdef + 2 * NPX
    if glide:
        assert t_glide % 4 == 0
        E(raw, b"".join(v.to_bytes(4, "little") for v in glide_table()))
    t_fade = t_glide + 4 * 129
    t_fidef = t_fade + 4 * 129
    if fade:
        assert glide
        E(raw, b"".join(v.to_bytes(4, "little") for v in fade_table()))
        E(raw, b"".join(v.to_bytes(2, "little") for v in FIDEF))

    # ---- c_flblk() -> r0 = the block in the record's tail, 0 without the record; clobbers r1, r2
    a.label("c_flblk")
    E(push_list, [], lr=True)
    E(bl, L["c_rrt"])
    E(cmp_imm, 0, 0)
    E(b_cond, "fb_x", "eq")
    E(movw, 1, BLK_OFF)
    E(adds_reg, 0, 0, 1)
    a.label("fb_x")
    E(pop_list, [], pc=True)

    # ---- c_flsum(r0 = block) -> r0 = its check byte; clobbers r1-r3
    a.label("c_flsum")
    E(movs_imm, 1, 4)
    E(movs_imm, 2, 0)
    a.label("fs_l")
    E(raw, h(0x5C43))                                      # ldrb r3, [r0, r1]
    E(adds_reg, 2, 2, 3)
    E(adds_imm8, 1, 1)
    E(cmp_imm, 1, BLK_LEN)
    E(b_cond, "fs_l", "lo")
    E(movs_imm, 0, 0xFF)
    E(raw, h(0x4010))                                      # ands r0, r2
    E(movs_imm, 1, CHECK)
    E(eors_reg, 0, 1)
    E(raw, h(0x4770))

    # ---- c_flok(r0 = block) -> r0 = 1 when its mark and check byte hold; clobbers r1-r3
    a.label("c_flok")
    E(push_list, [4], lr=True)
    E(mov_reg, 4, 0)
    E(ldrb_imm, 1, 4, 0)
    E(cmp_imm, 1, MARK0)
    E(b_cond, "fo_n", "ne")
    E(ldrb_imm, 1, 4, 1)
    E(cmp_imm, 1, MARK1)
    E(b_cond, "fo_n", "ne")
    E(bl, "c_flsum")
    E(ldrb_imm, 1, 4, 2)
    E(cmp_reg, 0, 1)
    E(b_cond, "fo_n", "ne")
    E(movs_imm, 0, 1)
    E(pop_list, [4], pc=True)
    a.label("fo_n")
    E(movs_imm, 0, 0)
    E(pop_list, [4], pc=True)

    def slot_off(rt, rtrack, rk):                          # rt = 4 + 12 t + 2 k (rk = k)
        E(movs_imm, rt, 12)
        E(muls, rt, rtrack)
        E(adds_reg, rt, rt, rk)
        E(adds_reg, rt, rt, rk)
        E(adds_imm8, rt, 4)

    # ---- c_fsval(r0 = track, r1 = value 0..17) -> r0 = the value (0..11 Stock+'s, 12..17 ours: their defaults without a good block)
    a.label("c_fsval")
    E(cmp_imm, 1, V0)
    E(b_cond, "fv_o", "hs")
    E(b_w, L["c_shval"])
    a.label("fv_o")
    if vol:
        if fade:
            E(cmp_imm, 1, FI0)
            E(b_cond, "fv_p", "lo")
            E(b_w, "c_fival")
            a.label("fv_p")
        if px:
            E(cmp_imm, 1, PX0)
            E(b_cond, "fv_v", "lo")
            E(b_w, "c_pxval")
            a.label("fv_v")
        E(cmp_imm, 1, V1)
        E(b_cond, "fv_f", "lo")
        E(b_w, "c_vlval")
        a.label("fv_f")
    E(push_list, [4, 5, 6], lr=True)
    E(mov_reg, 4, 0)
    E(subs_imm8, 1, V0)
    E(mov_reg, 5, 1)                                       # r5 = k
    E(bl, "c_flblk")
    E(cmp_imm, 0, 0)
    E(b_cond, "fv_d", "eq")
    E(mov_reg, 6, 0)
    E(bl, "c_flok")
    E(cmp_imm, 0, 0)
    E(b_cond, "fv_d", "eq")
    slot_off(1, 4, 5)
    E(ldrh_reg, 0, 6, 1)
    imm32(2, t_def)
    E(lsls_imm, 3, 5, 1)
    E(adds_reg, 2, 2, 3)
    E(raw, h(0x8812))                                      # ldrh r2, [r2]
    E(eors_reg, 0, 2)
    E(pop_list, [4, 5, 6], pc=True)
    a.label("fv_d")
    imm32(2, t_def)
    E(lsls_imm, 3, 5, 1)
    E(adds_reg, 2, 2, 3)
    E(raw, h(0x8810))                                      # ldrh r0, [r2]
    E(pop_list, [4, 5, 6], pc=True)

    # ---- c_fsput(r0 = track, r1 = value 0..17, r2 = v): ours into the block (a bad block first made the defaults), the track to write
    a.label("c_fsput")
    E(cmp_imm, 1, V0)
    E(b_cond, "fp_o", "hs")
    E(b_w, L["c_shput"])
    a.label("fp_o")
    if vol:
        if fade:
            E(cmp_imm, 1, FI0)
            E(b_cond, "fp_p", "lo")
            E(b_w, "c_fiput")
            a.label("fp_p")
        if px:
            E(cmp_imm, 1, PX0)
            E(b_cond, "fp_v", "lo")
            E(b_w, "c_pxput")
            a.label("fp_v")
        E(cmp_imm, 1, V1)
        E(b_cond, "fp_f", "lo")
        E(b_w, "c_vlput")
        a.label("fp_f")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    E(subs_imm8, 1, V0)
    E(mov_reg, 5, 1)
    E(mov_reg, 6, 2)
    E(bl, "c_flblk")
    E(cmp_imm, 0, 0)
    E(b_cond, "fp_x", "eq")
    E(mov_reg, 7, 0)                                       # r7 = the block
    E(bl, "c_flok")
    E(cmp_imm, 0, 0)
    E(b_cond, "fp_k", "ne")
    E(movs_imm, 0, 0)
    E(movs_imm, 1, 0)
    a.label("fp_z")
    E(raw, h(0x5478))                                      # strb r0, [r7, r1]
    E(adds_imm8, 1, 1)
    E(cmp_imm, 1, BLK_LEN)
    E(b_cond, "fp_z", "lo")
    E(movs_imm, 0, MARK0)
    E(strb_imm, 0, 7, 0)
    E(movs_imm, 0, MARK1)
    E(strb_imm, 0, 7, 1)
    a.label("fp_k")
    imm32(2, t_def)
    E(lsls_imm, 3, 5, 1)
    E(adds_reg, 2, 2, 3)
    E(raw, h(0x8812))                                      # ldrh r2, [r2]
    E(eors_reg, 2, 6)
    slot_off(1, 4, 5)
    E(strh_reg, 2, 7, 1)
    E(mov_reg, 0, 7)
    E(bl, "c_flsum")
    E(strb_imm, 0, 7, 2)
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    E(b_cond, "fp_x", "eq")
    E(movw, 1, O)
    E(adds_reg, 0, 0, 1)
    E(ldrb_imm, 1, 0, 0)
    E(movs_imm, 2, 1)
    E(lsls_reg, 2, 4)
    E(orrs_reg, 1, 2)
    E(strb_imm, 1, 0, 0)
    a.label("fp_x")
    E(pop_list, [4, 5, 6, 7], pc=True)

    # ---- c_flreset(r0 = track): its 6 values to their defaults
    a.label("c_flreset")
    E(push_list, [4, 5], lr=True)
    E(mov_reg, 4, 0)
    E(movs_imm, 5, 0)
    a.label("fr_l")
    E(mov_reg, 0, 4)
    E(mov_reg, 1, 5)
    E(adds_imm8, 1, V0)
    imm32(2, t_def)
    E(lsls_imm, 3, 5, 1)
    E(adds_reg, 2, 2, 3)
    E(raw, h(0x8812))                                      # ldrh r2, [r2]
    E(bl, "c_fsput")
    E(adds_imm8, 5, 1)
    E(cmp_imm, 5, NV)
    E(b_cond, "fr_l", "lo")
    E(pop_list, [4, 5], pc=True)

    if vol:
        vl_code(a, E, imm32, L, O, t_vdef)
    if px:
        vl_code(a, E, imm32, L, O, t_pxdef, "px", PXBLK_OFF, PXBLK_LEN, (PXMARK0, PXMARK1), PX0, NPX)
    if fade:
        vl_code(a, E, imm32, L, O, t_fidef, "fi", FIBLK_OFF, FIBLK_LEN, (FIMARK0, FIMARK1), FI0, NFI)

    # ---- c_flr(r0 = the rate's value) -> r0 = R: 0 in the middle, Stock+'s rate table right of it, BPM x KQ[i] >> 8 left; clobbers r1-r3
    a.label("c_flr")
    E(push_list, [4], lr=True)
    E(movw, 1, X7)
    E(subs_reg, 0, 0, 1)
    E(b_cond, "rt_l", "lt")
    E(cmp_imm, 0, DEAD)
    E(b_cond, "rt_0", "lt")
    E(lsls_imm, 1, 0, 1)
    imm32(0, L["t_rate"])
    E(bl, L["c_spint"])
    E(pop_list, [4], pc=True)
    a.label("rt_l")
    E(raw, h(0x4240))                                      # rsbs r0, r0, #0
    E(cmp_imm, 0, DEAD)
    E(b_cond, "rt_0", "lt")

    def div_index(tag):                                    # r0 = -(v - 8192) >= DEAD -> r0 = its division's index
        E(subs_imm8, 0, DEAD)
        E(lsrs_imm, 0, 0, DIV_SHIFT)
        E(cmp_imm, 0, 15)
        E(b_cond, f"dv_{tag}", "le")
        E(movs_imm, 0, 15)
        a.label(f"dv_{tag}")
    div_index("r")
    E(lsls_imm, 4, 0, 2)
    imm32(0, TEMPO)
    E(movs_imm, 1, 0)
    E(bl, CI.PARAM_NEW)
    E(ldrb_imm, 0, 0, 0)                                   # the BPM
    E(cmp_imm, 0, 30)
    E(b_cond, "rt_b", "hs")
    E(movs_imm, 0, 120)
    a.label("rt_b")
    imm32(1, t_kq)
    E(adds_reg, 1, 1, 4)
    E(ldr_imm, 1, 1, 0)
    E(muls, 0, 1)
    E(lsrs_imm, 0, 0, 8)
    E(pop_list, [4], pc=True)
    a.label("rt_0")
    E(movs_imm, 0, 0)
    E(pop_list, [4], pc=True)

    # ---- c_fldsp(r0 = track): its words into core 1; clobbers r0-r3, r12
    a.label("c_fldsp")
    E(push_list, [4, 5], lr=True)
    E(mov_reg, 4, 0)

    def val(k):
        E(mov_reg, 0, 4)
        E(movs_imm, 1, V0 + k)
        E(bl, "c_fsval")

    def put(off):
        E(movw, 1, FB + off)
        E(adds_reg, 1, 1, 4)
        E(bl, L["c_spw"])
    val(2)
    E(mov_reg, 1, 0)
    imm32(0, L["t_steps"])
    E(bl, L["c_spint"])
    put(O_S)
    val(1)
    E(movw, 1, 8192)
    E(subs_reg, 0, 0, 1)
    E(movw, 1, A_SCALE)
    E(muls, 0, 1)
    put(O_A)
    val(0)
    E(lsls_imm, 0, 0, 4)
    E(lsrs_imm, 0, 0, 14)
    put(O_E)
    val(3)
    E(movs_imm, 1, PS.NL)
    E(muls, 0, 1)
    E(lsrs_imm, 0, 0, 14)
    put(O_Q)
    val(5)
    E(movw, 1, L_SCALE)
    E(muls, 0, 1)
    put(O_L)
    val(4)
    E(bl, "c_flr")
    E(mov_reg, 5, 0)
    put(O_R)
    E(cmp_imm, 5, 0)
    E(b_cond, "fd_x", "ne")
    imm32(0, K3_MIDPH)                                     # off: the LFO at its centre
    put(O_P)
    a.label("fd_x")
    if vol:
        def vval(k):
            E(mov_reg, 0, 4)
            E(movs_imm, 1, V1 + k)
            E(bl, "c_fsval")
        vval(1)
        E(bl, "c_flr")
        E(lsrs_imm, 0, 0, R_SHIFT)
        E(mov_reg, 5, 0)                                   # r5 = R
        put(VB - FB + O_VR)
        vval(0)
        E(lsrs_imm, 0, 0, 10)                              # the shape, 0..15
        E(cmp_imm, 0, PS.NL)
        E(b_cond, "vq_l", "lo")
        E(subs_imm8, 0, PS.NL)
        E(lsls_imm, 0, 0, 6)
        E(movw, 1, PS.VOL_Y)
        E(b, "vq_p")
        a.label("vq_l")
        E(lsls_imm, 0, 0, 6)
        E(movw, 1, PS.LFO_Y)
        a.label("vq_p")
        E(adds_reg, 0, 0, 1)
        put(VB - FB + O_VQ)
        vval(2)
        E(lsls_imm, 0, 0, D_SHIFT)
        E(cmp_imm, 5, 0)
        E(b_cond, "vd_p", "ne")
        E(movs_imm, 0, 0)                                  # the rate's middle: off, the full level
        a.label("vd_p")
        put(VB - FB + O_VD)
    if move:
        import mixmove as MM
        vval(4)
        E(bl, "c_flr")
        E(lsrs_imm, 0, 0, R_SHIFT)
        E(mov_reg, 5, 0)                                   # r5 = MR
        put(MB - FB)
        vval(3)
        E(lsrs_imm, 0, 0, 10)
        E(cmp_imm, 0, PS.NL)
        E(b_cond, "mq_l", "lo")
        E(subs_imm8, 0, PS.NL)
        E(lsls_imm, 0, 0, 6)
        E(movw, 1, PS.VOL_Y)
        E(b, "mq_p")
        a.label("mq_l")
        E(lsls_imm, 0, 0, 6)
        E(movw, 1, PS.LFO_Y)
        a.label("mq_p")
        E(adds_reg, 0, 0, 1)
        put(MB - FB + 8)
        for k, off, mid in ((5, MM.O_PD, False), (6, MM.O_RD, True), (7, MM.O_DD, True)):
            vval(k)
            if mid:
                E(movw, 1, 8192)
                E(subs_reg, 0, 0, 1)
                E(lsls_imm, 0, 0, 10)                      # -8192..8191 << 10
            else:
                E(lsls_imm, 0, 0, D_SHIFT)
            E(cmp_imm, 5, 0)
            E(b_cond, f"md_{k}", "ne")
            E(movs_imm, 0, 0)                              # the move's rate off: no movement
            a.label(f"md_{k}")
            E(movw, 1, MM.YD + off)
            E(adds_reg, 1, 1, 4)
            E(bl, "c_fl0w")
    if px:
        E(mov_reg, 0, 4)
        E(movs_imm, 1, PX0)
        E(bl, "c_fsval")
        E(mov_reg, 1, 0)
        E(muls, 0, 1)
        E(lsrs_imm, 0, 0, 10)
        E(movs_imm, 1, 3)
        E(muls, 0, 1)                                      # RD = (d x d >> 10) x 3
        E(movw, 1, RD)
        E(adds_reg, 1, 1, 4)
        E(bl, L["c_spw"])
    if glide:
        E(mov_reg, 0, 4)
        E(movs_imm, 1, PX0 + 1)
        E(bl, "c_fsval")
        E(mov_reg, 1, 0)
        imm32(0, t_glide)
        E(bl, L["c_spint"])
        E(movw, 1, GK)
        E(adds_reg, 1, 1, 4)
        E(bl, L["c_spw"])
    if fade:
        E(mov_reg, 0, 4)
        E(movs_imm, 1, FI0)
        E(bl, "c_fsval")
        E(mov_reg, 1, 0)
        imm32(0, t_fade)
        E(bl, L["c_spint"])
        E(movw, 1, FR)
        E(adds_reg, 1, 1, 4)
        E(bl, L["c_spw"])
    E(pop_list, [4, 5], pc=True)
    if move:
        # ---- c_fl0w(r0 = word, r1 = core 0's Y address) / c_flsw(r0 = word, r1 = a shared address): through core 0; clobbers r0-r3, r12
        a.label("c_fl0w")
        E(movw, 2, 0x8000)
        E(orrs_reg, 1, 2)
        a.label("c_flsw")
        E(push_list, [4], lr=True)
        E(mov_reg, 2, 1)
        E(lsls_imm, 1, 0, 8)
        E(movs_imm, 0, 0)
        E(bl, WR16)
        E(pop_list, [4], pc=True)

    # ---- c_flframe(): the LED task's: core 1 READY and Stock+'s wait done -> a changed track's words (else the round's every ROUND
    #      frames), then the synced LFOs' phase when the tick moved; before that every track marked; clobbers r0-r3
    inv = {"eq": "ne", "ne": "eq"}
    nx = [0]

    def to_x(cond):                                        # b<cond> ff_x (vol: beyond +-256)
        if not vol:
            E(b_cond, "ff_x", cond)
            return
        nx[0] += 1
        E(b_cond, f"ff_k{nx[0]}", inv[cond])
        E(b, "ff_x")
        a.label(f"ff_k{nx[0]}")
    a.label("c_flframe")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(bl, L["c_ciok"])
    E(cmp_imm, 0, 0)
    to_x("eq")
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    to_x("eq")
    E(mov_reg, 7, 0)                                       # r7 = rhstate
    E(movw, 1, O)
    E(adds_reg, 6, 0, 1)                                   # r6 = our slot
    E(movw, 1, O_TH)
    E(adds_reg, 1, 7, 1)
    E(ldrb_imm, 1, 1, 0)
    E(cmp_imm, 1, PS.READY)
    E(b_cond, "ff_all", "ne")
    E(movw, 1, O_W)
    E(adds_reg, 1, 7, 1)
    E(ldrb_imm, 1, 1, 0)
    E(cmp_imm, 1, PS.SP_WAIT)
    E(b_cond, "ff_go", "hs")
    a.label("ff_all")
    E(movs_imm, 0, 0xFF)
    E(strb_imm, 0, 6, 0)
    E(b, "ff_x")
    a.label("ff_go")
    E(ldrb_imm, 0, 6, 0)
    E(cmp_imm, 0, 0)
    E(b_cond, "ff_rd", "eq")
    E(movs_imm, 4, 0)
    a.label("ff_b")
    E(movs_imm, 1, 1)
    E(lsls_reg, 1, 4)
    E(tst_reg, 0, 1)
    E(b_cond, "ff_f", "ne")
    E(adds_imm8, 4, 1)
    E(b, "ff_b")
    a.label("ff_f")
    E(bics_reg, 0, 1)
    E(strb_imm, 0, 6, 0)
    E(mov_reg, 0, 4)
    E(bl, "c_fldsp")
    E(b, "ff_s")
    a.label("ff_rd")
    E(ldrb_imm, 0, 6, 1)
    E(adds_imm8, 0, 1)
    E(strb_imm, 0, 6, 1)
    E(movs_imm, 1, ROUND - 1)
    E(tst_reg, 0, 1)
    E(b_cond, "ff_s", "ne")
    E(lsrs_imm, 0, 0, 3)
    E(movs_imm, 1, 7)
    E(raw, h(0x4008))                                      # ands r0, r1
    E(bl, "c_fldsp")
    a.label("ff_s")
    imm32(0, SEQ + 0x90)
    E(ldr_imm, 0, 0, 0)
    E(movs_imm, 1, 0)
    E(bl, CI.PARAM_NEW)
    E(ldr_imm, 5, 0, 0)                                    # r5 = the global tick
    E(ldr_imm, 0, 6, 4)
    E(cmp_reg, 0, 5)
    to_x("eq")
    E(str_imm, 5, 6, 4)
    E(movs_imm, 4, 0)
    a.label("ff_t")

    def sync(vi, off, tag, shared=None):                   # track r4's LFO of rate value vi, synced: its phase at Y:off + r4 (or shared + r4)
        E(mov_reg, 0, 4)
        E(movs_imm, 1, vi)
        E(bl, "c_fsval")
        E(movw, 1, X7)
        E(subs_reg, 0, 0, 1)
        E(b_cond, f"f{tag}_n", "ge")                       # the middle or free: not synced
        E(raw, h(0x4240))                                  # rsbs r0, r0, #0
        E(cmp_imm, 0, DEAD)
        E(b_cond, f"f{tag}_n", "lt")
        div_index(tag)
        E(lsls_imm, 7, 0, 2)
        imm32(1, t_divs)
        E(adds_reg, 1, 1, 7)
        E(ldr_imm, 1, 1, 0)                                # D
        E(raw, CI.udiv(0, 5, 1))
        E(muls, 0, 1)
        E(subs_reg, 0, 5, 0)                               # tick mod D
        imm32(1, t_phq)
        E(adds_reg, 1, 1, 7)
        E(ldr_imm, 1, 1, 0)
        E(muls, 0, 1)
        imm32(1, K3_MIDPH)
        E(adds_reg, 0, 0, 1)
        if shared is None:
            put(off)
        else:
            imm32(1, shared)
            E(adds_reg, 1, 1, 4)
            E(bl, "c_flsw")
        a.label(f"f{tag}_n")
    sync(V0 + 4, O_P, "f")
    if vol:
        sync(V1 + 1, VB - FB + O_VP, "v")
    if move:
        import mixmove as MM
        sync(V1 + 4, 0, "m", shared=MM.SH + 8)
    E(adds_imm8, 4, 1)
    E(cmp_imm, 4, 8)
    if move:
        E(b_cond, "ff_tx", "hs")
        E(b, "ff_t")
        a.label("ff_tx")
    else:
        E(b_cond, "ff_t", "lo")
    a.label("ff_x")
    E(pop_list, [4, 5, 6, 7], pc=True)
    return a.assemble()


def vl_code(a, E, imm32, L, O, t_vdef, p="vl", boff=VBLK_OFF, blen=VBLK_LEN, marks=(VMARK0, VMARK1), v0=V1, n=NV2):
    """(vol) the "VL" block (or p's): c_vlblk / c_vlsum / c_vlok as the "FL" block's; c_vlval / c_vlput as c_fsval / c_fsput for values
    v0 .. v0 + n - 1 (18..25); c_vlreset(r0 = track): its n values to their defaults"""
    sh = (2 * n).bit_length() - 1
    assert 2 * n == 1 << sh
    a.label(f"c_{p}blk")
    E(push_list, [], lr=True)
    E(bl, L["c_rrt"])
    E(cmp_imm, 0, 0)
    E(b_cond, f"{p}b_x", "eq")
    E(adds_imm8, 0, boff)
    a.label(f"{p}b_x")
    E(pop_list, [], pc=True)

    a.label(f"c_{p}sum")
    E(movs_imm, 1, 4)
    E(movs_imm, 2, 0)
    a.label(f"{p}s_l")
    E(raw, h(0x5C43))                                      # ldrb r3, [r0, r1]
    E(adds_reg, 2, 2, 3)
    E(adds_imm8, 1, 1)
    E(cmp_imm, 1, blen)
    E(b_cond, f"{p}s_l", "lo")
    E(movs_imm, 0, 0xFF)
    E(raw, h(0x4010))                                      # ands r0, r2
    E(movs_imm, 1, CHECK)
    E(eors_reg, 0, 1)
    E(raw, h(0x4770))

    a.label(f"c_{p}ok")
    E(push_list, [4], lr=True)
    E(mov_reg, 4, 0)
    E(ldrb_imm, 1, 4, 0)
    E(cmp_imm, 1, marks[0])
    E(b_cond, f"{p}o_n", "ne")
    E(ldrb_imm, 1, 4, 1)
    E(cmp_imm, 1, marks[1])
    E(b_cond, f"{p}o_n", "ne")
    E(bl, f"c_{p}sum")
    E(ldrb_imm, 1, 4, 2)
    E(cmp_reg, 0, 1)
    E(b_cond, f"{p}o_n", "ne")
    E(movs_imm, 0, 1)
    E(pop_list, [4], pc=True)
    a.label(f"{p}o_n")
    E(movs_imm, 0, 0)
    E(pop_list, [4], pc=True)

    def slot_off(rt, rtrack, rk):                          # rt = 4 + 2 n t + 2 k (rk = k)
        E(lsls_imm, rt, rtrack, sh)
        E(adds_reg, rt, rt, rk)
        E(adds_reg, rt, rt, rk)
        E(adds_imm8, rt, 4)

    def vdef(rd, rk):                                      # rd = VDEF[rk]; clobbers r3
        imm32(rd, t_vdef)
        E(lsls_imm, 3, rk, 1)
        E(adds_reg, rd, rd, 3)
        E(raw, h(0x8800 | rd << 3 | rd))                   # ldrh rd, [rd]

    a.label(f"c_{p}val")
    E(push_list, [4, 5, 6], lr=True)
    E(mov_reg, 4, 0)
    E(subs_imm8, 1, v0)
    E(mov_reg, 5, 1)
    E(bl, f"c_{p}blk")
    E(cmp_imm, 0, 0)
    E(b_cond, f"{p}v_d", "eq")
    E(mov_reg, 6, 0)
    E(bl, f"c_{p}ok")
    E(cmp_imm, 0, 0)
    E(b_cond, f"{p}v_d", "eq")
    slot_off(1, 4, 5)
    E(ldrh_reg, 0, 6, 1)
    vdef(2, 5)
    E(eors_reg, 0, 2)
    E(pop_list, [4, 5, 6], pc=True)
    a.label(f"{p}v_d")
    vdef(0, 5)
    E(pop_list, [4, 5, 6], pc=True)

    a.label(f"c_{p}put")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    E(subs_imm8, 1, v0)
    E(mov_reg, 5, 1)
    E(mov_reg, 6, 2)
    E(bl, f"c_{p}blk")
    E(cmp_imm, 0, 0)
    E(b_cond, f"{p}p_x", "eq")
    E(mov_reg, 7, 0)
    E(bl, f"c_{p}ok")
    E(cmp_imm, 0, 0)
    E(b_cond, f"{p}p_k", "ne")
    E(movs_imm, 0, 0)
    E(movs_imm, 1, 0)
    a.label(f"{p}p_z")
    E(raw, h(0x5478))                                      # strb r0, [r7, r1]
    E(adds_imm8, 1, 1)
    E(cmp_imm, 1, blen)
    E(b_cond, f"{p}p_z", "lo")
    E(movs_imm, 0, marks[0])
    E(strb_imm, 0, 7, 0)
    E(movs_imm, 0, marks[1])
    E(strb_imm, 0, 7, 1)
    a.label(f"{p}p_k")
    vdef(2, 5)
    E(eors_reg, 2, 6)
    slot_off(1, 4, 5)
    E(strh_reg, 2, 7, 1)
    E(mov_reg, 0, 7)
    E(bl, f"c_{p}sum")
    E(strb_imm, 0, 7, 2)
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    E(b_cond, f"{p}p_x", "eq")
    E(movw, 1, O)
    E(adds_reg, 0, 0, 1)
    E(ldrb_imm, 1, 0, 0)
    E(movs_imm, 2, 1)
    E(lsls_reg, 2, 4)
    E(orrs_reg, 1, 2)
    E(strb_imm, 1, 0, 0)
    a.label(f"{p}p_x")
    E(pop_list, [4, 5, 6, 7], pc=True)

    a.label(f"c_{p}reset")
    E(push_list, [4, 5], lr=True)
    E(mov_reg, 4, 0)
    E(movs_imm, 5, 0)
    a.label(f"{p}r_l")
    E(mov_reg, 0, 4)
    E(mov_reg, 1, 5)
    E(adds_imm8, 1, v0)
    vdef(2, 5)
    E(bl, f"c_{p}put")
    E(adds_imm8, 5, 1)
    E(cmp_imm, 5, n)
    E(b_cond, f"{p}r_l", "lo")
    E(pop_list, [4, 5], pc=True)


def install(img, report, base_addr, vol=False, move=False, px=False, glide=False, fade=False):
    """After pshape (FILT through strip()), stockplus_rp, rhrec, countin, dspready and rhstate; with ourram's slot (RH_FSHAPE=1).
    vol: strip(vol=True), pshape with vol; LVL in place of the stock's level ramp."""
    import rhbuild
    import rhdsp1
    import rhrec
    for need in ("pshape", "stockplus", "rhrec", "countin", "cthresh", "rhstate"):
        assert need in report, f"fshape needs {need}"
    assert getattr(PS, "FILT", None), "fshape.strip() before pitchmod"
    assert "fshape" in rhstate.OFF and rhstate.OFF["fshape"][1] >= 8, "fshape needs ourram's slot (RH_FSHAPE=1)"
    rhrec.check_layout()
    assert all(o + n <= BLK_OFF for o, n in rhrec.OFF54.values()) and BLK_OFF + BLK_LEN <= 530, "the block between Remix's and the page block"
    if vol:
        assert len(PS.FILT) > 2 and report["pshape"].get("vol"), "vol: strip(vol=True) and pshape's vol"
        gm, pc = rhrec.OFF["granmulti"], rhrec.OFF["patchain"]
        assert gm[0] <= VBLK_OFF and VBLK_OFF + VBLK_LEN <= pc[0] + pc[1] and not any(k in report for k in ("granmulti", "patchain"))
    lab = lambda m, k: int(report[m]["labels"][k], 16)                         # noqa: E731
    sp = report["stockplus"]
    L = dict(c_rst=lab("rhstate", "c_rst"), c_rrt=lab("rhrec", "c_rrt"), c_ciok=lab("countin", "c_ciok"),
             c_spint=lab("stockplus", "c_spint"), c_spw=lab("stockplus", "c_spw"),
             c_shval=lab("pshape", "c_shval"), c_shput=lab("pshape", "c_shput"),
             t_rate=int(sp["tables"], 16) + 4 * 129, t_steps=int(report["pshape"]["steps"], 16))
    assert not move or (vol and MOVE[0] and "mixmove" in report), "move: strip(move=True) and mixmove's hooks"
    assert not px or (move and PX[0] and VBLK_OFF + VBLK_LEN <= PXBLK_OFF and PXBLK_OFF + PXBLK_LEN <= BLK_OFF), "px: strip(px=True)"
    assert not glide or (px and GLIDE[0]), "glide: strip(glide=True)"
    if fade:
        pc = rhrec.OFF["patchain"]
        assert glide and FADE[0] and PXBLK_OFF + PXBLK_LEN <= FIBLK_OFF and FIBLK_OFF + FIBLK_LEN <= pc[0] + pc[1] and FIBLK_OFF < 256, "fade: strip(fade=True)"
    code, labels = arm_code(base_addr, L, vol, move, px, glide, fade)
    img += bytes([0xFF]) * (base_addr - rhbuild.BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    assert DSP_LABELS, "pitchmod built voicefilt after fshape.strip()"
    extra = {}
    if vol:
        lvl = PS.LABELS["lvl"]
        assert lvl < 0x1000, "LVL in the short jsr's reach"
        rhdsp1.patch_p(img, LVL_CALL, 0x0D0000 | STOCK_LVL, 0x0D0000 | lvl)
        extra = dict(vol=True, vb=hex(VB), lvl=hex(lvl), vblk_off=VBLK_OFF, vdefs=list(VDEF_M if move else VDEF))
        if move:
            extra.update(move=True, mb=hex(MB))
        if px:
            extra.update(px=True, pxblk_off=PXBLK_OFF, pxdefs=list(PXDEF), rd=hex(RD), ro=hex(RO), seed=hex(RSEED))
        if glide:
            extra.update(glide=True, gk=hex(GK), gp=hex(GP))
        if fade:
            extra.update(fade=True, fiblk_off=FIBLK_OFF, fidefs=list(FIDEF), fr=hex(FR), fw=hex(FW))
    report["fshape"] = dict(fb=hex(FB), blk_off=BLK_OFF, lpidx=hex(DSP_LABELS["lpidx"]), defs=list(DEF), slot=hex(rhstate.ST + rhstate.OFF["fshape"][0]),
                            labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")}, **extra)
    return labels, code
