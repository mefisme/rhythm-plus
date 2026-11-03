"""Unicorn test of smpads.py on a build with it (RH_BUILD) and the RAM dump: Clear + pad 1 / 2 sets the pitch to 64 and the stock's
«applied» to none without the stock's fit; without Clear, and every other pad, the stock's handler.

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
    print("ALL PASS" if not ET.FAILS else f"{len(ET.FAILS)} FAIL")
    if ET.FAILS:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
