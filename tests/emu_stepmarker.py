"""Track + stopped selection marker compared with stock Velocity/Gate renderer."""
from pathlib import Path
import struct
import sys
import emu_tmenu as E


def main():
    stock, fw, ram = (Path(p).read_bytes() for p in sys.argv[1:4])
    uc = E.setup(fw, ram)
    ref = E.setup(stock, ram, False)
    t = E.sel(uc)
    head = E.rhbuild.bl_target(bytearray(fw), E.C.LED_CALLS[0])
    so = E.u32(uc, E.T.CONT + E.T.STEPOBJ + 4*t)
    rso = E.u32(ref, E.T.CONT + E.T.STEPOBJ + 4*t)
    def setp(u, obj, off, p, v): u.mem_write(E.ptr(u, E.u32(u, obj+off), p), bytes([v]))
    def play(v): uc.mem_write(E.ptr(uc, E.C.TRANSPORT, 0), bytes([v]))
    def frame(): return E.led(uc, head)
    def code(mode, step, note):
        E.call(ref, 0x0804D6B6, E.T.CONT, mode)
        setp(ref, rso, 0x18, 1, step)
        ref.mem_write(rso + 0x74 + 2*step, struct.pack('<H', 2 if note else 0))
        E.call(ref, 0x0805D3D6, rso)  # stock Velocity/Gate selected-step redraw
        pixels = E.u32(ref, E.u32(ref, rso+4))
        return int.from_bytes(ref.mem_read(pixels + 2*step, 2), 'little')
    play(0)
    E.tap(uc, t)
    before = bytes(uc.mem_read(so, 0x100))
    f = frame()
    current = uc.mem_read(E.ptr(uc, E.u32(uc, so+0x18), 1), 1)[0]
    E.check('opening stopped Track + shows existing step position without a pad press', f[current & 15] in (0x1A, 0x1B), (current, hex(f[current & 15])))
    for mode in (2, 3):
        for step in (0, 7, 15, 16, 23, 31):
            for note in (False, True):
                setp(uc, so, 0x18, 1, step)
                setp(uc, so, 0x60, 0, step >> 4)
                uc.mem_write(so+0x74+2*step, struct.pack('<H', 2 if note else 0))
                f = frame()
                want = code(mode, step, note)
                E.check(f'step {step+1}, {"hit" if note else "empty"}: same selected code as stock mode {mode}', f[step & 15] == want, (hex(f[step & 15]), hex(want)))
    # Wrong page must not show the selected position on the corresponding pad.
    setp(uc, so, 0x18, 1, 23); setp(uc, so, 0x60, 0, 0)
    f = frame()
    E.check('selected step on other page does not mark this page', f[7] not in (0x1A, 0x1B), hex(f[7]))
    setp(uc, so, 0x60, 0, 0); setp(uc, so, 0x18, 1, 0)
    play(1); f = frame()
    E.check('playing: existing playhead drawing retained, no stopped marker', f[0] not in (0x1A, 0x1B), hex(f[0]))
    # Select a pad through the real controller. It must not add a note.
    play(0)
    rec = E.u32(uc, E.T.AUTO + E.T.AUTO_RECS + 4*t)
    pats = E.u32(uc, rec+4)
    notes = bytes(uc.mem_read(pats, 8*E.T.PAT_SIZE))
    E.pad(uc, 4); E.unpad(uc, 4)
    f = frame()
    selected = uc.mem_read(E.ptr(uc, E.u32(uc, so+0x18), 1), 1)[0]
    E.check('pad selection marker remains after release', selected == 4 and f[4] in (0x1A, 0x1B), (selected, hex(f[4])))
    E.check('selecting pad adds no notes or automation', bytes(uc.mem_read(pats, 8*E.T.PAT_SIZE)) == notes)
    play(1); setp(uc, so, 0x18, 1, 9); frame(); play(0); f = frame()
    E.check('pause shows current position marker', f[9] in (0x1A, 0x1B), hex(f[9]))
    # All Track + knob pages share the same selected step marker.
    for page in [i for i in E.PADMAP if i is not None]:
        E.pad(uc, E.pp(page)); E.unpad(uc, E.pp(page))
        f = frame()
        E.check(f'Track + page {page+1} retains selected position', f[9] in (0x1A, 0x1B))
    E.tap(uc, t); f = frame()
    E.check('closing Track + removes added marker', E.b8(uc, E.T.O_OPEN) == 0 and f[9] not in (0x1A, 0x1B), hex(f[9]))
    print('ALL PASS' if not E.FAILS else f'{len(E.FAILS)} FAILED')
    if E.FAILS: raise SystemExit(1)


if __name__ == '__main__': main()
