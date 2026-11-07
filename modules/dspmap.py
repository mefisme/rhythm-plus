"""The DSP's memory ledger (MIT; Rhythm Plus, Circuit Rhythm 5706): every region a build's code or tables own, per core and space.

regions(report) -> [Region]: the stock's regions and each feature's, from the modules' own constants and the build's report (a feature's
regions only when the build has it).  tests/emu_dspmap.py fails a build when two regions overlap or when core 1's program reads or writes
an address outside every region.  Core 1: P $0..$FFF, X $0..$2FFF, Y $0..$1FFF; core 0: P $0..$3FFF, X $0..$5FFF, Y $0..$3FFF (the
memory switch's split).  Shared memory ($30000..) is the stock's and is not listed.
"""
from __future__ import annotations

import sys
from collections import namedtuple
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]

Region = namedtuple("Region", "core space start end owner")       # end: one past the last word
REUSE = "in stock code: "                                         # an owner's prefix: words of the stock's program that never run, rewritten
SIZE = {(1, "p"): 0x1000, (1, "x"): 0x3000, (1, "y"): 0x2000, (0, "p"): 0x4000, (0, "x"): 0x6000, (0, "y"): 0x4000}


def regions(rep):
    import fshape as FS
    import loopxf as XF
    import mixmove as MM
    import pitchmod as PM
    import pshape as PS
    import voicefilt as VF
    import voicefx as VX
    out = []
    c0 = rep.get("c0fx")

    def add(core, space, start, n, owner):
        out.append(Region(core, space, start, start + n, owner))

    # core 1, the stock
    add(1, "p", 0, 0xD32, "stock program")
    add(1, "x", 0, 0x200, "stock: voice state")
    add(1, "x", 0x200, 0x2800, "stock: pitch filter tables")
    add(1, "x", 0x2A00, 0xCF, "stock: voice buffers, rate table")
    add(1, "y", 0, 0x400, "stock: voice state, rate tables")
    add(1, "y", 0x400, 0x1000, "stock: sample rings (8 x 512)")
    add(1, "y", 0x1400, 0x10, "stock: filter coefficients, voice index")
    pm = rep.get("pitchmod")
    if pm:
        sh = int(pm["shift"], 16)
        yb = PM.Y_BASE + sh
        add(1, "p", int(pm["start"], 16), pm["core1_words"], "our core 1 code (pitchmod's block)")
        add(1, "y", int(pm["y_idle"], 16), 3, "pitchmod: idle, burn, block count")
        add(1, "y", PM.Y_TMP0 + sh, 2, "pitchmod: TRIG scratch")
        add(1, "y", yb, VX.Y_BASE - PM.Y_BASE, "pitchmod: envelope, LFO")
        if pm.get("fx"):
            add(1, "y", VX.Y_BASE + sh, 0x60, "voicefx: ring, filter, drive words")
            if not rep.get("nocomb"):
                add(1, "y", VX.SHIFT_COMB if sh else VX.Y_COMB, 0x800, "voicefx: comb rings (8 x 256)")
        add(1, "y", VX.Y_BASE + sh + 0x60, PM.OFF_PITCH - (VX.Y_BASE - PM.Y_BASE) - 0x60, "voicefilt: type, follow")
        add(1, "y", yb + PM.OFF_PITCH, 0x20, "pitchmod: pitch, scan LFO")
        add(1, "y", VF.TMP, 7, "voicefilt: scratch")
        add(1, "y", VF.STATE2, 0x80, "voicefilt: biquad states, kept coefficients")
        if pm.get("loopxf"):
            add(1, "p", XF.AT, XF.END - XF.AT, REUSE + "loopxf: XF")
            add(1, "p", XF.WC_AT, XF.WC_END - XF.WC_AT, REUSE + "loopxf: WC")
            add(1, "y", XF.TEMP, XF.N_MAX, "loopxf: TEMP")
    if rep.get("pshape"):
        add(1, "y", PS.SHP_E, 8, "pshape: envelope shape + t")
        add(1, "y", PS.SHP_L, 8, "pshape: LFO shape + t")
        add(1, "y", PS.SCR, 1, "pshape: RR scratch")
        for s in range(PS.NE):
            add(1, "y", PS.ENV_Y + PS.STRIDE * s, 1 + PS.NPT, f"pshape: envelope {s}")
        for s in range(PS.NL):
            add(1, "y", PS.LFO_Y + PS.STRIDE * s, 1 + PS.NPT, f"pshape: LFO {s}")
        if rep["pshape"].get("vol"):
            for s in range(PS.NG):
                add(0 if c0 else 1, "y", PS.VOL_Y + PS.STRIDE * s, 1 + PS.NPT, f"pshape: gate {s}")
        if c0:
            for s in range(PS.NL):
                add(0, "y", PS.LFO_Y + PS.STRIDE * s, 1 + PS.NPT, f"pshape: LFO {s} (c0fx's copy)")
    fs = rep.get("fshape")
    if fs:
        add(1, "y", FS.FB, FS.O_M + 8, "fshape: filter LFO")
        if fs.get("vol"):
            add(0 if c0 else 1, "y", FS.VB, FS.O_VX + 8, "fshape: volume LFO")
            if not c0:
                add(1, "y", FS.LVL_R0, 1, "fshape: LVL's r0")
        if fs.get("move"):
            add(0 if c0 else 1, "y", FS.MB, 16, "fshape: move LFO")
        if fs.get("px"):
            add(1, "y", FS.RD, 8, "fshape: random pitch depth")
            add(1, "y", FS.RSEED, 1, "fshape: random seed")
            add(1, "y", FS.RO, 8, "fshape: note offset")
        if fs.get("glide"):
            add(1, "y", FS.GK, 16, "fshape: glide")
        if fs.get("fade"):
            add(1, "y", FS.FR, 16, "fshape: fade-in")
        if fs.get("sm"):
            add(1, "y", FS.SMF, 8, "fshape: Sample mode switches")
        if fs.get("declick") is True:
            add(1, "y", FS.DCB, 16, "fshape: de-click D, L")
        if fs.get("drone"):
            add(1, "y", FS.LN, 16, "fshape: drone's last note-on, last note-off's block")
        if fs.get("declick") or fs.get("loopfade"):
            add(1, "p", FS.LOW_AT, FS.LOW_END - FS.LOW_AT, REUSE + "fshape: low code (the dead level ramp)")
        if fs.get("loopxf"):
            add(1, "y", FS.XFS, len(FS.XF_SCRATCH), "loopxf: scratch (moved)")
            add(1, "y", FS.XFB, 8, "loopxf: on + t (moved)")
    pv = rep.get("pvloop")
    if pv:
        import pvloop as PV
        add(1, "p", PV.A1, PV.E1 - PV.A1, REUSE + "pvloop: the preview player")
        add(1, "p", PV.A2, PV.E2 - PV.A2, REUSE + "pvloop: the preview gain")
    # core 0, the stock (data: its pointers and absolute addresses, and what reads non-zero on a playing unit)
    add(0, "p", 0, 0x1FED, "stock program")
    add(0, "x", 0, 0x1400, "stock: state, mixer")
    add(0, "x", 0x1600, 0xE00, "stock: tables, effect words")
    add(0, "x", 0x4400, 0x900, "stock: tables, effect words")
    add(0, "x", 0x4F80, 0x10, "stock: words at $4F85 / $4F87")
    add(0, "y", 0, 0x1400, "stock: state, mixer")
    add(0, "y", 0x2000, 0x800, "stock: effect words")
    mm = rep.get("mixmove")
    if mm:
        add(0, "p", MM.AT, mm["words"], REUSE + "mixmove: hooks (unused vectors)")
        add(0, "x", MM.Q, 0x20, "mixmove: Q")
        add(0, "y", MM.YD, 0x18, "mixmove: pan, reverb, delay depth")
    if c0:
        import c0fx as C0
        import core0
        add(0, "p", int(c0["at"], 16), c0["words"], "c0fx: the LFOs and the ring mod")
        add(0, "p", core0.LD, rep["core0"]["ld_words"], "core0: Remix's loader")
        add(0, "y", C0.MP, 8, "c0fx: move phase")
        add(0, "y", C0.SAVE, 24, "c0fx: the stock's registers")
        add(0, "y", C0.ring_y(), C0.VX_RAM + 8, "c0fx: ring phase, step, amount (voicefx's)")
    return out


def overlaps(regs):
    """-> [(a, b)]: regions of one core and space that share a word"""
    bad = []
    key = sorted(regs, key=lambda r: (r.core, r.space, r.start))
    for i, a in enumerate(key):
        for b in key[i + 1:]:
            if (b.core, b.space) != (a.core, a.space) or b.start >= a.end:
                break
            if not (a.owner == "stock program" and b.owner.startswith(REUSE)):
                bad.append((a, b))
    return bad


def free(regs, core, space):
    """-> [(start, end)]: the words of a core's space in no region"""
    used = sorted((r.start, r.end) for r in regs if (r.core, r.space) == (core, space))
    out, at = [], 0
    for s, e in used:
        if s > at:
            out.append((at, s))
        at = max(at, e)
    if at < SIZE[(core, space)]:
        out.append((at, SIZE[(core, space)]))
    return out
