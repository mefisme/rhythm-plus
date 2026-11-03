"""Regression for the A0040 device failure: sound reset but knobs resumed old values.

Seed by actual stock knob turns. Compare view values and the next turn with the
stock's own Clear + right reset, not just the engine getter used by older tests.
"""
from pathlib import Path
import sys
import emu_tmenu as E


def main():
    stock, fw, ram = (Path(p).read_bytes() for p in sys.argv[1:4])
    reset = int(E.MAN['report']['pageclear']['labels']['c_pcstock'], 16)
    default_table = int(E.MAN['report']['pageclear']['default_table'], 16) - 0x08010000
    defaults = list(stock[default_table + 6:default_table + 16])
    for k in range(8):
        uc, ref = E.setup(fw, ram), E.setup(stock, ram, False)
        t = E.sel(uc)
        # Same real knob movement in both images; no direct writes to its values.
        delta = -17 if defaults[k] == 127 else 17
        sub = []
        hook = ref.hook_add(E.UC_HOOK_CODE, lambda u, a, n, d: sub.append(u.reg_read(E.UC_ARM_REG_R0)), None, 0x08058160, 0x08058161)
        E.knob(ref, k, delta); E.knob(uc, k, delta)
        ref.hook_del(hook)
        old = E.kval(uc, t, k)
        view = sub[0]
        flag = E.ptr(ref, E.u32(ref, view + 0x20), 0)
        ref.mem_write(flag, b'\x01')
        for _ in range(40): E.knob(ref, k, 1)
        ref.mem_write(flag, b'\0')
        E.call(ref, 0x0805862C, view)  # stock Clear-release count/LED refresh
        E.call(uc, reset, t)
        expected = E.kval(ref, t, k)
        E.check(f'K{k+1}: control value resets from {old} to stock default {expected}', E.kval(uc, t, k) == expected, E.kval(uc, t, k))
        E.led(uc, E.rhbuild.bl_target(bytearray(fw), E.C.LED_CALLS[0]))
        E.led(ref, E.rhbuild.bl_target(bytearray(stock), E.C.LED_CALLS[0]))
        rgb = E.out(uc, E.rhbuild.bl_target(bytearray(fw), E.T.OUT_CALL))[60+k]
        ref_rgb = E.out(ref, E.rhbuild.bl_target(bytearray(stock), E.T.OUT_CALL))[60+k]
        E.check(f'K{k+1}: reset LED matches stock reset', rgb == ref_rgb, (hex(rgb), hex(ref_rgb)))
        step = -1 if expected == 127 else 1
        E.knob(ref, k, step); E.knob(uc, k, step)
        E.check(f'K{k+1}: next click starts at reset position, as stock', E.kval(uc, t, k) == E.kval(ref, t, k), (E.kval(uc, t, k), E.kval(ref, t, k)))
        if k in (1, 2):
            fine = E.T.FINE[k]
            E.check(f'K{k+1}: fine position also matches stock', E.kval(uc, t, fine) == E.kval(ref, t, fine))
    # Confirmed track reset must also restore mixer/send control stores.
    uc = E.setup(fw, ram)
    t = E.sel(uc)
    head = E.rhbuild.bl_target(bytearray(fw), E.C.LED_CALLS[0])
    ids = ((16, 0x91), (17, 0x99), (18, 0x80), (19, 0x88))
    def engine(index, value): E.call(uc, 0x08031A38, 0x20010E10, 0x10+t, index, value)
    def control(index, value): E.call(uc, 0x08038A08, 0x20011998, index+t, value)
    def read(index):
        offsets = {0x91:0x2c, 0x99:0x30, 0x80:0x20, 0x88:0x24}
        st = E.u32(uc, 0x20011998 + offsets[index])
        return uc.mem_read(E.ptr(uc, st, t), 1)[0]
    baseline = (73, 49, 11, 23)
    for (p, gid), val in zip(ids, baseline): engine(p, val); control(gid, val)
    E.led(uc, head)
    for p, gid in ids: engine(p, 37); control(gid, 37)
    E.knob(uc, 4, 30)
    held = E.u32(uc, E.C.CTRL + 0xA0)
    import struct
    uc.mem_write(E.C.CTRL + 0xA0, struct.pack('<I', held | (1 << 23)))
    E.press(uc, t); E.release(uc, t); E.press(uc, t); E.release(uc, t)
    E.check('confirmed reset updates stock knob control value', E.kval(uc, t, 4) == defaults[4], E.kval(uc, t, 4))
    E.check('confirmed reset updates level/pan/send controls to load snapshot', tuple(read(gid) for _, gid in ids) == baseline, tuple(read(gid) for _, gid in ids))
    print('ALL PASS' if not E.FAILS else f'{len(E.FAILS)} FAILED')
    if E.FAILS: raise SystemExit(1)


if __name__ == '__main__': main()
