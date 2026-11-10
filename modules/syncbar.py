"""One bar language for the rate and shape knobs (MIT; Rhythm Plus, Circuit Rhythm 5706).

  * the rate knobs (Stock+'s pitch LFO rate 2 and scan speed 7, the filter LFO's 16, the volume LFO's 19): what the knob shows and
    turns is the stored value mirrored about the middle (c_uval / c_uput: u = 16384 - v, at most 16383), so right of the middle is
    the engine's synced half and left its free half (free values keep their speed);
  * the synced half's 16 steps, from the middle out: 8 bars, 4, 2, 1 bar, 1/2, 1/4, 1/8, 1/16, then the same as triplets: Stock+'s
    and fshape's DIVS / KQ / PHQ tables (each one copy in flash) in that order (PERM), the code unchanged;
  * c_uval / c_uput are fshape's c_fsval / c_fsput for every other value.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import Asm, b_cond, b_w, bl, cmp_imm, cmp_reg, mov_reg, movw, pop_list, push_list, subs_reg  # noqa: E402

RATES = (2, 7, 16, 19)
MOVE_RATE = 22                                           # (move) the mix page's move rate
MID, DEAD, STEP = 8192, 128, 512                         # a synced step = 4 clicks
SYNC0 = MID + DEAD                                       # the knob's first synced value
PERM = tuple(15 - 2 * (s & 7) - (s >> 3) for s in range(16))   # the knob's step s -> the index into the stock DIVS order
K8_1BAR = MID - (DEAD + 3 * STEP + STEP // 2)            # Stock+'s scan speed default: 1 bar (step 3), stored
NOTES = ("8 bars", "4 bars", "2 bars", "1 bar", "1/2", "1/4", "1/8", "1/16")


def mirror(v):
    """the knob's value <-> the stored one"""
    return min(16383, 16384 - v)


def step_of(u):
    """the knob's value u -> its synced step 0..15, or None (the middle or the free half)"""
    return min(15, (u - SYNC0) // STEP) if u >= SYNC0 else None


def div_index(d, ui=False):
    """stockplus.div_index with the tables in PERM's order (for the tests: stockplus.div_index = this)"""
    assert not ui
    return PERM[min(15, (-d - DEAD) >> 9)]


def tables(divs, kq, phq):
    return b"".join(x.to_bytes(4, "little") for t in (divs, kq, phq) for x in t)


def arm_code(base, L):
    a = Asm(base)
    E = a.emit

    def mirror_reg(r, tag):                              # r = min(16383, 16384 - r); clobbers r3
        E(movw, 3, 16384)
        E(subs_reg, r, 3, r)
        E(movw, 3, 16383)
        E(cmp_reg, r, 3)
        E(b_cond, f"m_{tag}", "le")
        E(mov_reg, r, 3)
        a.label(f"m_{tag}")

    # ---- c_uval(r0 = track, r1 = value) -> r0 = c_fsval's, a rate mirrored; clobbers r1-r3
    a.label("c_uval")
    E(push_list, [4], lr=True)
    E(mov_reg, 4, 1)
    E(bl, L["c_fsval"])
    for i in RATES:
        E(cmp_imm, 4, i)
        E(b_cond, "uv_m", "eq")
    E(pop_list, [4], pc=True)
    a.label("uv_m")
    mirror_reg(0, "v")
    E(pop_list, [4], pc=True)

    # ---- c_uput(r0 = track, r1 = value, r2 = v): c_fsput, a rate mirrored
    a.label("c_uput")
    for i in RATES:
        E(cmp_imm, 1, i)
        E(b_cond, "up_m", "eq")
    E(b_w, L["c_fsput"])
    a.label("up_m")
    mirror_reg(2, "p")
    E(b_w, L["c_fsput"])
    return a.assemble()


def install(img, report, base_addr, move=False, soundonly=False):
    """After stockplus_rp (k3sync, k8sync, no ui) and fshape; move: the move rate mirrored too."""
    import rhbuild
    global RATES
    if soundonly:
        RATES = (2, 7)
    if move:
        assert report["fshape"].get("move")
        RATES = RATES + (MOVE_RATE,)
    import fshape as FS
    import stockplus as SP
    sp = report["stockplus"]
    assert sp.get("k3sync") and sp.get("k8sync") and not sp.get("ui") and "fshape" in report, "syncbar: Stock+ k3sync / k8sync, fshape"
    assert (FS.DIVS, FS.KQ, FS.PHQ) == (SP.DIVS, SP.KQ, SP.PHQ)
    old = tables(SP.DIVS, SP.KQ, SP.PHQ)
    new = tables(*([t[i] for i in PERM] for t in (SP.DIVS, SP.KQ, SP.PHQ)))
    at, b = [], bytes(img)
    i = b.find(old)
    while i >= 0:
        at.append(i)
        i = b.find(old, i + 1)
    assert len(at) == (1 if soundonly else 2), f"the sync tables ({len(at)} found)"
    for o in at:
        img[o:o + len(old)] = new
    L = {k: int(report["fshape"]["labels"][k], 16) for k in ("c_fsval", "c_fsput")}
    code, labels = arm_code(base_addr, L)
    img += bytes([0xFF]) * (base_addr - rhbuild.BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    report["syncbar"] = dict(rates=list(RATES), perm=list(PERM), tables=[hex(rhbuild.BASE + o) for o in at],
                             labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
