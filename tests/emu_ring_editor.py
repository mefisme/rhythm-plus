"""Check the Ring Mod page (Extras, with Scan), exclusive DSP routing, and project settings."""

import struct
import zlib

import emu_fx_native_edges as fixture
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

G, E, SM = fixture.G, fixture.E, fixture.SM


def check_scan(u, report, state, slot, labels, call, packets):
    # FxSettings: value[8][4], before, active, selected[8], fine[8], sent[8], tick, phase[8], amount[8], scan_sent[8], synced.
    phase, amount, synced = state + 88, state + 104, state + 136
    assert bytes(u.mem_read(state + 2, 2)) == bytes([16, 48]), 'K3 sets Scan depth; K4 rate starts at 48'
    tick = E.u32(u, 0x20006f3c)
    start = struct.unpack('<H', bytes(u.mem_read(phase, 2)))[0]
    packets.clear()
    u.mem_write(0x20006f3c, struct.pack('<I', tick + 100))
    call('runtime_frame', slot, 1, 0)
    position = struct.unpack('<H', bytes(u.mem_read(phase, 2)))[0]
    assert position == (start + 100 * (8 + 2 * 48)) & 0xffff, (start, position)
    p = position >> 8 & 255
    level = 16 * (p if p < 128 else 255 - p) * 2
    assert struct.unpack('<H', bytes(u.mem_read(amount, 2)))[0] == level and level
    assert (1, level * 248 << 8, 0x9e10) in packets, 'track 1 Scan amount on core 1'
    assert not any(c == 1 and 0x9e11 <= a <= 0x9e17 and v for c, v, a in packets), 'other tracks stay at 0'
    word = labels.get('c_gr_runtime_word')
    if word:
        E.call(u, word, slot, 0, 4)
        assert u.reg_read(UC_ARM_REG_R0) == 2047 * level >> 15, 'Granular Position gets the same move'
    print('PASS Scan: K3 depth x a triangle LFO at the K4 rate goes to core 1 for the track; Granular Position follows')


def main():
    u = fixture.setup()
    report = E.MAN['report']
    granular = report['granular']
    ring = report['ring_mod_dsp']
    pad = ring['editor_pad'] - 1
    slot = int(granular['bridge']['slot'], 16)
    menu = int(granular['ui']['menu'], 16)
    state = ring['settings_itcm_start']
    scan = 'scan_dsp' in report
    count = 4 if scan else 2
    before, fine = state + 8 * count, state + 8 * count + 10
    labels = granular['arm_kernel']['labels']
    buf = 0x20001000
    SM.sel(u, 0)
    u.mem_write(menu + E.T.O_OPEN, b'\1')
    u.mem_write(G.CONT + 0x264, b'\0')

    def call(name, *args):
        E.call(u, labels['c_gr_' + name], *args)
        return u.reg_read(UC_ARM_REG_R0)

    def tap(p):
        G.pad(u, p)
        G.unpad(u, p)

    packets = []

    def write(uc, address, size, data):
        packets.append(tuple(uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    u.hook_add(UC_HOOK_CODE, write, None, G.WR16, G.WR16 + 1)
    tap(pad)
    assert bytes(u.mem_read(state, 2)) == bytes([0, 64])
    G.knob(u, 0, 32)
    G.knob(u, 1, 16)
    G.knob(u, 2, 16)
    configured = bytes([32, 80])
    assert bytes(u.mem_read(state, 2)) == configured
    call('runtime_frame', slot, 1, 0)
    version = report['storageshadow']['granular_settings_version']
    if version >= 10:
        original_step = next(value for core, value, target in packets if core == 0 and target == 0x9e88)
        shift_store = E.u32(u, E.C.CTRL + 0x0c)
        u.mem_write(E.ptr(u, shift_store, 0), b'\1')
        G.knob(u, 1, 1)
        u.mem_write(E.ptr(u, shift_store, 0), b'\0')
        assert bytes(u.mem_read(state, 2)) == configured
        assert u.mem_read(fine, 1)[0] == 1
        call('runtime_frame', slot, 1, 0)
        fine_step = [value for core, value, target in packets if core == 0 and target == 0x9e88][-1]
        assert original_step < fine_step < original_step * 1.01
    amount = 32 * 66052 << 8
    assert (0, amount, 0x9e90) in packets
    assert all(not value for c, value, a in packets if c == 1 and 0x9e70 <= a <= 0x9e77)
    if scan:
        check_scan(u, report, state, slot, labels, call, packets)

    G.pad(u, pad)
    tick = E.u32(u, 0x20000820)
    u.mem_write(0x20000820, struct.pack('<I', tick + 400))
    call('runtime_ui_frame', slot, 0, 1)
    tap(16)
    packets.clear()
    call('runtime_frame', slot, 1, 0)
    assert packets.index((0, 0, 0x9e90)) < packets.index((1, amount, 0x9e70))
    assert u.mem_read(before, 1)[0] & 1
    E.press(u, 19)
    E.release(u, 19)
    G.knob(u, 0, 17)
    assert bytes(u.mem_read(state, 2)) == configured
    tap(17)
    G.unpad(u, pad)
    tap(pad)
    assert u.mem_read(slot + 317, 1)[0] == 28

    assert call('runtime_settings_store', slot, buf) == 1
    saved = bytes(u.mem_read(buf, report['storageshadow']['granular_settings_bytes']))
    assert saved[:3] == b'GS'+bytes([version])
    if version >= 10: assert saved[402] == 1
    assert saved[385:387] == configured and saved[401] & 1
    assert call('runtime_settings_load', slot, 0)
    assert bytes(u.mem_read(state, 2)) == bytes([0, 64])
    assert call('runtime_settings_load', slot, buf)
    assert bytes(u.mem_read(state, 2)) == configured
    assert u.mem_read(slot + 317, 1)[0] == 28
    if version >= 10: assert u.mem_read(fine, 1)[0] == 1

    tap(pad)
    points = SM.pat(u, 0) + 0x128 + 192
    u.mem_write(points, b'\xff' * 192)
    u.mem_write(E.ptr(u, E.C.TRANSPORT, 1), b'\1')
    G.pad(u, 4)
    G.knob(u, 0, 12)
    G.unpad(u, 4)
    assert u.mem_read(points + 24, 1)[0] < 128
    u.mem_write(E.ptr(u, E.C.TRANSPORT, 1), b'\0')
    G.held(u, 23, True)
    G.knob(u, 0, -40)
    G.held(u, 23, False)
    assert bytes(u.mem_read(points, 192)) == b'\xff' * 192

    if version >= 10:
        legacy_ring = bytearray(saved[:402])
        legacy_ring[2] = 9
        struct.pack_into('<I', legacy_ring, 4, zlib.crc32(legacy_ring[8:]))
        u.mem_write(buf, bytes(legacy_ring))
        assert call('runtime_settings_load', slot, buf)
        assert bytes(u.mem_read(state, 2)) == configured
        assert u.mem_read(fine, 1)[0] == 0
    legacy = bytearray(saved[:385])
    legacy[2], legacy[153] = 8, 0
    struct.pack_into('<I', legacy, 4, zlib.crc32(legacy[8:]))
    u.mem_write(buf, bytes(legacy))
    assert call('runtime_settings_load', slot, buf)
    assert bytes(u.mem_read(state, 2)) == bytes([0, 64])
    assert u.mem_read(before, 1)[0] == 0
    print('PASS Ring Mod controls, exclusive routing, assignment, Record-off Clear, companion round trip, and older defaults')


if __name__ == '__main__':
    main()
