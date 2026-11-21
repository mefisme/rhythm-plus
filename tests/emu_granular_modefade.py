"""Turning Granular off, or Textured to Triggered, while its note sounds: the order of the route write and the stop.

The plain voice stays paused at its start while Granular owns the track. With mode_fade the stop comes first and the route goes
back only once the voice is quiet; without it the route goes back first (the plain sample's start is heard until the stop fades).
Usage: emu_granular_modefade.py BUILD
"""
import struct
import emu_fx_native_edges as F
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1

G, E = F.G, F.E
CONTROL, SNAPSHOT = 0x37400, 0x37420
ACTIVE, INACTIVE, IDLE_ACK = 0x674132, 0x674531, 0x674732
OFF, TRIGGERED, TEXTURE, QUIET = 0, 1, 2, 1
STOP = 0x08040814


def main():
    u = F.setup()
    g = E.MAN['report']['granular']; K = g['arm_kernel']['labels']
    s = int(g['bridge']['slot'], 16)
    fade = bool(g.get('mode_fade'))
    events, snap = [], {}

    def ret(uc, v=0):
        uc.reg_write(UC_ARM_REG_R0, v); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def dsp(uc, a, n, d):
        events.append(('w', uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1))); ret(uc)

    def shared(uc, a, n, d):
        ret(uc, snap.get(uc.reg_read(UC_ARM_REG_R0), 0))

    def stop(uc, a, n, d):
        events.append(('stop', uc.reg_read(UC_ARM_REG_R0))); ret(uc)
    for at, fn in ((K['c_gr_dsp_write'], dsp), (K['c_gr_shared_read'], shared), (STOP, stop)):
        u.hook_add(UC_HOOK_CODE, fn, None, at, at + 1)
    u.hook_add(UC_HOOK_CODE, lambda uc, a, n, d: ret(uc), None, K['c_gr_sample_read'], K['c_gr_sample_read'] + 1)

    def owner(t):
        epoch, note, mode, wanted, phase, settings = struct.unpack_from('<IIBBBB', u.mem_read(s + 12 * t, 12))
        return epoch, mode, wanted, phase

    def frame():
        events.clear(); E.call(u, K['c_gr_runtime_frame'], s, 1, 0)
        return list(events)

    def sounding(t, mode):
        """track t owned by Granular in mode, its note sounding, the DSP on the owner's epoch"""
        epoch = 40 + t
        u.mem_write(s + 12 * t, struct.pack('<IIBBBB', epoch, 0, mode, mode, 0, 1))
        u.mem_write(s + 168 + t, bytes([mode]))
        u.mem_write(s + 469, bytes(3))                                      # GL and its time: nothing fading
        snap.update({SNAPSHOT + 8 * t: ACTIVE, SNAPSHOT + 8 * t + 1: epoch, SNAPSHOT + 8 * t + 2: 1})

    flags = E.u32(u, s + 184); u.mem_write(s + 184, struct.pack('<I', flags | 3))
    for name, t, before, after in (('Granular off', 0, TEXTURE, OFF), ('Textured to Triggered', 1, TEXTURE, TRIGGERED),
                                   ('Triggered to Textured', 2, TRIGGERED, TEXTURE)):
        sounding(t, before)
        u.mem_write(s + 168 + t, bytes([after]))
        first = frame()
        route_off = [i for i, e in enumerate(first) if e == ('w', CONTROL + 4 * t, 0)]
        stops = [i for i, e in enumerate(first) if e == ('stop', t)]
        assert stops, (name, first)
        epoch, mode, wanted, phase = owner(t)
        assert (mode, wanted, phase) == (before, after, QUIET), (name, owner(t))
        if not fade:
            assert route_off and route_off[0] < stops[0], (name, first)
            print(f'NOTE {name}: the route goes back to the plain sample before the stop (the plain start is heard)')
            continue
        assert not route_off, (name, first)
        assert not frame() or not any(e == ('w', CONTROL + 4 * t, 0) for e in events), 'route back while the voice sounds'
        print(f'PASS {name}: the stop comes first; the route stays while the note sounds')
        snap[SNAPSHOT + 8 * t] = INACTIVE
        back = frame()
        assert ('w', CONTROL + 4 * t, 0) in back, (name, back)
        new_epoch = owner(t)[0]
        assert ('w', CONTROL + 4 * t + 1, new_epoch) in back and back.index(('w', CONTROL + 4 * t, 0)) < back.index(('w', CONTROL + 4 * t + 1, new_epoch))
        print(f'PASS {name}: once the voice is quiet, the route goes back, then the new epoch')
        snap.update({SNAPSHOT + 8 * t: IDLE_ACK, SNAPSHOT + 8 * t + 1: new_epoch})
        frame()
        epoch, mode, wanted, phase = owner(t)
        assert (mode, phase) == (after, 0), (name, owner(t))
        print(f'PASS {name}: the new mode applies after the idle acknowledgement')
    print('ALL PASS')


if __name__ == '__main__':
    main()
