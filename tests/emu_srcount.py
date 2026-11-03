"""Unicorn test of srcount.py on the RAM dump (the view set to the Sample Rec view's object, the sampler ready).
    python tests/emu_srcount.py STOCK.bin BUILT.bin RAM.bin
Pads 23 / 24 (their states and LEDs; the other pads reach the stock) and every case that leaves Record to the stock.  The count itself
is clkci's (tests/emu_clkci.py, which uses setup() here).  The hooked record function arms the sampler (state 2).
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import emu_countin as E  # noqa: E402  (ourram first, then countin)
import countin as C  # noqa: E402
import clkci as K  # noqa: E402
import srcount as S  # noqa: E402
from emu_playfix import call, machine  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1  # noqa: E402

SR_VIEW, MGR = 0x2004DC90, 0x20048B9C
BLK = S.rhstate.ST
check, u32, w32, setp, tick, FRAME = E.check, E.u32, E.w32, E.setp, E.tick, E.FRAME


def sampler_state(uc, v): setp(uc, u32(uc, S.SAMPLER + S.O_SSTATE), 0, v)
def pad(uc, i): call(uc, u32(uc, S.ROW_VT), S.ROW, i)
def row_led(uc, i): return struct.unpack("<H", uc.mem_read(u32(uc, u32(uc, S.ROW + 4)) + 2 * i, 2))[0]
def frame(uc, led): return struct.unpack("<H", uc.mem_read(FRAME + 2 * led, 2))[0]


def setup(fw, ram, mode=1, play=0, view=SR_VIEW, state=1):
    uc, log = E.setup(fw, ram, True)
    log.rowpress, log.rec, log.rec_before = [], [], []
    uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: (log.rowpress.append(u.reg_read(UC_ARM_REG_R1)),
                                                  u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))), None, S.ROW_PRESS, S.ROW_PRESS + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: (log.rec.append((u32(u, C.HAL_TICK), u.reg_read(UC_ARM_REG_R0))),
                                                  log.rec_before.append(len(log.press)), sampler_state(u, 2),
                                                  u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))), None, S.REC_FN, S.REC_FN + 1)
    w32(uc, C.CTRL + 0x7C, view)
    sampler_state(uc, state)
    setp(uc, C.TRANSPORT, 0, 0)
    uc.mem_write(BLK + S.O_MODE, bytes([mode, play]))
    beat = 60000 // max(E.newest(uc, C.TEMPO, 0), 30)
    return uc, log, beat


def main():
    stock, fw, ram = (open(p, "rb").read() for p in sys.argv[1:4])

    uc, log, beat = setup(fw, ram, mode=0)
    seen = []
    for _ in range(4):
        pad(uc, S.PAD_MODE)
        seen.append(uc.mem_read(BLK + S.O_MODE, 1)[0])
    check("pad 23: off -> on -> off -> on -> off", seen == [1, 0, 1, 0], f"{seen}")
    pad(uc, S.PAD_PLAY)
    on = uc.mem_read(BLK + S.O_PLAY, 1)[0]
    pad(uc, S.PAD_PLAY)
    check("pad 24: on, off", on == 1 and uc.mem_read(BLK + S.O_PLAY, 1)[0] == 0)
    for i in range(6):
        pad(uc, i)
    check("pads 17-22: the stock's, same index", log.rowpress == list(range(6)), f"{log.rowpress}")
    for mode, play in ((0, 0), (1, 1), (1, 0)):
        uc.mem_write(BLK + S.O_MODE, bytes([mode, play]))
        tick(uc, 10000)
        E.led(uc)
        check(f"LEDs: pad 23 state {mode}, pad 24 {'on' if play else 'off'}",
              row_led(uc, S.PAD_MODE) == S.MODE_COLS[mode] and row_led(uc, S.PAD_PLAY) == S.PLAY_COLS[play])

    for name, kw, shift in (("pad 23 off", dict(mode=0), 0), ("a step view", dict(view=MGR), 0), ("sampler recording", dict(state=3), 0),
                            ("sampler armed", dict(state=2), 0), ("Shift held", {}, 1)):
        uc, log, beat = setup(fw, ram, **kw)
        setp(uc, E.shift_store(uc), 0, shift)
        E.press(uc, S.ID_REC)
        check(f"{name}: Record straight to the stock", [p[1] for p in log.press] == [S.ID_REC] and uc.mem_read(BLK + K.O_FL, 1)[0] == 0)

    uc, log, beat = setup(fw, ram)
    E.press(uc, C.ID_PLAY)
    check("Play in the Sample Rec view: as before (to the stock)", [p[1] for p in log.press] == [C.ID_PLAY])

    uc = machine(fw, ram)
    lg = E.Log(uc, True)
    lg.rowpress = []
    uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: (lg.rowpress.append(u.reg_read(UC_ARM_REG_R1)),
                                                  u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))), None, S.ROW_PRESS, S.ROW_PRESS + 1)
    tick(uc, 10000)
    w32(uc, S.rhstate.HEAP_LIMIT_PTR, 0x20000000)      # c_rst cannot reserve the block
    w32(uc, C.CTRL + 0x7C, SR_VIEW)
    pad(uc, S.PAD_MODE)
    check("no block: pad 23 to the stock", lg.rowpress == [S.PAD_MODE])
    E.press(uc, S.ID_REC)
    check("no block: Record to the stock", [p[1] for p in lg.press] == [S.ID_REC])

    print("ALL PASS" if not E.fails else f"{len(E.fails)} FAILED")
    sys.exit(1 if E.fails else 0)


if __name__ == "__main__":
    main()
