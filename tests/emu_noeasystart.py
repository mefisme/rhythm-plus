"""Unicorn: with Easy Start removed, the USB set-up (0x08035814) takes no mass storage class even when the setting's bit 17 is on;
the stock image takes it.  The freed code is 0xFF, the button and LED sites are changed.
Usage: emu_noeasystart.py STOCK.bin IMAGE.bin [RAM.bin]"""
import struct
import sys

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_THUMB, Uc
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_SP

BASE, SETUP, PARAM_GET, USB_INIT = 0x08010000, 0x08035814, 0x0803FC58, 0x080432A8
RAM, OBJ, WORD, STACK = 0x20000000, 0x20001000, 0x20001100, 0x20008000
HOLES = ((0x0802EFC8, 0x0802F184), (0x080458D0, 0x08045DFC), (0x080661DC, 0x080662BC))


def usb_class(image, easy_start):
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    uc.mem_map(0x08000000, 0x80000)
    uc.mem_write(BASE, image)
    uc.mem_map(RAM, 0x10000)
    uc.mem_write(OBJ + 4, struct.pack("<I", 0x20001200))
    uc.mem_write(WORD, struct.pack("<I", (1 << 17) if easy_start else 0))
    seen = []

    def code(uc, addr, size, _):
        if addr == PARAM_GET:                                   # the settings' p2: our word
            uc.reg_write(UC_ARM_REG_R0, WORD)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif addr == USB_INIT:
            seen.append(uc.reg_read(UC_ARM_REG_R0))
            uc.emu_stop()
    uc.hook_add(UC_HOOK_CODE, code)
    uc.reg_write(UC_ARM_REG_SP, STACK)
    uc.reg_write(UC_ARM_REG_R0, OBJ)
    uc.reg_write(UC_ARM_REG_LR, 0x08000001)
    uc.emu_start(SETUP | 1, 0x08000000, count=200)
    assert len(seen) == 1, seen
    return seen[0]


def main():
    stock, img = (open(p, "rb").read() for p in sys.argv[1:3])
    assert usb_class(stock, True) == 0x101 and usb_class(stock, False) == 0x001, "the stock's set-up"
    print("PASS stock: the setting's bit 17 adds the mass storage class (0x101), off = USB MIDI only (0x001)")
    assert usb_class(img, True) == 0x001 and usb_class(img, False) == 0x001
    print("PASS Easy Start removed: USB MIDI only, whatever the setting")
    for lo, hi in HOLES:
        assert img[lo - BASE:hi - BASE] == bytes([0xFF]) * (hi - lo), f"{lo:#x}"
    assert img[0x0805144A - BASE:0x0805144C - BASE] == b"\x00\xbf" and img[0x0805176C - BASE:0x0805176E - BASE] == b"\x00\x20"
    assert img[0x0802764A - BASE:0x0802764E - BASE] == b"\xaf\xf3\x00\x80" and img[0x0802766E - BASE:0x08027672 - BASE] == b"\x70\x47\x00\xbf"
    print("PASS the freed code is empty (1,992 B); button 9 does nothing, its LED is dark, the transport is never called")
    print("ALL PASS")


if __name__ == "__main__":
    main()
