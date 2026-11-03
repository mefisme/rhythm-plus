"""Core 0 with a build's granular in dsptool (MIT; Circuit Rhythm 5706): the words the ARM uploads on a mode 0 upload, then one block of
the engine (GR, from the hook at P:$224 to the stock's mix at P:$367) on a track with a sample in four pages of the sample memory.

    python tests/emu_grain0.py BUILD [BUILD ...]      (BUILD: firmware/<build>)

Checks: the upload holds the stock block unchanged, the engine at granular0's place and the hook P:$224 = jsr GR; GR leaves the track's
samples as they are without the key or with no track; with the key on the track: the gate on (the steps) opens on the voice's samples
and the grains replace them; the gate off (a drone) sounds from the sample with a silent voice; another track is never touched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import core0 as C0  # noqa: E402
import grain_rp as GR  # noqa: E402
import granular0 as G  # noqa: E402
import rhdspemu  # noqa: E402

TRK, OTHER, SMPN, LEN = 2, 5, 5, 0x4000
PAGE0 = 0x040                                             # the sample's four pages: $40.. (4 096 words each, Y space; dsptool keeps Y below $100000)
FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def uploaded(build):
    d = HERE / "firmware" / build
    rep = json.loads((d / "manifest.json").read_text())["report"]
    img = (d / f"rhythmplus-{build.upper()}.bin").read_bytes()
    _, stream = C0.sent(img, rep)
    segs, i = [], 0
    while i < len(stream):
        cnt, addr = stream[i], stream[i + 1]
        if cnt == 0:
            break
        segs.append(("p", addr, stream[i + 2:i + 2 + cnt]))
        i += 2 + cnt
    return rep, segs


def run(segs, gr, controls, voice, other):
    buf = lambda t: G.TRK_BUF + 64 * t                                       # noqa: E731 (y:$FFFFD0 = 0: the first half)
    pages = [((PAGE0 + 2 * j) << 12) | (PAGE0 + 2 * j + 1) for j in range(2)]
    mem = [("x", G.GB, controls), ("y", 0xFFFFD0, [0]),
           ("y", buf(TRK), voice), ("y", buf(OTHER), other),
           ("y", G.PAR0 + 0x20 * TRK, [SMPN]), ("x", G.SMP + 4 * SMPN, [0, LEN]), ("y", G.PAGES + G.PSTRIDE * SMPN, pages)]
    for p in range(4):                                                       # a loud saw, a period of 256 words
        base = (PAGE0 + p) << 12
        for k in range(0, 4096, 64):
            mem.append(("y", base + k, [((((p * 4096 + k + j) & 0xFF) - 128) << 15) & 0xFFFFFF for j in range(64)]))
    res, ran = rhdspemu.run(0, pc=gr, stop=G.MIX, mem=mem, segs=segs, dumps=[("y", buf(TRK), 32), ("y", buf(OTHER), 32)], maxins=2_000_000)
    return res[("y", buf(TRK))], res[("y", buf(OTHER))], ran


def main():
    for build in sys.argv[1:]:
        rep, segs = uploaded(build)
        stock = rhdspemu.segments(0)[0]
        gr = int(rep["granular0"]["gr"], 16)
        check(f"{build}: the stock block uploaded as it is, at P:$0", segs[0] == ("p", 0, stock[2]) or (segs[0][1] == 0 and segs[0][2] == stock[2]))
        code, labels, _ = G.code(note=True)
        at = {a: w for _, a, w in segs[1:]}
        check(f"{build}: the engine at P:${G.CODE:x} as granular0 makes it (note), the hook P:$224 = jsr GR",
              at.get(C0.SEG, [])[G.CODE - C0.SEG:] == code and at.get(G.HOOK) == [0x0BF080, gr] and gr == labels["gr"],
              (len(at.get(C0.SEG, [])), at.get(G.HOOK)))
        vals = list(GR.DEF)
        ctrl = [0] * 16
        for k, v in enumerate(vals):
            ctrl[GR.IDX[k]] = GR.model_engine(v, k) & 0xFFFFFF
        voice = [(0x300000 if j % 2 else 0xD00000) for j in range(32)]
        other = [0x123456] * 32
        for name, c in (("no key", dict(trk=TRK + 1, key=0)), ("the key, no track", dict(trk=0, key=G.KEY))):
            w = list(ctrl)
            w[G.P_TRK], w[G.P_KEY] = c["trk"], c["key"]
            out, oth, ran = run(segs, gr, w, voice, other)
            check(f"{build}: {name}: the track's samples as they were", out == voice and oth == other, (ran, [hex(x) for x in out[:4]]))
        w = list(ctrl)
        w[G.P_TRK], w[G.P_KEY], w[G.P_GATE] = TRK + 1, G.KEY, 1
        out, oth, ran = run(segs, gr, w, voice, other)
        check(f"{build}: the key, track {TRK + 1}, the gate on, a loud voice: the grains in place of the voice, track {OTHER + 1} untouched",
              out != voice and any(out) and oth == other, (ran, [hex(x) for x in out[:8]]))
        w[G.P_GATE] = 0
        out, oth, ran = run(segs, gr, w, [0] * 32, other)
        check(f"{build}: the gate off (a drone), a silent voice: the grains sound", any(out) and oth == other, (ran, [hex(x) for x in out[:8]]))
        w[G.P_GATE] = 1
        out, oth, ran = run(segs, gr, w, [0] * 32, other)
        check(f"{build}: the gate on, a silent voice (no step): silence", not any(out) and oth == other, (ran, [hex(x) for x in out[:8]]))
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAIL")
    raise SystemExit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
