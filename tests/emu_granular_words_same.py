"""Every Granular control's DSP words: random states (all knobs, fine parts, settings bits, Level) through the real frame code of two
builds must send the same words, apart from field 13 bit 15 (Scan home), which must be set exactly when Scan's word is 0, Freeze is
off and no slices are on, and with scan_centre Scan's word, which is 0 for Scan knob 63-65.  Usage: emu_granular_words_same.py BUILD REFERENCE (e.g. a0268 a0266)"""
import os
import random
import struct
import sys
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1

ROOT = Path(__file__).resolve().parents[1]
POOL, HOME, FREEZE_BIT = 0x2400, 1 << 15, 2
PARAMS, CONFIG, LEVEL, FINE = 104, 168, 212, 404      # GRuntime offsets (after GOwner 96 B and GSettingsUi 8 B)


def words(build, states):
    os.environ['RH_BUILD'] = build
    for m in [m for m in sys.modules if m.startswith(('emu_', 'automation_bank_helpers'))]:
        del sys.modules[m]
    sys.argv[1:2] = [build]
    import emu_fx_native_edges as F
    u = F.setup()
    g = F.E.MAN['report']['granular']; K = g['arm_kernel']['labels']
    s = int(g['bridge']['slot'], 16)
    out = {}

    def ret(uc, v=0):
        uc.reg_write(UC_ARM_REG_R0, v); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def dsp(uc, a, n, d):
        out[uc.reg_read(UC_ARM_REG_R0)] = uc.reg_read(UC_ARM_REG_R1); ret(uc)
    u.hook_add(UC_HOOK_CODE, dsp, None, K['c_gr_dsp_write'], K['c_gr_dsp_write'] + 1)
    for at in (K['c_gr_shared_read'], K['c_gr_sample_read'], 0x08040814):
        u.hook_add(UC_HOOK_CODE, lambda uc, a, n, d: ret(uc), None, at, at + 1)
    flags = F.E.u32(u, s + 184); u.mem_write(s + 184, struct.pack('<I', flags | 3))
    result = []
    for params, fine, config, level in states:
        u.mem_write(s + PARAMS, params); u.mem_write(s + FINE, fine)
        u.mem_write(s + CONFIG, config); u.mem_write(s + LEVEL, level)
        frame = []
        for t in range(8):
            out.clear()
            u.mem_write(s + 200, struct.pack('<I', 1 << t))
            F.E.call(u, K['c_gr_runtime_frame'], s, 1, 0)
            frame.append({a - POOL - 256 * t: v for a, v in out.items() if POOL + 256 * t <= a < POOL + 256 * t + 16})
        result.append(frame)
    return result, g


def main():
    build, ref = sys.argv[1:3]
    rng = random.Random(268)
    states = []
    for _ in range(300):
        params = bytes(rng.choice((0, 63, 64, 65, 127, rng.randrange(128))) for _ in range(64))
        fine = bytes(rng.choice((0, 0, rng.randrange(16))) for _ in range(64))
        config = bytes(rng.randrange(256) & ~3 for _ in range(8))      # mode bits 0-1 stay off: no ownership change
        level = bytes(rng.randrange(128) for _ in range(8))
        states.append((params, fine, config, level))
    new, g = words(build, states)
    old, _ = words(ref, states)
    home_seen = away_seen = centre_seen = 0
    for k, (a, b) in enumerate(zip(new, old)):
        for t in range(8):
            wa, wb = a[t], b[t]
            assert set(wa) == set(wb) == {1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14}, (k, t, sorted(wa), sorted(wb))
            for f in wa:
                x, y = wa[f], wb[f]
                if f == 13 and g.get('scan_home'):
                    home = bool(x & HOME)
                    want = wa[6] == 0 and not (x & FREEZE_BIT) and not (wa[7] >> 8 & 0x1f)
                    assert home == want, (k, t, hex(x), hex(wa[6]), hex(wa[7]))
                    home_seen += home; away_seen += not home
                    x &= ~HOME
                if f == 6 and g.get('scan_centre') and 63 <= states[k][0][8 * t + 3] <= 65:
                    assert x == 0, (k, t, hex(x), states[k][0][8 * t + 3], states[k][1][8 * t + 3])
                    centre_seen += y != 0
                    continue
                assert x == y, (k, t, f, hex(x), hex(y))
    print(f'PASS 300 random states x 8 tracks: all 13 control words of every track equal {ref}' +
          (f'; Scan home set in {home_seen} cases, exactly when Scan is 0, Freeze off and no slices ({away_seen} not)' if g.get('scan_home') else '') +
          (f'; Scan knob 63-65 sends 0 ({centre_seen} cases that {ref} sent off centre)' if g.get('scan_centre') else ''))
    print('ALL PASS')


if __name__ == '__main__':
    main()
