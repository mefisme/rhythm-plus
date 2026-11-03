"""pshape's pitch envelope and LFO on core 1 in dsptool (MIT; Circuit Rhythm 5706): a build's own core 1 program, RR called for a voice
with the shape tables in Y as the ARM writes them; P:$1C3 replaced by a stub that keeps the pitch it gets.

    python tests/emu_pshape.py BUILD [BUILD ...]      (BUILD: firmware/<build>)

Checks: the timeline (T += S, at most 1), A x ENV[shape](T) for every envelope at several points, L x LFO[shape](phase / 2) for every
LFO, the phase step, the clamp at the stock's top, all zero = the stock's pitch; (fshape px) RR adds the note's random offset before the
clamp, TRIG takes the LCG's next seed and keeps r x depth for its track (the pitch it gives moved by that much); (fshape glide) RR's
G = y0 + K x (G - y0) kept for the track, the envelope, the LFO and the offset on top, K = 0 = the pitch as it is; (fshape fade) RR's
mute W -= FR (at least 0) and the LFO x (1 - W), TRIG's W = 1 for its track, a fade's length from the table.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rpasm  # noqa: E402
rpasm.use()
import pitchmod as PM  # noqa: E402
import pshape as S  # noqa: E402
import rhdsp1  # noqa: E402
import rhdsppatch as DP  # noqa: E402
import rhdspemu  # noqa: E402

KEEP = 0x1F80                                              # the stub's pitch word (Y, free)
FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def s24(w):
    return w - (1 << 24) if w & 0x800000 else w


def mpy(a, b):
    return (a * b) >> 23                                   # the DSP's fractional product, truncated (mpy, then a's high word)


def main():
    for build in sys.argv[1:]:
        d = HERE / "firmware" / build
        rep = json.loads((d / "manifest.json").read_text())["report"]
        img = bytearray((d / f"rhythmplus-{build.upper()}.bin").read_bytes())
        segs, _ = rhdsp1.parse(rhdsp1.sent(img, rep, "pitchmod"))
        stub = DP.asm([f"move y0,y:>${KEEP:x}"]) + [0x00000C]                       # P:$1C3: keep the pitch, rts
        segs = segs + [("p", PM.P_EXP, stub)]
        rr = int(rep["pitchmod"]["rr"], 16)
        tw = S.table_words(rep["pshape"].get("v2", False))
        tabs = [("y", S.ENV_Y + i, [w]) for i, w in enumerate(tw) if w is not None]
        tab = lambda base, s: [tw[base - S.ENV_Y + S.STRIDE * s + j] for j in range(S.NPT + 1)]   # noqa: E731
        tab_e = lambda s: tab(S.ENV_Y, s)                                                         # noqa: E731
        yb = S.YB

        def rr_run(t, pitch, words):
            mem = [m for m in tabs] + [("y", a, [v]) for a, v in words.items()]
            regs = DP.asm([f"move #>${0x40 + 0x10 * t:x},r4", f"move #>${pitch & 0xFFFFFF:x},y0"])
            res, ran = rhdspemu.run(1, call=rr, mem=mem, segs=segs, regs_code=regs,
                                    dumps=[("y", KEEP, 1), ("y", yb + t, 1), ("y", yb + PM.OFF_PH + t, 1)])
            return s24(res[("y", KEEP)][0]), res[("y", yb + t)][0], res[("y", yb + PM.OFF_PH + t)][0], ran

        t, p0 = 3, 0x100000
        got, T, ph, ran = rr_run(t, p0, {})
        check(f"{build}: all zero: the stock's pitch, T and the phase stay 0", got == p0 and T == 0 and ph == 0, (hex(got), T, ph, ran))
        got, T, _, _ = rr_run(t, p0, {yb + t: 0x100000, yb + PM.OFF_D + t: 0x123456})
        check(f"{build}: T += S", T == 0x223456, hex(T))
        got, T, _, _ = rr_run(t, p0, {yb + t: 0x7F0000, yb + PM.OFF_D + t: 0x123456})
        check(f"{build}: T at most 1 ($7FFFFF)", T == 0x7FFFFF, hex(T))
        A = 0xC0000                                             # 12 semitones
        bad = []
        for s in range(S.NE):
            for T0 in (0, 0x123456, 0x400000, 0x5A5A5A, 0x7FFFFF):
                got, T, _, _ = rr_run(t, p0, {yb + t: T0, yb + PM.OFF_A + t: A, S.SHP_E + t: s})
                want = p0 + mpy(A, S.value(tab(S.ENV_Y, s), T0))
                if abs(got - want) > 2:
                    bad.append((S.ENV_NAMES[s], hex(T0), hex(got), hex(want)))
        check(f"{build}: A x ENV[shape](T): the 16 envelopes at 5 points each", not bad, bad[:4])
        L = 0x60000                                             # 6 semitones
        bad = []
        for s in range(S.NL):
            for ph0 in (0, 0x200000, 0x6789AB, 0xA00000, 0xFFFFF0):
                got, _, ph, _ = rr_run(t, p0, {yb + PM.OFF_PH + t: ph0 - 0x1000, yb + PM.OFF_R + t: 0x1000, yb + PM.OFF_L + t: L, S.SHP_L + t: s})
                want = p0 + mpy(L, S.value(tab(S.LFO_Y, s), (ph0 & 0xFFFFFF) >> 1))
                if abs(got - want) > 2 or ph != ph0 & 0xFFFFFF:
                    bad.append((S.LFO_NAMES[s], hex(ph0), hex(got), hex(want), hex(ph)))
        check(f"{build}: phase += R, L x LFO[shape](phase / 2): the 10 LFOs at 5 points each", not bad, bad[:4])
        got, _, _, _ = rr_run(t, p0, {yb + t: 0x200000, yb + PM.OFF_A + t: A, S.SHP_E + t: 5, yb + PM.OFF_PH + t: 0x3FF000,
                                      yb + PM.OFF_R + t: 0x1000, yb + PM.OFF_L + t: L, S.SHP_L + t: 1})
        want = p0 + mpy(A, S.value(tab(S.ENV_Y, 5), 0x200000)) + mpy(L, S.value(tab(S.LFO_Y, 1), 0x200000))
        check(f"{build}: the envelope and the LFO together", abs(got - want) <= 3, (hex(got), hex(want)))
        got, _, _, _ = rr_run(t, PM.PITCH_MAX - 0x1000, {yb + t: 0, yb + PM.OFF_A + t: 0x180000, S.SHP_E + t: 0})
        check(f"{build}: clamped at the stock's top", got == PM.PITCH_MAX, hex(got))
        got, _, _, _ = rr_run(5, p0, {yb + 5: 0x7FFFFF, yb + PM.OFF_A + 5: A, S.SHP_E + 5: 3})
        check(f"{build}: track 6, rise at its end: +12 semitones held", abs(got - (p0 + mpy(A, S.value(tab(S.ENV_Y, 3), 0x7FFFFF)))) <= 2
              and abs(got - (p0 + A)) <= 0x200, hex(got))
        fs = rep.get("fshape", {})
        if fs.get("px"):
            import fshape as FS
            RD, RO, SEED = (int(fs[k], 16) for k in ("rd", "ro", "seed"))
            ok = [rr_run(t, p0, {RO + t: 0x50000})[0] == p0 + 0x50000, rr_run(t, p0, {RO + t: -0x30000 & 0xFFFFFF})[0] == p0 - 0x30000,
                  rr_run(t, PM.PITCH_MAX - 0x1000, {RO + t: 0xC0000})[0] == PM.PITCH_MAX, rr_run(t, p0, {RO + 2: 0x50000})[0] == p0]
            check(f"{build}: (px) RR: the pitch + the track's offset at Y:${RO:X} + t (up, down, clamped at the top; another track's not added)", all(ok), ok)
            trig = int(rep["pitchmod"]["trig"], 16)

            def trig_run(tr, seed, d):
                mem = tabs + [("y", SEED, [seed]), ("y", RD + tr, [d])]
                res, ran = rhdspemu.run(1, call=trig, mem=mem, segs=segs, regs_code=DP.asm([f"move #>${tr:x},y1"]),
                                        dumps=[("y", SEED, 1), ("y", RO, 8), ("y", KEEP, 1), ("y", 0x121, 1)])
                return res[("y", SEED)][0], res[("y", RO)], s24(res[("y", KEEP)][0]), res[("y", 0x121)][0]
            bad, seed, seen = [], 0, set()
            for n, (tr, d) in enumerate([(3, 0xBFFA0), (0, 0x12C00), (7, 0xBFFA0), (5, 0x40000)] * 3):
                s1, ro, pitch, v121 = trig_run(tr, seed, d)
                want_s = (seed * FS.LCG_A + FS.LCG_C) & 0xFFFFFF
                want_ro = mpy(s24(want_s), d) & 0xFFFFFF
                _, ro0, pitch0, _ = trig_run(tr, seed, 0)
                if s1 != want_s or ro != [want_ro if k == tr else 0 for k in range(8)] or ro0 != [0] * 8 or v121 != 0                         or pitch - pitch0 != s24(want_ro) or abs(s24(want_ro)) > d:
                    bad.append((n, tr, hex(s1), hex(want_s), [hex(x) for x in ro], hex(want_ro), hex(pitch - pitch0)))
                seen.add(s24(want_ro) > 0)
                seed = s1
            check(f"{build}: (px) TRIG: seed x ${FS.LCG_A:X} + ${FS.LCG_C:X}, the track's offset r x depth (12 notes, 4 tracks), the note's pitch moved by "
                  f"it, $121 restored, both signs seen", not bad and seen == {True, False}, bad[:3])
        if fs.get("glide"):
            import fshape as FS
            GK, GP, RO = (int(fs[k], 16) for k in ("gk", "gp", "ro"))

            def gl_run(tr, pitch, words):
                mem = tabs + [("y", a, [v & 0xFFFFFF]) for a, v in words.items()]
                regs = DP.asm([f"move #>${0x40 + 0x10 * tr:x},r4", f"move #>${pitch & 0xFFFFFF:x},y0"])
                res, _ = rhdspemu.run(1, call=rr, mem=mem, segs=segs, regs_code=regs, dumps=[("y", KEEP, 1), ("y", GP, 8)])
                return s24(res[("y", KEEP)][0]), [s24(w) for w in res[("y", GP)]]
            gtab = FS.glide_table()
            bad = []
            for tr, p, g, k in ((3, 0x100000, -0x50000, gtab[64]), (0, -0x80000, 0x180000, gtab[128]), (7, 0x20000, 0x20000, gtab[1]),
                                (5, 0x1C0000, -0x300000, gtab[100]), (2, -0x200000, 0x210000, 0x7FFFFF)):
                got, gp = gl_run(tr, p, {GK + tr: k, GP + tr: g})
                want = p + mpy(g - p, k)
                if got != max(PM.PITCH_MIN - (1 << 24), min(PM.PITCH_MAX, want)) or gp != [want if i == tr else 0 for i in range(8)]:
                    bad.append((tr, hex(got), hex(want), [hex(x) for x in gp]))
            check(f"{build}: (glide) RR: G = y0 + K x (G - y0), kept at Y:${GP:X} + t, the pitch G in the clamp (5 tracks, up and down)", not bad, bad[:3])
            got, gp = gl_run(4, 0x90000, {GP + 4: -0x123456})
            check(f"{build}: (glide) K = 0: the pitch as it is, G = the pitch", got == 0x90000 and gp[4] == 0x90000, (hex(got), hex(gp[4])))
            A = 0xC0000
            got, gp = gl_run(3, 0x100000, {GK + 3: gtab[80], GP + 3: 0, yb + 3: 0x400000, yb + PM.OFF_A + 3: A, S.SHP_E + 3: 2, RO + 3: 0x30000})
            g1 = 0x100000 + mpy(-0x100000, gtab[80])
            want = g1 + mpy(A, S.value(tab_e(2), 0x400000)) + 0x30000
            check(f"{build}: (glide) the envelope and the random offset on top of G, G kept without them", abs(got - want) <= 2 and gp[3] == g1,
                  (hex(got), hex(want), hex(gp[3]), hex(g1)))
            p, g, n, k = 0x180000, 0, 0, gtab[96]
            while abs(p - g) > (p * 5) // 100 and n < 2000:
                g, _ = gl_run(1, p, {GK + 1: k, GP + 1: g})
                n += 1
            t95 = FS.GL_MIN * (FS.GL_MAX / FS.GL_MIN) ** (95 / 127)
            check(f"{build}: (glide) knob 96 / 128: 95 % of a jump in {n} updates ({n / FS.UPD:.3f} s, the table says {t95:.3f} s)",
                  abs(n / FS.UPD - t95) <= 2 / FS.UPD, n)
            check(f"{build}: (glide) the table: 0 at the knob's left, rising, below 1", gtab[0] == 0 and all(a < b for a, b in zip(gtab, gtab[1:])) and gtab[-1] < 0x7FFFFF,
                  [hex(x) for x in gtab[:3] + gtab[-2:]])
        if fs.get("fade"):
            import fshape as FS
            FR, FW = (int(fs[k], 16) for k in ("fr", "fw"))
            ftab = FS.fade_table()
            L, ph0 = 0x60000, 0x200000

            def fd_run(tr, w, r):
                mem = tabs + [("y", a, [v & 0xFFFFFF]) for a, v in {FW + tr: w, FR + tr: r, yb + PM.OFF_PH + tr: ph0 - 0x1000, yb + PM.OFF_R + tr: 0x1000,
                                                                     yb + PM.OFF_L + tr: L, S.SHP_L + tr: 1}.items()]
                regs = DP.asm([f"move #>${0x40 + 0x10 * tr:x},r4", f"move #>${p0:x},y0"])
                res, _ = rhdspemu.run(1, call=rr, mem=mem, segs=segs, regs_code=regs, dumps=[("y", KEEP, 1), ("y", FW, 8)])
                return s24(res[("y", KEEP)][0]), res[("y", FW)]
            lfo = mpy(L, S.value(tab(S.LFO_Y, 1), ph0 >> 1))
            bad = []
            for tr, w, r in ((3, 0x7FFFFF, ftab[40]), (0, 0x400000, ftab[100]), (6, 0x100, ftab[1]), (2, 0x7FFFFF, 0x7FFFFF), (5, 0, ftab[128])):
                got, fw = fd_run(tr, w, r)
                w1 = max(0, w - r)
                want = p0 + mpy(lfo, 0x7FFFFF - w1)
                if abs(got - want) > 3 or fw != [w1 if i == tr else 0 for i in range(8)]:
                    bad.append((tr, hex(got), hex(want), [hex(x) for x in fw]))
            check(f"{build}: (fade) RR: W -= FR (at least 0) at Y:${FW:X} + t, the LFO x (1 - W) (5 tracks; none: the full LFO at once)", not bad, bad[:3])
            got, _ = fd_run(4, 0, 0)
            check(f"{build}: (fade) W = 0: the LFO as without the fade", abs(got - (p0 + lfo)) <= 3, (hex(got), hex(p0 + lfo)))
            w, n = 0x7FFFFF, 0
            while w and n < 2000:
                _, fw = fd_run(1, w, ftab[96])
                w, n = fw[1], n + 1
            t = FS.FD_MIN * (FS.FD_MAX / FS.FD_MIN) ** (95 / 127)
            check(f"{build}: (fade) knob 96 / 128: the full fade in {n} updates ({n / FS.UPD:.3f} s, the table says {t:.3f} s)", abs(n / FS.UPD - t) <= 2 / FS.UPD, n)
            check(f"{build}: (fade) the table: none (1) at the knob's left, then falling (longer)", ftab[0] == 0x7FFFFF and all(a > b for a, b in zip(ftab, ftab[1:])),
                  [hex(x) for x in ftab[:3] + ftab[-2:]])
            trig = int(rep["pitchmod"]["trig"], 16)
            bad = []
            for tr, r in ((3, ftab[50]), (0, 0x7FFFFF), (7, ftab[128])):
                mem = tabs + [("y", FR + tr, [r])]
                res, _ = rhdspemu.run(1, call=trig, mem=mem, segs=segs, regs_code=DP.asm([f"move #>${tr:x},y1"]), dumps=[("y", FW, 8)])
                if res[("y", FW)] != [max(0, 0x7FFFFF - r) if i == tr else 0 for i in range(8)]:
                    bad.append((tr, [hex(x) for x in res[("y", FW)]]))
            check(f"{build}: (fade) TRIG: W = 1 for its track, then the note's first update (none: W = 0 at once)", not bad, bad)
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAIL")
    raise SystemExit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
