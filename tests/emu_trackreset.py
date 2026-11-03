"""A0040: protected two-press track reset, snapshot lifecycle and pattern boundaries."""
from pathlib import Path
import sys
import struct
import emu_tmenu as E


def main():
    stock, fw, ram = (Path(p).read_bytes() for p in sys.argv[1:4])
    report = E.MAN['report']['trackreset']
    slot = int(report['slot'], 16)
    labs = {k: int(v, 16) for k, v in report['labels'].items()}
    head = E.rhbuild.bl_target(bytearray(fw), E.C.LED_CALLS[0])
    outhead = E.rhbuild.bl_target(bytearray(fw), E.T.OUT_CALL)
    uc = E.setup(fw, ram)
    from unicorn.arm_const import UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC
    uc.reg_write(UC_ARM_REG_C1_C0_2, uc.reg_read(UC_ARM_REG_C1_C0_2) | 0xF00000)
    uc.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
    selected = E.sel(uc)
    target = (selected + 1) % 8
    def led(): return E.led(uc, head)
    def rgb(): return E.out(uc, outhead)
    def clear(on):
        p = E.C.CTRL + 0xA0
        v = E.u32(uc, p)
        uc.mem_write(p, struct.pack('<I', v | (1 << 23) if on else v & ~(1 << 23)))
    def tap(t): E.press(uc, t); E.release(uc, t)
    def armed(): return uc.mem_read(slot + 1, 1)[0]
    def vals(t):
        v = []
        for i in range(25):
            E.call(uc, 0x08046410, t + 0x10, i)
            v.append(uc.reg_read(E.UC_ARM_REG_R0) & 255)
        return v
    def setv(t, i, v): E.call(uc, 0x08031A38, 0x20010E10, t + 0x10, i, v)
    def smpptr(t):
        E.call(uc, labs['c_trsample'], t)
        return uc.reg_read(E.UC_ARM_REG_R0)
    def smp(t):
        return uc.mem_read(E.ptr(uc, smpptr(t), 0), 1)[0]
    def setsmp(t, value):
        st = smpptr(t)
        E.call(uc, 0x0803FD26, st, 0)
        uc.mem_write(uc.reg_read(E.UC_ARM_REG_R0), bytes([value]))
        E.call(uc, 0x0803FBEC, st)
    def sp(t): return [E.spval(uc, t, k) for k in range(12)]
    def changed():
        for i in range(25): setv(target, i, 19 if i not in (0, 1, 2, 3, 4, 5, 20) else 1)
        setsmp(target, (baseline_sample + 1) % 64)
        for k in range(12): E.call(uc, E.SPL['c_spput'], target, k, 2048)
    led()  # Snapshot after the real LED chain, as on the unit.
    baseline, baseline_sample = vals(target), smp(target)
    E.check('snapshot taken at first LED frame', uc.mem_read(slot, 1)[0] == 0xC3)
    changed()
    before, before_sample, before_sp = vals(target), smp(target), sp(target)
    rec = E.u32(uc, E.T.AUTO + E.T.AUTO_RECS + 4 * target)
    pats = E.u32(uc, rec + 4)
    pat = uc.mem_read(E.ptr(uc, E.u32(uc, rec + 0x28), 0), 1)[0]
    lanes = pats + pat * E.T.PAT_SIZE + E.T.LANES
    uc.mem_write(lanes, bytes([39]) * (12 * E.T.LANE_SIZE))
    all_before = bytes(uc.mem_read(pats, 8 * E.T.PAT_SIZE))
    othertrack = vals(selected), smp(selected), sp(selected)
    clear(True); E.press(uc, target)
    E.check('first press arms target without any value or automation change', armed() == target + 1 and vals(target) == before and smp(target) == before_sample and sp(target) == before_sp and bytes(uc.mem_read(pats, 8 * E.T.PAT_SIZE)) == all_before)
    E.check('armed target number solid red', rgb()[32 + target] == E.clear_red(uc))
    E.press(uc, target)
    E.check('duplicate press while still held cannot confirm', vals(target) == before and armed() == target + 1)
    E.release(uc, target)
    clear(False); E.release(uc, 23)
    E.check('Clear release cancels before another frame', armed() == 0)
    clear(True); tap(target)
    E.press(uc, 16)
    E.check('another button cancels', armed() == 0 and vals(target) == before)
    E.release(uc, 16)
    clear(True); tap(target)
    E.pad(uc, 0); E.unpad(uc, 0)
    E.check('pad press cancels', armed() == 0 and vals(target) == before)
    clear(True); tap(target); tap(selected)
    E.check('different track cancels without resetting either track', armed() == 0 and vals(target) == before and vals(selected) == othertrack[0], (armed(), vals(selected), othertrack[0]))
    # Whole-lane clearing must hold even when the recorder thinks a step is held.
    hp = E.ptr(uc, E.u32(uc, rec + 0x40), 0)
    uc.mem_write(hp, b'\x01')
    clear(True); tap(target); E.press(uc, target)
    E.check('second released-and-pressed track confirms', armed() == 0 and uc.mem_read(slot + 3, 1)[0] == target + 1)
    actual = vals(target)
    E.check('non-knob settings restored to project-load snapshot', actual[:6] + actual[16:] == baseline[:6] + baseline[16:], (actual, baseline))
    defaults = list(fw[0x0806900C - 0x08010000 + 6:0x0806900C - 0x08010000 + 16])
    E.check('stock knobs and fine values use normal defaults', actual[6:16] == defaults, (actual[6:16], defaults))
    E.check('sample selection restored to project-load snapshot', smp(target) == baseline_sample)
    pv = E.MAN['report']['pageclear'].get('page_values', [[0, 1, 2, 3, 11, 7], [10, 5, 9, 4, 8]])
    reset = set(pv[0]) | set(pv[1])
    E.check(f'all {len(reset)} Stock+ controls of the pages use feature defaults', [v for i, v in enumerate(sp(target)) if i in reset] == [v for i, v in enumerate(E.DEFS) if i in reset], sp(target))
    E.check('all 12 stock lanes cleared in current pattern', bytes(uc.mem_read(lanes, 12 * E.T.LANE_SIZE)) == bytes([255]) * (12 * E.T.LANE_SIZE))
    expected = bytearray(all_before)
    at = pat * E.T.PAT_SIZE + E.T.LANES
    expected[at:at + 12 * E.T.LANE_SIZE] = bytes([255]) * (12 * E.T.LANE_SIZE)
    E.check('notes, sample flips and every other pattern unchanged', bytes(uc.mem_read(pats, 8 * E.T.PAT_SIZE)) == expected)
    E.check('other track values and sample unchanged', (vals(selected), smp(selected), sp(selected)) == othertrack, ((vals(selected), smp(selected), sp(selected)), othertrack))
    E.check('held-step flag restored', uc.mem_read(hp, 1)[0] == 1)
    seen = []
    for _ in range(6): seen.append(rgb()[32 + target]); E.tick(uc, 64)
    E.check('confirmed reset flashes red three times', seen == [E.clear_red(uc), 0] * 3, seen)
    end = rgb()[32 + target]
    E.check('feedback ends in target track colour', end == E.u32(uc, E.T.COLOURS + 4 * E.T.TRK_SLOTS[target]), hex(end))
    E.release(uc, target)
    # New load invalidates both snapshot and arm, then captures new settings.
    clear(True); tap(target)
    newbase = vals(target)
    newbase[16] = 37
    setv(target, 16, 37)
    # Stub only the original tail's resend; execute our real invalidation wrapper.
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR
    hook = uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)), None, 0x08031A10, 0x08031A11)
    E.call(uc, labs['c_trload'])
    uc.hook_del(hook)
    E.check('project load invalidates old snapshot and cancels arm', armed() == 0 and uc.mem_read(slot, 1)[0] == 0)
    led(); setv(target, 16, 53)
    E.call(uc, labs['c_trreset'], target)
    E.check('reset after load uses new baseline', vals(target)[16] == 37)
    clear(False)
    E.tap(uc, E.sel(uc)); led()
    menu = E.b8(uc, E.T.O_OPEN)
    setv(target, 16, 61)
    clear(True); tap(target)
    E.check('Track + open: first press arms without resetting or closing menu', menu == 1 and E.b8(uc, E.T.O_OPEN) == 1 and vals(target)[16] == 61)
    tap(target)
    E.check('Track + open: confirmed reset keeps menu open', E.b8(uc, E.T.O_OPEN) == 1 and vals(target)[16] == 37)
    print('ALL PASS'  if not E.FAILS else f'{len(E.FAILS)} FAILED')
    if E.FAILS: raise SystemExit(1)


if __name__ == '__main__': main()
