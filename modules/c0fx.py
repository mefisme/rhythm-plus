"""The volume LFO, the move LFO and the ring mod on DSP core 0 (MIT; Rhythm Plus, Circuit Rhythm 5706).

  * where: core 0 mixes the eight tracks at P:$367 (`jsr $367` at P:$224, once a block): track t's 32 mono samples from core 1 at shared
    Y:$304F0 + 64 t + 32 (y:$FFFFD0 bit 0).  Ours: P:$224 -> `jsr C0` (a segment of Remix's core 0 loader, core0.py), then `jmp $367`;
  * C0, for each track: the move LFO (phase at Y:MP + t += MR, M = shape(phase / 2) at shared Y:SH + t, 0 while MR = 0) for mixmove's
    hooks; the volume LFO (phase += R, VX = D x (1 - shape(phase / 2)) / 2, 0 while D = 0), smoothed into Y:VB + O_VX + t
    (+= (VX - it) x VK a block) for mixmove's pan hook (L and R x (1 - it)); the ring mod on the track's samples (gain = 1 - m + m s(phase),
    voicefx's), while its amount is not 0;
  * the words sit at core 1's addresses in core 0's Y: fshape's VB / MB, pshape's LFO and gate tables, voicefx's ring words.  upguard's
    c_dspw sends the ARM's writes there (ROUTES); the LFO tables go to both cores (core 1's pitch and filter LFOs read them);
  * strip(): core 1 without them (no fshape LVL: the stock's level ramp keeps its call; voicefx without the ring stage).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import core0  # noqa: E402

AT = 0x2000                                               # core 0's P loaded by core0.py's loader (free: $1FED..$3FDF)
HOOK, OLD_HOOK, MIX = 0x224, (0x0BF080, 0x000367), 0x367  # jsr $367 (the mix) in core 0's block
MP, SAVE = 0x1438, 0x1440                                 # core 0's Y: the move phase + t; the stock's r / n / m while C0 runs
VK = 0x32AB81                                           # 1 - (63 / 64) ^ 32: core 1's per-word level smoothing over a block
BANK = 0x304F0                                            # shared Y: track t's samples at + 64 t + 32 (y:$FFFFD0 bit 0)
STRIPPED = [False]                                        # set by strip()


def ring_y():
    import pshape as PS
    import voicefx as VX
    return VX.Y_BASE + PS.SHIFT


def routes():
    """-> (core 0 only, both): [(first, end)] of core 1 Y addresses the ARM's writes go to"""
    import fshape as FS
    import pshape as PS
    r = ring_y()
    return [(r + VX_RPH, r + VX_RAM + 8), (FS.VB, PS.VOL_Y + PS.NG * PS.STRIDE)], [(PS.LFO_Y, PS.LFO_Y + PS.NL * PS.STRIDE)]


VX_RPH, VX_RST, VX_RAM = 0, 8, 16                         # voicefx's ring words: phase, step, amount (+ t)


def ring_body(buf):
    """voicefx's ring mod a word: b = the phase, x0 = the step, y1 = m; the word at buf (post-increment)"""
    one = 0x7FFFFF
    return ["add x0,b", "move b1,y0", "move y0,b", "tfr b,a", "abs a", "asl a", f"sub #>${one:x},a", "move a,x1",
            "abs a", "move a,y0", "mpy -x1,y0,a", "add x1,a", "add x1,a", "move a,x1", "mpy y1,x1,a", "sub y1,a",
            f"add #>${one:x},a", "move a,x1", f"move {buf},y0", "mpy x1,y0,a", f"move a,{buf}+"]


def items():
    import fshape as FS
    import mixmove as MM
    import pshape as PS
    L = []
    e = L.extend
    e([("label", "c0"), ("jsr", "c0_sv"),
       f"move #>${FS.VB:x},r1", f"move #>${FS.MB:x},r2", f"move #>${MP:x},r4", f"move #>${MM.SH:x},r5",
       "do #8,${c0_le:x}",
       "move y:(r2),x0", "move y:(r2+$8),r0", "clr b", "move x0,a", "tst a", ("jcc", "eq", "c0_m0"),      # the move LFO
       "move y:(r4),a", "add x0,a", "move a1,y:(r4)", "lsr #1,a", ("jsr", "lk"), "move a,b",
       ("label", "c0_m0"), "move b,y:(r5)",
       f"move y:(r1+${FS.O_VD:x}),b", "tst b", ("jcc", "eq", "c0_v0"),                                      # the volume LFO
       f"move y:(r1+${FS.O_VP:x}),a", f"move y:(r1+${FS.O_VR:x}),x0", "add x0,a", f"move a1,y:(r1+${FS.O_VP:x})", "lsr #1,a",
       f"move y:(r1+${FS.O_VQ:x}),r0", ("jsr", "lk"),
       "move a,x0", "move #>$7fffff,a", "sub x0,a", "asr a", "move a,x0", f"move y:(r1+${FS.O_VD:x}),x1", "mpy x1,x0,b",
       ("label", "c0_v0"),
       f"move y:(r1+${FS.O_VX:x}),a", "sub a,b", "move b,x0", f"move #>${VK:x},x1", "mpy x1,x0,b", "add a,b",
       f"move b,y:(r1+${FS.O_VX:x})",
       "move (r1)+", "move (r2)+", "move (r4)+", "move (r5)+",
       ("label", "c0_le"),
       "movep y:<<$ffffd0,b", "asl #5,b,b", "move b,n3",                                                     # the bank, as P:$367
       f"move #>${BANK:x},r3", "lua (r3)+n3,r3", "move #$40,n3", f"move #>${ring_y():x},r6",
       "do #8,${c0_re:x}",
       f"move y:(r6+${VX_RAM:x}),a", "tst a", ("jcc", "eq", "c0_rn"),                                       # the ring mod
       "move r3,r2",
       f"move y:(r6+${VX_RPH:x}),b", f"move y:(r6+${VX_RST:x}),x0", f"move y:(r6+${VX_RAM:x}),y1",
       "move x:$3a,n5", "do n5,${c0_rs:x}",                                                  # the block's words
       *ring_body("y:(r2)"),
       ("label", "c0_rs"),
       f"move b1,y:(r6+${VX_RPH:x})",
       ("label", "c0_rn"),
       "move (r3)+n3", "move (r6)+",
       ("label", "c0_re"),
       ("jsr", "c0_rt"), ("jmp", MIX)])
    e([("label", "c0_sv")])                                    # the stock's r / n / m to Y:SAVE (m: the raw MOVEC words), then m linear
    for k in range(8):
        e([f"move r{k},y:>${SAVE + k:x}", f"move n{k},y:>${SAVE + 8 + k:x}", ("words", [0x057060 | k, SAVE + 16 + k]),
           ("words", [0x05F420 | k, 0xFFFFFF])])
    e(["rts", ("label", "c0_rt")])
    for k in range(8):
        e([f"move y:>${SAVE + k:x},r{k}", f"move y:>${SAVE + 8 + k:x},n{k}", ("words", [0x05F060 | k, SAVE + 16 + k])])
    e(["rts", *PS.lk_items()])
    return L


def code():
    import voicefx
    words, labels = core0.asm_at(items(), AT)
    voicefx.check(words, AT)
    assert AT + len(words) <= core0.LD, hex(AT + len(words))
    return words, labels


def strip():
    """from now on fshape builds no LVL and voicefx has no ring stage (after nocomb.strip())"""
    import voicefx
    fx0 = voicefx.items

    def fx_items(shift=0, pre=None, lite=False):
        out = fx0(shift, pre, lite)
        a = out.index(("label", "fx")) + (2 if pre is not None else 1)
        b = out.index(("label", "filt"))
        assert out[a:a + 3] == ["move y:>$1405,n1", f"move #>${voicefx.Y_BASE + shift:x},r1", "lua (r1)+n1,r1"], out[a:a + 3]
        assert "move x:(r2),y0" in out[a:b] and out[b - 2:b] == [("label", "r_end"), "move b1,y:(r1+$0)"], out[b - 2:b]
        return out[:a] + out[b:]
    voicefx.items = fx_items
    STRIPPED[0] = True


def install(img, report, base_addr):
    assert STRIPPED[0], "c0fx: strip() before pitchmod installs"
    words, labels = code()
    _, _, ws = core0.block_words(img)
    assert tuple(ws[HOOK:HOOK + 2]) == OLD_HOOK, "core 0's jsr $367 at P:$224 moved"
    segs = [(AT, words), (HOOK, [0x0BF080, labels["c0"]])]
    core0.install(img, report, base_addr, counter=False, loader=True, segs=segs)
    only0, both = routes()
    report["c0fx"] = dict(at=hex(AT), words=len(words), c0=hex(labels["c0"]), lk=hex(labels["lk"]), mp=hex(MP), save=hex(SAVE),
                          vk=hex(VK), ring=hex(ring_y()), only0=[[hex(a), hex(b)] for a, b in only0], both=[[hex(a), hex(b)] for a, b in both])
    return labels
