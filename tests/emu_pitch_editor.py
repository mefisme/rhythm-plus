"""Exercise Pitch editor gestures, automation, companion settings and DSP writes."""

import struct

import emu_fx_native_edges as fixture
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

G, E, SM = fixture.G, fixture.E, fixture.SM


def main():
    u = fixture.setup()
    report = E.MAN['report']
    granular = report['granular']
    pitch = report['pitch_envelope_dsp']
    pad = pitch['editor_pad'] - 1
    slot = int(granular['bridge']['slot'], 16)
    menu = int(granular['ui']['menu'], 16)
    labels = granular['arm_kernel']['labels']
    values = pitch['settings_itcm_start']
    settings = 0x20001000
    SM.sel(u, 0)
    u.mem_write(menu + E.T.O_OPEN, b'\1')
    u.mem_write(G.CONT + 0x264, b'\0')

    def call(name, *args):
        E.call(u, labels['c_gr_' + name], *args)
        return u.reg_read(UC_ARM_REG_R0)

    def tap(p):
        G.pad(u, p)
        G.unpad(u, p)

    def advance(ms):
        now = E.u32(u, E.C.HAL_TICK)
        u.mem_write(E.C.HAL_TICK, struct.pack('<I', now + ms))

    packets = []
    serial = 0

    def write(uc, address, size, data):
        core, value, target = (uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
        if core == 1 and 0x9e20 <= target <= 0x9e27:
            packets.append((target - 0x9e20, struct.unpack('<i', struct.pack('<I', value))[0] >> 8))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def read(uc, address, size, data):
        target = uc.reg_read(UC_ARM_REG_R1)
        uc.reg_write(UC_ARM_REG_R0, serial << 8 if target == 0x9f90 else 0)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    u.hook_add(UC_HOOK_CODE, write, None, G.WR16, G.WR16 + 1)
    u.hook_add(UC_HOOK_CODE, read, None, 0x08031268, 0x08031268)
    tap(pad)
    assert bytes(u.mem_read(values, 6)) == bytes([64, 0, 32, 0, 0, 48])
    marker = E.MAN['marker']
    shifted = (marker[:1]=='A' and len(marker)==4) and 'A290' <= marker
    decay_on_k3 = (marker[:1]=='A' and len(marker)==4) and 'A291' <= marker
    stock_pitch = E.kval(u, 0, 0)
    if shifted:
        G.knob(u, 0, 12)
        assert E.kval(u, 0, 0) != stock_pitch
        assert bytes(u.mem_read(values, 6)) == bytes([64, 0, 32, 0, 0, 48])
        stock_pitch = E.kval(u, 0, 0)
        stock_k8 = E.kval(u, 0, 7)
        G.knob(u, 7, 17)
        assert E.kval(u, 0, 7) == stock_k8
    for k, delta in enumerate((32, 64, 8, 40, 50, 24)):
        physical_knob = 3-k if decay_on_k3 and k in (1, 2) else k
        G.knob(u, physical_knob + shifted, delta)
    configured = bytes([96, 64, 40, 40, 50, 72])
    assert bytes(u.mem_read(values, 6)) == configured
    assert E.kval(u, 0, 0) == stock_pitch

    for next_serial in (0, 1, 1):
        serial = next_serial
        advance(25)
        call('runtime_frame', slot, 1, 0)
    modulation = [offset for track, offset in packets if track == 0]
    assert len(modulation) >= 2 and len(set(modulation)) >= 2
    assert all(offset == 0 for track, offset in packets if track != 0)

    G.pad(u, pad)
    tick = E.u32(u, 0x20000820)
    u.mem_write(0x20000820, struct.pack('<I', tick + 400))
    call('runtime_ui_frame', slot, 0, 1)
    if (marker[:1]=='A' and len(marker)==4) and 'A293' <= marker:
        E.led(u, int(report['tmenu']['labels']['c_tmled'], 16))
        down = E.out(u, int(granular['ui']['labels']['c_guout'], 16))[51]
        assert down and down == (down & 255) * 0x010101
    tap(16)
    E.press(u, 19)
    E.release(u, 19)
    assert u.mem_read(slot + 380, 1)[0] & 128
    G.knob(u, 3 + shifted, 5)
    assert bytes(u.mem_read(values, 6)) == configured
    tap(17)
    G.unpad(u, pad)
    tap(pad)
    assert bytes(u.mem_read(slot + 317, 1)) == b'\x19'

    assert call('runtime_settings_store', slot, settings) == 1
    assert bytes(u.mem_read(settings + 336, 7)) == configured + bytes([64])
    assert u.mem_read(settings + 384, 1)[0] & 1
    assert call('runtime_settings_load', slot, 0) == 1
    assert call('runtime_settings_load', slot, settings) == 1
    assert bytes(u.mem_read(values, 6)) == configured
    assert bytes(u.mem_read(slot + 317, 1)) == b'\x19'

    tap(pad)
    points = SM.pat(u, 0) + 0x128 + 192
    u.mem_write(points, b'\xff' * 192)
    u.mem_write(E.ptr(u, E.C.TRANSPORT, 1), b'\1')
    G.pad(u, 4)
    G.knob(u, 3 + shifted, 12)
    G.unpad(u, 4)
    assert u.mem_read(points + 24, 1)[0] < 128
    u.mem_write(E.ptr(u, E.C.TRANSPORT, 1), b'\0')
    G.held(u, 23, True)
    G.knob(u, 3 + shifted, -40)
    G.held(u, 23, False)
    assert bytes(u.mem_read(points, 192)) == b'\xff' * 192
    if (marker[:1]=='A' and len(marker)==4) and 'A292' <= marker:
        # Match the track's Stock setting for value-bar taps.
        config = u.mem_read(slot + 168, 1)[0]
        u.mem_write(slot + 168, bytes([config | 4]))
        for knob, pad, index, expected in ((2, 23, 2, 127), (3, 21, 1, 64), (5, 19, 4, 63)):
            u.mem_write(menu + E.T.O_KNOB, bytes([knob + 1]))
            tap(pad)
            assert u.mem_read(values + index, 1)[0] == expected
        assert E.kval(u, 0, 0) == stock_pitch
        u.mem_write(menu + E.T.O_KNOB, b'\x01')
        tap(23)
        assert E.kval(u, 0, 0) == 127
        u.mem_write(menu + E.T.O_KNOB, b'\x05')
        u.mem_write(E.ptr(u, E.C.TRANSPORT, 1), b'\1')
        G.pad(u, 4)
        tap(16)
        G.unpad(u, 4)
        assert bytes(u.mem_read(points + 24, 1)) == b'\0'
        print('PASS Pitch value-bar taps, shape markers, Stock Tune, and assigned recording')
    print('PASS Pitch knobs, combined modulation, track isolation, assignment, companion round trip, and Record-off clear')


if __name__ == '__main__':
    main()
