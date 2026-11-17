"""The core 0 stretch engine (modules/stretch_dsp.py) in dsptool against its block model (tools/stretch_block.py).

    python tests/emu_stretch_dsp.py [quick]

Each case puts a sample in emulated sample memory (pages from $40, Y space), runs st_restart then st_block
block by block, and needs every output word equal to the model's: speeds 0.25-4, Tune, a loop, reverse,
hits, page edges and a region that does not start at 0.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / d) for d in ("modules", "tools", "tests", "remix/tools")]
import rhdspemu  # noqa: E402
import stretch_block as M  # noqa: E402
import stretch_dsp as S  # noqa: E402

PAGE0 = 0x40
PTAB = 0x1800                   # Y: the test sample's page table
LOG = 0x10000                   # Y: the blocks' words, below the sample pages (dsptool keeps no Y at $80000)
DRIVER = 0x3c00
NBLK = 0x1700                   # Y: blocks left (driver)
LOGP = 0x1701
FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def driver():
    import core0
    items = [f"move #>${S.ST_X:x},r7", ("jsr", "rst"),
             ("label", "loop"), f"move y:>${NBLK:x},a", "tst a", ("jcc", "le", "done"),
             f"move #>${S.ST_X:x},r7", ("jsr", "blk"),
             f"move y:>${LOGP:x},r1", f"move #>${S.OUT:x},r0", "do #$20,${cp:x}", "move y:(r0)+,x0", "move x0,y:(r1)+", ("label", "cp"),
             f"move r1,y:>${LOGP:x}", f"move y:>${NBLK:x},a", "sub #>$1,a", f"move a1,y:>${NBLK:x}", ("jmp", "loop"),
             ("label", "done"), "nop", ("label", "stop"), "nop"]
    return items


def run_case(name, x, speed, rate, loop=False, reverse=False, start=0, blocks=None):
    """x: the sample's words in memory order; the region is x[start:], read backwards when reverse."""
    words, labels = S.code()
    import core0
    drv = driver()
    drv = [("jsr", labels["st_restart"]) if it == ("jsr", "rst") else ("jsr", labels["st_block"]) if it == ("jsr", "blk") else it for it in drv]
    dw, dl = core0.asm_at(drv, DRIVER)
    region = x[start:]
    n = len(region)
    play = region[::-1] if reverse else region
    sp, rt = round(speed * (1 << 24)), round(rate * (1 << 24))
    nb = blocks or min(int((n - 1) / speed) // 32, 400)
    M.Search.owner = None
    t = M.Track(list(play), sp, rt, loop)
    want = [w for _ in range(nb) for w in t.block()]
    npages = (len(x) + 4095) // 4096
    pt = [(((PAGE0 + 2 * j) & 0xFFF) << 12) | ((PAGE0 + 2 * j + 1) & 0xFFF) for j in range((npages + 1) // 2)]
    mem = [("y", PTAB, pt), ("x", S.GT, S.tables()),
           ("y", S.GV, [0] * S.GV_WORDS), ("y", NBLK, [nb, LOG])]
    gv = {S.G_S: start, S.G_N: n, S.G_REV: int(reverse), S.G_LOOP: int(loop), S.G_PTAB: PTAB,
          S.G_SPI: sp >> 24, S.G_SPF: sp & 0xFFFFFF, S.G_RTI: rt >> 24, S.G_RTF: rt & 0xFFFFFF, S.G_TRK: 0, S.G_OWN: 0}
    mem += [("y", S.GV + k, [v & 0xFFFFFF]) for k, v in gv.items()]
    for p in range(npages):
        chunk = x[p * 4096:(p + 1) * 4096]
        mem.append(("y", (PAGE0 + p) << 12, [v & 0xFFFFFF for v in chunk]))
    res, ran = rhdspemu.run(0, pc=DRIVER, stop=dl["stop"], mem=mem, segs=[("p", S.AT, words), ("p", DRIVER, dw)],
                            dumps=[("y", LOG, nb * 32)], maxins=400_000_000)
    got = [(v ^ 0x800000) - 0x800000 for v in res[("y", LOG)]]
    stopped = f"pc={dl['stop']:06x}" in ran
    bad = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), None)
    ins = int(ran.split("ins=")[1].split()[0]) if "ins=" in ran else 0
    check(f"{name}: {nb} blocks equal the model (locks {t.stats['locks']}, splices {t.stats['splices']}, kept {t.stats['kept']}; "
          f"{ins // max(nb, 1)} instructions a block)",
          stopped and bad is None, f"{ran.strip()} first difference at word {bad}: dsp {got[bad] if bad is not None else ''} "
          f"model {want[bad] if bad is not None else ''}" if not stopped or bad is not None else "")
    return got, want


def tone_hits(n, seed=1):
    """A low tone with drum-like hits every 0.3 s and noise: loud, quiet and page-crossing content."""
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        v = 0.3 * math.sin(2 * math.pi * 110 * i / 48000)
        k = i % 14400
        if k < 2400:
            v += 0.6 * math.exp(-k / 300) * (rnd.random() * 2 - 1)
        out.append(max(-0x800000, min(0x7FFFFF, int(v * 0x7FFFFF))))
    return out


def main():
    quick = "quick" in sys.argv
    x = tone_hits(48000 if quick else 96000)
    run_case("speed 1, Tune 0", x, 1.0, 1.0, blocks=120)
    run_case("speed 0.5", x, 0.5, 1.0, blocks=250 if quick else 400)
    run_case("speed 1.5", x, 1.5, 1.0)
    if not quick:
        run_case("speed 0.25", x, 0.25, 1.0, blocks=400)
        run_case("speed 4", x, 4.0, 1.0)
        run_case("speed 0.8, Tune +7", x, 0.8, 2 ** (7 / 12))
        run_case("speed 1.25, Tune -12", x, 1.25, 0.5)
        run_case("speed 0.7, a loop", x[:20000], 0.7, 1.0, loop=True, blocks=400)
        run_case("speed 0.6, reverse", x, 0.6, 1.0, reverse=True)
        run_case("speed 0.9, the region from 5,000", x, 0.9, 1.0, start=5000)
    print("FAILED: " + ", ".join(FAILS) if FAILS else "ALL PASS")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
