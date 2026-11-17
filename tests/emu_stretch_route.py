"""Core 1's route for time stretch (granular_inplace_candidate, packed) in dsptool: the native reader, the crossfade, the export.

    python tests/emu_stretch_route.py

A stub at P:$1E5 (the native reader) counts its calls and writes known words into the buffer; one at P:$25E (the refill after the
fade's test) counts its calls; the track's bank holds known stretch words. Word 3 = 0 or 1 (Granular): as before, the gain cleared.
2 (stretch on): the native reader in Loop play mode and while the gain is not full, the stretch words crossfaded in over
XFADE_BLOCKS blocks. 3 (fading out): the native reader, the stretch words crossfaded out, then the native words alone. 4 (draining):
the native reader, the stretch words full. No stretch words in a block: the native words stay when the reader ran. The snapshot's export gives each track's native reader position.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["RH_STRETCH"] = "1"

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / d) for d in ("modules", "tools", "tests", "remix/tools")]
import core0  # noqa: E402
import granular_inplace_candidate as I  # noqa: E402
import granular_snapshot_candidate as SN  # noqa: E402
import rhdspemu  # noqa: E402

AT, DRIVER, STOP = 0xC00, 0xB00, 0xBF0
COUNT, NWORDS = 0x1F00, 0x1E00  # Y: reader calls, refill calls; the native words the reader stub writes
T, EPOCH, FRAME = 3, 7, 0x55
ONE = 0x7FFFFF
NATIVE = [0x100000 + 0x1000 * i for i in range(32)]
STRETCH = [0xF00000 - 0x800 * i for i in range(32)]
FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def sx(v):
    return (v ^ 0x800000) - 0x800000


def code():
    I.LOOP_NATIVE, old = True, I.AT
    try:
        I.AT = AT
        segs, meta = I.code()
    finally:
        I.AT, I.LOOP_NATIVE = old, False
    return segs, meta["labels"]


def stubs():
    bump = lambda k: [f"move y:>${COUNT + k:x},a", "add #>$1,a", f"move a1,y:>${COUNT + k:x}"]
    reader, _ = core0.asm_at([*bump(0), f"move #>${I.BUFFER:x},r1", f"move #>${NWORDS:x},r2", "do #$20,${rd_e:x}",
                              "move y:(r2)+,a", "move a,x:(r1)+", ("label", "rd_e"), "rts"], 0x1E5)
    refill, _ = core0.asm_at([*bump(1), "rts"], 0x25E)
    assert 0x1E5 + len(reader) <= 0x25E
    return [("p", 0x1E5, reader), ("p", 0x25E, refill)]


def run(word3, mode, xg, key=True, audio=True):
    """-> (reader calls, refill calls), the buffer's 32 words, the gain after, the bank after"""
    segs, labels = code()
    drv, _ = core0.asm_at([f"move #>${T:x},a", "move a1,y:>$1405", "move #>$44,r0",
                           ("jsr", labels["source"]), f"move #>${T:x},a", "move a1,y:>$1405", f"move #>${0x44 + 16 * T:x},r0",
                           ("jsr", labels["fade"]), ("jmp", STOP)], DRIVER)
    bank = I.BANK + 64 * T
    mem = [("y", I.CONTROL + 4 * T, [I.KEY if key else 0, EPOCH, FRAME, word3]), ("y", I.PLAY_MODE + 32 * T, [mode]),
           ("y", COUNT, [0, 0]), ("y", NWORDS, NATIVE), ("y", I.XG + T, [xg]), ("y", I.NRUN + T, [0x5A5A5A]),
           ("y", SN.SNAPSHOT + 8 * T, [I.AUDIO_KEY if audio else 0x674732, EPOCH, FRAME]), ("y", bank, STRETCH),
           ("x", I.BUFFER, [0x111111] * 32)]
    res, ran = rhdspemu.run(1, pc=DRIVER, stop=STOP, mem=mem, maxins=200_000, segs=list(segs) + stubs() + [("p", DRIVER, drv)],
                            dumps=[("y", COUNT, 2), ("x", I.BUFFER, 32), ("y", I.XG + T, 1), ("y", bank, 32)])
    assert f"pc={STOP:06x}" in ran, ran
    return res[("y", COUNT)], [sx(v) for v in res[("x", I.BUFFER)]], res[("y", I.XG + T)][0], res[("y", bank)]


def mixed(g0, step):
    """the DSP's crossfade: n + (e - n) x g >> 23, g from g0 by step a sample"""
    out = []
    for i, (n, e) in enumerate(zip(NATIVE, STRETCH)):
        d = max(-0x800000, min(0x7FFFFF, sx(e) - sx(n)))
        out.append(sx(n) + ((d * (g0 + step * i)) >> 23))
    return out


def export():
    keep = SN.AT, SN.LIMIT, SN.EXPORT_POSITION, SN.SNAPSHOT, SN.SERIAL, SN.SAVE
    try:
        SN.AT, SN.LIMIT, SN.EXPORT_POSITION, SN.SNAPSHOT, SN.SERIAL, SN.SAVE = 0xD00, 0x1000, True, 0x37420, 0x1F90, 0x1F80
        words, labels = SN.code()
        pos = SN.SNAPSHOT + SN.POSITION_OFFSET
    finally:
        SN.AT, SN.LIMIT, SN.EXPORT_POSITION, SN.SNAPSHOT, SN.SERIAL, SN.SAVE = keep
    drv, _ = core0.asm_at([("jsr", labels["export"]), ("jmp", STOP)], DRIVER)
    mem = [("x", 0x40 + 16 * t + 3, [0x10000 + 0x111 * t]) for t in range(8)] + [("x", 0x40 + 16 * 2 + 4, [0x300000])]
    res, ran = rhdspemu.run(1, pc=DRIVER, stop=STOP, mem=mem, maxins=200_000, segs=[("p", 0xD00, words), ("p", DRIVER, drv)],
                            dumps=[("y", pos, 8)])
    assert f"pc={STOP:06x}" in ran, ran
    return res[("y", pos)]


def main():
    got = export()
    check("the export: every track's native reader position, active or not", got == [0x10000 + 0x111 * t for t in range(8)],
          [hex(v) for v in got])
    stretch = [sx(v) for v in STRETCH]
    native = [sx(v) for v in NATIVE]
    step = I.XSTEP
    cases = (  # name, word 3, play mode, gain before, calls, the buffer, the gain after
        ("word 3 = 0 (Granular), Loop: no native reader, the words copied, the gain cleared", 0, 2, ONE, [0, 0], stretch, 0),
        ("word 3 = 1 (Granular), One Shot: the native reader, the words copied, the gain cleared", 1, 0, ONE, [1, 1], stretch, 0),
        ("word 3 = 2, Loop, full: the native reader runs on, the stretch words copied", 2, 2, ONE, [1, 1], stretch, ONE),
        ("word 3 = 2, One Shot, full: no native reader, the stretch words copied", 2, 0, ONE, [0, 0], stretch, ONE),
        ("word 3 = 2, Gated, full: no native reader", 2, 1, ONE, [0, 0], stretch, ONE),
        ("word 3 = 2, One Shot, gain 0: the native reader, the first block of the crossfade in", 2, 0, 0, [1, 1], mixed(0, step), 32 * step),
        ("word 3 = 2, the gain at 7/8: the last block in, then full", 2, 0, 7 * 32 * step, [1, 1], mixed(7 * 32 * step, step), ONE),
        ("word 3 = 3, full: the native reader, the first block of the crossfade out", 3, 0, ONE, [1, 1], mixed(ONE, -step), ONE - 32 * step),
        ("word 3 = 3, the gain at 1/8: the last block out, then 0", 3, 2, 32 * step, [1, 1], mixed(32 * step, -step), 0),
        ("word 3 = 3, gain 0: the native words alone", 3, 0, 0, [1, 1], native, 0),
        ("word 3 = 4 (draining), One Shot, full: the native reader runs unheard, the stretch words copied", 4, 0, ONE, [1, 1], stretch, ONE),
        ("word 3 = 4, Gated, full: the native reader runs unheard", 4, 1, ONE, [1, 1], stretch, ONE),
        ("word 3 = 4, Loop, full: the native reader runs unheard", 4, 2, ONE, [1, 1], stretch, ONE))
    for name, w3, mode, g, calls, buf, after in cases:
        c, b, xg, _ = run(w3, mode, g)
        check(name, c == calls and b == buf and xg == after, (c, hex(xg), [hex(v & 0xFFFFFF) for v in b[:3]]))
    c, b, xg, bank = run(2, 0, 0, audio=False)
    check("no stretch words while fading in: the native words stay, the bank cleared, the gain kept",
          c == [1, 1] and b == native and xg == 0 and bank == [0] * 32, (c, xg, b[:2]))
    c, b, xg, _ = run(4, 0, ONE, audio=False)
    check("draining, no stretch words: the native words stay", c == [1, 1] and b == native and xg == ONE, (c, hex(xg), b[:2]))
    c, b, xg, _ = run(1, 0, 0, audio=False)
    check("no grain words on a Granular track: silence, as before", c == [1, 1] and b == [0] * 32, (c, b[:2]))
    c, b, xg, _ = run(2, 0, ONE, key=False)
    check("no route key: the native reader and its refill, the gain cleared", c == [1, 1] and xg == 0 and b == native, (c, xg))
    g = 0
    for _ in range(I.XFADE_BLOCKS):
        _, _, g, _ = run(2, 0, g)
    check(f"{I.XFADE_BLOCKS} blocks fade in to full", g == ONE, hex(g))
    I.LOOP_NATIVE = False
    words = I.code()[1]["source_words"]
    check("the standalone layout is unchanged (105 words)", words == 105, words)
    print("FAILED: " + ", ".join(FAILS) if FAILS else "ALL PASS")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
