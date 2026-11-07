"""The sample preview's loop without a dip (MIT; Rhythm Plus, Circuit Rhythm 5706): core 1's preview player, rewritten in place.

The stock (core 1, read in the program): the preview is its own player, not a track voice.  The ARM's command Y:$372FA (P:$81C: bit 1
start, bit 2 reverse, bit 3 loop, slot << 16) sets shared Y: S = $371EA (the slot; $7F0000 = none), P = $371EB (the position from the
start, down from 0 in reverse), ST = $371EC (the start; start + length in reverse), RV = $371ED, L = $371D9 (the length), LP = $371EE.
Each block P:$3C1 (forward; P:$374 reverse) copies 32 words a block through COPY P:$422 (the slot's pages, x 1/4) to OUT $306F0, then
P:$469 ramps the gain G = $371EF on them.  Loop mode is the gain's: 256 words before L the target goes to 0, and 8 blocks later
(RS = $371F1) P = 0: a dip and a jump at every pass.
Ours, over P:$374..$421 and P:$469..$4CC (the two entries P:$3C1 / P:$469 called once a block from P:$123 / P:$124; COPY and its zero
fill P:$422..$468 kept): one-shot and reverse as the stock's, word for word in effect; loop mode wraps P at L inside the block (forward
and reverse, page splits as the stock's) and keeps the gain's target full while it plays.  The stop command's fade (STP = $371F0) is
the stock's in every mode.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]

S, P, ST, RV, L, LP, G, STP, RS = 0x371EA, 0x371EB, 0x371EC, 0x371ED, 0x371D9, 0x371EE, 0x371EF, 0x371F0, 0x371F1
OUT, COPY, ZF, TAB = 0x306F0, 0x422, 0x45D, 0x30000
A1, E1, A2, E2 = 0x374, 0x422, 0x469, 0x4CD                # our two regions: P:$374..$421, P:$469..$4CC
CALL_PV, CALL_ENV = 0x123, 0x124                          # the main loop's jsr $3C1 / jsr $469
OLD_PV, OLD_ENV = 0x0D03C1, 0x0D0469
STOCK_FIRST = ((0x374, 0x5EF000), (0x3C1, 0x5EF000), (0x421, 0x00000C), (0x469, 0x240000), (0x4CC, 0x00000C))
N = 0x20                                                  # the stock's block: 32 words


def y(a):
    return f"y:>${a:x}"


def player_items():
    """P:A1..: pv (the entry), pv_i (none), cnt; r6 = P and (r6 + n6) = ST from pv on (the stock never sets m6)"""
    return [
        ("label", "pv"),
        f"move {y(S)},a", "cmp #>$80,a", ("jccs", "ge", "pv_i"),
        "asl #2,a,a", f"add #>${TAB:x},a", "move a1,r4",
        f"move #>${OUT:x},b", "move b1,r5", f"move #>${P:x},r6", f"move #${ST - P:x},n6",      # r6 = P, (r6 + n6) = ST
        f"move {y(LP)},a", "tst a", ("jccs", "eq", "pv_n"),
        f"move {y(L)},a", "tst a", ("jccs", "gt", "pv_l"),
        ("label", "pv_n"),
        f"move {y(RV)},a", "tst a", ("jccs", "ne", "pv_r"),
        "move (r4)+", "move y:(r4)+,b", "move y:(r6),a", "cmp b,a", ("jccs", "gt", "pv_i"),        # forward: past the slot's length
        "move y:(r6+n6),y1", "add y1,a", "move y:(r4)-,b", f"sub #>${N:x},b", "cmp a,b", ("jccs", "lt", "pv_i"),   # within a block of its end
        "move y:(r4),b", "move y:(r6),a", "sub a,b",
        ("jsrs", "cnt"), ("jsrs", "pfp"), ("jmps", "pv_z"),
        ("label", "pv_r"),
        "move (r4)+", "move y:(r4),b", "move y:(r6),a", "abs a", "cmp b,a", ("jccs", "ge", "pv_i"),
        "move (r4)-", "move y:(r6+n6),a", "move y:(r6),x0", "add x0,a", f"sub #>${N:x},a", "move y:(r4)+,b", "cmp b,a",
        ("jccs", "lt", "pv_i"),
        "move y:(r4),b", "move y:(r6),a", "abs a", "sub a,b",
        ("jsrs", "cnt"), ("jsrs", "prp"),
        ("label", "pv_z"),
        "move n1,a", "tst a", ("jccs", "eq", "pv_x"), ("jmps", ZF),                                 # short of a block: zeros, none
        ("label", "pv_x"), "rts",
        ("label", "pv_l"),                                                                         # loop: n1 = the words still to copy
        f"move #${N:x},n1",
        ("label", "pl_t"),
        "move y:(r6),a", "abs a", f"move {y(L)},b", "cmp b,a", ("jccs", "lt", "pl_c"), "clr a", "move a,y:(r6)",
        ("label", "pl_c"),
        "move y:(r6),a", "abs a", f"move {y(L)},b", "sub a,b", "move n1,a", "cmp a,b", "tgt a,b",   # b = min(L - |P|, n1)
        "move n1,a", "sub b,a", "move a1,n1",
        f"move {y(RV)},a", "tst a", ("jccs", "ne", "pl_r"), ("jsrs", "pfp"), ("jmps", "pl_n"),
        ("label", "pl_r"), ("jsrs", "prp"),
        ("label", "pl_n"), "move n1,a", "tst a", ("jccs", "ne", "pl_t"), "rts",
        ("label", "pv_i"),                                                                         # none: a block of zeros
        f"move #>${OUT:x},b", "move b,r5", "clr b",
        ("do", "pi_e"), "move b,y:(r5)+", ("label", "pi_e"),
        "move #$7f,x1", f"move x1,{y(S)}", f"move b,{y(P)}", "rts",
        ("label", "cnt"),                                                                          # b = the words left -> x0 = b = min(32, b), n1 = 32 - b
        f"move #>${N:x},a", f"cmp #>${N:x},b", "tgt a,b", "move b,x0", "sub b,a", "move a1,n1", "rts",
    ]


def piece_items():
    """pfp / prp (r6, n6 as pv sets them): a piece of b words, the stock's two copies around a page's end"""
    return [
        ("label", "pfp"),                                                                          # forward: up to the page's end, then the rest
        "move b,x0", "move y:(r6),a", "move y:(r6+n6),b", "add b,a", "and #>$fff,a", "move a1,a", "move #>$1000,b", "sub a,b",
        "move x0,a", "cmp x0,b", "tlt b,a",
        ("jsrs", COPY), "move y:(r6),b", "add a,b", "move b1,y:(r6)",
        "move x0,b", "sub a,b", "tfr b,a", ("jsrs", COPY), "move y:(r6),b", "add a,b", "move b1,y:(r6)", "rts",
        ("label", "prp"),                                                                          # reverse: down to the page's start, then the rest
        "move b,x0", "move y:(r6),a", "move y:(r6+n6),b", "add b,a", "and #>$fff,a", "move a1,a", "move x0,b", "cmp x0,a",
        "tlt a,b", "tfr b,a",
        ("jsrs", COPY), "move y:(r6),b", "sub a,b", "move b1,y:(r6)",
        "move x0,b", "sub a,b", "tfr b,a", ("jsrs", COPY), "move y:(r6),b", "sub a,b", "move b1,y:(r6)", "rts",
    ]


def env_items():
    """P:A2..: env, the stock's gain ramp; loop mode: the target full while it plays"""
    return [
        ("label", "env"),
        "move #$0,x0", "move #>$8,y0",
        f"move {y(STP)},a", "tst a", ("jccs", "ne", "e_r"),
        f"move {y(LP)},a", "tst a", ("jccs", "ne", "e_a"),
        f"move {y(L)},a", "sub #>$100,a", f"move {y(P)},b", "abs b", "cmp b,a", ("jccs", "lt", "e_n"),
        ("label", "e_a"),
        f"move {y(S)},b", "cmp #>$80,b", ("jccs", "ge", "e_n"),
        "move #>$7fffff,x0", "move #>$4,y0", ("jmps", "e_r"),
        ("label", "e_n"),
        f"move {y(LP)},a", "tst a", ("jccs", "eq", "e_r"), f"move {y(RS)},b", "tst b", ("jccs", "ne", "e_r"),
        "move #>$8,x1", f"move x1,{y(RS)}",
        ("label", "e_r"),
        f"move #>${OUT:x},b", "move b1,r5", f"move {y(G)},a",
        ("do", "e_e"),
        "move a,x1", "move x0,b", "sub a,b", "asr y0,b,b", "add b,a", "move a,y1", "move y:(r5),x1", "mpy y1,x1,b", "move b,y:(r5)+",
        ("label", "e_e"),
        f"move a,{y(G)}",
        f"move {y(STP)},a", "tst a", ("jccs", "eq", "e_s"), "sub #>$1,a", f"move a,{y(STP)}", "tst a", ("jccs", "ne", "e_s"),
        "move #$7f,x1", f"move x1,{y(S)}", "clr a", f"move a,{y(P)}", f"move a,{y(STP)}",
        ("label", "e_s"),
        f"move {y(RS)},a", "tst a", ("jccs", "eq", "e_x"), "sub #>$1,a", f"move a,{y(RS)}", "tst a", ("jccs", "ne", "e_x"),
        "clr a", f"move a,{y(P)}", f"move a,{y(RS)}",
        ("label", "e_x"), "rts",
    ]


def code():
    """-> ({P address: word}, labels): the player and the pieces at A1, the gain ramp at A2"""
    import voicefx as V
    w1, l1 = V.assemble(player_items() + piece_items(), A1)
    w2, l2 = V.assemble(env_items(), A2)
    assert A1 + len(w1) <= E1, f"player: {len(w1)} words from ${A1:x} (room {E1 - A1})"
    assert A2 + len(w2) <= E2, f"gain: {len(w2)} words from ${A2:x} (room {E2 - A2})"
    out = {A1 + i: x for i, x in enumerate(w1)}
    out.update({A2 + i: x for i, x in enumerate(w2)})
    return out, {**l1, **l2}


def install(img, report, base_addr):
    """core 1's preview player and gain ramp over the stock's (no ARM code)"""
    import rhdsp1

    def word(a):
        o = rhdsp1.where(img, a)
        return int.from_bytes(img[o:o + 3], "big")
    for a, w in STOCK_FIRST:
        assert word(a) == w, f"P:${a:x} is not the stock's"
    words, labels = code()
    for a, w in words.items():
        rhdsp1.patch_p(img, a, word(a), w)
    for a in list(range(A1, E1)) + list(range(A2, E2)):
        if a not in words:
            rhdsp1.patch_p(img, a, word(a), 0x000000)          # nop
    rhdsp1.patch_p(img, CALL_PV, OLD_PV, 0x0D0000 | labels["pv"])
    rhdsp1.patch_p(img, CALL_ENV, OLD_ENV, 0x0D0000 | labels["env"])
    report["pvloop"] = dict(pv=hex(labels["pv"]), env=hex(labels["env"]), words=len(words),
                            room=(E1 - A1) + (E2 - A2) - len(words))
    return {}, b""
