"""fshape declick in dsptool: the retrigger de-click of a build's core 1.
    python tests/emu_declick.py BUILD [BUILD ...]      (BUILD: firmware/<build>)
TRIG sets D = the voice's last word L (0 with the de-click off); LVL adds D to the voice's 32 words, D x DK a word, keeps L; a voice not
sounding gets L = 0; the stock's level ramp P:$244..$25B holds lfade / dcidle / dclast; the end fade as emu_loopfade's.
Declick 2: the note-on's stage 4, switch on: the smooth fade; off: the stock's straight fade.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rpasm  # noqa: E402
rpasm.use()
import rhdsp1  # noqa: E402
import rhdspemu  # noqa: E402
import rhdsppatch as DP  # noqa: E402

FAILS = []
BUF, LEVEL, N = 0x2A02, 0x37301, 32
LSTUB = 0xFD0 + 0x30                                     # LVL's caller (P past our code)


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def s24(w):
    return w - (1 << 24) if w & 0x800000 else w


def smooth(build, img, segs, fs):
    """declick 2: the note-on's stage 4 (P:$636) with the switch on = the block x gain x (1 + cos(pi (n + 1) / 33)) / 2, off = the
    stock's straight fade; both end in stage 5 with the gain 0"""
    import fshape as FS
    smf, st4 = int(fs["smf"], 16), int(fs["st4"], 16)
    o = rhdsp1.where(img, FS.ST4_AT)
    check(f"{build}: P:$636 = jmp st4 (${st4:x})", [int.from_bytes(img[o + 3 * i:o + 3 * i + 3], "big") for i in (0, 1)] == [0x0AF080, st4])
    o = rhdsp1.where(img, 0x23A)
    check(f"{build}: P:$23A is the stock's", [int.from_bytes(img[o + 3 * i:o + 3 * i + 3], "big") for i in (0, 1)] == list(FS.IDLE_OLD))
    stock = rhdspemu.segments(1, 0)
    stub = [("p", LSTUB, DP.jsr(FS.ST4_AT) + [0x00000C])]
    v, r6 = 3, 0x40 + 16 * 3
    sine = [round(0.8 * math.sin(2 * math.pi * 220 * i / 48000 + 1.1) * (1 << 23)) & 0xFFFFFF for i in range(N)]
    full = [0x7FFFFF] * N

    def run(sg, gain, flags, buf):
        mem = [("x", 1, [N]), ("x", BUF - 1, [0x123456] + buf), ("y", 0x1405, [v]), ("y", smf, [0x6] * 8), ("y", smf + v, [flags]),
               ("x", r6 + 0xA, [4, gain])]
        res, _ = rhdspemu.run(1, call=LSTUB, mem=mem, segs=sg + stub,
                              regs_code=DP.asm([f"move #>${gain:x},a", f"move #>${BUF:x},r1", f"move #>${BUF - 1:x},r4", f"move #>${r6:x},r6"]),
                              dumps=[("x", BUF, N), ("x", r6 + 0xA, 2)])
        return [s24(w) for w in res[("x", BUF)]], res[("x", r6 + 0xA)]
    for gain in (0x7FFFFF, 0x400000, 0x123456):
        for name, buf in (("a sine", sine), ("full scale", full)):
            want = [s24(x) * gain / (1 << 23) * (1 + math.cos(math.pi * (n + 1) / 33)) / 2 for n, x in enumerate(buf)]
            out, st = run(segs, gain, 4, buf)
            err = max(abs(a - b) for a, b in zip(out, want))
            check(f"{build}: switch on, gain {gain:#x}, {name}: the smooth fade (within 64 of the model, -102 dB), then stage 5, gain 0",
                  err <= 64 and st == [5, 0], (err, st, out[:2], [round(x) for x in want[:2]]))
            ref, sr = run(stock, gain, 6, buf)
            out, st = run(segs, gain, 6, buf)
            check(f"{build}: switch off, gain {gain:#x}, {name}: the stock's straight fade word for word", out == ref and st == sr, (out[:2], ref[:2]))


def main():
    for build in sys.argv[1:]:
        d = HERE / "firmware" / build
        rep = json.loads((d / "manifest.json").read_text())["report"]
        os.environ["RH_PSHAPE"] = os.environ["RH_FSHAPE"] = "1"
        import pshape as S
        img = bytearray((d / f"rhythmplus-{build.upper()}.bin").read_bytes())
        segs, _ = rhdsp1.parse(rhdsp1.sent(img, rep, "pitchmod"))
        fs = rep["fshape"]
        if fs["declick"] == 2:
            smooth(build, img, segs, fs)
            continue
        dcb, smf, dk = int(fs["dcb"], 16), int(fs["smf"], 16), int(fs["dk"], 16)
        lvl, trig, idle = int(fs["lvl"], 16), int(rep["pitchmod"]["trig"], 16), int(fs["dcidle"], 16)
        o = rhdsp1.where(img, 0x23A)
        check(f"{build}: P:$23A = jeq dcidle (${idle:x})", [int.from_bytes(img[o + 3 * i:o + 3 * i + 3], "big") for i in (0, 1)] == [0x0AF0AA, idle])
        stub = [("p", LSTUB, DP.jsr(lvl) + [0x00000C])]
        tw = S.table_words(rep["pshape"].get("v2", False), vol=True)
        tabs = [("y", S.ENV_Y + i, [w]) for i, w in enumerate(tw) if w is not None]
        samples = [(0x012345 * (i + 1) * (1 if i % 2 else -1)) & 0xFFFFFF for i in range(N)]
        v = 5

        def lvl_run(d0, buf=samples):
            mem = tabs + [("x", 1, [N]), ("x", BUF, buf), ("y", 0x1405, [v]), ("y", LEVEL + 2 * v, [0x7FFFFF, 0x7FFFFF]),
                          ("y", dcb, [0] * 16), ("y", dcb + v, [d0 & 0xFFFFFF])]
            res, _ = rhdspemu.run(1, call=LSTUB, mem=mem, segs=segs + stub, regs_code=DP.asm(["move #>$94,r0"]),
                                  dumps=[("x", BUF, N), ("y", dcb, 16)])
            return [s24(w) for w in res[("x", BUF)]], [s24(w) for w in res[("y", dcb)]]

        ref, dl = lvl_run(0)
        check(f"{build}: LVL, D = 0: L = the voice's last word, D stays 0", dl[8 + v] == ref[-1] and dl[v] == 0 and dl[:v] + dl[v + 1:8] == [0] * 7,
              (dl, ref[-1]))
        for d0 in (0x200000, -0x300000, 0x7FFFFF):
            out, dl = lvl_run(d0)
            want, dd = [], d0
            for r in ref:
                want.append(max(-0x800000, min(0x7FFFFF, r + dd)))         # the move to X limits
                dd = (dd * dk) >> 23
            dd = dd if abs(dd) >= 0x3F else 0
            check(f"{build}: LVL, D = {d0:#x}: each word + D (limited), D x {dk:#x} a word, then D and L kept", out == want and dl[v] == dd and dl[8 + v] == out[-1],
                  (out[:3], want[:3], dl[v], dd))
        zero = [0] * N
        out, dl = lvl_run(0x2000, zero)
        dd = 0x2000
        for _ in range(N):
            dd = (dd * dk) >> 23
        check(f"{build}: LVL, a small D: added, then above $3F kept ({dd:#x})", dl[v] == dd and out[0] == 0x2000, (out[:2], dl[v]))
        out, dl = lvl_run(0x40, zero)
        check(f"{build}: LVL, D below $3F after the block: D = 0", dl[v] == 0 and out[0] == 0x40, (out[:2], dl[v]))

        def trig_run(t, flags, last):
            mem = tabs + [("y", dcb, [0x111] * 8 + [0] * 8), ("y", dcb + 8 + t, [last & 0xFFFFFF]), ("y", smf, [0] * 8), ("y", smf + t, [flags])]
            res, _ = rhdspemu.run(1, call=trig, mem=mem, segs=segs, regs_code=DP.asm([f"move #>${t:x},y1"]), dumps=[("y", dcb, 8)])
            return [s24(w) for w in res[("y", dcb)]]
        for t, flags, want in ((2, 0, 0x234567), (6, 2, 0), (0, 4, 0x234567), (7, 6, 0)):
            dd = trig_run(t, flags, 0x234567)
            check(f"{build}: TRIG, track {t + 1}, DSP switches {flags} (de-click {'off' if flags & 2 else 'on'}): D = {want:#x}, other tracks kept",
                  dd[t] == want and all(x == 0x111 for i, x in enumerate(dd) if i != t), [hex(x) for x in dd])
        dd = trig_run(3, 0, -0x100000)
        check(f"{build}: TRIG, a negative L: D = L", dd[3] == -0x100000, hex(dd[3]))

        mem = [("y", 0x1405, [7]), ("y", dcb, [0x55] * 16)]
        res, _ = rhdspemu.run(1, call=idle, mem=mem, segs=segs, regs_code=DP.asm(["move #>$b4,r0", "move #$10,n0", "clr b"]),
                              dumps=[("y", dcb, 16), ("y", 0x1405, 1)])
        got = res[("y", dcb)]
        check(f"{build}: a voice not sounding: its L = 0, others kept, then the stock's $6C6 (next voice)",
              got[15] == 0 and got[:15] == [0x55] * 15 and res[("y", 0x1405)] == [8], ([hex(x) for x in got], res[("y", 0x1405)]))
    print("ALL PASS" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
