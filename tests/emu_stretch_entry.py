"""st_entry (modules/stretch_dsp.py) in dsptool: the stretch engine behind Granular's route, every track.

    python tests/emu_stretch_entry.py

A driver plays core 1's part each block (a new frame in the control and snapshot words, the snapshot
ready) and calls st_entry. Checks: a stretch track's buffer holds the block model's words and its
snapshot turns to audio; a track without the host key and a Granular track are left
alone; a new note serial restarts the track; the search scratch of a track that stops is released;
a Loop play mode loops; a length gives the speed sample / length (with TGT_PART: region / length); after a gap
of more than RESUME_GAP blocks the track resumes where core 1's native reader is, after a shorter one it runs on.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / d) for d in ("modules", "tools", "tests", "remix/tools")]
import core0  # noqa: E402
import granular0 as G  # noqa: E402
import granular_route_candidate as R  # noqa: E402
import granular_inplace_candidate as I  # noqa: E402
import rhdspemu  # noqa: E402
import stretch_block as M  # noqa: E402
import stretch_dsp as S  # noqa: E402
from emu_stretch_dsp import PAGE0, tone_hits  # noqa: E402

CONTROL, SNAPSHOT, STATE, PARAMS = 0x37400, 0x37420, 0x2400, 0x307c8
POSITIONS = SNAPSHOT + 0x40
PTAB0 = 0x1800                  # Y: the page tables, stride G.PSTRIDE (emulated)
LOG = 0x10000
DRIVER = 0x3c00
V_N, V_LOGP, V_STOP, V_SERIAL, V_GAP = 0x1700, 0x1701, 0x1702, 0x1703, 0x1704
TRK, OTHER, GRAN = 2, 5, 6
SLOT, LEN = 9, 40000
FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def entry():
    return dict(control=CONTROL, snapshot=SNAPSHOT, state=STATE, smp=G.SMP, pages=PTAB0, pstride=G.PSTRIDE,
                trk_buf=G.TRK_BUF, route_key=R.KEY, audio_key=I.AUDIO_KEY, params=PARAMS, positions=POSITIONS)


def run(blocks, speed=0.75, rate=1.0, serial_at=None, stop_at=None, mode=0, target=0, gap=None):
    """gap: (block, frames, position): at that block the frame moves on by frames and the native reader is at position"""
    words, labels = S.code(entry=entry())
    c, s = CONTROL + 4 * TRK, SNAPSHOT + 8 * TRK
    buf = G.TRK_BUF + 64 * TRK
    # each block: frame + 1 in control and snapshot, the snapshot ready, then st_entry; the track's 32 words to the log
    gb, gk, gp = gap or (0, 1, 0)
    drv = [("label", "loop"), f"move y:>${V_N:x},a", "tst a", ("jcc", "le", "done"),
           f"move y:>${V_GAP:x},x0", "cmp x0,a", "move #>$1,x1", ("jcc", "ne", "step"),
           f"move #>${gk:x},x1", f"move #>${gp:x},a", f"move a1,y:>${POSITIONS + TRK:x}",
           ("label", "step"), f"move y:>${c + 2:x},a", "add x1,a", f"move a1,y:>${c + 2:x}", f"move a1,y:>${s + 2:x}",
           f"move #>${R.KEY:x},a", f"move a1,y:>${s:x}",
           f"move y:>${V_STOP:x},a", f"move y:>${V_N:x},x0", "cmp x0,a", ("jcc", "ne", "keep"), "clr a", f"move a1,x:>${STATE + 256 * TRK + 15:x}",
           ("label", "keep"), f"move y:>${V_SERIAL:x},a", f"move y:>${V_N:x},x0", "cmp x0,a", ("jcc", "ne", "same"),
           f"move y:>${s + 7:x},a", "add #>$1,a", f"move a1,y:>${s + 7:x}",
           ("label", "same"), ("jsr", labels["st_entry"]),
           f"move y:>${V_LOGP:x},r1", f"move #>${buf:x},r0", "do #$20,${cp:x}", "move y:(r0)+,x0", "move x0,y:(r1)+", ("label", "cp"),
           f"move y:>${s:x},x0", "move x0,y:(r1)+",
           f"move r1,y:>${V_LOGP:x}", f"move y:>${V_N:x},a", "sub #>$1,a", f"move a1,y:>${V_N:x}", ("jmp", "loop"),
           ("label", "done"), "nop", ("label", "stop"), "nop"]
    dw, dl = core0.asm_at(drv, DRIVER)
    x = tone_hits(LEN + 1000)
    region = x[500:500 + LEN]
    sp, rt = round(speed * (1 << 24)), round(rate * (1 << 24))
    npages = (len(x) + 4095) // 4096
    pt = [(((PAGE0 + 2 * j) & 0xFFF) << 12) | ((PAGE0 + 2 * j + 1) & 0xFFF) for j in range((npages + 1) // 2)]
    hostp = [0] * 16
    sp &= ~0xF                                                                  # the host word is Q20
    hostp[S.H_SPD], hostp[S.H_TGT], hostp[15] = sp >> 4, target, S.HOST_KEY
    mem = [("y", PTAB0 + G.PSTRIDE * SLOT, pt), ("x", G.SMP + 4 * SLOT, [0, len(x)]),
           ("x", STATE + 256 * TRK, hostp), ("x", STATE + 256 * GRAN + 15, [G.KEY]),
           ("y", CONTROL + 4 * TRK, [R.KEY, 7, 0, 0]), ("y", CONTROL + 4 * OTHER, [R.KEY, 7, 0, 0]),
           ("y", SNAPSHOT + 8 * TRK, [R.KEY, 7, 0, SLOT, 500, 500 + LEN, rt >> 9, 1]),
           ("y", SNAPSHOT + 8 * OTHER, [R.KEY, 7, 0, SLOT, 500, 500 + LEN, rt >> 9, 1]),
           ("y", G.TRK_BUF, [0x123456] * 512), ("y", PARAMS + 32 * TRK + 1, [mode]),
           ("y", POSITIONS + TRK, [500 + S.READER_LEAD]),                          # a new note's reader
           ("y", S.GV, [0x5A5A5A] * S.GV_WORDS),                                     # power-up garbage
           ("y", V_N, [blocks, LOG, blocks - stop_at if stop_at else -1, blocks - serial_at if serial_at else -1,
                       blocks - gb if gap else -1])]
    for p in range(npages):
        mem.append(("y", (PAGE0 + p) << 12, [v & 0xFFFFFF for v in x[p * 4096:(p + 1) * 4096]]))
    res, ran = rhdspemu.run(0, pc=DRIVER, stop=dl["stop"], mem=mem, segs=[("p", S.AT, words), ("p", DRIVER, dw)],
                            dumps=[("y", LOG, blocks * 33), ("y", G.TRK_BUF + 64 * OTHER, 64), ("y", G.TRK_BUF + 64 * GRAN, 64),
                                   ("y", SNAPSHOT + 8 * OTHER, 1), ("y", S.GV + S.G_OWN, 1)], maxins=400_000_000)
    assert f"pc={dl['stop']:06x}" in ran, ran
    log = res[("y", LOG)]
    out = [[(v ^ 0x800000) - 0x800000 for v in log[b * 33:b * 33 + 32]] for b in range(blocks)]
    tags = [log[b * 33 + 32] for b in range(blocks)]
    return out, tags, res, region, sp, rt


def target_speed(n, target):
    """the DSP's speed for a length: 8 q, q = N / 4T with 23 fraction bits"""
    d = 4 * target
    for _ in range(2):
        if d > 0x7FFFFF:
            d, n = d >> 1, n >> 1
    if n >= d:
        return S.RATE_MAX
    return max((n << 23) // d, S.SPEED_MIN >> 3) << 3


def resume_at(position, n, loop):
    """the DSP's start index for a resume (forward, the region at 500)"""
    d = position - 500 - S.READER_LEAD
    if loop:
        d = d + n if d < 0 else d
        d = d - n if d >= n else d
    d = min(max(d, 0), n)
    return d if d >= S.RESUME_MIN else 0


def model(region, sp, rt, blocks, serial_at=None, loop=False, resume=None):
    """resume: (block, index): the track restarts there at that index"""
    M.Search.owner = None
    t = M.Track(list(region), sp, rt, loop)
    out = []
    for b in range(blocks):
        if serial_at is not None and b == serial_at:
            t.restart()
        if resume is not None and b == resume[0]:
            t.restart(resume[1])
        out.append(t.block())
    return out


def main():
    n = 160
    out, tags, res, region, sp, rt = run(n)
    want = model(region, sp, rt, n)
    check("a stretch track's buffer holds the block model's words, every block", out == want,
          f"first block that differs {next((i for i, (a, b) in enumerate(zip(out, want)) if a != b), None)}")
    check("its snapshot turns to audio each block", all(t == I.AUDIO_KEY for t in tags), str([hex(t) for t in tags[:4]]))
    check("a track without the host key keeps its buffer and snapshot",
          res[("y", G.TRK_BUF + 64 * OTHER)] == [0x123456] * 64 and res[("y", SNAPSHOT + 8 * OTHER)] == [R.KEY])
    check("a Granular track's buffer is not touched", res[("y", G.TRK_BUF + 64 * GRAN)] == [0x123456] * 64)
    out2, tags2, _, region, sp, rt = run(120, serial_at=70)
    want2 = model(region, sp, rt, 120, serial_at=70)
    check("a new note serial restarts the track", out2 == want2,
          f"first block that differs {next((i for i, (a, b) in enumerate(zip(out2, want2)) if a != b), None)}")
    # the track stops (its host key goes) while it holds the scratch: released at the end of that block
    out3, tags3, res3, *_ = run(60, stop_at=44)
    check("a stopped track's search scratch is released", res3[("y", S.GV + S.G_OWN)] == [0], str(res3[("y", S.GV + S.G_OWN)]))
    check("a stopped track publishes nothing", all(t == R.KEY for t in tags3[44:]) and all(t == I.AUDIO_KEY for t in tags3[:44]),
          str([hex(t) for t in tags3[42:47]]))
    for name, gap, loop in (("a gap of 20 blocks: the track resumes at the native reader's place", (60, 21, 500 + 20000), False),
                            ("a gap of 5 blocks: the track runs on", (60, 6, 500 + 20000), False),
                            ("a gap in a loop, the reader past the end: it resumes wrapped", (60, 21, 500 + LEN + 3000), True),
                            ("a gap, the reader near the start: it starts at 0 (a new note)", (60, 21, 500 + 500), False)):
        outg, *_, region, sp, rt = run(120, gap=gap, mode=2 if loop else 0)
        res_at = (gap[0], resume_at(gap[2], LEN, loop)) if gap[1] > S.RESUME_GAP else None
        wantg = model(region, sp, rt, 120, loop=loop, resume=res_at)
        check(f"{name} ({res_at[1] if res_at else 'no restart'})", outg == wantg,
              f"first block that differs {next((i for i, (a, b) in enumerate(zip(outg, wantg)) if a != b), None)}")
    out4, _, _, region, sp, rt = run(160, speed=1.3, mode=2)
    want4 = model(region, sp, rt, 160, loop=True)
    check("a Loop play mode loops the region", out4 == want4,
          f"first block that differs {next((i for i, (a, b) in enumerate(zip(out4, want4)) if a != b), None)}")
    out6, _, _, region, sp, rt = run(400, speed=4.0, mode=2)
    want6 = model(region, sp, rt, 400, loop=True)
    check("a Loop at speed 4 passes its loop point", out6 == want6,
          f"first block that differs {next((i for i, (a, b) in enumerate(zip(out6, want6)) if a != b), None)}")
    for target, part in ((53333, True), (4_000_000, True), (9000, True), (55000, False), (3_000_000, False)):
        out5, _, _, region, _, rt = run(120, target=target | (S.TGT_PART if part else 0))
        sp5 = target_speed(LEN if part else LEN + 1000, target)
        want5 = model(region, sp5, rt, 120)
        check(f"a length of {target} samples, the {'region' if part else 'whole sample'}: the speed {sp5 / (1 << 24):.4f}", out5 == want5,
              f"first block that differs {next((i for i, (a, b) in enumerate(zip(out5, want5)) if a != b), None)}")
    print("FAILED: " + ", ".join(FAILS) if FAILS else "ALL PASS")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
