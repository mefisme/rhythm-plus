"""Sample mode switches without the Pitch and FX pages (MIT; Rhythm Plus, Circuit Rhythm 5706).

Sample mode pads 19-21 (smpads sm=3): 19 the loop crossfade, 20 the drone, 21 the end fade, saved with the project (value 29).
  * core 1: pitchmod with dspload (its block counter), the start clear, the host port fix and Remix's loop crossfade v4. pitchmod's
    two hooks keep the stock's addresses, so no RR or TRIG of ours runs. Our words: fshape's drone / droff (the note-on / note-off
    handlers) and lfade (the end fade's test), on fshape's Y words;
  * ARM: value 29 in fshape's "SM" block of the record's tail (c_smval / c_smput); c_swdsp(track) writes its words; c_swled, a head of
    the LED task's chain, writes a changed track once core 1 is READY and SW_WAIT frames went by, else one track every ROUND frames.
RAM: rhstate "smswitch" + 0 the tracks to write (bit t), + 1 the frame counter, + 2 the frames since READY.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, adds_imm8, adds_reg, b, b_cond, bl, cmp_imm, eors_reg, h, ldrb_imm, lsls_imm, lsls_reg, lsrs_imm,  # noqa: E402
                   mov_reg, movs_imm, movt, movw, pop_list, push_list, raw, strb_imm, tst_reg, bics_reg)
import countin as CI  # noqa: E402
import fshape as FS  # noqa: E402
import pitchmod as PM  # noqa: E402
import rhstate  # noqa: E402

WR16 = 0x08031200
READY = 0xA0                                             # dspready's byte for the mode 0 program
SW_WAIT = 200                                            # frames after READY before the first write (Stock+'s wait)
ROUND = 8
LABELS = {}


def lfade_items():
    """(from P:$261, the end fade's `brset #0,y1`) a loop returns at the stock's rts; with the track's end fade off too; else the stock's tests"""
    return [("label", "lfade"), f"jset #1,y1,${FS.EF_RTS:x}",
            f"move #>${FS.SMF:x},r5", "move y:>$1405,n5", "lua (r5)+n5,r5", f"btst #{FS.SM_EF.bit_length() - 1},y:(r5)", f"jcs ${FS.EF_RTS:x}",
            f"jset #0,y1,${FS.EF_REV:x}", f"jmp ${FS.EF_FWD:x}"]


def code(at, shift=0, store_pitch=False, scan=False, stretch=False, lscan=None):
    """pitchmod.code's place: our words, and the stock's addresses as RR and TRIG (pitchmod's hooks unchanged)"""
    import voicefx as V
    assert shift == 0x300 and not (store_pitch or scan or stretch) and lscan is None
    w, labels = V.assemble([*FS.drone_items(), *lfade_items()], at)
    LABELS.update(labels)
    return w, PM.P_EXP, PM.P_START


def strip():
    """from now on pitchmod builds our words; Remix's crossfade on fshape's Y words"""
    import loopxf as XF
    PM.code = code
    for k, name in enumerate(FS.XF_SCRATCH):
        setattr(XF, name, FS.XFS + k)
    XF.XFON = FS.XFB


def arm_code(base, L):
    import loopxf as XF
    a = Asm(base)
    E = a.emit
    O = rhstate.OFF["smswitch"][0]
    O_TH = rhstate.OFF["cthresh"][0] + 1

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, (v >> 16) & 0xFFFF)
    t_def = base
    E(raw, b"".join(v.to_bytes(2, "little") for v in FS.SMDEF) + b"\0\0")
    FS.vl_code(a, E, imm32, L, O, t_def, "sm", FS.SMBLK_OFF, FS.SMBLK_LEN, (FS.SMMARK0, FS.SMMARK1), FS.SM0, FS.NSM, reset=False)

    # ---- c_sww(r0 = word, r1 = core 1's Y address); clobbers r0-r3, r12 (the bl at + 16: upguard's writer)
    a.label("c_sww")
    E(push_list, [4], lr=True)
    E(lsls_imm, 0, 0, 8)
    E(mov_reg, 2, 1)
    E(movw, 1, 0x8000)
    E(raw, h(0x430A))                                      # orrs r2, r1
    E(mov_reg, 1, 0)
    E(movs_imm, 0, 1)
    E(bl, WR16)
    E(pop_list, [4], pc=True)

    # ---- c_swdsp(r0 = track): its switches, its crossfade on / off and the crossfade's length into core 1
    xn, xq = XF.length_words(FS.XF_N)
    a.label("c_swdsp")
    E(push_list, [4, 5], lr=True)
    E(mov_reg, 4, 0)
    E(movs_imm, 1, FS.SM0)
    E(bl, "c_smval")
    E(mov_reg, 5, 0)
    E(movs_imm, 1, FS.SMDEF[0])
    E(eors_reg, 0, 1)
    E(movw, 1, FS.SMF)
    E(adds_reg, 1, 1, 4)
    E(bl, "c_sww")
    E(movs_imm, 0, FS.SM_XF)
    E(raw, h(0x4028))                                      # ands r0, r5
    E(movw, 1, FS.XFB)
    E(adds_reg, 1, 1, 4)
    E(bl, "c_sww")
    for w, at in ((xn, XF.XN), (xq, XF.XQ)):
        E(movw, 0, w)
        E(movw, 1, at)
        E(bl, "c_sww")
    E(pop_list, [4, 5], pc=True)

    # ---- c_swled(r0 = ctrl, r1 = frame): our round, then the chain
    a.label("c_swled")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 1)
    E(bl, "c_swframe")
    E(mov_reg, 0, 4)
    E(mov_reg, 1, 5)
    E(bl, L["prev_led"])
    E(pop_list, [4, 5, 6, 7], pc=True)

    a.label("c_swframe")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(bl, L["c_ciok"])
    E(cmp_imm, 0, 0)
    E(b_cond, "sf_x", "eq")
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    E(b_cond, "sf_x", "eq")
    E(mov_reg, 7, 0)
    E(movw, 1, O)
    E(adds_reg, 6, 0, 1)                                   # r6 = our slot
    E(movw, 1, O_TH)
    E(adds_reg, 1, 7, 1)
    E(ldrb_imm, 1, 1, 0)
    E(movs_imm, 0, 0)
    E(cmp_imm, 1, READY)
    E(b_cond, "sf_all", "ne")                              # not READY: the wait starts again
    E(ldrb_imm, 0, 6, 2)
    E(cmp_imm, 0, SW_WAIT)
    E(b_cond, "sf_go", "hs")
    E(adds_imm8, 0, 1)
    a.label("sf_all")
    E(strb_imm, 0, 6, 2)
    E(movs_imm, 0, 0xFF)
    E(strb_imm, 0, 6, 0)
    E(b, "sf_x")
    a.label("sf_go")
    E(ldrb_imm, 0, 6, 0)
    E(cmp_imm, 0, 0)
    E(b_cond, "sf_rd", "eq")
    E(movs_imm, 4, 0)
    a.label("sf_b")
    E(movs_imm, 1, 1)
    E(lsls_reg, 1, 4)
    E(tst_reg, 0, 1)
    E(b_cond, "sf_f", "ne")
    E(adds_imm8, 4, 1)
    E(b, "sf_b")
    a.label("sf_f")
    E(bics_reg, 0, 1)
    E(strb_imm, 0, 6, 0)
    E(mov_reg, 0, 4)
    E(bl, "c_swdsp")
    E(b, "sf_x")
    a.label("sf_rd")
    E(ldrb_imm, 0, 6, 1)
    E(adds_imm8, 0, 1)
    E(strb_imm, 0, 6, 1)
    E(movs_imm, 1, ROUND - 1)
    E(tst_reg, 0, 1)
    E(b_cond, "sf_x", "ne")
    E(lsrs_imm, 0, 0, 3)
    E(movs_imm, 1, 7)
    E(raw, h(0x4008))                                      # ands r0, r1
    E(bl, "c_swdsp")
    a.label("sf_x")
    E(pop_list, [4, 5, 6, 7], pc=True)
    return a.assemble()


def install(img, report, base_addr):
    """After pitchmod (built after strip(), loopxf=4, load), rhrec, countin, dspready and rhstate; ourram's slot (RH_SMSWITCH=1)."""
    import rhbuild
    import rhdsp1
    import rhrec
    import loopxf as XF
    for need in ("pitchmod", "rhrec", "countin", "cthresh", "rhstate"):
        assert need in report, f"smswitch needs {need}"
    assert PM.code is code and LABELS, "smswitch.strip() before pitchmod"
    assert report["pitchmod"].get("loopxf_v") == 4 and XF.XFON == FS.XFB, "pitchmod with loopxf=4"
    assert int(report["pitchmod"]["y_blocks"], 16) == FS.BLK, "drone: BLK is dspload's counter"
    assert not any(k in report for k in ("stockplus", "pshape", "fshape")), "smswitch replaces fshape's switches"
    assert "smswitch" in rhstate.OFF and "cthresh" in rhstate.OFF, "smswitch needs ourram's slots (RH_SMSWITCH=1)"
    rhrec.check_layout()
    assert all(o + n <= FS.SMBLK_OFF for o, n in rhrec.OFF54.values()) and FS.SMBLK_OFF + FS.SMBLK_LEN <= FS.BLK_OFF
    lab = lambda m, k: int(report[m]["labels"][k], 16)                         # noqa: E731
    prev = rhbuild.bl_target(img, CI.LED_CALLS[0])
    assert all(rhbuild.bl_target(img, c) == prev for c in CI.LED_CALLS)
    L = dict(c_rst=lab("rhstate", "c_rst"), c_rrt=lab("rhrec", "c_rrt"), c_ciok=lab("countin", "c_ciok"), prev_led=prev)
    code_arm, labels = arm_code(base_addr, L)
    img += bytes([0xFF]) * (base_addr - rhbuild.BASE - len(img)) + code_arm
    while len(img) % 4:
        img += bytes([0xFF])
    for c in CI.LED_CALLS:
        rhbuild.patch(img, c, f"bl #{prev:#x}", bl(c, labels["c_swled"]))
    lf, dr, do = LABELS["lfade"], LABELS["drone"], LABELS["droff"]
    rhdsp1.patch_p(img, FS.EF_SITE, FS.EF_OLD[0], 0x0AF080)
    rhdsp1.patch_p(img, FS.EF_SITE + 1, FS.EF_OLD[1], lf)
    rhdsp1.patch_p(img, FS.NOTE_AT, FS.NOTE_OLD[0], 0x0AF080)
    rhdsp1.patch_p(img, FS.NOTE_AT + 1, FS.NOTE_OLD[1], dr)
    rhdsp1.patch_p(img, FS.OFF_AT, FS.OFF_OLD[0], 0x0AF080)
    rhdsp1.patch_p(img, FS.OFF_AT + 1, FS.OFF_OLD[1], do)
    out = {k: hex(v) for k, v in labels.items() if k.startswith("c_")}
    out.update(c_fsval=out["c_smval"], c_fsput=out["c_smput"])
    report["smswitch"] = dict(sm=True, sm0=FS.SM0, smblk_off=FS.SMBLK_OFF, smdefs=list(FS.SMDEF), smf=hex(FS.SMF), loopfade=hex(lf),
                              drone=hex(dr), droff=hex(do), ln=hex(FS.LN), loff=hex(FS.LOFF), blk=hex(FS.BLK), sm_dr=FS.SM_DR,
                              loopxf=True, xfb=hex(FS.XFB), xfs=hex(FS.XFS), xf_n=FS.XF_N,
                              xf_words={k: hex(getattr(XF, k)) for k in FS.XF_SCRATCH},
                              slot=hex(rhstate.ST + rhstate.OFF["smswitch"][0]), prev_led=hex(prev), labels=out)
    return labels, code_arm
