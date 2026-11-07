"""fshape loopfade in dsptool: core 1's end fade P:$25C, the stock's program against a build's.
    python tests/emu_loopfade.py BUILD [BUILD ...]      (BUILD: firmware/<build>)
Voice 0 (r0 = $44) of track 3 with its fetch 100 words inside its end (or 1000 away), forward and reverse, one-shot and loop: the stock
zeroes the track's level target (shared Y:$37301 + 2 t) near the end in every mode; the build keeps it in loop mode, as the stock elsewhere.
A build with fshape's sm: the same with the track's end fade on (Y:SMF + t: the switches XOR their defaults), and the target kept in
every mode with it off.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rpasm  # noqa: E402
rpasm.use()
import rhdsp1  # noqa: E402
import rhdspemu  # noqa: E402
import rhdsppatch as DP  # noqa: E402

FAILS = []
T, END, FULL = 3, 200000, 0x7FFFFF
TARGET = 0x37301 + 2 * T
CASES = (  # name, mode (bit 0 reverse, bit 1 loop), fetch, the stock zeroes
    ("one-shot near the end", 0, END - 100, True),
    ("one-shot far from the end", 0, END - 1000, False),
    ("loop near the end", 2, END - 100, True),
    ("loop far from the end", 2, END - 1000, False),
    ("reverse near the start", 1, END + 100, True),
    ("reverse loop near the start", 3, END + 100, True),
)


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def target(segs, mode, fetch, sm=None):
    mem = [("x", 0x43, [fetch]), ("y", 0x43, [END]), ("y", 0x45, [mode]), ("y", 0x1405, [T]), ("y", TARGET, [FULL])]
    if sm:
        smf, flags, _ = sm
        mem += [("y", smf, [0] * 8), ("y", smf + T, [flags ^ sm[2]])]
    res, _ = rhdspemu.run(1, call=0x25C, mem=mem, segs=segs, regs_code=DP.asm(["move #>$44,r0"]), dumps=[("y", TARGET, 1)])
    return res[("y", TARGET)][0]


def main():
    stock = rhdspemu.segments(1, 0)
    for build in sys.argv[1:]:
        d = HERE / "firmware" / build
        rep = json.loads((d / "manifest.json").read_text())["report"]
        img = bytearray((d / f"rhythmplus-{build.upper()}.bin").read_bytes())
        segs, _ = rhdsp1.parse(rhdsp1.sent(img, rep, "pitchmod"))
        fs = rep["fshape"]
        smf = int(fs["smf"], 16) if fs.get("sm") else None
        ef = 4
        for name, mode, fetch, zero in CASES:
            s = target(stock, mode, fetch)
            check(f"{build} stock, {name}: target {'0' if zero else 'full'}", s == (0 if zero else FULL), hex(s))
            want = FULL if mode & 2 else (0 if zero else FULL)
            if smf is None:
                b = target(segs, mode, fetch)
                check(f"{build}, {name}: target {'0' if want == 0 else 'full'}", b == want, hex(b))
                continue
            for flags in (fs["smdefs"][0], ef, ef | 3):
                b = target(segs, mode, fetch, (smf, flags, fs["smdefs"][0]))
                check(f"{build}, end fade on (switches {flags}), {name}: target {'0' if want == 0 else 'full'}", b == want, hex(b))
            for flags in (0, 3):
                b = target(segs, mode, fetch, (smf, flags, fs["smdefs"][0]))
                check(f"{build}, end fade off (switches {flags}), {name}: target full", b == FULL, hex(b))
    print("ALL PASS" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
