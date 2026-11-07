"""fshape's filter envelope and LFO on core 1 in dsptool (MIT; Circuit Rhythm 5706): a build's own core 1 program, RR's filter half for a
voice with the shape tables in Y, and voicefilt's LPIDX with FM added; P:$1C3 replaced by a stub that returns.

    python tests/emu_fshape.py BUILD [BUILD ...]      (BUILD: firmware/<build>)

Checks: the filter's timeline (T += S, at most 1), FM = (A x ENV[shape](T) + L x LFO[shape](phase / 2)) >> 16 for every shape, the
pitch's words untouched by it, LPIDX = the stock's index + FM clamped to 0..128 (the comb: 128; without it, the index as any type).
(vol) The voice loop's jsr to LVL; LVL with depth 0 = the stock's level ramp; phase += R, VX = D x (1 - shape(phase / 2)) / 2 for the
16 volume shapes; the samples and the level = the stock's ramp toward the target x (1 - VX); r0 kept.  (c0fx) no LVL: the stock's call
and ramp (the LFOs: tests/emu_c0fx.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rpasm  # noqa: E402
rpasm.use()
import fshape as F  # noqa: E402
import pitchmod as PM  # noqa: E402
import pshape as S  # noqa: E402
import rhdsp1  # noqa: E402
import rhdsppatch as DP  # noqa: E402
import rhdspemu  # noqa: E402
import voicefilt as VF  # noqa: E402

KEEP, PARS, STUB = 0x1F80, 0x1F90, 0xFC0                 # Y: the stub's words, a voice's parameters; P: LPIDX's caller
LSTUB, R0KEEP, BUF, LEVEL = 0xFD0, 0x16EA, 0x2A02, 0x37301  # (vol) P: LVL's caller; Y: its r0 after; X: the voice's samples; Y: the levels
FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def s24(w):
    return w - (1 << 24) if w & 0x800000 else w


def mpy(a, b):
    return (s24(a) * b) >> 23


def vol_checks(build, img, rep, segs):
    if rep.get("c0fx"):
        st = (HERE / "remix" / "stock" / "circuitrhythm-firmware-5706-STOCK.bin").read_bytes()
        word = lambda im, a: int.from_bytes(im[rhdsp1.where(im, a):rhdsp1.where(im, a) + 3], "big")   # noqa: E731
        check(f"{build}: (c0fx) P:$241 = the stock's jsr $244, its level ramp P:$244..$25B the stock's words",
              word(img, F.LVL_CALL) == word(st, F.LVL_CALL) == 0x0D0000 | F.STOCK_LVL
              and all(word(img, a) == word(st, a) for a in range(F.LOW_AT, F.LOW_END)))
        return
    lvl = int(rep["fshape"]["lvl"], 16)
    o = rhdsp1.where(img, F.LVL_CALL)
    check(f"{build}: the voice loop's P:$241 = jsr LVL (${lvl:x})", int.from_bytes(img[o:o + 3], "big") == 0x0D0000 | lvl)
    segs = segs + [("p", LSTUB, DP.jsr(lvl) + DP.asm([f"move r0,y:>${R0KEEP:x}"]) + [0x00000C])]
    tw = S.table_words(rep["pshape"].get("v2", False), vol=True)
    tabs = [("y", S.ENV_Y + i, [w]) for i, w in enumerate(tw) if w is not None]
    vb = F.VB
    samples = [(0x123456 * (i + 1) * (1 if i % 2 else -1)) & 0xFFFFFF for i in range(32)]

    stock_segs = rhdspemu.segments(1, 0)

    def run(call, v, tgt, cur, words, stock=False):
        mem = tabs + [("x", 1, [32]), ("x", BUF, samples), ("y", 0x1405, [v]), ("y", LEVEL + 2 * v, [tgt, cur])]
        mem += [("y", a, [w]) for a, w in words.items()]
        res, _ = rhdspemu.run(1, call=call, mem=mem, segs=stock_segs if stock else segs, regs_code=DP.asm(["move #>$54,r0"]),
                              dumps=[("x", BUF, 32), ("x", LEVEL + 2 * v + 1, 1), ("y", vb + F.O_VX + v, 1), ("y", vb + F.O_VP + v, 1),
                                     ("y", R0KEEP, 1)])
        return (res[("x", BUF)], res[("x", LEVEL + 2 * v + 1)][0], res[("y", vb + F.O_VX + v)][0], res[("y", vb + F.O_VP + v)][0],
                res[("y", R0KEEP)][0])

    v = 3
    bad = []
    for tgt, cur in ((0x7FFFFF, 0x7FFFFF), (0x7FFFFF, 0), (0, 0x7FFFFF), (0x400000, 0x123456)):
        st = run(0x244, v, tgt, cur, {}, stock=True)
        lv = run(LSTUB, v, tgt, cur, {vb + F.O_VR + v: 0x1000, vb + F.O_VQ + v: S.LFO_Y})
        if lv[:2] != st[:2] or lv[2] != 0 or lv[4] != 0x54:
            bad.append((hex(tgt), hex(cur), lv[1:], st[1:2]))
    check(f"{build}: LVL with depth 0 = the stock's ramp (VX 0, r0 kept)", not bad, bad[:2])

    def att(d, tab, pos):
        x0 = min((0x7FFFFF - S.value(tab, pos)) >> 1, 0x7FFFFF)
        return (d * x0) >> 23
    bad = []
    for sh in range(F.NVS):
        q = S.LFO_Y + S.STRIDE * sh if sh < S.NL else S.VOL_Y + S.STRIDE * (sh - S.NL)
        tab = [tw[q - S.ENV_Y + j] for j in range(S.NPT + 1)]
        for ph0, d in ((0, 0x7FFE00), (0x300000, 0x400000), (0x900000, 0x7FFE00), (0xF00000, 0x200000)):
            r = 0x800
            lv = run(LSTUB, v, 0x7FFFFF, 0x600000, {vb + F.O_VP + v: ph0 - r, vb + F.O_VR + v: r, vb + F.O_VD + v: d, vb + F.O_VQ + v: q})
            a = att(d, tab, (ph0 & 0xFFFFFF) >> 1)
            eff = ((0x7FFFFF << 24) - 2 * a * 0x7FFFFF) >> 24
            st = run(0x244, v, eff, 0x600000, {}, stock=True)
            if lv[2] != a or lv[3] != ph0 & 0xFFFFFF or lv[:2] != st[:2] or lv[4] != 0x54:
                bad.append((sh, hex(ph0), hex(lv[2]), hex(a), hex(lv[3])))
    check(f"{build}: LVL: phase += R, VX = D x (1 - shape) / 2, the stock's ramp toward target x (1 - VX): 16 shapes at 4 points", not bad, bad[:3])
    lv = run(LSTUB, v, 0x7FFFFF, 0x7FFFFF, {vb + F.O_VP + v: 0, vb + F.O_VR + v: 0, vb + F.O_VD + v: 0x7FFE00,
                                              vb + F.O_VQ + v: S.VOL_Y + S.STRIDE * 1})
    check(f"{build}: short gate shut (a quarter before the beat) at full depth: the level falls to near 0", lv[2] >= 0x7FFC00 and lv[1] < 0x7FFFFF * 0.62,
          (hex(lv[2]), hex(lv[1])))
    if rep["fshape"].get("move"):
        import mixmove as MM
        sh_m, sh_p = MM.SH + v, MM.SH + 8 + v

        def runm(words):
            mem = tabs + [("x", 1, [32]), ("x", BUF, samples), ("y", 0x1405, [v]), ("y", LEVEL + 2 * v, [0x7FFFFF, 0x600000])]
            mem += [("y", a, [w]) for a, w in words.items()]
            res, _ = rhdspemu.run(1, call=LSTUB, mem=mem, segs=segs, regs_code=DP.asm(["move #>$54,r0"]),
                                  dumps=[("x", BUF, 32), ("y", sh_m, 1), ("y", sh_p, 1), ("y", R0KEEP, 1)])
            return res[("x", BUF)], res[("y", sh_m)][0], res[("y", sh_p)][0], res[("y", R0KEEP)][0]
        base = run(LSTUB, v, 0x7FFFFF, 0x600000, {})
        bad = []
        for sh in range(F.NVS):
            q = S.LFO_Y + S.STRIDE * sh if sh < S.NL else S.VOL_Y + S.STRIDE * (sh - S.NL)
            tab = [tw[q - S.ENV_Y + j] for j in range(S.NPT + 1)]
            for ph0 in (0, 0x300000, 0x900000, 0xF00000):
                r = 0x800
                got = runm({F.MB + v: r, F.MB + 8 + v: q, sh_p: (ph0 - r) & 0xFFFFFF, sh_m: 0x123456})
                want = S.value(tab, (ph0 & 0xFFFFFF) >> 1) & 0xFFFFFF
                if got[1] != want or got[2] != ph0 & 0xFFFFFF or got[0] != base[0] or got[3] != 0x54:
                    bad.append((sh, hex(ph0), hex(got[1]), hex(want), hex(got[2])))
        check(f"{build}: (move) LVL: the move phase += MR at shared Y, M = shape(phase / 2): 16 shapes at 4 points; the volume as without it",
              not bad, bad[:3])
        got = runm({F.MB + v: 0, F.MB + 8 + v: S.LFO_Y, sh_p: 0x345678, sh_m: 0x123456})
        check(f"{build}: (move) the move rate 0: M = 0, the phase kept", got[1] == 0 and got[2] == 0x345678, (hex(got[1]), hex(got[2])))


def main():
    for build in sys.argv[1:]:
        d = HERE / "firmware" / build
        rep = json.loads((d / "manifest.json").read_text())["report"]
        img = bytearray((d / f"rhythmplus-{build.upper()}.bin").read_bytes())
        segs, _ = rhdsp1.parse(rhdsp1.sent(img, rep, "pitchmod"))
        lpidx = int(rep["fshape"]["lpidx"], 16)
        caller = DP.jsr(lpidx) + DP.asm([f"move n5,y:>${KEEP:x}", f"move b1,y:>${KEEP + 1:x}"]) + [0x00000C]
        segs = segs + [("p", PM.P_EXP, [0x00000C]), ("p", STUB, caller)]
        rr = int(rep["pitchmod"]["rr"], 16)
        tw = S.table_words(rep["pshape"].get("v2", False))
        tabs = [("y", S.ENV_Y + i, [w]) for i, w in enumerate(tw) if w is not None]
        tab = lambda base, s: [tw[base - S.ENV_Y + S.STRIDE * s + j] for j in range(S.NPT + 1)]   # noqa: E731
        fb = F.FB

        def rr_run(t, words):
            mem = tabs + [("y", a, [v]) for a, v in words.items()]
            regs = DP.asm([f"move #>${0x40 + 0x10 * t:x},r4", "move #>$100000,y0"])
            res, _ = rhdspemu.run(1, call=rr, mem=mem, segs=segs, regs_code=regs,
                                  dumps=[("y", fb + F.O_M + t, 1), ("y", fb + F.O_T + t, 1), ("y", fb + F.O_P + t, 1), ("y", S.YB + t, 1)])
            return (s24(res[("y", fb + F.O_M + t)][0]), res[("y", fb + F.O_T + t)][0], res[("y", fb + F.O_P + t)][0],
                    res[("y", S.YB + t)][0])

        t = 2
        fm, T, ph, pt = rr_run(t, {})
        check(f"{build}: all zero: FM 0, the filter's T and phase 0", fm == 0 and T == 0 and ph == 0, (fm, T, ph))
        fm, T, _, pt = rr_run(t, {fb + F.O_T + t: 0x100000, fb + F.O_S + t: 0x123456})
        check(f"{build}: the filter's T += S, the pitch's T untouched", T == 0x223456 and pt == 0, (hex(T), hex(pt)))
        _, T, _, _ = rr_run(t, {fb + F.O_T + t: 0x7F0000, fb + F.O_S + t: 0x123456})
        check(f"{build}: the filter's T at most 1", T == 0x7FFFFF, hex(T))
        A = 0x400000                                            # +64 semitones at the shape's top
        bad = []
        for sh in range(S.NE):
            for T0 in (0, 0x200000, 0x400000, 0x7FFFFF):
                fm, _, _, _ = rr_run(t, {fb + F.O_T + t: T0, fb + F.O_A + t: A, fb + F.O_E + t: sh})
                want = mpy(A, S.value(tab(S.ENV_Y, sh), T0)) >> 16
                if abs(fm - want) > 1:
                    bad.append((S.ENV_NAMES[sh], hex(T0), fm, want))
        check(f"{build}: FM = A x ENV[shape](T) >> 16: the 16 envelopes at 4 points each", not bad, bad[:4])
        fm, _, _, _ = rr_run(t, {fb + F.O_T + t: 0, fb + F.O_A + t: (-A) & 0xFFFFFF, fb + F.O_E + t: 0})
        check(f"{build}: a negative amount closes: drop at T 0 = -64", abs(fm + 64) <= 1, fm)
        L = 0x200000
        bad = []
        for sh in range(S.NL):
            for ph0 in (0, 0x300000, 0x900000, 0xF00000):
                fm, _, ph, _ = rr_run(t, {fb + F.O_P + t: ph0 - 0x1000, fb + F.O_R + t: 0x1000, fb + F.O_L + t: L, fb + F.O_Q + t: sh})
                want = mpy(L, S.value(tab(S.LFO_Y, sh), (ph0 & 0xFFFFFF) >> 1)) >> 16
                if abs(fm - want) > 1 or ph != ph0 & 0xFFFFFF:
                    bad.append((S.LFO_NAMES[sh], hex(ph0), fm, want, hex(ph)))
        check(f"{build}: phase += R, FM = L x LFO[shape](phase / 2) >> 16: the 10 LFOs at 4 points each", not bad, bad[:4])

        def lp_run(v, idx, res, fm, kt=0):
            mem = [("y", 0x1405, [v]), ("y", PARS + 0xC, [idx]), ("y", PARS + 0xD, [res]), ("y", VF.KTYPE + v, [kt]),
                   ("y", VF.FOLLOW + v, [0]), ("y", VF.PITCH + v, [0]), ("y", fb + F.O_M + v, [fm & 0xFFFFFF])]
            out, _ = rhdspemu.run(1, call=STUB, mem=mem, segs=segs, regs_code=DP.asm([f"move #>${PARS:x},r7"]), dumps=[("y", KEEP, 2)])
            return s24(out[("y", KEEP)][0]), out[("y", KEEP)][1]
        bad = []
        for idx, fm, want in ((100, 0, 100), (100, -30, 70), (60, 40, 100), (100, 50, 128), (20, -64, 0), (127, 0, 127)):
            n5, b = lp_run(5, idx, 33, fm)
            if (n5, b) != (want, 33):
                bad.append((idx, fm, n5, b, want))
        check(f"{build}: LPIDX: the stock's index + FM, clamped 0..128, the resonance kept", not bad, bad)
        n5, b = lp_run(5, 60, 33, -40, kt=2)
        if rep.get("nocomb"):
            check(f"{build}: LPIDX, no comb: a type word of 2 is the stock's index + FM", (n5, b) == (20, 33), (n5, b))
        else:
            check(f"{build}: LPIDX with the comb: 128, no resonance (FM not on it)", (n5, b) == (128, 0), (n5, b))
        if rep["fshape"].get("vol"):
            vol_checks(build, img, rep, segs)
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAIL")
    raise SystemExit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
