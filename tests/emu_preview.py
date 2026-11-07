"""pvloop in dsptool: core 1's sample preview, the stock's program against a build's.
    python tests/emu_preview.py BUILD [BUILD ...]      (BUILD: firmware/<build>)
A slot of 6000 words over two pages (X:$1000.., X:$2000..): one-shot forward and reverse, through the region's end and the slot's end,
and a stop: the build's player and gain = the stock's block for block (outputs and state).  Loop mode: the player's words run on
across the loop point with no gap or jump, forward and reverse; the gain's target stays full and no restart is counted.
dsptool keeps shared X and Y apart (the chip has one memory there): the player's copies land in X:$306F0, its zeros and the gain in Y.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rpasm  # noqa: E402
rpasm.use()
import pvloop as PV  # noqa: E402
import rhdsp1  # noqa: E402
import rhdspemu  # noqa: E402

FAILS = []
SLOT, LEN = 2, 6000
PT = 0x308C8 + SLOT * 0xBC                                # the slot's page table: page 0 -> 1 (X:$1000), page 1 -> 2 (X:$2000)
STATE = (PV.L, PV.S, PV.P, PV.ST, PV.RV, PV.LP, PV.G, PV.STP, PV.RS)
MARK = 0x5A5A5A


def s24(w):
    return w - (1 << 24) if w & 0x800000 else w


def sample(i):
    return (((i * 977) % 4001 - 2000) << 10) & 0xFFFFFF


DATA = [sample(i) for i in range(8192)]


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def base_mem():
    return [("x", 1, [32]), ("x", 0x1000, DATA), ("y", PV.TAB + 4 * SLOT, [0, LEN, LEN, 0]), ("y", PT, [0x001002])]


def block(segs, call, st, yin=None):
    """one call of the player (or the gain) with the state st {address: word} -> (X out, Y out, state)"""
    mem = base_mem() + [("y", a, [w & 0xFFFFFF]) for a, w in st.items()]
    mem += [("x", PV.OUT, [MARK] * 32), ("y", PV.OUT, yin if yin is not None else [MARK] * 32)]
    res, _ = rhdspemu.run(1, call=call, mem=mem, segs=segs, dumps=[("x", PV.OUT, 32), ("y", PV.OUT, 32)] + [("y", a, 1) for a in STATE])
    return res[("x", PV.OUT)], res[("y", PV.OUT)], {a: res[("y", a)][0] for a in STATE}


def start(st0, rv, loop, at=100, ln=5000):
    st = {a: 0 for a in STATE}
    st.update({PV.S: SLOT, PV.ST: at + (ln if rv else 0), PV.RV: 4 if rv else 0, PV.L: ln, PV.LP: 8 if loop else 0})
    st.update(st0)
    return st


def main():
    stock = rhdspemu.segments(1, 0)
    for build in sys.argv[1:]:
        d = HERE / "firmware" / build
        rep = json.loads((d / "manifest.json").read_text())["report"]
        img = bytearray((d / f"rhythmplus-{build.upper()}.bin").read_bytes())
        segs, _ = rhdsp1.parse(rhdsp1.sent(img, rep, "pitchmod"))
        pv, env = int(rep["pvloop"]["pv"], 16), int(rep["pvloop"]["env"], 16)
        o = rhdsp1.where(img, PV.CALL_PV)
        calls = [int.from_bytes(img[o + 3 * i:o + 3 * i + 3], "big") for i in (0, 1)]
        check(f"{build}: the main loop calls our player and gain (P:$123 / $124)", calls == [0x0D0000 | pv, 0x0D0000 | env], [hex(c) for c in calls])

        for name, st0, n in (("one-shot forward, through the region's end", start({PV.P: 4800}, False, False), 12),
                             ("one-shot forward, a short region", start({}, False, False, at=50, ln=300), 12),
                             ("one-shot forward, into the slot's end", start({PV.P: 5800}, False, False, at=0, ln=LEN), 10),
                             ("one-shot forward over the page's end", start({PV.P: 3980}, False, False, at=0, ln=LEN), 6),
                             ("one-shot reverse, through the region's start", start({PV.P: -4800}, True, False), 12),
                             ("one-shot reverse over the page's end", start({PV.P: -1000}, True, False, at=3000, ln=2000), 6),
                             ("a stop while playing", start({PV.P: 640, PV.STP: 4, PV.G: 0x7FFFFF}, False, False), 6),
                             ("nothing playing", {**start({}, False, False), PV.S: 0x7F0000}, 2)):
            a, b = dict(st0), dict(st0)
            bad = []
            for k in range(n):
                xa, ya, a2 = block(stock, 0x3C1, a)
                xb, yb, b2 = block(segs, pv, b)
                if (xa, ya, a2) != (xb, yb, b2):
                    bad.append((k, "player", {hex(x): (hex(a2[x]), hex(b2[x])) for x in a2 if a2[x] != b2[x]}, xa != xb, ya != yb))
                    break
                ga, ya2, a3 = block(stock, 0x469, a2, ya)
                gb, yb2, b3 = block(segs, env, b2, yb)
                if (ya2, a3) != (yb2, b3):
                    bad.append((k, "gain", {hex(x): (hex(a3[x]), hex(b3[x])) for x in a3 if a3[x] != b3[x]}, ya2 != yb2))
                    break
                a, b = a3, b3
            check(f"{build}: {name}: {n} blocks as the stock's (outputs, position, gain, slot)", not bad, bad)

        for rv in (False, True):
            ln, at = 1000, 3500                            # the loop crosses page 0's end
            st = start({}, rv, True, at=at, ln=ln)
            got = []
            for _ in range(70):                            # 2240 words: two passes and more
                x, yv, st = block(segs, pv, st)
                got += [s24(w) for w in x]
            idx = [(at + ln - (j % ln)) if rv else (at + j % ln) for j in range(len(got))]
            want = [s24(DATA[i]) >> 2 for i in idx]
            bad = [(j, got[j], want[j]) for j in range(len(got)) if got[j] != want[j]]
            check(f"{build}: loop {'reverse' if rv else 'forward'}: 70 blocks run on across the loop point, every word in order", not bad, bad[:3])
            check(f"{build}: loop {'reverse' if rv else 'forward'}: still playing (slot kept)", st[PV.S] == SLOT, hex(st[PV.S]))
        st = start({PV.P: 4900, PV.G: 0x400000}, False, True)
        _, yv, st2 = block(segs, env, st, [0x100000] * 32)
        check(f"{build}: loop, near the end: the gain rises toward full, no restart counted", st2[PV.G] > 0x400000 and st2[PV.RS] == 0 and st2[PV.P] == 4900,
              (hex(st2[PV.G]), st2[PV.RS], st2[PV.P]))
        _, ys, st3 = block(stock, 0x469, st, [0x100000] * 32)
        check(f"{build}: (the stock there: the gain falls, a restart counted: 8, one block gone)", st3[PV.G] < 0x400000 and st3[PV.RS] == 7, (hex(st3[PV.G]), st3[PV.RS]))
        a = b = start({PV.P: 640, PV.STP: 4, PV.G: 0x7FFFFF}, False, True)
        bad = []
        for k in range(6):
            _, ya, a = block(stock, 0x469, a, [0x200000] * 32)
            _, yb, b = block(segs, env, b, [0x200000] * 32)
            if (ya, a) != (yb, b):
                bad.append(k)
        check(f"{build}: loop, a stop: the stock's fade and end", not bad and a[PV.S] == 0x7F0000, (bad, hex(a[PV.S])))
    print("ALL PASS" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
