"""Panel gestures, shared native automation, and Filter modulation on FP277."""

import struct
import sys
import zlib

import emu_fx_native_edges as fixture
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

G, E, SM = fixture.G, fixture.E, fixture.SM
FILTER_PAD = 27


def main():
    u = fixture.setup()
    granular = E.MAN['report']['granular']
    labels = granular['arm_kernel']['labels']
    slot = int(granular['bridge']['slot'], 16)
    menu = int(granular['ui']['menu'], 16)
    SM.sel(u, 0)
    u.mem_write(menu + E.T.O_OPEN, b'\x01')
    u.mem_write(G.CONT + 0x264, b'\x00')
    dim = E.ptr(u, E.u32(u, E.C.CTRL + E.T.O_DIM), E.T.P_DIM)
    u.mem_write(dim, struct.pack('<I', E.u32(u, dim) & ~1024))

    def tap(pad):
        G.pad(u, pad)
        G.unpad(u, pad)

    def frame():
        E.led(u, int(E.MAN['report']['tmenu']['labels']['c_tmled'], 16))
        return E.out(u, int(granular['ui']['labels']['c_guout'], 16))

    marker = E.MAN['marker']
    full_white = (marker[:1]=='A' and len(marker)==4) and 'A284' <= marker
    white_cycle = full_white or marker == 'A283'
    page_color = E.MAN['report']['filter_cutoff'].get('page_rgb')
    tap(FILTER_PAD)
    assert frame()[61] == 0
    colors = frame()
    if E.MAN['report']['filter_cutoff'].get('page_rgb'):
        assert colors[FILTER_PAD] == page_color
        track_color = E.u32(u, E.T.COLOURS + 4 * E.T.TRK_SLOTS[0])
        filter_cycle = colors[24]
        if '--contrast' in sys.argv:
            assert filter_cycle == 0x1a1a1a
        else:
            assert 0 < filter_cycle < track_color
        u.mem_write(menu + E.T.O_KNOB, b'\x01')
        tap(24)
        assert u.mem_read(menu + E.T.O_KNOB, 1) == b'\x03'
        colors = frame()
        decay_brightness = (32 * 0x1cc + 0x1a00) >> 8
        dim_track = sum((((0xffffff if white_cycle else track_color) >> shift & 255) * decay_brightness // 255) << shift
                        for shift in (0, 8, 16))
        assert colors[62] == (0xffffff if full_white else dim_track)
        assert colors[16] == track_color
        G.knob(u, 2, 100)
        bright_track = sum((((0xffffff if white_cycle else track_color) >> shift & 255) * 254 // 255) << shift for shift in (0, 8, 16))
        assert frame()[62] == (0xffffff if full_white else bright_track)
        G.knob(u, 2, -95)
        assert frame()[62] == (0xffffff if full_white else dim_track)
        tap(E.GP)
        colors = frame()
        assert colors[E.GP] == 0x9eff59
        assert colors[24] == filter_cycle
        tap(25)
        stock = frame()
        assert stock[24] == filter_cycle
        if '--contrast' in sys.argv:
            assert stock[25] == track_color
        if white_cycle:
            assert all(stock[32 + t] == 0xffffff for t in range(1, 8))
            assert stock[32] == track_color
        tap(FILTER_PAD)
        if '--contrast' in sys.argv:
            buf = 0x20001000
            for track in range(8):
                E.call(u, labels['c_gr_runtime_pad'], slot, track, FILTER_PAD)
                E.call(u, labels['c_gr_runtime_release'], slot, FILTER_PAD)
                u.mem_write(buf, struct.pack('<69I', *([0xffffff] * 69)))
                E.call(u, labels['c_gr_runtime_draw'], slot, track, buf, 2)
                lights = struct.unpack('<69I', u.mem_read(buf, 69 * 4))
                hue = E.u32(u, E.T.COLOURS + 4 * E.T.TRK_SLOTS[track])
                assert lights[62] == (0xffffff if full_white else sum((((0xffffff if white_cycle else hue) >> shift & 255) * decay_brightness // 255) << shift
                                         for shift in (0, 8, 16)))
                ice_blue = page_color
                assert lights[63] == sum(((ice_blue >> shift & 255) * 26 // 255) << shift
                                         for shift in (0, 8, 16))
                assert lights[FILTER_PAD] == page_color
    if full_white:
        u.mem_write(menu + E.T.O_KNOB, b'\x01')
        lights = frame()
        assert lights[60] == 0xffffff
        for k in (6, 7):
            u.mem_write(menu + E.T.O_KNOB, bytes([k + 1]))
            assert frame()[60 + k] == 0xffffff
    before_aliases = [E.kval(u, 0, k) for k in (6, 7)]
    for k, initial in zip((6, 7), before_aliases):
        G.knob(u, k, -12 if initial > 64 else 12)
        assert E.kval(u, 0, k) != initial
    tap(25)  # White Stock page after visiting Filter.
    for k in range(8):
        initial = E.kval(u, 0, k)
        G.knob(u, k, -12 if initial > 64 else 12)
        assert E.kval(u, 0, k) != initial, ('Stock knob after Filter', k + 1)
    u.mem_write(0x3500, b'\xff'*E.MAN['report']['filter_cutoff']['itcm_bytes'])
    initial = E.kval(u, 0, 0)
    G.knob(u, 0, -12 if initial > 64 else 12)
    assert E.kval(u, 0, 0) != initial, 'stale Filter ITCM intercepted Stock K1'
    tap(FILTER_PAD)
    G.pad(u, FILTER_PAD)
    E.press(u, 19)
    E.release(u, 19)
    assert u.mem_read(slot + 380, 1)[0] & 128
    tap(16)
    if '--assignment-select' in sys.argv:
        scratch=0x20001000
        E.call(u,labels['c_gr_runtime_settings_store'],slot,scratch)
        before=bytes(u.mem_read(scratch,336))
        stock=[E.kval(u,0,k) for k in (6,7)]
        G.knob(u,2,30)
        G.knob(u,6,30)
        G.knob(u,7,30)
        E.call(u,labels['c_gr_runtime_settings_store'],slot,scratch)
        assert bytes(u.mem_read(scratch,336))==before
        assert [E.kval(u,0,k) for k in (6,7)]==stock
        lights=frame();ice_blue=page_color
        assert lights[24]==lights[62]==(0xffffff if white_cycle else ice_blue)
        assert lights[61]==lights[66]==lights[67]==0
        dim_ice_blue=sum(((ice_blue>>shift&255)*31//255)<<shift for shift in (0,8,16))
        assert all(lights[60+k]==dim_ice_blue for k in (0,3,4,5))
        tap(17)
        assert u.mem_read(slot+317,1)==b'\x15'  # K3 selected Envelope Decay.
        tap(17)
    G.unpad(u, FILTER_PAD)
    assert u.mem_read(slot + 316, 8) == bytes([17, 0, 0, 0, 0, 0, 0, 0])
    tap(FILTER_PAD)
    assert u.mem_read(slot + 380, 1)[0] & 128 == 0
    G.pad(u, FILTER_PAD)
    tick = E.u32(u, 0x20000820)
    u.mem_write(0x20000820, struct.pack('<I', tick + 334))
    E.call(u, labels['c_gr_runtime_ui_frame'], slot, 0, 1)
    tap(16)  # Tempo sync in the held Filter settings.
    G.unpad(u, FILTER_PAD)
    tap(FILTER_PAD)

    rec = SM.obj(u, 0)
    points = E.u32(u, rec + 4) + 0x128
    u.mem_write(points, b'\xff' * 192)
    u.mem_write(E.ptr(u, E.C.TRANSPORT, 1), b'\x01')
    u.mem_write(E.ptr(u, E.C.TRANSPORT, 0), b'\x00')
    G.pad(u, 4)
    G.knob(u, 3, 32)
    assert u.mem_read(points + 24, 1) == b'\x20'
    rgb = frame()[63]
    assert (rgb >> 16 & 255) > 4 * max(rgb >> 8 & 255, rgb & 255)
    G.held(u, 23, True)
    G.knob(u, 3, -40)
    G.held(u, 23, False)
    assert u.mem_read(points + 24, 1) == b'\xff'
    G.unpad(u, 4)

    packets = []

    def write(uc, address, size, data):
        packets.append(tuple(uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    hook = u.hook_add(UC_HOOK_CODE, write, None, G.WR16, G.WR16 + 1)
    if E.MAN['report']['filter_cutoff'].get('data_words', 8)>8:
        idle = fixture.setup()
        idle.hook_add(UC_HOOK_CODE, write, None, G.WR16, G.WR16 + 1)
        E.call(idle, labels['c_gr_runtime_frame'], slot, 1, 0)
        assert not any(core == 1 and 0x9e00 <= address <= 0x9e07 for core, _, address in packets)
    E.call(u, labels['c_gr_lane_inner'], 0x20043700, 0, 100, 3)
    for elapsed in (10, 90):
        now = E.u32(u, E.C.HAL_TICK)
        u.mem_write(E.C.HAL_TICK, struct.pack('<I', now + elapsed))
        E.call(u, labels['c_gr_runtime_frame'], slot, 1, 0)
    offsets = [value for core, value, addr in packets if core == 1 and addr == 0x9e00]
    assert len(offsets) >= 2 and offsets[0] != offsets[-1], offsets
    assert all(value == 0 for core, value, addr in packets if core == 1 and 0x9e01 <= addr <= 0x9e07)
    if '--audio' in sys.argv:
        from emu_filter_audio import verify_encoder_audio

        # Turn the actual panel encoder, capture its DSP write, then feed the
        # emitted word into the native DSP voice loop in the second emulator.
        G.knob(u, 3, -30)
        packets.clear()
        for elapsed in (17, 67):
            now = E.u32(u, E.C.HAL_TICK)
            u.mem_write(E.C.HAL_TICK, struct.pack('<I', now + elapsed))
            E.call(u, labels['c_gr_runtime_frame'], slot, 1, 0)
        emitted = [value>>8 for core,value,addr in packets if core==1 and addr==0x9e00 and value]
        assert emitted
        verify_encoder_audio(sys.argv[1], emitted[-1])
        E.call(u, labels['c_gr_lane_inner'], 0x20043700, 0, 100, 3)
    u.hook_del(hook)

    settings = 0x20001000
    E.call(u, labels['c_gr_runtime_settings_store'], slot, settings)
    assert u.reg_read(UC_ARM_REG_R0) == 1
    companion = E.MAN['report']['storageshadow']
    assert bytes(u.mem_read(settings, 3)) == b'GS' + bytes([companion['granular_settings_version']])
    assert u.mem_read(settings + 152, 1) == b'\x11'
    assert u.mem_read(settings + 288, 1) == b'd'
    assert u.mem_read(settings + 293, 1) == b'\x01'
    saved = bytes(u.mem_read(settings, companion['granular_settings_bytes']))
    E.call(u, labels['c_gr_runtime_settings_load'], slot, 0)
    E.call(u, labels['c_gr_runtime_settings_load'], slot, settings)
    assert u.reg_read(UC_ARM_REG_R0) == 1
    assert u.mem_read(slot + 316, 1) == b'\x11'

    tap(FILTER_PAD)
    u.mem_write(slot + 317, b'\x01')  # another lane belongs to Granular
    u.mem_write(points, b'\x20' * (192 * 3))
    G.held(u, 23, True)
    tap(FILTER_PAD)
    G.held(u, 23, False)
    assert bytes(u.mem_read(points, 192)) == b'\xff' * 192
    assert bytes(u.mem_read(points + 192, 384)) == b'\x20' * 384
    older = bytearray(saved[:288])
    older[2], older[152] = 5, 0
    struct.pack_into('<I', older, 4, zlib.crc32(older[8:]))
    u.mem_write(settings, bytes(older))
    E.call(u, labels['c_gr_runtime_settings_load'], slot, settings)
    assert u.reg_read(UC_ARM_REG_R0) == 1
    E.call(u, labels['c_gr_runtime_settings_store'], slot, settings)
    assert u.mem_read(settings + 288, 3) == b'\x00\x00\x30'

    tap(FILTER_PAD)
    u.mem_write(slot + 168, b'\x04')  # Track editor's value-bar taps enabled.
    u.mem_write(menu + E.T.O_KNOB, b'\x04')
    stock_value = E.kval(u, 0, 3)
    tap(23)
    E.call(u, labels['c_gr_runtime_settings_store'], slot, settings)
    assert u.mem_read(settings + 288, 1) == b'\x7f'
    assert E.kval(u, 0, 3) == stock_value
    E.call(u, labels['c_gr_runtime_settings_load'], slot, 0)

    # With the LFO disabled, a new accepted note serial reaches the signed
    # envelope maximum and then decays. Other tracks never receive offsets.
    tap(FILTER_PAD)
    G.knob(u, 0, 40)
    serial = 41

    def read(uc, address, size, data):
        if uc.reg_read(UC_ARM_REG_R0) != 1:
            return
        assert uc.reg_read(UC_ARM_REG_R1) == 0x9f90
        uc.reg_write(UC_ARM_REG_R0, serial << 8)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def skip(uc, address, size, data):
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    u.hook_add(UC_HOOK_CODE, read, None, 0x08031268, 0x08031269)
    for address in (0x08029c8c, 0x08030eb8):
        u.hook_add(UC_HOOK_CODE, skip, None, address, address + 1)
    u.hook_add(UC_HOOK_CODE, write, None, G.WR16, G.WR16 + 1)
    packets.clear()
    for frame_index, elapsed in enumerate((10, 10, 100)):
        now = E.u32(u, E.C.HAL_TICK)
        u.mem_write(E.C.HAL_TICK, struct.pack('<I', now + elapsed))
        E.call(u, labels['c_gr_runtime_frame'], slot, 1, 0)
        if frame_index == 0:
            serial = 42
    envelope = [value >> 8 for core, value, address in packets if core == 1 and address == 0x9e00]
    assert envelope[-2:] == [40, 28], envelope
    # Borrowing K7/K8's automation lanes must never disable the manual
    # cutoff/resonance knobs, including their aliases on the Filter page.
    u.mem_write(slot+316,bytes([0,0,0,0,0,0,17,18]))
    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\x00')
    for pad in (25,FILTER_PAD):
        tap(pad)
        for k in (6,7):
            initial=E.kval(u,0,k)
            G.knob(u,k,-12 if initial>64 else 12)
            assert E.kval(u,0,k)!=initial,('borrowed lane disables manual cutoff/resonance',pad,k)
    if '--shape-bar' in sys.argv:
        u.mem_write(menu + E.T.O_KNOB,b'\x05')
        for value,pad in ((0,16),(42,16),(43,19),(85,19),(86,23),(127,23)):
            E.call(u,labels['c_gr_lane_inner'],0x20043700,7,value,3)
            indicators=frame()[16:24]
            assert [i+16 for i,rgb in enumerate(indicators) if rgb]==[pad],(value,indicators)
    print('PASS Filter hold, assignment, held lock, clear, red feedback, LFO writes and settings round-trip')
    print('ALL PASS')


if __name__ == '__main__':
    main()
