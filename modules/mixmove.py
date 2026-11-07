"""The mix page's pan and send movement in core 0 (MIT; Rhythm Plus, Circuit Rhythm 5706).

The stock (core 0, read in its program): each block P:$2D9 smooths track t's left / right gains into X:$9D + 4 t / + 1 (a state: not
ours to write); P:$1202 copies the delay send X:$307DB + $20 t << 14 into X:$A0 + 4 t, P:$1231 the reverb send X:$307DA + $20 t << 14
into X:$9F + 4 t (a full send = 127 << 14); P:$11E3, $1202 and $1231 then ramp L, R, L x delay, R x delay, L x reverb, R x reverb from
r2 = $9D, each loop starting with the one-word `move #$9d,r2`.
Ours: that word -> a short jsr to a hook in the unused vectors P:$50..$FF (nop in the stock), which fills a copy Q (X:$1400, stride 4)
and returns r2 = Q:
  * LR (P:$11E3): m = PD x M; m >= 0: L x (1 - m), R; m < 0: L, R x (1 + m);
  * DLY (P:$120C), REV (P:$123B): k = D x (1 + M) / 2; k >= 0: s + k x (FULL - s); k < 0: s + k x s (s the stock's send);
M = the move LFO for the track at shared Y:SH + t (-1..1); PD, RD, DD = the depths the ARM writes to core 0's Y:YD + t, + 8, + 16
(0 when the move's rate is off).  vol: LR takes L and R x (1 - V) first, V = c0fx's volume cut at core 0's Y:VX + t (0 = full level). Core 0's X / Y:$1400.. are zero in every dump, with no absolute operand in the stock.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import core0  # noqa: E402

AT = 0x50                                                 # the hooks, in the unused vectors past the SHI's ($40-$4F: on, IPRP = 9)
Q, YD = 0x1400, 0x1420                                    # X: the copy of $9D..$BC; Y: pan, reverb, delay depth + t
SH = 0x37320                                              # shared Y: M + t (core 1 writes), the move LFO's phase + 8 + t
O_PD, O_RD, O_DD = 0, 8, 16
FULL = 127 << 14                                          # the stock's full send in X:$9F / $A0
SRC, OLD = 0x9D, 0x329D00                                 # move #$9d,r2
SITES = {0x11E3: "lr", 0x120C: "dly", 0x123B: "rev"}
SEND = {"dly": (3, O_DD), "rev": (2, O_RD)}              # the send's word in the track's four, its depth


def vx():
    import fshape as FS
    return FS.VB + FS.O_VX


def items(vol=False):
    m = ["move y:(r5)+,x0", "move y:(r4)+,x1", "mpy x1,x0,a", "move a,x0"]            # x0 = m
    lr = ["move x:(r1)+,y0", "move x:(r1)+,y1"]                                        # L, R
    cut = ["move y:(r3)+,x1", "mpy x1,y0,a", "move y0,b", "sub a,b", "move b,y0",
           "mpy y1,x1,a", "move y1,b", "sub a,b", "move b,y1"]                         # L, R x (1 - V)
    it = [("label", "lr"),
          f"move #>${SRC:x},r1", f"move #>${Q:x},r0", f"move #>${SH:x},r5", f"move #>${YD + O_PD:x},r4",
          *([f"move #>${vx():x},r3"] if vol else []),
          "do #8,${lr_e:x}",
          *(lr + cut + m if vol else m + lr),
          "tst a", ("jcc", "lt", "lr_n"),
          "mpy y0,x0,b", "move y0,a", "sub b,a", "move a,x:(r0)+", "move y1,x:(r0)+", ("jmp", "lr_c"),
          ("label", "lr_n"),
          "mpy x0,y1,b", "move y1,a", "add b,a", "move y0,x:(r0)+", "move a,x:(r0)+",
          ("label", "lr_c"),
          "move (r1)+", "move (r1)+", "move (r0)+", "move (r0)+",
          ("label", "lr_e"),
          f"move #>${Q:x},r2", "rts"]
    for n, (o, od) in SEND.items():
        it += [("label", n),
               f"move #>${SRC:x},r1", f"move #>${Q + o:x},r0", f"move #>${SH:x},r5", f"move #>${YD + od:x},r4",
               "do #8,${" + n + "_e:x}",
               "move y:(r5)+,a", "asr a", "add #>$400000,a", "move a,x0",               # x0 = (1 + M) / 2
               "move y:(r4)+,x1", "mpy x1,x0,a", "move a,x0",                           # x0 = k
               f"move x:(r1+{o}),y0",                                                   # the stock's send
               "tst a", ("jcc", "lt", f"{n}_n"),
               f"move #>${FULL:x},a", "sub y0,a", "move a,x1", "mpy x1,x0,a", "add y0,a", ("jmp", f"{n}_w"),
               ("label", f"{n}_n"),
               "mpy y0,x0,a", "add y0,a",
               ("label", f"{n}_w"),
               "move a,x:(r0)",
               "move (r0)+", "move (r0)+", "move (r0)+", "move (r0)+", "move (r1)+", "move (r1)+", "move (r1)+", "move (r1)+",
               ("label", f"{n}_e"),
               f"move #>${Q:x},r2", "rts"]
    return it


def code(vol=False):
    words, labels = core0.asm_at(items(vol), AT)
    assert AT + len(words) <= 0x100, ("the hooks past the vectors", hex(AT + len(words)))
    return words, labels


def install(img, report, base_addr=None, vol=False):
    words, labels = code(vol)
    for i, w in enumerate(words):
        core0.patch_p0(img, AT + i, 0, w)
    for at, n in SITES.items():
        core0.patch_p0(img, at, OLD, 0x0D0000 | labels[n])
    report["mixmove"] = dict(at=hex(AT), words=len(words), q=hex(Q), yd=hex(YD), sh=hex(SH), full=hex(FULL), **({"vx": hex(vx())} if vol else {}),
                             hooks={n: hex(labels[n]) for n in SITES.values()}, sites={hex(a): n for a, n in SITES.items()})
    return {}, b""
