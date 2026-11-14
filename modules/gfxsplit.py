"""Grid FX split (MIT; Rhythm Plus, Circuit Rhythm 5706): a track's dry sound goes around Grid FX in core 0, all of it or a share.

The stock (core 0's block, P:$202..): P:$BEF writes each track's dry L / R to X:$DE + 64 t (32 samples, L and R interleaved) and its
sends; P:$367 (called from P:$224) adds the eight tracks x a per-sample gain (Y:$304F0 + 64 t + n1, n1 = Y:$FFFFD0 << 5) into the
mix; Grid FX runs on X:$4B18 after it; P:$1A26 (called from P:$282, r1 = $4B18) is the compressor.
Ours, in the unused vectors P:$50..$FF:
  * P:$224 -> `pre`: track TRACK's dry L / R x its gain into DRY (X:$1400, 64 words), its dry buffer cleared, then the stock's P:$367;
    (sends) each track's share c = X:CUT + t (0 = all into Grid FX, the zero of a fresh core 0) -> the share in use X:APPLIED + t,
    which keeps its value while the beat repeat engine is on and c is lower (the track's recording is not in the repeat):
    DRY = the sum of dry x c x gain, the dry buffer x (1 - c); c = 0 skips the track;
  * P:$282 -> `post`: DRY added to X:$4B18, then the stock's P:$1A26.
The tracks' delay and reverb sends stay as the stock's.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import core0  # noqa: E402
import rhdsppatch as DP  # noqa: E402

AT = 0x50
DRY = 0x1400                                              # core 0 X, 2 words a sample
CUT = 0x1440                                              # core 0 X + t: the share around Grid FX, 0 .. $7FFF00
APPLIED = 0x1450                                          # core 0 X + t: the share in use
BR_STATE, BR_ON = 0xD5, 0                                 # the beat repeat engine's state word: bit 0 from the press to the end of its fade
TRACK = 0
SRC, GAIN, MIX = 0xDE, 0x304F0, 0x4B18
SUM, COMP = 0x367, 0x1A26
SITES = {0x225: SUM, 0x283: COMP}                         # the second word of `jsr` at P:$224 / $282


def items(track=TRACK):
    return [("label", "pre"),
            "movep y:<<$ffffd0,b", "asl #5,b,b", "move b,n1",                         # as P:$367: the gain's half
            f"move #>${GAIN + 64 * track:x},r1", f"move #>${SRC + 64 * track:x},r0", f"move #>${DRY:x},r4",
            "nop", "move (r1)+n1",
            "move x:$3a,y1", "do y1,${pre_e:x}",
            "move y:(r1)+,y0",
            "move x:(r0),x0", "mpy y0,x0,a", "clr b", "move a,x:(r4)+", "move b,x:(r0)+",
            "move x:(r0),x0", "mpy y0,x0,a", "move a,x:(r4)+", "move b,x:(r0)+",
            ("label", "pre_e"),
            ("jmp", SUM),
            ("label", "post"),
            f"move #>${MIX:x},r0", f"move #>${DRY:x},r2",
            "move x:$3a,y1", "do y1,${post_e:x}",
            "move x:(r0),a", "move x:(r2)+,x0", "add x0,a", "move a,x:(r0)+",
            "move x:(r0),a", "move x:(r2)+,x0", "add x0,a", "move a,x:(r0)+",
            ("label", "post_e"),
            f"move #>${MIX:x},r1",
            ("jmp", COMP)]


def send_items():
    post = items()
    return [("label", "pre"),
            "movep y:<<$ffffd0,b", "asl #5,b,b", "move b,n1",                         # as P:$367: the gain's half
            "clr a", f"move #>${DRY:x},r4", "move x:$3a,y1", "do y1,${clr_e:x}", "move a,x:(r4)+", "move a,x:(r4)+",
            ("label", "clr_e"),
            f"move #>${SRC:x},r0", f"move #>${GAIN:x},r2", f"move #>${CUT:x},r5", "move #>$40,n0", "move #>$40,n2",
            f"move #>${APPLIED:x},r3",
            "do #8,${trk_e:x}",
            "move x:(r5)+,a", "move x:(r3),b",
            ("words", [0x0B7020 | BR_ON, BR_STATE]), ("jcc", "cc", "take"),               # btst #BR_ON,x:>BR_STATE (as P:$166F)
            "cmp a,b", ("jcc", "gt", "keep"),                                          # beat repeat on: a send going up waits
            ("label", "take"), "tfr a,b",
            ("label", "keep"), "move b,x:(r3)+", "move b,y1", "tst b", ("jcc", "eq", "skip"),
            "move #>$7fffff,a", "sub y1,a", "move a,x1",                                # x1 = 1 - c, y1 = c
            "move r2,r1", "nop", "move (r1)+n1", f"move #>${DRY:x},r4",
            "move x:$3a,n4", "do n4,${smp_e:x}",
            "move y:(r1)+,y0",
            "move x:(r0),x0", "mpy x1,x0,a", "mpy x0,y1,b", "move a,x:(r0)+",
            "move b,x0", "mpy y0,x0,b", "move x:(r4),a", "add b,a", "move a,x:(r4)+",
            "move x:(r0),x0", "mpy x1,x0,a", "mpy x0,y1,b", "move a,x:(r0)+",
            "move b,x0", "mpy y0,x0,b", "move x:(r4),a", "add b,a", "move a,x:(r4)+",
            ("label", "smp_e"),
            ("jmp", "next"),
            ("label", "skip"), "move (r0)+n0",
            ("label", "next"), "move (r2)+n2", "nop",
            ("label", "trk_e"),
            ("jmp", SUM),
            *post[post.index(("label", "post")):]]


def code(track=TRACK, sends=False):
    import voicefx
    words, labels = core0.asm_at(send_items() if sends else items(track), AT)
    assert AT + len(words) <= 0x100, ("past the vectors", hex(AT + len(words)))
    voicefx.check(words, AT)                              # the assembler takes invalid mpy pairs as mpysu
    return words, labels


# Bypass coefficients: zero preserves the stock routing and fully wet Grid FX.
RETURN_CUT, BLEND, BLEND_NOW, CLEAN = 0x1458, 0x145A, 0x145B, 0x1480
RETRIGGER = 0x145C
CTRL_AT, CAPTURE_SITE, RETURN_SITE = 0x1FED, 0x23A, 0x5C0


def control_items(post, retrigger=False):
    reset=[f"move x:>${RETRIGGER:x},a", "tst a", ("jcc", "eq", "capture_audio"),
           # A later native stop or different live-pad command wins over an
           # older sequencer request. Negative D4 means already consumed.
           "move x:>$d4,b", "tst b", ("jcc", "eq", "br_cancel"),
           ("jcc", "lt", "br_reset"), "cmp a,b", ("jcc", "ne", "br_cancel"),
           ("label", "br_reset"),
           # A complete native command, consumed at the audio boundary. Clear
           # the old ring state AND same-rate cache before native press logic.
           "move a,x:>$d4", "clr a", f"move a,x:>${RETRIGGER:x}",
           "move a,x:>$d5", "move a,x:>$1b93", ("jmp", "capture_audio"),
           ("label", "br_cancel"), "clr a", f"move a,x:>${RETRIGGER:x}",
           ("label", "capture_audio")] if retrigger else []
    return [
        ("label", "capture"), *reset, f"move #>$4ad8,r0", f"move #>${CLEAN:x},r2",
        "move x:$3a,y1", "do y1,${capture_e:x}",
        "move x:(r0)+,a", "move a,x:(r2)+", "move x:(r0)+,a", "move a,x:(r2)+",
        ("label", "capture_e"), ("jmp", 0x166B),
        # Split each return before the native return sum. DRY bypass rejoins only
        # after Grid FX, with the same x:$77e gain shift as the native wet path.
        ("label", "returns"), f"move #>${RETURN_CUT:x},r5", "move #>$889,r6",
        "move #>$100,n6", "do #2,${returns_e:x}",
        "move x:(r5)+,y1", "move y1,a", "tst a", ("jcc", "eq", "returns_skip"),
        f"move #>${DRY:x},r4", "move x:>$77e,y0", "move x:$3a,n4",
        "do n4,${return_smp_e:x}",
        ("jsr", "split"), ("jsr", "split"),
        ("label", "return_smp_e"), "move (r6)+n6", ("jmp", "returns_next"),
        ("label", "returns_skip"), "move #>$140,n6", "move (r6)+n6", "move #>$100,n6",
        ("label", "returns_next"), "nop", ("label", "returns_e"),
        "move #>$9c9,r6", "rts",
        ("label", "split"), "move y:(r6),x0", "mpy x0,y1,a",
        "move #>$7fff00,x1", "move y1,b", "cmp x1,b", ("jcc", "lt", "split_part"),
        "move x0,a", ("label", "split_part"),
        "move a,x1", "move x0,b", "sub x1,b", "move b,y:(r6)+",
        "move x1,a", "asr y0,a,a", "move x:(r4),b", "add a,b", "move b,x:(r4)+", "rts",
        ("label", "blend"), f"move x:>${BLEND:x},a", f"move x:>${BLEND_NOW:x},b", "add b,a", "tst a",
        ("jcc", "eq", post), f"move #>${MIX:x},r0", f"move #>${CLEAN:x},r2",
        "move x:$3a,n4", "do n4,${blend_e:x}", ("jsr", "ramp"),
        ("jsr", "blend_sample"), ("jsr", "blend_sample"),
        ("label", "blend_e"), ("jmp", post),
        # Slew one 1/2048 step per stereo frame (about 43 ms full-scale).
        ("label", "ramp"), f"move x:>${BLEND_NOW:x},a", f"move x:>${BLEND:x},b", "sub a,b",
        "move #>$1000,x1", "cmp x1,b", "tgt x1,b",
        "move #>$fff000,x1", "cmp x1,b", "tlt x1,b",
        "add b,a", f"move a,x:>${BLEND_NOW:x}", "move a,y1",
        "move #>$7fffff,a", "sub y1,a", "move a,y0", "rts",
        ("label", "blend_sample"), "move x:(r0),x1", "move x:(r2)+,x0",
        "move #>$7fff00,a", "move y1,b", "cmp a,b", ("jcc", "ge", "blend_clean"),
        "tst b", ("jcc", "eq", "blend_wet"),
        "mpy x0,y1,a", "mac x1,y0,a", ("jmp", "blend_store"),
        ("label", "blend_clean"), "move x0,a", ("jmp", "blend_store"),
        ("label", "blend_wet"), "move x1,a",
        ("label", "blend_store"), "move a,x:(r0)+", "rts",

    ]


def install(img, report, base_addr=None, track=TRACK, sends=False, controls=False):
    words, labels = code(track, sends)
    for i, w in enumerate(words):
        core0.patch_p0(img, AT + i, 0, w)
    core0.patch_p0(img, 0x225, SUM, labels["pre"])
    core0.patch_p0(img, 0x283, COMP, labels["post"])
    controls_report = {}
    if controls:
        assert sends
        retrigger=os.environ.get('RH_GFX_RETRIGGER')=='1'
        extra, cl = core0.asm_at(control_items(labels["post"],retrigger), CTRL_AT)
        import voicefx
        voicefx.check(extra, CTRL_AT)
        core0.patch_p0(img, CAPTURE_SITE, 0x166B, cl["capture"])
        core0.patch_p0(img, RETURN_SITE, 0x66F400, 0x0BF080)
        core0.patch_p0(img, RETURN_SITE + 1, 0x9C9, cl["returns"])
        core0.patch_p0(img, 0x283, labels["post"], cl["blend"])
        _, ws = DP.core0(img)
        segmented=os.environ.get('RH_GFX_SEGMENTS')=='1'
        if segmented:
            # The original block already contains the in-place hooks above.
            # Send it from its existing address, followed only by the extension.
            # No DSP sound instruction or control address is changed.
            start=(DP.BASE+len(img)+3)&~3
            core0.install(img,report,start,counter=False,loader=True,segs=[(CTRL_AT,extra)])
            block=int(report['core0']['blocks'][1],16)
            count=len(ws)+len(extra)
        else:
            block, count = DP.relocate(img, ws, extra)
        controls_report = dict(controls={k: hex(v) for k, v in cl.items()}, control_words=len(extra),
                               control_at=hex(CTRL_AT), return_cut=hex(RETURN_CUT), blend=hex(BLEND), clean=hex(CLEAN),
                               control_block=hex(block), total_words=count)
        if retrigger:controls_report['retrigger']=hex(RETRIGGER)
        if segmented:controls_report['segmented']=True

    report["gfxsplit"] = dict(at=hex(AT), words=len(words), dry=hex(DRY), pre=hex(labels["pre"]), post=hex(labels["post"]),
                              **(dict(cut=hex(CUT), applied=hex(APPLIED)) if sends else dict(track=track)), **controls_report)
    return {}, b""


def program(img,g):
    """Effective contiguous sound program for comparisons/emulation.

    The segmented boot loader remains separately resident above this range.
    The actual loader/ARM stream is independently tested in emu_flashspace.
    """
    _,words=DP.core0(img)
    if not g.get('segmented'):return words
    at=int(g['control_block'],16)-DP.BASE
    n=int.from_bytes(img[at:at+3],'big');address=int.from_bytes(img[at+3:at+6],'big')
    assert address==CTRL_AT==len(words) and n==g['control_words']
    return words+[int.from_bytes(img[at+6+3*i:at+9+3*i],'big') for i in range(n)]
