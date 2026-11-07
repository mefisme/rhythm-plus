"""Shapes for Stock+'s pitch envelope and pitch LFO (MIT; Rhythm Plus, Circuit Rhythm 5706).

  * core 1 (pitchmod's RR and TRIG, replaced through pitchmod.code): the envelope is a timeline T 0 .. 1 ($7FFFFF), T += S each pitch
    update (S = D's word: stockplus's decay table holds steps, the decay knob = the shape's length); TRIG sets T = 0.  The pitch is
    A x ENV[shape](T) + L x LFO[shape](phase / 2); a shape is NPT points read with linear interpolation, or held (step shapes);
  * the tables: core 1's Y:ENV_Y + STRIDE s (16 envelopes), Y:LFO_Y + STRIDE s (10 LFOs): word 0 the mode (0 linear, 1 held), then
    NPT points at half scale; the ARM writes them WPF words a frame in turn (c_shframe, with dspready's READY), so a reset of core 1
    gets them back (after Stock+'s wait, as its words);
  * the shape of each track: Stock+'s value I_ENV (10, the bitcrush's) and I_LFO (6, K7's, stored XOR 8192: c_shval / c_shput take it
    off, so 0 = the first shape in every project); c_spdsp writes them (c_shenv / c_shlfo) to Y:SHP_E + t / SHP_L + t, in place of the
    stretch word and the drive type.
RAM: rhstate "pshape" + 0: the next table word (halfword).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, adds_reg, b, b_cond, b_w, bl, cmp_imm, eors_reg, h, ldr_imm, ldrb_imm, lsls_imm, lsrs_imm, mov_reg, movs_imm,  # noqa: E402
                   movt, movw, pop_list, push_list, raw, subs_imm8)
import pitchmod as PM  # noqa: E402
import rhdsppatch as DP  # noqa: E402
import rhstate  # noqa: E402

NPT, STRIDE = 33, 64
ENV_Y, LFO_Y = 0x1780, 0x1B80                            # core 1's Y (free: no stock reference, above voicefilt's $1700..$177F)
SHIFT = 0x300
YB = PM.Y_BASE + SHIFT                                   # pitchmod's words, track t at + t
SHP_E, SHP_L, SCR = 0x16D0, 0x16D8, 0x16E0               # + t: the envelope's / the LFO's shape; SCR: RR's scratch word
I_ENV, I_LFO = 10, 6
X7 = 8192
WPF = 4
READY = 0xA0
SP_WAIT = 200                                            # stockplus.SP_WAIT
ENV_NAMES = ("drop", "fast drop", "straight drop", "rise", "fast rise", "up and down", "down and up", "hold then drop",
             "overshoot", "bounce", "octave steps", "fifth and octave", "stairs", "trill", "random steps", "swell")
LFO_NAMES = ("triangle", "sine", "saw up", "saw down", "square", "narrow pulse", "stairs", "random steps", "smooth random", "bounce")
NE, NL = len(ENV_NAMES), len(LFO_NAMES)
assert ENV_Y + NE * STRIDE <= LFO_Y and LFO_Y + NL * STRIDE <= 0x2000                 # below the comb's buffers (Y:$2000)
GATE_NAMES = ("pump", "short gate", "long gate", "pattern 1", "pattern 2", "stutter")  # (vol) the volume's shapes after the 10 LFOs
VOL_Y, NG = 0x1E80, len(GATE_NAMES)
assert VOL_Y + NG * STRIDE <= 0x2000
FILT = None                                              # (fshape.strip()) (RR's filter half, TRIG's[, code after RR]) item lists
LABELS = {}                                              # RR's labels in core 1, as pitchmod placed them
LATE_PITCH = [False]                                     # (fshape nfollow) PADD keeps voicefilt's pitch, not RR's entry
PADD = None                                              # (fshape.strip(px=True)) RR's items after the pitch's sum, before the clamp
PLFO = None                                              # (fshape.strip(fade=True)) RR's items on b = L x LFO, before the envelope joins it


def _drop(t, base):
    return (base ** t - base) / (1 - base)


def _overshoot(t):
    return (1 - math.exp(-2 * t) * math.cos(2.5 * math.pi * t)) / OVER_PEAK


OVER_PEAK = 1.4632901618832035                              # the curve's top, at t = 12 / 32: scaled to 1, it settles at 0.68


def env_shape(k, v2=False):
    """-> (held, NPT values in -1 .. 1) of envelope k over its timeline 0 .. 1; v2: the overshoot inside the table"""
    ts = [i / (NPT - 1) for i in range(NPT)]
    steps = (0.7, -0.75, 0.85, -0.5, 0.9, 0.35, -0.2, -0.45, 0.0)
    f = (lambda t: _drop(t, 0.05),
         lambda t: _drop(t, 0.001),
         lambda t: 1 - t,
         lambda t: 1 - _drop(t, 0.05),
         lambda t: 1 - _drop(t, 0.001),
         lambda t: math.sin(math.pi * t),
         lambda t: -math.sin(math.pi * t),
         lambda t: 1.0 if t <= 0.5 else (1 - (t - 0.5) / 0.5) ** 3,
         _overshoot if v2 else lambda t: 1 - math.exp(-6 * t) * math.cos(2.5 * math.pi * t),
         lambda t: math.exp(-4 * t) * math.cos(6 * math.pi * t) * (1 - t),
         lambda t: (1.0, 0.5, 0.0)[min(2, int(t * 3))],
         lambda t: (1.0, 7 / 12, 0.0)[min(2, int(t * 3))],
         lambda t: 1 - min(8, int(t * 8)) / 8,
         lambda t: (1.0 if int(t * 12) % 2 == 0 else 0.0) if t < 0.75 else 0.0,
         lambda t: steps[min(8, int(t * 8))],
         lambda t: t * t)[k]
    held = k in (10, 11, 12, 13, 14)
    vs = [f(t) for t in ts]
    assert not v2 or all(abs(v) <= 1 + 1e-9 for v in vs), (k, "clipped")
    return held, [max(-1.0, min(1.0, v)) for v in vs]


def lfo_shape(k):
    """-> (held, NPT values) of LFO k over one cycle (point NPT - 1 = point 0); the triangle, sine and saws cross 0 rising at a quarter"""
    us = [i / (NPT - 1) for i in range(NPT)]
    vals = (0.9, -0.6, 0.0, 0.7, -1.0, 0.4, -0.3, 0.8)

    def tri(u):
        return 4 * u - 1 if u < 0.5 else 3 - 4 * u
    f = (tri,
         lambda u: math.sin(2 * math.pi * (u - 0.25)),
         lambda u: 2 * ((u + 0.25) % 1) - 1,
         lambda u: 1 - 2 * ((u + 0.25) % 1),
         lambda u: 1.0 if 0.25 <= u % 1 < 0.75 else -1.0,
         lambda u: 1.0 if 0.25 <= u % 1 < 0.375 else 0.0,
         lambda u: (-1.0, -1 / 3, 1 / 3, 1.0)[int((u % 1) * 4)],
         lambda u: vals[int((u % 1) * 8)],
         lambda u: vals[int((u % 1) * 8)],
         lambda u: 2 * abs(math.sin(math.pi * u)) - 1)[k]
    held = k in (4, 5, 6, 7)
    if k == 8:                                             # smooth random: the 8 values joined by lines
        pts = []
        for u in us:
            x = (u % 1) * 8
            i = int(x)
            pts.append(vals[i % 8] + (vals[(i + 1) % 8] - vals[i % 8]) * (x - i))
        return False, pts
    return held, [max(-1.0, min(1.0, f(u))) for u in us]


def gate_shape(k):
    """-> (held, NPT values) of volume shape k: +1 open, -1 shut; u_b = the cycle from the synced LFO's start (a quarter in)"""
    def g(u):
        ub = (u - 0.25) % 1
        if k == 0:
            return 2 * (1 - math.exp(-6 * ub)) / (1 - math.exp(-6)) - 1
        if k in (1, 2):
            return 1.0 if ub < (0.25, 0.75)[k - 1] else -1.0
        if k in (3, 4):
            s, f = int(ub * 4), (ub * 4) % 1
            return 1.0 if ((1, 1, 0, 1), (1, 0, 1, 1))[k - 3][s] and f < 0.75 else -1.0
        return 1.0 if (ub * 8) % 1 < 0.5 else -1.0
    return k != 0, [g(i / (NPT - 1)) for i in range(NPT)]


def half(v):
    return round(v * 0.5 * (1 << 23)) & 0xFFFFFF


def table_words(v2=False, vol=False):
    """core 1's Y from ENV_Y: STRIDE words a shape (envelopes, then LFOs from LFO_Y, vol: the gates from VOL_Y); None = not written"""
    out = [None] * ((VOL_Y - ENV_Y + NG * STRIDE) if vol else (LFO_Y - ENV_Y) + NL * STRIDE)
    for base, n, fn in ((0, NE, lambda s: env_shape(s, v2)), (LFO_Y - ENV_Y, NL, lfo_shape)) + (((VOL_Y - ENV_Y, NG, gate_shape),) if vol else ()):
        for s in range(n):
            held, pts = fn(s)
            o = base + STRIDE * s
            out[o] = 1 if held else 0
            out[o + 1:o + 1 + NPT] = [half(v) for v in pts]
    return out


def value(table, pos):
    """the DSP's lookup (for the tests): the shape at table (mode, points), pos 0 .. $7FFFFF -> the full-scale value (24-bit signed)"""
    i, frac = pos >> 18, (pos & 0x3FFFF) << 5
    if table[0]:
        frac = 0
    s = lambda w: w - (1 << 24) if w & 0x800000 else w      # noqa: E731
    v0, v1 = s(table[1 + i]), s(table[2 + i])
    d = max(-0x800000, min(0x7FFFFF, v1 - v0))
    v = v0 + ((frac * d) >> 23)
    return max(-0x800000, min(0x7FFFFF, 2 * v))


def step_table():
    """stockplus's decay table as steps: the timeline's S for the knob's 129 points (the shape lasts T_MIN .. T_MAX)"""
    import stockplus as SP
    out = []
    for i in range(129):
        n = max(SP.T_MIN * (SP.T_MAX / SP.T_MIN) ** (i / 128) * SP.UPD, 1.0)
        out.append(min(0x7FFFFF, round(0x7FFFFF / n)))
    return out


def shape_index(v, n):
    return (v * n) >> 14


# ---------------------------------------------------------------- core 1
def lk_items():
    """lk: a1 = the position 0 .. $7FFFFF, r0 = the shape's table in Y -> a = its value; changes b, x0, x1, y1, r0"""
    return [("label", "lk"),
            "move a1,b", "lsr #18,b", "move y:(r0)+,x0", "move r0,x1", "add x1,b", "move b1,r0",
            "move a1,b", "and #>$3ffff,b", "asl #5,b,b",
            "move x0,a", "tst a", ("jcc", "eq", "lk_l"), "clr b",
            ("label", "lk_l"),
            "move b1,x1", "move y:(r0)+,x0", "move y:(r0),a", "sub x0,a", "move a,y1", "mpy y1,x1,a", "add x0,a", "asl a", "rts"]


def code(at, shift=0, store_pitch=False, scan=False, stretch=False, lscan=None):
    """pitchmod.code's place: -> (words for P:at.., RR's address, TRIG's address)"""
    import voicefx as V
    assert shift == SHIFT and not stretch and lscan is None, "pshape: pitchmod with the shift, no stretch"
    yb, t0, t1 = YB, PM.Y_TMP0 + shift, PM.Y_TMP1 + shift
    extra = ([f"move y0,y:(r1+${PM.OFF_PITCH:x})"] if store_pitch and not LATE_PITCH[0] else []) + (
        [f"move y:(r1+${PM.OFF_SCANPH:x}),a", f"move y:(r1+${PM.OFF_SCANR:x}),x0", "add x0,a", f"move a1,y:(r1+${PM.OFF_SCANPH:x})"] if scan else [])
    filt = [*FILT[0](), f"move #>${yb:x},r1", "lua (r1)+n1,r1"] if FILT else []
    rr = ["move r4,a", "sub #>$40,a", "lsr #4,a", "move a1,n1", f"move #>${yb:x},r1", "lua (r1)+n1,r1", *extra, *filt,
          "move y:(r1),a", f"move y:(r1+${PM.OFF_D:x}),x0", "add x0,a",                                   # T += S, at most 1
          "move #>$7fffff,x0", "cmp x0,a", "tgt x0,a", "move a1,y:(r1)",
          f"move y:(r1+${SHP_E - yb:x}),b", "asl #6,b,b", f"add #>${ENV_Y:x},b", "move b1,r0",
          ("jsr", "lk"),
          "move a,x0", f"move y:(r1+${PM.OFF_A:x}),x1", "mpy x1,x0,a", f"move a,y:>${SCR:x}",             # A x ENV(T)
          f"move y:(r1+${PM.OFF_PH:x}),a", f"move y:(r1+${PM.OFF_R:x}),x0", "add x0,a", f"move a1,y:(r1+${PM.OFF_PH:x})",
          "lsr #1,a",
          f"move y:(r1+${SHP_L - yb:x}),b", "asl #6,b,b", f"add #>${LFO_Y:x},b", "move b1,r0",
          ("jsr", "lk"),
          "move a,x0", f"move y:(r1+${PM.OFF_L:x}),x1", "mpy x1,x0,b", *(PLFO() if PLFO else []), f"move y:>${SCR:x},a", "add a,b",  # + L x LFO(phase)
          "move y0,a", "add b,a", *(PADD() if PADD else []),
          f"move #>${PM.PITCH_MAX:x},x0", "cmp x0,a", "tgt x0,a",
          f"move #>${PM.PITCH_MIN:x},x0", "cmp x0,a", "tlt x0,a",
          "move a1,y0", ("jmp", PM.P_EXP),
          *lk_items(),
          *(FILT[2]() if FILT and len(FILT) > 2 else [])]
    rw, labels = V.assemble(rr, at)
    LABELS.update(labels)
    trig_at = at + len(rw)
    trig = (DP.asm([f"move y1,y:>${t0:x}"]) + DP.jsr(PM.P_START) + DP.asm([
        f"move y:>${t0:x},a", "and #>$7,a", "move a1,n1", f"move #>${yb:x},r1",
        "move #>$0,x0", "move x0,y:(r1+n1)", *(FILT[1]() if FILT else []),                            # T = 0
        "move y:>$121,x0", f"move x0,y:>${t1:x}", "sub #>$1,a", "and #>$7,a", "move a1,y:>$121"])
        + DP.jsr(PM.P_RR) + DP.asm([f"move y:>${t1:x},x0", "move x0,y:>$121", "rts"]))
    return rw + trig, at, trig_at


def strip():
    """from now on pitchmod builds our RR and TRIG"""
    PM.code = code


# ---------------------------------------------------------------- the ARM
def arm_code(base, L, v2=False, once=False, vol=False):
    a = Asm(base)
    E = a.emit
    O = rhstate.OFF["pshape"][0]
    O_TH = rhstate.OFF["cthresh"][0] + 1

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, (v >> 16) & 0xFFFF)
    tw = table_words(v2, vol)
    t_tab = base
    E(raw, b"".join((0xFFFFFFFF if w is None else w).to_bytes(4, "little") for w in tw))

    # ---- c_shval(r0 = track, r1 = value) -> r0: Stock+'s value, I_LFO without its XOR; c_shput(r0, r1, r2 = v): the same way in
    a.label("c_shval")
    E(push_list, [4], lr=True)
    E(mov_reg, 4, 1)
    E(bl, L["c_spval"])
    E(cmp_imm, 4, I_LFO)
    E(b_cond, "sv_x", "ne")
    E(movw, 1, X7)
    E(eors_reg, 0, 1)
    a.label("sv_x")
    E(pop_list, [4], pc=True)
    a.label("c_shput")
    E(cmp_imm, 1, I_LFO)
    E(b_cond, "sp_j", "ne")
    E(movw, 3, X7)
    E(eors_reg, 2, 3)
    a.label("sp_j")
    E(b_w, L["c_spput"])

    # ---- c_shenv(r4 = track) -> r0 = its envelope's shape, r1 = SHP_E; c_shlfo(r4) -> r0 = its LFO's shape (c_spdsp's words)
    a.label("c_shenv")
    E(push_list, [], lr=True)
    E(mov_reg, 0, 4)
    E(movs_imm, 1, I_ENV)
    E(bl, L["c_spval"])
    E(lsls_imm, 0, 0, 4)
    E(lsrs_imm, 0, 0, 14)
    E(movw, 1, SHP_E)
    E(pop_list, [], pc=True)
    a.label("c_shlfo")
    E(push_list, [], lr=True)
    E(mov_reg, 0, 4)
    E(movs_imm, 1, I_LFO)
    E(bl, "c_shval")
    E(movs_imm, 1, NL)
    E(raw, h(0x4348))                                      # muls r0, r1
    E(lsrs_imm, 0, 0, 14)
    E(pop_list, [], pc=True)

    # ---- c_shframe(): WPF table words into core 1 (the mode 0 program only), in turn; once: one pass after each Stock+ wait; clobbers r0-r3
    a.label("c_shframe")
    E(push_list, [4, 5, 6], lr=True)
    E(bl, L["c_ciok"])
    E(cmp_imm, 0, 0)
    E(b_cond, "sf_x", "eq")
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    E(b_cond, "sf_x", "eq")
    E(movw, 1, O_TH)
    E(adds_reg, 1, 0, 1)
    E(ldrb_imm, 1, 1, 0)
    E(cmp_imm, 1, READY)
    E(b_cond, "sf_r" if once else "sf_x", "ne")
    E(movw, 1, rhstate.OFF["spwait"][0])
    E(adds_reg, 1, 0, 1)
    E(ldrb_imm, 1, 1, 0)
    E(cmp_imm, 1, SP_WAIT)
    E(b_cond, "sf_r" if once else "sf_x", "lo")            # core 1 still starting: Stock+'s wait first
    E(movw, 1, O)
    E(adds_reg, 6, 0, 1)                                   # r6 = our slot
    E(movs_imm, 5, WPF)
    a.label("sf_l")
    E(raw, h(0x8834))                                      # ldrh r4, [r6]
    if once:
        E(movw, 1, len(tw))
        E(raw, h(0x428C))                                  # cmp r4, r1
        E(b_cond, "sf_x", "hs")                            # the pass done
    E(lsls_imm, 1, 4, 2)
    imm32(0, t_tab)
    E(adds_reg, 0, 0, 1)
    E(ldr_imm, 0, 0, 0)
    E(movs_imm, 1, 0)
    E(raw, h(0x43C9))                                      # mvns r1, r1
    E(raw, h(0x4288))                                      # cmp r0, r1
    E(b_cond, "sf_n", "eq")                                # not written
    E(movw, 1, ENV_Y)
    E(adds_reg, 1, 1, 4)
    E(bl, L["c_spw"])
    E(subs_imm8, 5, 1)
    a.label("sf_n")
    E(raw, h(0x8834))                                      # ldrh r4, [r6]
    E(raw, h(0x1C64))                                      # adds r4, r4, #1
    E(movw, 1, len(tw))
    E(raw, h(0x428C))                                      # cmp r4, r1
    E(b_cond, "sf_w", "lo")
    if not once:
        E(movs_imm, 4, 0)
    a.label("sf_w")
    E(raw, h(0x8034))                                      # strh r4, [r6]
    E(cmp_imm, 5, 0)
    E(b_cond, "sf_l", "gt")
    if once:
        E(b, "sf_x")
        a.label("sf_r")                                    # r0 = rhstate: the next pass from the start
        E(movw, 1, O)
        E(adds_reg, 1, 0, 1)
        E(movs_imm, 2, 0)
        E(raw, h(0x800A))                                  # strh r2, [r1]
    a.label("sf_x")
    E(pop_list, [4, 5, 6], pc=True)
    return a.assemble(), t_tab


def install(img, report, base_addr, v2=False, once=False, vol=False):
    """After stockplus_rp (v2, nocrush, no stretch), countin, dspready and rhstate; pitchmod built after strip()."""
    import rhbuild
    import stockplus as SP
    import voicefx as V
    lab = lambda m, k: int(report[m]["labels"][k], 16)                         # noqa: E731
    for need in ("stockplus", "countin", "cthresh", "rhstate", "pitchmod"):
        assert need in report, f"pshape needs {need}"
    sp = report["stockplus"]
    assert sp.get("no_stretch") and sp.get("no_crush"), "pshape takes the stretch word and the drive type"
    assert PM.code is code, "pshape.strip() before pitchmod"
    assert "pshape" in rhstate.OFF, "pshape needs ourram's slot (RH_PSHAPE=1)"
    L = dict(c_rst=lab("rhstate", "c_rst"), c_ciok=lab("countin", "c_ciok"),
             **{k: lab("stockplus", k) for k in ("c_spval", "c_spput", "c_spw")})
    assert not vol or once, "vol: the tables once after each wait"
    (code_arm, labels), t_tab = arm_code(base_addr, L, v2, once, vol)
    img += bytes([0xFF]) * (base_addr - rhbuild.BASE - len(img)) + code_arm
    while len(img) % 4:
        img += bytes([0xFF])
    hw = lambda a: int.from_bytes(img[a - rhbuild.BASE:a - rhbuild.BASE + 2], "little")   # noqa: E731
    from thumb import movw as MOVW
    sw = int(sp["sd_sw"], 16)
    o = sw - rhbuild.BASE
    import stretch as STR
    assert hw(sw) == 0x2000 and bytes(img[o + 2:o + 6]) == MOVW(1, STR.STRETCH), "c_spdsp's stretch word moved"
    img[o:o + 6] = bl(sw, labels["c_shenv"]) + h(0xBF00)
    cr = int(sp["no_crush"], 16)
    o = cr - rhbuild.BASE
    vy = V.Y_BASE + SHIFT
    assert hw(cr) == 0x2000 and hw(cr + 2) == 0xBF00 and bytes(img[o + 4:o + 8]) == MOVW(1, vy + V.DTYPE), "c_spdsp's drive type moved"
    img[o:o + 4] = bl(cr, labels["c_shlfo"])
    img[o + 4:o + 8] = MOVW(1, SHP_L)
    old = b"".join(w.to_bytes(4, "little") for w in SP.decay_table())
    at = bytes(img).find(old)
    assert at > 0 and bytes(img).find(old, at + 1) < 0, "stockplus's decay table"
    img[at:at + len(old)] = b"".join(w.to_bytes(4, "little") for w in step_table())
    report["pshape"] = dict(tables=hex(t_tab), steps=hex(rhbuild.BASE + at), env=list(ENV_NAMES), lfo=list(LFO_NAMES), v2=v2, once=once, vol=vol,
                            slot=hex(rhstate.ST + rhstate.OFF["pshape"][0]), labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code_arm
