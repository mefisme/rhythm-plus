"""Grid FX sends and the FX track (MIT): a send for each track into Grid FX, on a third knob page of the Mixer and Grid FX views;
one track can be the FX track, its steps the Grid FX slots (gfxmix.c; after Circuit Remix's fxseq, MIT).

The stock: the Mixer (0x2004E090, vtable 0x08067918) is also the Grid FX view (its mode p0 of [view + 0x1CC] = 7); one knob page for
both, read by 0x0805A4CE(view + 0x13C): 0 the pans, 1 the levels, 2.. Grid FX's effect pages (Down / Up, buttons 19 / 20); its knob
slot 4 = (view, knob, delta).
Ours: Down on the pans = the sends page, Up = back to the pans; a knob = its track's send (0..127, 127 = all into Grid FX, the
stock's sound), Clear + knob = 127; the knob LEDs in GX_RGB by the send. The sends: rhrec's tail + BLK_OFF, "GX", a check byte, the
version, 8 sends. Each LED frame, once the DSP is READY, a changed send goes to core 0's X:CUT + t (gfxsplit's share around Grid FX);
one track again every ROUND frames.
The FX track: Sample mode's pad 8 (one track at a time; the block's byte 12, its K1-K8 from before at 13). Its note-on (the head of
0x08040778) is kept from the DSP; a step's slots (its flip and reverb-send lane, read at the players' slot 4) turn on through
the parameter setters after the stock's lock (the note wrappers' release, or the next LED frame) and play for the step's gate,
counted in the players' ticks (slot 1); a later step of the same type takes over, one after a gap starts afresh. Its sample view:
the stock's steps and the 16 Grid FX pads; its K1-K8 are the sends, or a held pad's settings. Its button is lit amber, the Mixer button dim amber off its view; no Track Parameter
Editor on it. Install after stepmut (the button, pad,
knob and output heads).
"""
from __future__ import annotations

import struct
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / d) for d in ("modules", "builds", "tests", "remix/tools")]
import countin as C  # noqa: E402
import gfxsplit as GS  # noqa: E402
import rhstate  # noqa: E402
import stepmut as SM  # noqa: E402

SRC = ROOT / "modules" / "gfxmix.c"
MIX_VT = 0x08067918
KNOB_SLOT = MIX_VT + 0x10
BLK_OFF, BLK_LEN = 504, 26
SLOT_LEN = 472
PK_OFF, PK_LEN = 548, 196                       # the FX track's steps' codes
PS_OFF, PS_LEN = 2, 145                         # their sets
LABELS = ("c_gx_btn", "c_gx_rel", "c_gx_knob", "c_gx_out", "c_gx_pad", "c_gx_padrel", "c_gx_tknob", "c_gx_noteon", "c_gx_tick", "c_gx_unl",
          "c_gx_s4")
NOTE_ON, ON_HEAD = 0x08040778, "push.w {r4, r5, r6, r7, r8, sb, fp, lr}"
UNLOCK, UNLOCK_SITES = 0x08030EB8, (0x080467A4, 0x0804681E)
PLAYER_VT = 0x08068D24
SLOT1 = PLAYER_VT + 0x4                          # the players' vtable, slot 1: a tick (player, pattern, step, micro, [sp] tick)
SLOT4 = PLAYER_VT + 0x10                         # slot 4: the step's sample


def stubs(base, lab, img, prev_s1, prev_s4):
    """the entries that keep every register and the stack for the stock: the note-on, the players' slots 1 and 4"""
    import rhbuild
    from thumb import Asm, b_cond, b_w, bl, cmp_imm, h, ldr_sp, movs_imm, pop_list, push_list, raw
    a = Asm(base)
    E = a.emit
    ldr_lr = h(0xF85D) + h(0xEB04)                                     # ldr lr, [sp], #4

    def head(at, n):
        return bytes(img[at - rhbuild.BASE:at - rhbuild.BASE + n])

    def call(fn):
        E(push_list, [0, 1, 2, 3, 4], lr=True)
        E(bl, lab[fn])
        E(cmp_imm, 0, 0)
        E(pop_list, [0, 1, 2, 3, 4])
        E(raw, ldr_lr)
    a.label("c_gx_on_e")
    call("c_gx_noteon")
    E(b_cond, "on_kept", "ne")
    E(raw, head(NOTE_ON, 4))
    E(b_w, NOTE_ON + 4)
    a.label("on_kept")
    E(movs_imm, 0, 0)
    E(raw, h(0x4770))
    a.label("c_gx_tick_e")
    E(push_list, [0, 1, 2, 3, 4], lr=True)
    E(ldr_sp, 1, 24)                                                   # the tick, the stock's 5th argument
    E(bl, lab["c_gx_tick"])
    E(pop_list, [0, 1, 2, 3, 4])
    E(raw, ldr_lr)
    E(b_w, prev_s1)
    a.label("c_gx_s4_e")
    call("c_gx_s4")
    E(b_w, prev_s4)
    return a.assemble()


def install(img, report, base_addr):
    import rhbuild
    import rhrec
    import tmenu as T
    from thumb import b_w as bw_ins, bl as bl_ins
    assert "stepmut" in report and "gfxmix" in rhstate.OFF and "cthresh" in report and "c_pcsync" in report["pageclear"]["labels"],         "gfxmix: after stepmut, pageclear with viewsync, ourram's slot, dspready"
    assert rhstate.OFF["gfxmix"][1] >= SLOT_LEN
    sm_reserved = ((276,20),) if report['stepmut'].get('offload') else ((SM.BLK_OFF, SM.BLK_LEN),)
    taken = ((192, 84), (384, 20), (T.PG_OFF, T.PG_LEN), (748, 112)) + sm_reserved
    ours = ((BLK_OFF, BLK_LEN), (PK_OFF, PK_LEN), (PS_OFF, PS_LEN))
    assert all(a + n <= o or o + m <= a for a, n in ours for o, m in taken) and all(a + n <= rhrec.FREE_LEN for a, n in ours)
    GS.install(img, report, sends=True, controls=True)
    base_addr = rhbuild.BASE + len(img)
    u = lambda a_: struct.unpack_from("<I", img, a_ - rhbuild.BASE)[0]       # noqa: E731
    lab = lambda k, n: int(report[k]["labels"][n], 16)                        # noqa: E731
    prev = dict(PREV_BTN=rhbuild.bw_target(img, C.BTN_ENTRY), PREV_REL=rhbuild.bw_target(img, C.BTN_RELEASE), PREV_OUT=rhbuild.bl_target(img, T.OUT_CALL),
                PREV_KNOB=u(KNOB_SLOT) & ~1, PREV_PAD=rhbuild.bw_target(img, T.PP_ENTRY),
                PREV_PADREL=rhbuild.bw_target(img, T.PR_ENTRY), PREV_TKNOB=rhbuild.bw_target(img, T.KN_ENTRY))
    prev_s1, prev_s4 = u(SLOT1) & ~1, u(SLOT4) & ~1
    base_addr = (base_addr + 3) & ~3
    defs = dict(prev, SLOT=rhstate.ST + rhstate.OFF["gfxmix"][0], BLK_OFF=BLK_OFF, PK_OFF=PK_OFF, PS_OFF=PS_OFF, DSP_CUT=GS.CUT, DSP_RET=GS.RETURN_CUT, DSP_BLEND=GS.BLEND,
                READY_AT=int(report["cthresh"]["slot"], 16) + 1, C_RRT=lab("rhrec", "c_rrt"), C_CIOK=lab("countin", "c_ciok"),
                C_PCSYNC=lab("pageclear", "c_pcsync"), SM_SLOT=int(report["stepmut"]["slot"], 16), MS_SLOT=int(report["mutset"]["slot"], 16),
                TM_SLOT=int(report["tmenu"]["slot"], 16), TM_OPEN=T.O_OPEN, TM_STICKY=T.O_STICKY, TM_BACK=T.O_BACK, TM_ARM=T.O_ARM,
                TM_ARM_OFF=T.ARM_OFF, TM_PTRK=T.O_PTRK, TM_SHOP=T.O_SHOP,
                BTN_ENTRY_A=C.BTN_ENTRY, CI_PASS=rhstate.ST + rhstate.OFF["countin"][0] + 2)
    if os.environ.get('RH_AUTOMATION3')=='1':defs['AUTOMATION3']=1
    if os.environ.get('RH_GFX_RETRIGGER')=='1':defs['DSP_RETRIGGER']=GS.RETRIGGER
    if os.environ.get('RH_GFX_FEEDBACK')=='1':defs.update(REC_FEEDBACK=1,TM_HELD=lab('tmenu','c_tmheld'))
    if os.environ.get('RH_AUTO_BULK')=='1':defs['AUTO_BULK']=1
    if os.environ.get('RH_PRIVATE_GESTURE')=='1':defs['PRIVATE_GESTURE']=1
    if os.environ.get('RH_GFX_OVERDUB')=='1':defs['GFX_OVERDUB']=1
    if os.environ.get('RH_GFX_EDITOR_GUARD')=='1':defs['EDITOR_GUARD']=1
    if os.environ.get('RH_GFX_INPUT_TRACE')=='1':defs['INPUT_TRACE']=1
    if os.environ.get('RH_GFX_NATIVE_EDGES')=='1':defs['NATIVE_EDGES']=1
    if os.environ.get('RH_AUTOMATION_TASK_GUARD')=='1':defs['TASK_GUARD']=1
    if os.environ.get('RH_GFX_PAGECOPY')=='1':defs['FX_VISUALS']=1
    if os.environ.get('RH_GRANULAR_CURRENT_ARM')=='1':defs['GRANULAR_INTERLOCK']=1
    code, labels = SM.compile_c(base_addr, defs, src=SRC, name="gfxmix", prefix="c_gx_", need=LABELS + ("c_gx_smread", "c_gx_smwrite", "c_gx_smsample"), max_code=0x6000)
    img += bytes([0xFF]) * (base_addr - rhbuild.BASE - len(img)) + code
    if defs.get('EDITOR_GUARD'):
        at=lab('tmenu','c_tmallowed')
        rhbuild.patch(img,at,'mov r0, r0|bx lr',bw_ins(at,labels['c_gx_tmallowed']))
    while len(img) % 4:
        img += bytes([0xFF])
    st_base = rhbuild.BASE + len(img)
    st_code, st_labels = stubs(st_base, labels, img, prev_s1, prev_s4)
    img += st_code
    while len(img) % 4:
        img += bytes([0xFF])
    labels.update({k: v for k, v in st_labels.items() if k.startswith("c_")})
    rhbuild.patch(img, C.BTN_ENTRY, f"b.w #{prev['PREV_BTN']:#x}", bw_ins(C.BTN_ENTRY, labels["c_gx_btn"]))
    rhbuild.patch(img, C.BTN_RELEASE, f"b.w #{prev['PREV_REL']:#x}", bw_ins(C.BTN_RELEASE, labels["c_gx_rel"]))
    rhbuild.patch(img, T.KN_ENTRY, f"b.w #{prev['PREV_TKNOB']:#x}", bw_ins(T.KN_ENTRY, labels["c_gx_tknob"]))
    rhbuild.patch(img, T.PP_ENTRY, f"b.w #{prev['PREV_PAD']:#x}", bw_ins(T.PP_ENTRY, labels["c_gx_pad"]))
    rhbuild.patch(img, T.PR_ENTRY, f"b.w #{prev['PREV_PADREL']:#x}", bw_ins(T.PR_ENTRY, labels["c_gx_padrel"]))
    rhbuild.patch(img, T.OUT_CALL, f"bl #{prev['PREV_OUT']:#x}", bl_ins(T.OUT_CALL, labels["c_gx_out"]))
    rhbuild.patch_word(img, KNOB_SLOT, prev["PREV_KNOB"] | 1, labels["c_gx_knob"] | 1)
    rhbuild.patch(img, NOTE_ON, ON_HEAD, bw_ins(NOTE_ON, labels["c_gx_on_e"]))
    rhbuild.patch_word(img, SLOT1, prev_s1 | 1, labels["c_gx_tick_e"] | 1)
    rhbuild.patch_word(img, SLOT4, prev_s4 | 1, labels["c_gx_s4_e"] | 1)
    for c in UNLOCK_SITES:
        rhbuild.patch(img, c, f"bl #{UNLOCK:#x}", bl_ins(c, labels["c_gx_unl"]))
    for name, target, head in (("c_sm_fxread", "c_gx_smread", "movs r0, #0|bx lr"),
                               ("c_sm_fxwrite", "c_gx_smwrite", "bx lr|nop"),
                               ("c_sm_fxsample", "c_gx_smsample", "bx lr|nop")):
        rhbuild.patch(img, lab("stepmut", name), head, bw_ins(lab("stepmut", name), labels[target]))
    report["gfxmix"] = dict(overdub=bool(defs.get('GFX_OVERDUB')),native_edges=bool(defs.get('NATIVE_EDGES')),input_trace=bool(defs.get('INPUT_TRACE')),slot=hex(defs["SLOT"]), blk_off=BLK_OFF, blk_len=BLK_LEN, pk_off=PK_OFF, ps_off=PS_OFF, code=len(code) + len(st_code), cut=hex(GS.CUT),
                            prev_s1=hex(prev_s1), prev_s4=hex(prev_s4), stubs=hex(st_base),
                            prev={k.lower(): hex(v) for k, v in prev.items()}, labels={k: hex(v) for k, v in labels.items()})
    return labels, code
