"""gfxsplit's core 0 hooks in dsptool (MIT; Circuit Rhythm 5706): a build's own core 0 program.

    python tests/emu_gfxsplit.py BUILD

Checks: P:$224 / $282 call the hooks, the rest of the block as the stock's; `pre` = the track's dry x its gain into DRY, its buffer
cleared, then the stock's sum (= the stock's sum without that track); `post` = DRY added into the Grid FX mix before the compressor.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / d) for d in ("modules", "builds", "tests", "remix/tools")]
import core0  # noqa: E402
import gfxsplit as G  # noqa: E402
import rhdspemu  # noqa: E402

STOCK = HERE / "remix" / "stock" / "circuitrhythm-firmware-5706-STOCK.bin"
FAILS = []
N = 32


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def s24(w):
    w &= 0xFFFFFF
    return w - (1 << 24) if w & 0x800000 else w


def mpy(a, b):
    return (s24(a) * s24(b) * 2) >> 24


def sat(v):
    return max(-0x800000, min(0x7FFFFF, v)) & 0xFFFFFF


def sends(img, g):
    pre, post, cut_at = int(g["pre"], 16), int(g["post"], 16), int(g["cut"], 16)
    ws = G.program(img,g)
    _, _, sws = core0.block_words(bytearray(STOCK.read_bytes()))
    top = int(g["at"], 16) + g["words"]
    diff = [hex(a) for a in range(len(sws)) if ws[a] != sws[a] and not (G.AT <= a < top) and a not in G.SITES and a not in ((G.CAPTURE_SITE, G.RETURN_SITE, G.RETURN_SITE + 1) if "controls" in g else ())]
    check("P:$224 / $282 call the hooks; the rest of core 0's block is the stock's",
          ws[0x225] == pre and ws[0x283] == (int(g["controls"]["blend"], 16) if "controls" in g else post) and not diff and top <= 0x100, diff[:4])
    segs, ssegs = [("p", 0, ws)], [("p", 0, sws)]
    try:
        import voicefx
        voicefx.check(ws[G.AT:top], G.AT)
        ok = True
    except AssertionError as e:
        ok = e
    check("the hooks' words: no mpysu / macsu (an invalid mpy pair; the emulator runs it as mpy, the unit does not)", ok is True, ok)
    rnd = random.Random(9)
    src = [rnd.randrange(1 << 24) for _ in range(8 * 2 * N)]
    dly = [rnd.randrange(1 << 24) for _ in range(8 * 2 * N)]
    rev = [rnd.randrange(1 << 24) for _ in range(8 * 2 * N)]
    gain = [rnd.randrange(0x800000) for _ in range(8 * 64)]
    dumps = [("x", G.DRY, 2 * N), ("x", G.SRC, 2 * N * 8), ("x", 0x30430, 2 * N), ("x", 0x30470, 2 * N), ("x", 0x304B0, 2 * N)]
    app_at = int(g["applied"], 16)
    old = [0x7FFF00, 0, 0x400000, 0x200000, 0, 0x7FFF00, 0x100000, 0x300000]
    new = [0, 0x7FFF00, 0x100000, 0x600000, 0, 0x7FFF00, 0x300000, 0x100000]
    for name, cut, was, br in (("all into Grid FX (a fresh core 0)", [0] * 8, [0] * 8, 0),
                               ("tracks 1 and 4 out, the others in", [0x7FFF00, 0, 0, 0x7FFF00, 0, 0, 0, 0], old, 0),
                               ("shares", [rnd.randrange(0x800000) for _ in range(8)], old, 0),
                               ("beat repeat on: a send going up keeps the share in use, going down takes it", new, old, 1),
                               ("beat repeat off again: every share taken", new, old, 0x1E)):
        base = [("x", 0x3A, [N]), ("x", G.SRC, src), ("x", G.SRC + 0x200, dly), ("x", G.SRC + 0x400, rev), ("y", G.GAIN, gain),
                ("x", cut_at, cut), ("x", app_at, was), ("x", G.BR_STATE, [br])]
        res, _ = rhdspemu.run(0, call=pre, mem=base, segs=segs, dumps=dumps + [("x", app_at, 8)])
        use = [w if br & 1 << G.BR_ON and c < w else c for c, w in zip(cut, was)]
        check(f"sends, {name}: the shares in use", res[("x", app_at)] == use, ([hex(v) for v in res[("x", app_at)]], [hex(v) for v in use]))
        keep = [s for s in src]
        dry = [0] * (2 * N)
        for t in range(8):
            if not use[t]:
                continue
            s_ = 0x7FFFFF - use[t]
            for i in range(2 * N):
                x = src[64 * t + i]
                keep[64 * t + i] = sat(mpy(x, s_))
                dry[i] = sat(s24(dry[i]) + mpy(sat(mpy(x, use[t])), gain[64 * t + i // 2]))
        check(f"sends, {name}: the dry buffers x (1 - c)", res[("x", G.SRC)] == keep,
              [(i, hex(a), hex(b)) for i, (a, b) in enumerate(zip(res[("x", G.SRC)], keep)) if a != b][:3])
        check(f"sends, {name}: DRY = the sum of dry x c x gain", res[("x", G.DRY)] == dry,
              [(i, hex(a), hex(b)) for i, (a, b) in enumerate(zip(res[("x", G.DRY)], dry)) if a != b][:3])
        ref, _ = rhdspemu.run(0, call=G.SUM, mem=[m if m[1] != G.SRC else ("x", G.SRC, keep) for m in base], segs=ssegs,
                              dumps=dumps[2:])
        check(f"sends, {name}: then the stock's sum of what is left; the delay and reverb sends kept",
              all(res[k] == ref[k] for k in (("x", 0x30430), ("x", 0x30470), ("x", 0x304B0))))
    mix = [rnd.randrange(1 << 24) for _ in range(2 * N)]
    dry = [rnd.randrange(1 << 24) for _ in range(2 * N)]
    res, _ = rhdspemu.run(0, call=post, stop=G.COMP, mem=[("x", 0x3A, [N]), ("x", G.MIX, mix), ("x", G.DRY, dry)], segs=segs,
                          dumps=[("x", G.MIX, 2 * N)])
    check("post: DRY added into the Grid FX mix, before the compressor",
          res[("x", G.MIX)] == [sat(s24(a) + s24(b)) for a, b in zip(mix, dry)])
    if "controls" in g:
        control_tests(img, g, segs, rnd)
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED")
    sys.exit(1 if FAILS else 0)


def control_tests(img, g, segs, rnd):
    labels = {k: int(v, 16) for k, v in g["controls"].items()}
    words = G.program(img,g)
    import voicefx
    voicefx.check(words[G.CTRL_AT:], G.CTRL_AT)
    check("effective upload includes the complete control program", len(words) == g["total_words"] and len(words) < 0x4000)
    signal = [rnd.randrange(-0x40000, 0x40000) & 0xFFFFFF for _ in range(64)]
    captured, _ = rhdspemu.run(0, call=labels["capture"], stop=0x166B,
        mem=[("x",0x3A,[N]),("x",0x4AD8,signal)], segs=segs, dumps=[("x",G.CLEAN,64)])
    check("global blend captures clean audio before Beat Repeat and other Grid FX", captured["x",G.CLEAN] == signal)
    rev = signal
    delay = list(reversed(signal))
    for rc, dc in ((0,0),(0x7FFF00,0),(0,0x7FFF00),(0x7FFF00,0x7FFF00),(0x200000,0x600000)):
        for shift in (0,1,2):
            res, _ = rhdspemu.run(0, call=labels["returns"], mem=[("x",0x3A,[N]),("x",G.RETURN_CUT,[rc,dc]),
                ("x",0x77E,[shift]),("y",0x889,rev),("y",0x9C9,delay),("x",G.DRY,[0]*64)], segs=segs,
                dumps=[("y",0x889,64),("y",0x9C9,64),("x",G.DRY,64)])
            parts = [[s24(x) if c == 0x7FFF00 else mpy(x,c) for x in data] for c,data in ((rc,rev),(dc,delay))]
            check(f"return routing {rc:x}/{dc:x}, shift {shift}: wet plus bypass retains both returns",
                  res["y",0x889] == [sat(s24(x)-d) for x,d in zip(rev,parts[0])]
                  and res["y",0x9C9] == [sat(s24(x)-d) for x,d in zip(delay,parts[1])]
                  and res["x",G.DRY] == [sat((a>>shift)+(b>>shift)) for a,b in zip(*parts)])
    processed = [rnd.randrange(-0x100000,0x100000)&0xFFFFFF for _ in range(64)]
    bypass = [rnd.randrange(-0x10000,0x10000)&0xFFFFFF for _ in range(64)]
    for level in (0,0x200000,0x400000,0x7FFF00):
        res, _ = rhdspemu.run(0, call=labels["blend"], stop=G.COMP, mem=[("x",0x3A,[N]),
            ("x",G.BLEND,[level,level]),("x",G.MIX,processed),("x",G.CLEAN,signal),("x",G.DRY,bypass)], segs=segs,
            dumps=[("x",G.MIX,64),("x",G.BLEND_NOW,1)])
        want=[sat(s24(d)+(s24(w) if level==0 else s24(c) if level==0x7FFF00
                         else (s24(c)*level*2+s24(w)*(0x7FFFFF-level)*2)>>24))
              for w,c,d in zip(processed,signal,bypass)]
        check(f"global blend {level:x}: clean/processed blend plus unprocessed bypass",res["x",G.MIX]==want,
              [(i,hex(a),hex(b)) for i,(a,b) in enumerate(zip(res["x",G.MIX],want)) if a!=b][:3])
    res, _ = rhdspemu.run(0, call=labels["blend"], stop=G.COMP, mem=[("x",0x3A,[N]),
        ("x",G.BLEND,[0x7FFF00,0]),("x",G.MIX,processed),("x",G.CLEAN,signal),("x",G.DRY,[0]*64)],
        segs=segs,dumps=[("x",G.BLEND_NOW,1)])
    check("global blend slews rather than jumping to the target",res["x",G.BLEND_NOW]==[N*0x1000])


def main():
    b = sys.argv[1]
    d = HERE / "firmware" / b
    img = bytearray((d / f"rhythmplus-{b.upper()}.bin").read_bytes())
    rep = json.loads((d / "manifest.json").read_text())["report"]
    g = rep["gfxsplit"]
    if "cut" in g:
        return sends(img, g)
    t, pre, post = g["track"], int(g["pre"], 16), int(g["post"], 16)
    ws = G.program(img,g)
    _, _, sws = core0.block_words(bytearray(STOCK.read_bytes()))
    top = int(g["at"], 16) + g["words"]
    diff = [hex(a) for a in range(len(sws)) if ws[a] != sws[a] and not (G.AT <= a < top) and a not in G.SITES and a not in ((G.CAPTURE_SITE, G.RETURN_SITE, G.RETURN_SITE + 1) if "controls" in g else ())]
    check("P:$224 / $282 call the hooks; the rest of core 0's block is the stock's",
          ws[0x224] == ws[0x282] == 0x0BF080 and ws[0x225] == pre and ws[0x283] == (int(g["controls"]["blend"], 16) if "controls" in g else post) and not diff and top <= 0x100, diff[:4])
    segs, ssegs = [("p", 0, ws)], [("p", 0, sws)]
    rnd = random.Random(7)
    src = [rnd.randrange(1 << 24) for _ in range(8 * 2 * N)]                 # dry L / R of the 8 tracks
    dly = [rnd.randrange(1 << 24) for _ in range(8 * 2 * N)]
    rev = [rnd.randrange(1 << 24) for _ in range(8 * 2 * N)]
    gain = [rnd.randrange(0x800000) for _ in range(8 * 64)]
    base = [("x", 0x3A, [N]), ("x", G.SRC, src), ("x", G.SRC + 0x200, dly), ("x", G.SRC + 0x400, rev), ("y", G.GAIN, gain)]
    dumps = [("x", G.DRY, 2 * N), ("x", G.SRC, 2 * N * 8), ("x", 0x30430, 2 * N), ("x", 0x30470, 2 * N), ("x", 0x304B0, 2 * N)]
    res, _ = rhdspemu.run(0, call=pre, mem=base, segs=segs, dumps=dumps)
    want = [sat(mpy(gain[64 * t + i // 2], src[64 * t + i])) for i in range(2 * N)]
    check(f"pre: track {t + 1}'s dry x its gain into DRY", res[("x", G.DRY)] == want,
          [(i, hex(a), hex(b)) for i, (a, b) in enumerate(zip(res[("x", G.DRY)], want)) if a != b][:3])
    check(f"pre: track {t + 1}'s dry buffer cleared, the others kept",
          res[("x", G.SRC)][64 * t:64 * t + 64] == [0] * 64
          and all(res[("x", G.SRC)][i] == src[i] for i in range(512) if not 64 * t <= i < 64 * t + 64))
    zsrc = list(src)
    zsrc[64 * t:64 * t + 64] = [0] * 64
    ref, _ = rhdspemu.run(0, call=G.SUM, mem=[m if m[1] != G.SRC else ("x", G.SRC, zsrc) for m in base], segs=ssegs,
                          dumps=dumps[2:])
    check("pre then the stock's sum: the mix = the stock's without that track; its delay and reverb sends kept",
          all(res[k] == ref[k] for k in (("x", 0x30430), ("x", 0x30470), ("x", 0x304B0))) and any(ref[("x", 0x30430)]))
    mix = [rnd.randrange(1 << 24) for _ in range(2 * N)]
    dry = [rnd.choice((0x7FFFFF, 0x800000, rnd.randrange(1 << 24))) for _ in range(2 * N)]
    res, _ = rhdspemu.run(0, call=post, stop=G.COMP, mem=[("x", 0x3A, [N]), ("x", G.MIX, mix), ("x", G.DRY, dry)], segs=segs,
                          dumps=[("x", G.MIX, 2 * N)])
    want = [sat(s24(a) + s24(b)) for a, b in zip(mix, dry)]
    check("post: DRY added into the Grid FX mix (limited), before the compressor", res[("x", G.MIX)] == want,
          [(i, hex(a), hex(b)) for i, (a, b) in enumerate(zip(res[("x", G.MIX)], want)) if a != b][:3])
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
