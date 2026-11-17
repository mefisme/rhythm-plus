"""8 stretch tracks at once: st_entry (modules/stretch_dsp.py) in dsptool, timed block by block.

    python tests/emu_stretch_load.py

Every track stretches its own region of one sample, each at its own speed, Tune and play mode, so
the searches, hits and fades fall on different blocks. Checks: each track's words equal the block
model's, run track by track in one model (one search at a time across the tracks), and st_entry's
worst block stays under LIMIT instructions. Prints the worst and the mean block.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / d) for d in ("modules", "tools", "tests", "remix/tools")]
import core0  # noqa: E402
import granular0 as G  # noqa: E402
import granular_route_candidate as R  # noqa: E402
import rhdsp  # noqa: E402
import stretch_block as M  # noqa: E402
import stretch_dsp as S  # noqa: E402
from emu_stretch_dsp import PAGE0, tone_hits  # noqa: E402
from emu_stretch_entry import CONTROL, DRIVER, PARAMS, POSITIONS, PTAB0, SLOT, SNAPSHOT, STATE, entry  # noqa: E402

BLOCKS = 400
LOG, V_N = 0x10000, 0x1700
LEN = 32000
# speed, Tune (rate), Loop
TRACKS = ((0.75, 1.0, True), (0.5, 1.0, True), (1.3, 1.0, True), (0.25, 1.0, False),
          (2.0, 0.8, True), (4.0, 1.0, True), (0.6, 1.25, True), (1.1, 0.67, False))
# core 0 free time a block (notes/stretch-engine.md): ~30,000 cycles with 3 heavy Granular tracks, ~60,000 with none
LIMIT = 30_000                  # a guard: the measured worst is about 28,400 (the search loop in A0220's proven form)
FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def start(t):
    return 500 + 1000 * t


def dsptool(segs, mem, lines, dumps):
    """-> the RAN lines, {(space, addr): words}"""
    d = tempfile.mkdtemp()
    try:
        script = []
        for k, (addr, ws) in enumerate(segs):
            fn = os.path.join(d, f"seg{k}.bin")
            Path(fn).write_bytes(b"".join(w.to_bytes(3, "big") for w in ws))
            script.append(f"LOADP {fn} {addr:x}")
        for sp, addr, ws in mem:
            for i in range(0, len(ws), 64):
                script.append("%s %x %s" % (sp.upper(), addr + i, " ".join("%06x" % (x & 0xFFFFFF) for x in ws[i:i + 64])))
        script += lines + [f"DUMP{sp.upper()} {addr:x} {n}" for sp, addr, n in dumps]
        sc = os.path.join(d, "s.txt")
        Path(sc).write_text("\n".join(script) + "\n")
        out = subprocess.run([rhdsp.TOOL, "run", sc], capture_output=True, text=True).stdout
    finally:
        shutil.rmtree(d, ignore_errors=True)
    ran, res = [], {}
    for line in out.splitlines():
        if line.startswith("RAN"):
            ran.append(line)
        elif line[:1] in "XYP" and ":" in line:
            k, v = line.split(":", 1)
            sp, a = k.split()
            res[(sp.lower(), int(a, 16))] = [int(x, 16) for x in v.split()]
    return ran, res


def run():
    """-> each block's st_entry instructions, each track's blocks of 32 words"""
    words, labels = S.code(entry=entry())
    bump = [s for t in range(8) for s in (f"move y:>${CONTROL + 4 * t + 2:x},a", "add #>$1,a", f"move a1,y:>${CONTROL + 4 * t + 2:x}",
                                          f"move a1,y:>${SNAPSHOT + 8 * t + 2:x}", f"move #>${R.KEY:x},a",
                                          f"move a1,y:>${SNAPSHOT + 8 * t:x}")]
    drv = [("label", "loop"), f"move y:>${V_N:x},a", "tst a", ("jcc", "le", "done"), *bump,
           ("label", "pre"), ("jsr", labels["st_entry"]), ("label", "post"),
           f"move y:>${V_N + 1:x},r1", f"move #>${G.TRK_BUF:x},r0", "do #$8,${cpt:x}", "do #$20,${cpw:x}",
           "move y:(r0)+,x0", "move x0,y:(r1)+", ("label", "cpw"), "move #>$20,n0", "nop", "move (r0)+n0", ("label", "cpt"),
           f"move r1,y:>${V_N + 1:x}", f"move y:>${V_N:x},a", "sub #>$1,a", f"move a1,y:>${V_N:x}", ("jmp", "loop"),
           ("label", "done"), "nop", ("label", "stop"), "nop"]
    dw, dl = core0.asm_at(drv, DRIVER)
    x = tone_hits(start(7) + LEN + 500)
    npages = (len(x) + 4095) // 4096
    pt = [(((PAGE0 + 2 * j) & 0xFFF) << 12) | ((PAGE0 + 2 * j + 1) & 0xFFF) for j in range((npages + 1) // 2)]
    mem = [("y", PTAB0 + G.PSTRIDE * SLOT, pt), ("x", G.SMP + 4 * SLOT, [0, len(x)]),
           ("y", S.GV, [0x5A5A5A] * S.GV_WORDS), ("y", V_N, [BLOCKS, LOG])]
    for p in range(npages):
        mem.append(("y", (PAGE0 + p) << 12, [v & 0xFFFFFF for v in x[p * 4096:(p + 1) * 4096]]))
    params = []
    for t, (speed, rate, loop) in enumerate(TRACKS):
        sp, rt = round(speed * (1 << 24)) & ~0xF, round(rate * (1 << 24))
        hostp = [0] * 16
        hostp[S.H_SPD], hostp[15] = sp >> 4, S.HOST_KEY
        mem += [("x", STATE + 256 * t, hostp), ("y", CONTROL + 4 * t, [R.KEY, 7, 0, 0]),
                ("y", SNAPSHOT + 8 * t, [R.KEY, 7, 0, SLOT, start(t), start(t) + LEN, rt >> 9, 1]),
                ("y", PARAMS + 32 * t + 1, [2 if loop else 0]), ("y", POSITIONS + t, [start(t) + S.READER_LEAD])]
        params.append((sp, (rt >> 9) << 9, loop))
    lines = [f"PC {DRIVER:x}", "MAX 400000000"]
    for _ in range(BLOCKS):
        lines += [f"STOP {dl['pre']:x}", "RUN", f"STOP {dl['post']:x}", "RUN"]
    lines += [f"STOP {dl['stop']:x}", "RUN"]
    ran, res = dsptool([(S.AT, words), (DRIVER, dw)], mem, lines, [("y", LOG, BLOCKS * 256)])
    assert f"pc={dl['stop']:06x}" in ran[-1], ran[-1]
    cost = [int(r.split("ins=")[1].split()[0]) for r in ran[1:2 * BLOCKS:2]]
    log = [(v ^ 0x800000) - 0x800000 for v in res[("y", LOG)]]
    out = [[log[b * 256 + 32 * t:b * 256 + 32 * t + 32] for b in range(BLOCKS)] for t in range(8)]
    return cost, out, x, params


def model(x, params):
    M.Search.owner = None
    tracks = [M.Track(list(x[start(t):start(t) + LEN]), sp, rt, loop) for t, (sp, rt, loop) in enumerate(params)]
    out = [[] for _ in tracks]
    for _ in range(BLOCKS):
        for t, tr in enumerate(tracks):
            out[t].append(tr.block())
    return out, tracks


def main():
    cost, out, x, params = run()
    want, tracks = model(x, params)
    for t in range(8):
        speed, rate, loop = TRACKS[t]
        st = tracks[t].stats
        check(f"track {t + 1} (speed {speed}, Tune {rate}, {'Loop' if loop else 'One Shot'}) equals the model "
              f"(splices {st['splices']}, kept {st['kept']}, locks {st['locks']}, delayed {st.get('delayed', 0)})", out[t] == want[t],
              f"first block that differs {next((i for i, (a, b) in enumerate(zip(out[t], want[t])) if a != b), None)}")
    worst = max(cost)
    srt = sorted(cost)
    print(f"st_entry, 8 tracks: worst block {worst} instructions (block {cost.index(worst)}), mean {sum(cost) // len(cost)}, "
          f"median {srt[len(srt) // 2]}, 95% {srt[len(srt) * 95 // 100]}")
    check(f"the worst block is under {LIMIT} instructions", worst < LIMIT, worst)
    print("FAILED: " + ", ".join(FAILS) if FAILS else "ALL PASS")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
