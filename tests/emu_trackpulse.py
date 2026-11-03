"""Exercise the real stock LED palette updater: track pulse follows white step pulse."""
from pathlib import Path
import struct
import sys
import emu_tmenu as E


def main():
    stock, fw, ram = (Path(p).read_bytes() for p in sys.argv[1:4])
    uc = E.setup(fw, ram)
    t = E.sel(uc)
    E.tap(uc, t)
    E.led(uc, E.rhbuild.bl_target(bytearray(fw), E.C.LED_CALLS[0]))
    uc.mem_write(E.C.CTRL + 0xA4, struct.pack('<I', 0))
    uc.mem_write(E.C.CTRL + 0xA8, b'\0')
    samples, white = [], []
    for phase in range(96):
        # The actual frame update refreshes white selection palette entries,
        # grayscale pulse coefficient, and invokes our normal output chain.
        E.call(uc, 0x0803E47A, E.C.CTRL, E.OUT, phase)
        coefficient = E.u32(uc, E.T.COLOURS + 4*0x0A) & 255
        colour = E.u32(uc, E.T.COLOURS + 4*E.T.TRK_SLOTS[t])
        wanted = E.scl(colour, 64 + ((255-coefficient)*192 >> 8))
        actual = E.u32(uc, E.OUT + 4*(32+t))
        E.check(f'stock frame phase {phase}: track pulse uses same coefficient as white step', actual == wanted and actual != 0, (hex(actual), hex(wanted)))
        samples.append(actual)
        white.append(E.u32(uc, E.T.COLOURS + 4*0x1B))
    E.check('full stock cycle: visible pulse, never off', len(set(samples)) > 8 and 0 not in samples)
    E.check('stock white selection pulse also changes in same frame cycle', len(set(white)) > 8)
    # Confirmation red must override the coloured pulse.
    uc.mem_write(E.C.CTRL + 0xA0, struct.pack('<I', E.u32(uc, E.C.CTRL + 0xA0) | (1<<23)))
    E.press(uc, t); E.release(uc, t)
    outfn = E.rhbuild.bl_target(bytearray(fw), E.T.OUT_CALL)
    E.check('Clear + track confirmation still solid red over pulse', E.out(uc, outfn)[32+t] == E.clear_red(uc))
    print('ALL PASS' if not E.FAILS else f'{len(E.FAILS)} FAILED')
    if E.FAILS: raise SystemExit(1)


if __name__ == '__main__': main()
