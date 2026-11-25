"""Easy Start (the stock's USB mass storage) removed; its code becomes free flash (MIT; the sites are Circuit Remix's noes.py, Alpha 0.16).

The stock: bit 17 of the settings' p2 (Advanced Setup button 9) picks the USB set-up with the mass storage class (0x08035814); its bulk-only
transport and SCSI layer run from the endpoints' service (0x0802764A, 0x0802766E).  Here the USB set-up never takes the class, the button
does nothing and its LED is dark, the two calls are gone, and the code only they reach is filled with 0xFF and listed as free (HOLES).
USB MIDI is unchanged.
"""
import struct

import rhbuild
from thumb import h

HOLES = ((0x0802EFC8, 0x0802F184), (0x080458D0, 0x08045DFC), (0x080661DC, 0x080662BC))
NOP, NOPW = h(0xBF00), h(0xF3AF) + h(0x8000)
HOOKS = ((0x08035820, "ubfx r0, r1, #0x11, #1", h(0x2000) + NOP),             # movs r0, #0; nop: no mass storage class
         (0x0805144A, "beq #0x8051456", NOP),                                 # button 9 does nothing
         (0x0805176C, "ldrh r0, [r5, r0]", h(0x2000)),                        # its LED dark
         (0x0802764A, "bl #0x802f014", NOPW),                                 # the transport's service call
         (0x0802766E, "b.w #0x802f04a", h(0x4770) + NOP))                     # bx lr; nop (its pop.w {r4, lr} is just before)


def free(b):
    for at, expect, new in HOOKS:
        b.hook(at, expect, new)
    for lo, hi in HOLES:
        o = lo - rhbuild.BASE
        b.img[o:hi - rhbuild.BASE] = bytes([0xFF]) * (hi - lo)
        b.patched.append((o, hi - lo))
    b.report["noeasystart"] = dict(hooks=[hex(a) for a, _, _ in HOOKS], holes=[[hex(lo), hex(hi), hi - lo] for lo, hi in HOLES],
                                   freed=sum(hi - lo for lo, hi in HOLES))


def _inside(v):
    return any(lo <= v < hi for lo, hi in HOLES)


def check(img, stock_len, thumb_instruction=None, placed=()):
    """Our code (after the stock's end) neither branches into the freed code nor holds an address in it; placed: (lo, hi) of our modules there."""
    ours = bytes(img[stock_len:])
    free_ = lambda v: _inside(v) and not any(lo <= v < hi for lo, hi in placed)   # noqa: E731
    base = rhbuild.BASE + stock_len
    for i in range(0, len(ours) - 3, 2):
        hi_, lo_ = struct.unpack_from("<HH", ours, i)
        if hi_ >> 11 == 0b11110 and lo_ >> 14 == 0b11 and lo_ & 0x1000:          # bl / b.w
            s = (hi_ >> 10) & 1
            j1, j2 = (lo_ >> 13) & 1, (lo_ >> 11) & 1
            off = (s << 24) | ((~(j1 ^ s) & 1) << 23) | ((~(j2 ^ s) & 1) << 22) | ((hi_ & 0x3FF) << 12) | ((lo_ & 0x7FF) << 1)
            if s:
                off -= 1 << 25
            target = base + i + 4 + off
            assert not free_(target), f"our code at {base + i:#x} branches into Easy Start's freed code ({target:#x})"
    for i in range(0, len(ours) - 3, 4):
        w = struct.unpack_from("<I", ours, i)[0]
        if not free_(w & ~1):continue
        if thumb_instruction and thumb_instruction(base+i,ours[i:i+4]):continue
        raise AssertionError(f"our word at {base + i:#x} holds {w:#x}, inside Easy Start's freed code")
