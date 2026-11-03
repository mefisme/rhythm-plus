"""Core 1 boot check in dsptool: a build's own core 1 program from its loader to the main loop's wait (MIT; Circuit Rhythm 5706).

With no core 0 mailbox, a booted core 1 turns in its wait at P:$111; dspload's IDLE counts each turn at Y:IDLE (+ the shift).  The check: the
counter moves, no block ran (Y:BLOCKS 0), and pitchmod's Y words above voice 7's sample ring start cleared.

    emu_dspboot.py BUILD [BUILD ...]      (BUILD: firmware/<build>)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rhdsp1  # noqa: E402
import rhdspemu  # noqa: E402

MAXINS = 5_000_000
ENTRY, NEVER = 0x100, 0xFFFF                              # the loader ends with jmp $100; a stop never reached


def boot(build):
    d = HERE / "firmware" / build
    rep = json.loads((d / "manifest.json").read_text())["report"]
    img = bytearray((d / f"rhythmplus-{build.upper()}.bin").read_bytes())
    pm = rep["pitchmod"]
    segs, _ = rhdsp1.parse(rhdsp1.sent(img, rep, "pitchmod"))
    idle, blocks = int(pm["y_idle"], 16), int(pm["y_blocks"], 16)
    yb = int(pm["y_base"], 16)
    res, ran = rhdspemu.run(1, pc=ENTRY, stop=NEVER, segs=segs, dumps=[("y", idle, 1), ("y", blocks, 1), ("y", yb, 64)], maxins=MAXINS)
    return res[("y", idle)][0], res[("y", blocks)][0], res[("y", yb)], ran


def main():
    fails = 0
    for build in sys.argv[1:]:
        n_idle, n_blocks, words, ran = boot(build)
        ok = n_idle > 0 and n_blocks == 0 and not any(words)
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'} {build}: wait turns {n_idle}, blocks {n_blocks}, pitchmod words cleared {not any(words)}  ({ran.strip()[-80:]})")
    print("ALL PASS" if not fails else f"{fails} FAIL")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
