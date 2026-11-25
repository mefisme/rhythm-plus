"""The Extras page on pad 30: light, Scan knobs, pad 25, Free/Sync, lanes, Clear and the GS v12 round trip.
Frames run between the steps and knobs turn in small steps, as on the unit."""

import struct

import emu_fx_native_edges as fixture
from unicorn.arm_const import UC_ARM_REG_R0

G, E, SM = fixture.G, fixture.E, fixture.SM


def main():
    u = fixture.setup()
    report = E.MAN['report']
    if 'scan_dsp' not in report:
        print('SKIP no Scan in this build')
        return
    granular = report['granular']
    page = report['ring_mod_dsp']['editor_pad'] - 1
    assert page == 29 and report['ring_mod_dsp']['page_rgb'] == 0x4000dd
    slot = int(granular['bridge']['slot'], 16)
    menu = int(granular['ui']['menu'], 16)
    state = report['ring_mod_dsp']['settings_itcm_start']
    synced = state + 136
    labels = granular['arm_kernel']['labels']
    buf = 0x20001000
    SM.sel(u, 0)
    u.mem_write(menu + E.T.O_OPEN, b'\1')
    u.mem_write(G.CONT + 0x264, b'\0')

    def call(name, *args):
        E.call(u, labels['c_gr_' + name], *args)
        return u.reg_read(UC_ARM_REG_R0)

    def frame(ms=20):
        for address in (0x20000820, 0x20006f3c):
            u.mem_write(address, struct.pack('<I', E.u32(u, address) + ms))
        call('runtime_ui_frame', slot, 0, 1)
        call('runtime_frame', slot, 1, 0)

    def tap(p):
        G.pad(u, p)
        frame()
        G.unpad(u, p)
        frame()

    def turn(k, steps):
        for _ in range(abs(steps)):
            G.knob(u, k, 1 if steps > 0 else -1)
            frame(5)

    def draw():
        u.mem_write(buf, struct.pack('<69I', *([0x404040] * 69)))
        call('runtime_draw', slot, 0, buf, max(u.mem_read(menu + 8, 1)[0], 1) - 1)
        return struct.unpack('<69I', u.mem_read(buf, 69 * 4))

    def values():
        return list(u.mem_read(state, 4))

    def rgb_is_page(rgb):
        r, g, b = rgb >> 16 & 255, rgb >> 8 & 255, rgb & 255
        return b > r > g and b > 2 * r

    tap(page)
    out = draw()
    assert rgb_is_page(out[page]), ('pad 30 is purple', hex(out[page]))
    assert out[30] == 0, ('pad 31 is dark', hex(out[30]))
    assert values() == [0, 64, 0, 48]
    tap(30)
    assert u.mem_read(state + 33, 1)[0] & 1 and values() == [0, 64, 0, 48], 'pad 31 opens nothing; the FX page stays'
    tap(page)

    turn(2, 5)
    turn(3, 3)
    assert values() == [0, 64, 5, 51], values()
    out = draw()
    assert all(out[60 + k] == 0 for k in range(4, 8)), 'K5-K8 dark'
    assert out[63] == 0xffffff or out[63] & 0xffffff, 'K4 lit'

    knob = menu + 8
    seen = []
    for _ in range(4):
        tap(24)
        seen.append(u.mem_read(knob, 1)[0])
    assert sorted(seen) == [1, 2, 3, 4], ('pad 25 cycles K1-K4', seen)

    G.pad(u, page)
    for _ in range(20):
        frame()
    tap(17)
    assert u.mem_read(synced, 1)[0] & 1, 'settings pad 18: Tempo Sync'
    out = draw()
    assert rgb_is_page(out[17]), ('Sync is the page colour', hex(out[17]))
    assert out[16] & 0xffffff and not rgb_is_page(out[16]), ('pad 17 white: after the filter', hex(out[16]))
    tap(17)
    assert not u.mem_read(synced, 1)[0] & 1, 'pad 18 again: Free'
    tap(17)
    E.press(u, 19)
    E.release(u, 19)
    frame()
    G.knob(u, 2, 1)
    frame()
    tap(18)
    assert u.mem_read(slot + 316 + 2, 1)[0] == 30, 'Scan depth on lane 3'
    G.unpad(u, page)
    for _ in range(3):
        frame()

    assert call('runtime_settings_store', slot, buf) == 1
    saved = bytes(u.mem_read(buf, 423))
    assert saved[:4] == b'GS\x0c\x08' and saved[406:408] == bytes([5, 51]) and saved[422] & 1
    assert saved[152 + 2] == 30
    assert call('runtime_settings_load', slot, 0)
    assert values() == [0, 64, 0, 48] and not u.mem_read(synced, 1)[0]
    assert call('runtime_settings_load', slot, buf)
    assert values() == [0, 64, 5, 51] and u.mem_read(synced, 1)[0] & 1
    assert u.mem_read(slot + 316 + 2, 1)[0] == 30, 'lane 30 kept in v12'

    tap(page)
    G.held(u, 23, True)
    frame()
    G.pad(u, page)
    frame()
    G.unpad(u, page)
    G.held(u, 23, False)
    frame()
    assert values() == [0, 64, 0, 48] and not u.mem_read(synced, 1)[0] & 1, ('Clear + pad 30 resets the page', values())
    assert u.mem_read(slot + 316 + 2, 1)[0] == 30, 'Clear keeps the lane'
    print('PASS pad 30 purple, pad 31 dark; K3/K4 Scan, K5-K8 dark; pad 25 K1-K4; pad 18 Free/Sync; lane 30; '
          'GS v12 round trip; Clear + pad 30')
    print('ALL PASS')


if __name__ == '__main__':
    main()
