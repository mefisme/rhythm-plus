"""mixmove's core 0 hooks in dsptool (MIT; Circuit Rhythm 5706): a build's own core 0 program.

    python tests/emu_mixmove.py BUILD [BUILD ...]      (BUILD: firmware/<build>)

Checks: P:$11E3 / $120C / $123B = short jsr to the hooks; each hook's copy Q against the model for pan and send depths, both signs,
every move value; the stock's three routines with the depths at 0 = the stock's own output; with depths = the stock's output from
the model's gains (r2 = Q, nothing else changed).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import core0  # noqa: E402
import mixmove as M  # noqa: E402
import rhdspemu  # noqa: E402

STOCK = HERE / "remix" / "stock" / "circuitrhythm-firmware-5706-STOCK.bin"
FAILS = []
OUT, NOUT = 0x2008, 2 * 32                                # the ramps' output (Y), 2 words a sample for x:$3a = 32 samples


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def s24(w):
    w &= 0xFFFFFF
    return w - (1 << 24) if w & 0x800000 else w


def mpy(a, b):
    """the DSP's fractional a x b, as the accumulator's top word (truncated toward minus infinity)"""
    return (s24(a) * s24(b) * 2) >> 24


def sat(v):
    return max(-0x800000, min(0x7FFFFF, v)) & 0xFFFFFF


def model(src, m_vals, pd, rd, dd, vx=None):
    """the copy Q (32 words) the three hooks make from X:$9D.. src; vx: the volume cut + t (L and R x (1 - V) first)"""
    q = list(src)
    for t in range(8):
        L, R, rv, dl = (s24(x) for x in src[4 * t:4 * t + 4])
        if vx:
            L, R = (s24(sat(((g << 24) - 2 * g * s24(vx[t])) >> 24)) for g in (L, R))
        m = mpy(m_vals[t], pd[t])
        if m >= 0:
            q[4 * t], q[4 * t + 1] = sat(((L << 24) - 2 * L * m) >> 24), R & 0xFFFFFF
        else:
            q[4 * t], q[4 * t + 1] = L & 0xFFFFFF, sat(((R << 24) + 2 * R * m) >> 24)
        w = sat((s24(m_vals[t]) >> 1) + 0x400000)
        for o, d in ((2, rd[t]), (3, dd[t])):
            s = s24(src[4 * t + o])
            k = mpy(w, d)
            q[4 * t + o] = sat(s + mpy(k, M.FULL - s)) if k >= 0 else sat(s + mpy(k, s))
    return q


def main():
    builds = sys.argv[1:] or ["a0081"]
    for b in builds:
        if b == "--stock":                                  # the stock with only mixmove patched in
            img, rep = bytearray(STOCK.read_bytes()), {}
            M.install(img, rep)
        else:
            d = HERE / "firmware" / b
            img = (d / f"rhythmplus-{b.upper()}.bin").read_bytes()
            rep = json.loads((d / "manifest.json").read_text())["report"]
        mm = rep["mixmove"]
        n, at, ws = core0.block_words(bytearray(img))
        hooks = {k: int(v, 16) for k, v in mm["hooks"].items()}
        bad = [hex(a) for a, nm in M.SITES.items() if ws[a] != 0x0D0000 | hooks[nm]]
        check(f"{b}: P:$11E3 / $120C / $123B = short jsr to the hooks", not bad, bad)
        segs = [("p", 0, ws)]
        _, _, sws = core0.block_words(bytearray(STOCK.read_bytes()))
        top = int(mm["at"], 16) + mm["words"]
        check(f"{b}: the hooks at P:${int(mm['at'], 16):X}..${top - 1:X}, past the SHI's vectors; P:$0..$4F as the stock's",
              int(mm["at"], 16) >= 0x50 and top <= 0x100 and ws[:0x50] == sws[:0x50] and all(w == 0 for w in sws[0x50:0x100]))
        ssegs = [("p", 0, sws)]
        rnd = random.Random(5)

        def mem_for(src, mv, pd, rd, dd, sends=None):
            mem = [("x", M.SRC, src), ("y", M.SH, mv), ("y", M.YD + M.O_PD, pd), ("y", M.YD + M.O_RD, rd), ("y", M.YD + M.O_DD, dd),
                   ("x", 0x39, [5]), ("x", 0x3A, [32])]
            if sends:
                for t in range(8):
                    mem += [("x", 0x307DA + 0x20 * t, [sends[t][0]]), ("x", 0x307DB + 0x20 * t, [sends[t][1]])]
            return mem

        # each hook alone
        cases = []
        for _ in range(6):
            src = [rnd.randrange(0, 0x7FFFFF) if i % 4 < 2 else rnd.randrange(0, M.FULL + 1) for i in range(32)]
            mv = [rnd.choice((0x7FFFFF, 0x800000, 0, 0x400000, 0xC00000)) if rnd.random() < 0.4 else rnd.randrange(1 << 24) for _ in range(8)]
            pd = [rnd.choice((0, 0x7FFE00, rnd.randrange(0x800000))) for _ in range(8)]
            rd = [rnd.choice((0, 0x7FFC00, 0x800000, rnd.randrange(1 << 24))) for _ in range(8)]
            dd = [rnd.choice((0, 0x7FFC00, 0x800000, rnd.randrange(1 << 24))) for _ in range(8)]
            cases.append((src, mv, pd, rd, dd))
        bad = []
        for src, mv, pd, rd, dd in cases:
            want = model(src, mv, pd, rd, dd)
            got = []
            for nm, part in (("lr", (0, 1)), ("rev", (2,)), ("dly", (3,))):
                res, _ = rhdspemu.run(0, call=hooks[nm], mem=mem_for(src, mv, pd, rd, dd), segs=segs, dumps=[("x", M.Q, 32)])
                q = res[("x", M.Q)]
                got += [(4 * t + o, q[4 * t + o]) for t in range(8) for o in part]
            diff = [(i, hex(g), hex(want[i])) for i, g in got if g != want[i]]
            if diff:
                bad.append(diff[:3])
        check(f"{b}: the hooks' Q = the model (pan both ways, sends up and down, 6 random sets)", not bad, bad[:2])
        if "vx" in mm:
            vxa, bad = int(mm["vx"], 16), []
            for src, mv, pd, rd, dd in cases:
                vx = [rnd.choice((0, 0x7FFFFF, 0x400000, rnd.randrange(0x800000))) for _ in range(8)]
                want = model(src, mv, pd, rd, dd, vx)
                res, _ = rhdspemu.run(0, call=hooks["lr"], mem=mem_for(src, mv, pd, rd, dd) + [("y", vxa, vx)], segs=segs,
                                      dumps=[("x", M.Q, 32)])
                q = res[("x", M.Q)]
                diff = [(i, hex(q[i]), hex(want[i])) for i in range(32) if i % 4 < 2 and q[i] != want[i]]
                if diff:
                    bad.append(diff[:3])
            check(f"{b}: (vol) the pan hook's L / R x (1 - V) at Y:${vxa:X} + t, then the pan (6 random sets)", not bad, bad[:2])
        lim = []
        src = [0x600000, 0x500000, M.FULL, 0] * 8
        res, _ = rhdspemu.run(0, call=hooks["rev"], mem=mem_for(src, [0x7FFFFF] * 8, [0] * 8, [0x7FFC00] * 8, [0] * 8), segs=segs,
                              dumps=[("x", M.Q, 32)])
        lim.append(all(res[("x", M.Q)][4 * t + 2] <= M.FULL for t in range(8)))
        res, _ = rhdspemu.run(0, call=hooks["dly"], mem=mem_for(src, [0x7FFFFF] * 8, [0] * 8, [0] * 8, [0x7FFC00] * 8), segs=segs,
                              dumps=[("x", M.Q, 32)])
        lim.append(all(res[("x", M.Q)][4 * t + 3] <= M.FULL for t in range(8)) and res[("x", M.Q)][3] > 0x1F0000)
        check(f"{b}: a send pushed to the top stays at most the stock's full ({M.FULL:#x}); from 0 it reaches near full", all(lim), lim)

        # the stock's three routines, patched against unpatched
        def ramps(sg, mem, call):
            res, _ = rhdspemu.run(0, call=call, mem=mem + [("x", 0x1B32, [0x111111 * (i % 7) for i in range(48)])], segs=sg,
                                  dumps=[("y", OUT, NOUT), ("x", 0x1B32, 48)])
            return res[("y", OUT)], res[("x", 0x1B32)]
        src = [rnd.randrange(0x7FFFFF) if i % 4 < 2 else 0 for i in range(32)]
        sends = [(rnd.randrange(128), rnd.randrange(128)) for _ in range(8)]
        full = [(src[4 * t], src[4 * t + 1], sends[t][0] << 14, sends[t][1] << 14) for t in range(8)]
        zero = [0] * 8
        bad0, badm = [], []
        mv = [rnd.randrange(1 << 24) for _ in range(8)]
        pd, rd, dd = [rnd.randrange(0x800000) for _ in range(8)], [rnd.randrange(1 << 24) for _ in range(8)], [rnd.randrange(1 << 24) for _ in range(8)]
        q = model([w for t in full for w in t], mv, pd, rd, dd)
        qq = list(q)
        for call in (0x11E3, 0x1202, 0x1231):
            st = ramps(ssegs, mem_for(src, mv, zero, zero, zero, sends), call)
            pre0 = [] if call == 0x11E3 else [("x", M.Q, src)]        # L / R in Q from this block's first hook (depth 0: the stock's)
            ours = ramps(segs, mem_for(src, mv, zero, zero, zero, sends) + pre0, call)
            if ours != st:
                bad0.append(hex(call))
            pre = [] if call == 0x11E3 else [("x", M.Q, qq)]          # L / R in Q from this block's first hook
            ours = ramps(segs, mem_for(src, mv, pd, rd, dd, sends) + pre, call)
            if call == 0x11E3:
                want = ramps(ssegs, [("x", M.SRC, qq), ("x", 0x39, [5]), ("x", 0x3A, [32])], call)
                if ours != want:
                    badm.append(hex(call))
            elif not send_ok(ours, qq, 3 if call == 0x1202 else 2):
                badm.append(hex(call))
        check(f"{b}: the depths at 0: the stock's three ramps and their states unchanged", not bad0, bad0)
        check(f"{b}: with depths: the ramps from the model's gains (L / R pan, the sends moved)", not badm, badm)
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED")
    if FAILS:
        raise SystemExit(1)


def send_ok(ours, qq, o):
    """the send loop's final ramp state words (X:$1B32 + 6 t + 2 / 5 for o = 3; + 1 / 4 for o = 2) = L x s << 2, R x s << 2"""
    _, st = ours
    for t in range(8):
        L, R, s = qq[4 * t], qq[4 * t + 1], qq[4 * t + o]
        a = sat((s24(s) * s24(L) * 8) >> 24)
        b = sat((s24(s) * s24(R) * 8) >> 24)
        i, j = (6 * t + 2, 6 * t + 5) if o == 3 else (6 * t + 1, 6 * t + 4)
        if (st[i], st[j]) != (a, b):
            return False
    return True


if __name__ == "__main__":
    main()
