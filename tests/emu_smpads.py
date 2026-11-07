"""Unicorn test of smpads.py on a build with it (RH_BUILD) and the RAM dump: Clear + pad 1 / 2 sets the pitch to 64 and the stock's
«applied» to none without the stock's fit; without Clear, and every other pad, the stock's handler.  A build with smpads' sm: pad 21
and its other pads (19, 20) turn the selected track's switches on / off (fshape's value 29, its block "SM" in the record), their LEDs in
Sample mode, the core 1 word.

    python tests/emu_smpads.py STOCK.bin BUILT.bin RAM.bin
"""
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("RH_BUILD", Path(sys.argv[2]).parent.name if len(sys.argv) > 2 else "a0063")
import emu_tmenu as ET  # noqa: E402  (ourram's layout from the build's manifest)
import smpads as M  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1  # noqa: E402

check, u32, call = ET.check, ET.u32, ET.call
SUB0, SUB_STRIDE = 0x2004D36C, 0x64
FIT0, FIT_STRIDE = 0x200469CC, 0xB4
STOCK_PADS, UNAPPLIED = [], []


def param(uc, t, store_off, i=0):
    call(uc, M.GET, u32(uc, FIT0 + FIT_STRIDE * t + store_off), i)
    return uc.reg_read(UC_ARM_REG_R0)


def pitch(uc, t): return uc.mem_read(param(uc, t, M.F_TRACK), 1)[0]
def setpitch(uc, t, p): uc.mem_write(param(uc, t, M.F_TRACK), bytes([p]))


def clear(uc, on):
    a = ET.C.CTRL + M.O_HELD
    w = u32(uc, a)
    uc.mem_write(a, struct.pack("<I", w | 1 << M.BIT_CLEAR if on else w & ~(1 << M.BIT_CLEAR)))


def pad(uc, t, i):
    STOCK_PADS.clear()
    UNAPPLIED.clear()
    call(uc, u32(uc, M.SMP_VT) & ~1, SUB0 + SUB_STRIDE * t, i, 100)


def setup(fw, ram):
    uc = ET.setup(fw, ram)
    uc.reg_write(UC_ARM_REG_C1_C0_2, uc.reg_read(UC_ARM_REG_C1_C0_2) | 0xF00000)   # the FPU (the stock's fit code uses it)
    uc.reg_write(UC_ARM_REG_FPEXC, 0x40000000)

    def stock_pad(u, a, n, d):
        STOCK_PADS.append(u.reg_read(UC_ARM_REG_R1))
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, stock_pad, None, M.SMP_PAD, M.SMP_PAD + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: UNAPPLIED.append(u.reg_read(UC_ARM_REG_R0)), None, M.UNAPPLY, M.UNAPPLY + 1)
    return uc


def smval(uc, t):
    call(uc, int(ET.MAN["report"]["fshape"]["labels"]["c_fsval"], 16), t, ET.MAN["report"]["fshape"]["sm0"])
    return uc.reg_read(UC_ARM_REG_R0)


def sm_checks(uc):
    import fshape as FS
    rep = ET.MAN["report"]
    lab = lambda m, k: int(rep[m]["labels"][k], 16)  # noqa: E731
    pads = {int(k): v for k, v in rep["smpads"]["pads"].items()}
    names = {FS.SM_XF: "loop crossfade", FS.SM_RD: "retrigger de-click", FS.SM_EF: "end fade", FS.SM_DR: "drone mode"}
    call(uc, M.SELTRK, M.CONT)
    t = uc.reg_read(UC_ARM_REG_R0)
    o = 1 if t != 1 else 2
    v0 = [smval(uc, k) for k in range(8)]
    check(f"sm: every track starts with the defaults ({FS.SMDEF[0]}: crossfade off, de-click on, end fade on)", v0 == [FS.SMDEF[0]] * 8, v0)
    cv, cm = ET.C.CTRL + M.O_VIEW, M.CONT + M.O_MODE
    view0, mode0 = u32(uc, cv), uc.mem_read(cm, 1)[0]
    col = lambda off: struct.unpack("<H", uc.mem_read(M.PAL + off, 2))[0]  # noqa: E731
    slot = rhstate_slot()
    for pd, bit in pads.items():
        nm = names[bit]
        uc.mem_write(slot, b"\0")
        pad(uc, t, pd)
        v = smval(uc, t)
        check(f"sm: pad {pd + 1} turns track {t + 1}'s {nm} {'off' if FS.SMDEF[0] & bit else 'on'}, not the stock's handler, other tracks and switches kept",
              v == FS.SMDEF[0] ^ bit and STOCK_PADS == [] and smval(uc, o) == FS.SMDEF[0], (v, STOCK_PADS))
        call(uc, lab("rhrec", "c_rrt"))
        blk = uc.reg_read(UC_ARM_REG_R0) + FS.SMBLK_OFF
        data = bytes(uc.mem_read(blk, FS.SMBLK_LEN))
        body = data[4:]
        check(f"sm: pad {pd + 1}: the record's block \"SM\", its check byte, the change from the defaults",
              data[:2] == b"SM" and data[2] == (sum(body) & 0xFF) ^ FS.CHECK and struct.unpack("<8H", body) == tuple(bit if k == t else 0 for k in range(8)),
              data.hex())
        check(f"sm: pad {pd + 1}: track {t + 1} marked to write", uc.mem_read(slot, 1)[0] >> t & 1 == 1, uc.mem_read(slot, 1)[0])
        uc.mem_write(cv, struct.pack("<I", M.CONT))
        uc.mem_write(cm, bytes([M.MODE_SMP]))
        f = ET.led(uc, lab("smpads", "c_smled"))
        lit = {q: f[q] == col(M.PAL_ON if v & b2 else M.PAL_OFF) for q, b2 in pads.items()}
        check(f"sm: Sample mode: pads {', '.join(str(q + 1) for q in pads)} in the stock's chosen / not chosen colours", all(lit.values()),
              {q + 1: hex(f[q]) for q in pads})
        pad(uc, t, pd)
        f = ET.led(uc, lab("smpads", "c_smled"))
        check(f"sm: pad {pd + 1} again: back to the defaults, its colour {'chosen' if FS.SMDEF[0] & bit else 'not chosen'}",
              smval(uc, t) == FS.SMDEF[0] and f[pd] == col(M.PAL_ON if FS.SMDEF[0] & bit else M.PAL_OFF), (smval(uc, t), hex(f[pd])))
        uc.mem_write(cv, struct.pack("<I", view0))
        uc.mem_write(cm, bytes([mode0]))
    uc.mem_write(cv, struct.pack("<I", M.CONT))
    uc.mem_write(cm, bytes([mode0 if mode0 != M.MODE_SMP else 0]))
    f2 = ET.led(uc, lab("smpads", "c_smled"))
    f3 = ET.led(uc, int(rep["smpads"]["prev_led"], 16))
    uc.mem_write(cv, struct.pack("<I", view0))
    uc.mem_write(cm, bytes([mode0]))
    check("sm: not Sample mode: the frame as the rest of the chain drew it", f2 == f3)
    for q in range(17, 22):
        if q not in pads and q != 21:
            pad(uc, t, q)
            check(f"sm: pad {q + 1}: the stock's", STOCK_PADS == [q] and smval(uc, t) == FS.SMDEF[0], (STOCK_PADS, smval(uc, t)))
    words = []
    spw = lab("stockplus", "c_spw")

    def hook(u, a, n, d):
        words.append((u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1)))
    h = uc.hook_add(UC_HOOK_CODE, hook, None, spw, spw + 1)
    for flags in (FS.SMDEF[0], FS.SM_RD, 0, 7, FS.SMDEF[0] | FS.SM_DR):
        call(uc, int(rep["fshape"]["labels"]["c_fsput"], 16), t, rep["fshape"]["sm0"], flags)
        words.clear()
        call(uc, lab("fshape", "c_fldsp"), t)
        got = [w for w, a in words if a == FS.SMF + t]
        check(f"sm: c_fldsp writes track {t + 1}'s switches {flags} XOR the defaults ({flags ^ FS.SMDEF[0]}) to core 1 Y:${FS.SMF + t:X}",
              got == [flags ^ FS.SMDEF[0]], got)
        if rep["fshape"].get("loopxf"):
            xfb, xw = int(rep["fshape"]["xfb"], 16), {k: int(v, 16) for k, v in rep["fshape"]["xf_words"].items()}
            on = [w for w, a in words if a == xfb + t]
            ln = [(w, a) for w, a in words if a in (xw["XN"], xw["XQ"])]
            check(f"sm: c_fldsp writes the crossfade {'on' if flags & 1 else 'off'} to Y:${xfb + t:X}, its length 256 (step $8000)",
                  on == [flags & 1] and ln == [(256, xw["XN"]), (0x8000, xw["XQ"])], (on, ln))
    uc.hook_del(h)
    call(uc, int(rep["fshape"]["labels"]["c_fsput"], 16), t, rep["fshape"]["sm0"], FS.SMDEF[0])


def rhstate_slot():
    import rhstate
    return rhstate.ST + rhstate.OFF["fshape"][0]


def main():
    stock, fw, ram = (open(p, "rb").read() for p in sys.argv[1:4])
    uc = setup(fw, ram)
    t = ET.sel(uc)
    fit = FIT0 + FIT_STRIDE * t
    check("Sample mode's slot 0 is ours", u32(uc, M.SMP_VT) & ~1 != M.SMP_PAD)
    for i in (M.PAD_FIT0, M.PAD_FIT1):
        setpitch(uc, t, 70)
        pad(uc, t, i)
        check(f"pad {i + 1} without Clear: the stock's, pitch kept", STOCK_PADS == [i] and pitch(uc, t) == 70 and not UNAPPLIED,
              (STOCK_PADS, pitch(uc, t), UNAPPLIED))
        clear(uc, True)
        pad(uc, t, i)
        clear(uc, False)
        check(f"Clear + pad {i + 1}: pitch 64, «applied» to none, not the stock's", STOCK_PADS == [] and pitch(uc, t) == 64
              and set(UNAPPLIED) == {fit}, (STOCK_PADS, pitch(uc, t), UNAPPLIED))
    clear(uc, True)
    pad(uc, t, M.PAD_FIT0)
    clear(uc, False)
    check("Clear + pad 1 at pitch 64: pitch kept, «applied» to none", pitch(uc, t) == 64 and UNAPPLIED == [fit] and STOCK_PADS == [])
    setpitch(uc, t, 70)
    for i in (2, 7, 8, 9, 14, 15, 31):
        for held in (False, True):
            clear(uc, held)
            pad(uc, t, i)
            check(f"pad {i + 1}{' with Clear' if held else ''}: the stock's, pitch kept", STOCK_PADS == [i] and pitch(uc, t) == 70
                  and not UNAPPLIED, (STOCK_PADS, pitch(uc, t)))
    clear(uc, False)
    if ET.MAN["report"]["smpads"].get("sm"):
        sm_checks(uc)
    print("ALL PASS" if not ET.FAILS else f"{len(ET.FAILS)} FAIL")
    if ET.FAILS:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
