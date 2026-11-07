"""fshape drone in dsptool: the note-on and note-off messages' handlers (P:$4F4, P:$509) of a build's core 1.
    python tests/emu_drone.py BUILD [BUILD ...]      (BUILD: firmware/<build>)
Switch off, another note, an idle voice, stage 3-5, a stage 2 from an earlier block, or a one-shot within $100 of its end: the stock's
note-on word for word (the queue, the stage).  Switch on with the same note on a sounding voice: no queue, stage 1.  Y:LN + t = the
message.  The note-off: the stock's stage 2, Y:LOFF + t = the block counter.
"""
from __future__ import annotations

import json
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
STUB = 0xFD0 + 0x30
QUEUE, SENT = 0x307B7, 0x5A5A5A
T, END = 5, 0x1F400


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def main():
    os.environ["RH_PSHAPE"] = os.environ["RH_FSHAPE"] = "1"
    import fshape as FS
    for build in sys.argv[1:]:
        d = HERE / "firmware" / build
        rep = json.loads((d / "manifest.json").read_text())["report"]
        fs = rep["fshape"]
        img = bytearray((d / f"rhythmplus-{build.upper()}.bin").read_bytes())
        segs, _ = rhdsp1.parse(rhdsp1.sent(img, rep, "pitchmod"))
        dr, ln, smf = int(fs["drone"], 16), int(fs["ln"], 16), int(fs["smf"], 16)
        o = rhdsp1.where(img, FS.NOTE_AT)
        check(f"{build}: P:$4F4 = jmp drone (${dr:x})", [int.from_bytes(img[o + 3 * i:o + 3 * i + 3], "big") for i in (0, 1)] == [0x0AF080, dr])
        check(f"{build}: pad 20 is the drone switch", rep["smpads"]["pads"].get("19") == FS.SM_DR)
        stock = rhdspemu.segments(1, 0)
        v = 0x40 + 16 * T

        loff, blk = int(fs["loff"], 16), int(fs["blk"], 16)
        NOW = 0x1234

        def run(sg, flags, old, msg, stage, mode, pos, active=0x300000, off=NOW, call=FS.NOTE_AT):
            mem = [("y", QUEUE, [SENT] * 16), ("y", smf, [0] * 8), ("y", smf + T, [flags]), ("y", ln, [0] * 16), ("y", ln + T, [old]),
                   ("y", loff + T, [off]), ("y", blk, [NOW]),
                   ("x", v, [0] * 16), ("x", v + 3, [pos]), ("x", v + 4, [active]), ("x", v + 0xA, [stage]), ("y", v, [0] * 16),
                   ("y", v + 3, [END]), ("y", v + 5, [mode])]
            res, _ = rhdspemu.run(1, call=STUB, mem=mem, segs=sg + [("p", STUB, DP.jsr(call) + [0x00000C])],
                                  regs_code=DP.asm([f"move #>${msg:x},y1", "move #>$64,y0"]),
                                  dumps=[("y", QUEUE + 2 * T, 2), ("x", v + 0xA, 1), ("y", ln + T, 1), ("y", loff + T, 1)])
            return res[("y", QUEUE + 2 * T)], res[("x", v + 0xA)][0], res[("y", ln + T)][0], res[("y", loff + T)][0]
        note = (0x3C << 8) | 0x90 | T
        other = (0x3E << 8) | 0x90 | T
        D = FS.SM_DR
        cases = [  # name, flags, old, msg, stage, mode, pos, extra, tie
            ("switch off", 0, note, note, 1, 2, 0x1000, {}, False),
            ("switch on, another note", D, other, note, 1, 2, 0x1000, {}, False),
            ("switch on, an idle voice in stage 2 (after stop)", D, note, note, 2, 2, 0x1000, dict(active=0), False),
            ("switch on, an idle voice in stage 1", D, note, note, 1, 2, 0x1000, dict(active=0), False),
            ("switch on, stage 2 from an earlier block's note-off", D, note, note, 2, 2, 0x1000, dict(off=NOW - 1), False),
            ("switch on, stage 3", D, note, note, 3, 2, 0x1000, {}, False),
            ("switch on, stage 4", D, note, note, 4, 2, 0x1000, {}, False),
            ("switch on, stage 5", D, note, note, 5, 2, 0x1000, {}, False),
            ("switch on, one-shot $80 before its end", D, note, note, 1, 0, END - 0x80, {}, False),
            ("switch on, reverse $80 past its start", D, note, note, 1, 1, END + 0x80, {}, False),
            ("switch on, loop, stage 1", D, note, note, 1, 2, END - 0x10, {}, True),
            ("switch on, loop, stage 0", D, note, note, 0, 2, 0x1000, {}, True),
            ("switch on, loop, stage 2 from this block's note-off", D, note, note, 2, 2, 0x1000, {}, True),
            ("switch on, one-shot $1000 before its end", D, note, note, 1, 0, END - 0x1000, {}, True),
            ("switch on, reverse $1000 past its start", D, note, note, 2, 1, END + 0x1000, {}, True),
        ]
        for name, flags, old, msg, stage, mode, pos, ex, tie in cases:
            q, st, last, _ = run(segs, flags, old, msg, stage, mode, pos, **ex)
            if tie:
                check(f"{build}: {name}: no new note, stage 1, Y:LN = the message",
                      q == [SENT, SENT] and st == 1 and last == msg, (q, st, hex(last)))
            else:
                rq, rst, _, _ = run(stock, flags, old, msg, stage, mode, pos, **ex)
                check(f"{build}: {name}: the stock's note-on (queue, stage 4), Y:LN = the message",
                      q == rq and st == rst == 4 and q == [msg, 0x64] and last == msg, (q, rq, st, rst, hex(last)))
        o = rhdsp1.where(img, FS.OFF_AT)
        dof = int(fs["droff"], 16)
        check(f"{build}: P:$509 = jmp droff (${dof:x})", [int.from_bytes(img[o + 3 * i:o + 3 * i + 3], "big") for i in (0, 1)] == [0x0AF080, dof])
        off = (0x3C << 8) | 0x80 | T
        for st0 in (1, 5):
            q, st, _, lo = run(segs, D, note, off, st0, 2, 0x1000, off=0, call=FS.OFF_AT)
            rq, rst, _, _ = run(stock, D, note, off, st0, 2, 0x1000, off=0, call=FS.OFF_AT)
            check(f"{build}: note-off from stage {st0}: the stock's stage 2, Y:LOFF = the block counter", st == rst == 2 and q == rq and lo == NOW,
                  (st, rst, q, rq, hex(lo)))
    print("ALL PASS" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
