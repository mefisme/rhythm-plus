"""Emit a stock knob behavior snapshot for comparison across firmware builds."""

import json
import hashlib
import struct
import sys

import emu_fx_native_edges as fixture

G, E, SM = fixture.G, fixture.E, fixture.SM


def main():
    u = fixture.setup()
    report = E.MAN['report']
    E.HEAD = int(report['tmenu']['labels']['c_tmled'],16)
    menu = int(report['granular']['ui']['menu'], 16)
    SM.sel(u, 0)
    u.mem_write(menu + E.T.O_OPEN, b'\x01')
    u.mem_write(G.CONT + 0x264, b'\x00')

    def tap(pad):
        G.pad(u, pad)
        G.unpad(u, pad)

    if 'filter_cutoff' in report:
        tap(report['filter_cutoff']['editor_pad']-1)
    tap(25)

    rec = SM.obj(u, 0)
    points = E.u32(u, rec + 4) + 0x128
    all_points = 12 * 192
    u.mem_write(points, b'\xff' * all_points)

    def values():
        return [E.kval(u,0,k) for k in range(8)]

    def turn_each():
        for k, value in enumerate(values()):
            G.knob(u, k, -20 if value>64 else 20)

    if '--led-range' in sys.argv:
        dim = E.ptr(u, E.u32(u, E.C.CTRL + E.T.O_DIM), E.T.P_DIM)
        u.mem_write(dim, struct.pack('<I', E.u32(u, dim) & ~1024))
        original = values()
        track_color = E.u32(u, E.T.COLOURS + 4 * E.T.TRK_SLOTS[0])
        u.mem_write(menu + E.T.O_KNOB, b'\x08')
        for value, levels in ((0, (251, 25)), (64, (25, 140)), (127, (251, 253))):
            for k in (0, 1):
                u.mem_write(E.ptr(u, E.kstore(u, 0), k), bytes([value]))
            E.led(u, E.HEAD)
            rgb = E.out(u, int(report['granular']['ui']['labels']['c_guout'], 16))
            for k, level in enumerate(levels):
                expected = sum(((track_color >> shift & 255) * level // 255) << shift
                               for shift in (0, 8, 16))
                assert rgb[60 + k] == expected
            assert rgb[67] == 0xffffff
        for k, value in enumerate(original):
            u.mem_write(E.ptr(u, E.kstore(u, 0), k), bytes([value]))

    before = values()
    turn_each()
    manual = values()
    assert all(a!=b for a,b in zip(before,manual)), (before,manual)

    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\x01')
    u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\x00')
    G.pad(u,4)
    turn_each()
    held = bytes(u.mem_read(points,all_points))
    assert all(held[k*192+4*6]<128 for k in range(8))

    for k in range(8):
        E.clr_turn(u,k,40,-1)
    G.unpad(u,4)
    cleared = bytes(u.mem_read(points,all_points))

    G.held(u,23,True)
    tap(25)
    G.held(u,23,False)
    assert bytes(u.mem_read(points,all_points))==b'\xff'*all_points
    page_defaults=values()

    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\x00')
    reset_colors=[]
    for k in range(8):
        reset_colors.append(E.clr_turn(u,k,40)[k])
    print(json.dumps(dict(initial=before,manual=manual,
                          held=[held[k*192+4*6] for k in range(8)],
                          clear_left=hashlib.sha256(cleared).hexdigest(),page_defaults=page_defaults,
                          after_clear_right=values(),clear_right_colors=reset_colors)))


if __name__=='__main__':
    main()
