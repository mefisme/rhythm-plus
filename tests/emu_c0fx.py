"""c0fx's core 0 code in dsptool (MIT; Circuit Rhythm 5706): a build's own core 0 program with its loader's segments.

    python tests/emu_c0fx.py BUILD [BUILD ...]      (BUILD: firmware/<build>)

Checks: the segments (C0 at P:$2000, P:$224 = jsr C0); the ring mod on each track's block of the bank y:$FFFFD0 selects = voicefx's ring
stage word for word (the samples, the phase), nothing on a track with amount 0 or on the other bank; the move LFO (phase += MR, M =
shape(phase / 2), 0 and the phase kept while MR = 0) and the volume LFO (phase += R, VX = D x (1 - shape) / 2, 0 while D = 0, the cut +=
(VX - cut) x VK) against the model for random tracks and all 16 shapes; the stock's r / n / m kept; the end at the stock's mix (P:$367).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / d) for d in ("modules", "builds", "tests", "remix/tools")]
import c0fx as C  # noqa: E402
import core0  # noqa: E402
import fshape as FS  # noqa: E402
import mixmove as MM  # noqa: E402
import pshape as S  # noqa: E402
import rhdsppatch as DP  # noqa: E402
import rhdspemu  # noqa: E402
import voicefx as VX  # noqa: E402

FAILS = []
WRAP, REF, KEEP, RW = 0x3100, 0x3000, 0x3200, 0x3400       # P: the caller, voicefx's ring stage; Y: the registers after, its words
BUF = 0x2A02


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def s24(w):
    w &= 0xFFFFFF
    return w - (1 << 24) if w & 0x800000 else w


def mpy(a, b):
    return (s24(a) * s24(b) * 2) >> 24


def lk(tab, pos):
    """pshape's lk as the DSP computes it (asl keeps the product's next bit): the shape at pos 0 .. $7FFFFF, 24-bit"""
    i, frac = pos >> 18, (pos & 0x3FFFF) << 5
    if tab[0]:
        frac = 0
    v0, v1 = s24(tab[1 + i]), s24(tab[2 + i])
    d = max(-0x800000, min(0x7FFFFF, v1 - v0))
    return max(-0x800000, min(0x7FFFFF, 2 * v0 + ((frac * d) >> 22))) & 0xFFFFFF


def program(img, rep):
    """-> core 0's segments after the upload: the stock block as patched, then the loader's segments"""
    _, stream = core0.sent(bytes(img), rep)
    out, i = [], 0
    while i < len(stream):
        n, at = stream[i] & 0xFFFF, stream[i + 1]
        if n == 0:
            break
        out.append(("p", at, stream[i + 2:i + 2 + n]))
        i += 2 + n
    return out


def ring_ref():
    """voicefx's ring stage (its own items, r1 = the track's ring words, X:BUF the samples) at P:REF, then rts"""
    L = VX.items(S.SHIFT, None, True)
    a = L.index(f"move y:(r1+${VX.RAM:x}),a")
    b = L.index(("label", "filt"))
    w, _ = VX.assemble(L[a:b] + [("label", "filt"), "rts"], REF)
    return w


def main():
    tw = S.table_words(False, vol=True)
    tabs = [("y", S.ENV_Y + i, [w]) for i, w in enumerate(tw) if w is not None]
    regs = [0x100 + k for k in range(8)] + [0x200 + k for k in range(8)]
    wrap = DP.asm([f"move #>${regs[k]:x},r{k}" for k in range(8)] + [f"move #>${regs[8 + k]:x},n{k}" for k in range(8)] + ["move #$3f,m1"])
    for build in sys.argv[1:]:
        d = HERE / "firmware" / build
        rep = json.loads((d / "manifest.json").read_text())["report"]
        img = bytearray((d / f"rhythmplus-{build.upper()}.bin").read_bytes())
        c0 = int(rep["c0fx"]["c0"], 16)
        segs = program(img, rep)
        got = {at: ws for _, at, ws in segs}
        check(f"{build}: the loader's segments: C0 at P:${C.AT:X}, P:$224 = jsr C0", C.AT in got and got.get(C.HOOK) == [0x0BF080, c0])
        st = got[0]
        bk = DP.asm(["movep y:<<$ffffd0,b", "asl #5,b,b", "move b,n3"])
        c0w = got[C.AT]
        at = next((i for i in range(len(c0w) - 2) if c0w[i:i + 3] == bk), None)
        check(f"{build}: the bank as the stock's mix takes it (P:$367: movep y:$FFFFD0, asl #5, into n1; ours n3)",
              at is not None and st[0x367:0x36A] == DP.asm(["movep y:<<$ffffd0,b", "asl #5,b,b", "move b,n1"]))
        tail = wrap + DP.jsr(c0) + DP.asm([f"move r{k},y:>${KEEP + k:x}" for k in range(8)] + [f"move n{k},y:>${KEEP + 8 + k:x}" for k in range(8)]
                                          + [f"move m1,y:>${KEEP + 16:x}"]) + [0x00000C]
        segs = segs + [("p", C.MIX, [0x00000C]), ("p", WRAP, tail), ("p", REF, ring_ref())]
        rnd = random.Random(7)
        rg = C.ring_y()

        def run(bank, words, samples):
            mem = tabs + [("x", 0x3A, [32]), ("y", 0xFFFFD0, [bank])] + [("y", a, ws) for a, ws in words.items()]
            mem += [("y", C.BANK + 64 * t, samples[t]) for t in range(8)]
            dumps = [("y", C.BANK, 512), ("y", MM.SH, 8), ("y", C.MP, 8), ("y", FS.VB, 0x28), ("y", rg, 8), ("y", KEEP, 17)]
            res, _ = rhdspemu.run(0, call=WRAP, mem=mem, segs=segs, dumps=dumps)
            return res

        def ref(words, t, block):
            mem = [("x", 1, [32]), ("x", BUF, block)] + [("y", RW + o, [words[rg + o][t]]) for o in (VX.RPH, VX.RST, VX.RAM)]
            res, _ = rhdspemu.run(0, call=REF, mem=mem, segs=segs, regs_code=DP.asm([f"move #>${RW:x},r1"]),
                                  dumps=[("x", BUF, 32), ("y", RW, 1)])
            return res[("x", BUF)], res[("y", RW)][0]

        bad_ring, bad_lfo, bad_reg = [], [], []
        for case in range(4):
            bank = 0                                      # (dsptool reads y:$FFFFD0 as 0: bank 1 by the words below)
            samples = [[rnd.randrange(1 << 24) for _ in range(64)] for _ in range(8)]
            amt = [rnd.choice((0, 0x7FFFFF, rnd.randrange(1, 0x800000))) for _ in range(8)]
            amt[case] = 0
            sh = [rnd.randrange(FS.NVS) for _ in range(16)]
            q = [S.LFO_Y + S.STRIDE * s if s < S.NL else S.VOL_Y + S.STRIDE * (s - S.NL) for s in sh]
            mr = [rnd.choice((0, rnd.randrange(1, 0x10000))) for _ in range(8)]
            vd = [rnd.choice((0, 0x7FFE00, rnd.randrange(1, 0x800000))) for _ in range(8)]
            words = {rg + VX.RPH: [rnd.randrange(1 << 24) for _ in range(8)], rg + VX.RST: [rnd.randrange(1 << 22) for _ in range(8)],
                     rg + VX.RAM: amt,
                     FS.MB: mr, FS.MB + 8: q[:8], C.MP: [rnd.randrange(1 << 24) for _ in range(8)],
                     FS.VB + FS.O_VP: [rnd.randrange(1 << 24) for _ in range(8)], FS.VB + FS.O_VR: [rnd.randrange(0x10000) for _ in range(8)],
                     FS.VB + FS.O_VD: vd, FS.VB + FS.O_VQ: q[8:], FS.VB + FS.O_VX: [rnd.randrange(0x800000) for _ in range(8)],
                     MM.SH: [0x5A5A5A] * 8}
            res = run(bank, words, samples)
            out = res[("y", C.BANK)]
            for t in range(8):
                blk = samples[t][32 * bank:32 * bank + 32]
                want, ph = (ref(words, t, blk) if amt[t] else (blk, words[rg + VX.RPH][t]))
                gotb = out[64 * t + 32 * bank:64 * t + 32 * bank + 32]
                other = out[64 * t + 32 * (1 - bank):64 * t + 32 * (1 - bank) + 32]
                if gotb != want or res[("y", rg)][t] != ph or other != samples[t][32 * (1 - bank):64 - 32 * bank]:
                    bad_ring.append((case, t, hex(amt[t]), gotb[:2], want[:2], hex(res[("y", rg)][t]), hex(ph)))
                tab = [tw[q[t] - S.ENV_Y + j] for j in range(S.NPT + 1)]
                if mr[t]:
                    p = (words[C.MP][t] + mr[t]) & 0xFFFFFF
                    m = lk(tab, p >> 1)
                else:
                    p, m = words[C.MP][t], 0
                vt = [tw[q[8 + t] - S.ENV_Y + j] for j in range(S.NPT + 1)]
                vp = words[FS.VB + FS.O_VP][t]
                if vd[t]:
                    vp = (vp + words[FS.VB + FS.O_VR][t]) & 0xFFFFFF
                    x0 = ((0x7FFFFF - s24(lk(vt, vp >> 1))) >> 1) & 0xFFFFFF
                    vx = mpy(vd[t], x0)
                else:
                    vx = 0
                cut = words[FS.VB + FS.O_VX][t]
                cut = (cut + mpy(C.VK, vx - cut)) & 0xFFFFFF
                vb = res[("y", FS.VB)]
                gotl = (res[("y", MM.SH)][t], res[("y", C.MP)][t], vb[FS.O_VP + t], vb[FS.O_VX + t])
                if gotl != (m, p, vp, cut):
                    bad_lfo.append((case, t, sh[t], sh[8 + t], [hex(x) for x in gotl], [hex(x) for x in (m, p, vp, cut)]))
            k = res[("y", KEEP)]
            if k[:16] != regs or k[16] != 0x3F:
                bad_reg.append((case, [hex(x) for x in k]))
        check(f"{build}: the ring mod on the bank's blocks = voicefx's ring stage (samples, phase); amount 0 and the other bank untouched",
              not bad_ring, bad_ring[:2])
        check(f"{build}: the move LFO (M, its phase) and the volume LFO (its phase, the smoothed cut) = the model, 4 sets of 8 tracks",
              not bad_lfo, bad_lfo[:2])
        check(f"{build}: the stock's r0-r7, n0-n7 and a modulo m1 kept", not bad_reg, bad_reg[:2])
        bad = []
        for s in range(FS.NVS):
            qq = S.LFO_Y + S.STRIDE * s if s < S.NL else S.VOL_Y + S.STRIDE * (s - S.NL)
            tab = [tw[qq - S.ENV_Y + j] for j in range(S.NPT + 1)]
            phs = [0, 0x300000, 0x900000, 0xF00000, 0x123456, 0x7FFFFF, 0xABCDEF, 0x555555]
            words = {FS.MB: [0x800] * 8, FS.MB + 8: [qq] * 8, C.MP: [(p - 0x800) & 0xFFFFFF for p in phs], MM.SH: [0] * 8,
                     FS.VB + FS.O_VD: [0] * 8, rg + VX.RAM: [0] * 8}
            res = run(0, words, [[0] * 64 for _ in range(8)])
            for t, p in enumerate(phs):
                if res[("y", MM.SH)][t] != lk(tab, p >> 1) or res[("y", C.MP)][t] != p:
                    bad.append((s, hex(p), hex(res[("y", MM.SH)][t])))
        check(f"{build}: the move LFO: all {FS.NVS} shapes at 8 phases", not bad, bad[:3])
    print("ALL PASS" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
