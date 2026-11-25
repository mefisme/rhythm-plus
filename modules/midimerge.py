"""MIDI Thru modes (Thru, Out 2, Merge, Filter), USB merge and their save (MIT; from Circuit Remix's midithru, usbmerge and setsave,
for the Circuit Rhythm 5706; stock facts in remix/tools/midithru.py and usbmerge.py).

  * Duplicate in Advanced Setup: Thru -> Out 2 -> Merge -> Filter -> Thru; its LED dim red Thru, green Out 2, yellow Merge, blue Filter.
    Bit 16 of the device settings' parameter 2 set = the Thru jack on USART2 (the stock's listener 0x080356AC drives the switch pin with
    !bit 16; Novation's guide: green = second MIDI Out, the default dim red = the hardware thru).  Thru 0, Out 2 bit 16, Merge bits 16 + 30,
    Filter bits 16 + 31.  remix/tools/midithru.py reads bit 16 the other way round.
  * Merge: every DIN In message also goes out of the Thru jack, with the unit's own MIDI.  Filter: the DIN In messages, but channel
    messages on a channel the unit listens on, and none of the unit's own.
  * Advanced Setup pad 23: USB merge (bit 28): the DIN In also goes to USB.
  * Clock rule: with Clock Tx on, the DIN In's clock and transport (F8, FA-FC) go neither to the Thru jack in Merge nor to USB: the
    unit sends its own.  With Clock Tx off they pass.  Filter always passes them (the unit's own clock is not sent there).
  * The settings are saved when bits 20-31 of parameter 2 change, with the transport stopped (the stock saves only on bits 0-19).
SysEx from the DIN In is not copied.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "remix" / "tools"))
from thumb import (Asm, adds_imm8, adds_reg, ands_reg, b, b_cond, b_w, bics_reg, bl, cmp_imm, cmp_reg, eors_reg, h, ldr_imm,  # noqa: E402
                   ldrb_imm, ldrb_reg, ldrb_w, lsls_imm, lsrs_imm, mov_reg, movs_imm, movt, movw, orrs_reg, pop_list, push_list, raw,
                   str_imm, strb_imm, strh_imm)
import countin as CI  # noqa: E402
import midithru as M  # noqa: E402

SETUP_VT, SETUP_MODE = 0x08067C74, 9  # the Setup view's vtable (slot 0 = its pads) and the controller's mode for it (remix/tools/pgmch.py)
SAVER, SAVER_VT, SAVE, O_STORE = 0x2003CD88, 0x08068F6C, 0x080356D0, 0xB0   # the device settings' saver (remix/tools/setsave.py)
TX, O_TXF, CLOCK_TX = 0x200126B0, 0x18, 0x08    # the transmitter: [+ 0x18] bit 3 = Clock Tx
USB, USB_BIT, PAD = 0, 1 << 28, 22               # USB merge: the out port, its bit of parameter 2, Advanced Setup pad 23
COL_ON, COL_DIM = 0x1E, 0x1F                     # green, dim green

RAM = 0x3AE8                          # ITCM, 8 B: the last bits 20-31 seen, + 4 KNOWN once taken (free with NO_A3, above the guard 0x3AE0)
KNOWN = 0x5E


def popw(regs, lr=False): return h(0xE8BD) + h(sum(1 << r for r in regs) | (1 << 14 if lr else 0))


def advanced(E, imm32, L, no):
    """'the Advanced Setup view is on the screen' (r4 = CTRL afterwards); clobbers r0-r3; to `no` if not"""
    E(bl, L["c_ciok"])
    E(cmp_imm, 0, 0)
    E(b_cond, no, "eq")
    imm32(4, CI.CTRL)
    E(ldr_imm, 0, 4, 0x7C)
    E(cmp_imm, 0, 0)
    E(b_cond, no, "ne")
    E(ldr_imm, 0, 4, 0x14)
    E(movs_imm, 1, 0)
    E(bl, L["c_cinew"])
    E(cmp_imm, 0, SETUP_MODE)
    E(b_cond, no, "ne")
    E(ldr_imm, 0, 4, 0x78)
    E(ldrb_w, 0, 0, 0x24)
    E(cmp_imm, 0, 0)
    E(b_cond, no, "eq")


def toggle(E, imm32, bit):
    """parameter 2 of the device settings XOR bit, committed; clobbers r0-r3"""
    imm32(0, M.SETTINGS)
    E(movs_imm, 1, 2)
    E(bl, CI.WPTR)
    E(ldr_imm, 1, 0, 0)
    imm32(2, bit)
    E(eors_reg, 1, 2)
    E(str_imm, 1, 0, 0)
    imm32(0, M.SETTINGS)
    E(bl, CI.COMMIT)


def p2bit(E, imm32, bit):
    """r0 = bit `bit` of parameter 2 (0 / non-zero); clobbers r1-r3"""
    imm32(0, M.SETTINGS)
    E(movs_imm, 1, 2)
    E(bl, CI.PARAM_GET)
    E(ldr_imm, 0, 0, 0)
    imm32(1, bit)
    E(raw, h(0x4008))                                                     # ands r0, r1


def arm_code(base, L, prev):
    a = Asm(base)
    E = a.emit

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, (v >> 16) & 0xFFFF)

    def port(rd, n):
        imm32(rd, M.ROUTER_PTR)
        E(ldr_imm, rd, rd, 0)
        E(ldr_imm, rd, rd, 0x14)
        E(ldr_imm, rd, rd, 4 * n)

    def p2(rd):
        imm32(0, M.SETTINGS)
        E(movs_imm, 1, 2)
        E(bl, M.PARAM_GET)
        E(ldr_imm, rd, 0, 0)

    # ---- c_mmin (queue, port, bytes) in place of the post of a short input message: the copies, then the post
    a.label("c_mmin")
    E(push_list, [0, 1, 2, 4, 5, 6], lr=True)
    E(cmp_imm, 1, M.DIN_IN)
    E(b_cond, "mi_go", "ne")
    E(mov_reg, 4, 2)                                                      # r4 = the message
    p2(5)                                                                 # r5 = parameter 2
    E(movs_imm, 6, 0)                                                     # r6 = 1: a clock / transport message the unit sends itself
    E(ldrb_imm, 0, 4, 0)
    E(cmp_imm, 0, 0xF8)
    E(b_cond, "mi_c", "eq")
    E(cmp_imm, 0, 0xFA)
    E(b_cond, "mi_u", "lo")
    E(cmp_imm, 0, 0xFC)
    E(b_cond, "mi_u", "hi")
    a.label("mi_c")
    imm32(0, TX)
    E(ldrb_imm, 0, 0, O_TXF)
    E(lsls_imm, 0, 0, 28)
    E(b_cond, "mi_u", "pl")                                               # Clock Tx off: it passes
    E(movs_imm, 6, 1)
    a.label("mi_u")                                                       # USB merge
    E(lsls_imm, 0, 5, 3)
    E(b_cond, "mi_t", "pl")                                               # bit 28
    E(cmp_imm, 6, 0)
    E(b_cond, "mi_t", "ne")
    port(0, USB)
    E(cmp_imm, 0, 0)
    E(b_cond, "mi_t", "eq")
    E(ldr_imm, 3, 0, 0)
    E(ldr_imm, 3, 3, 8)
    E(mov_reg, 1, 4)
    E(raw, h(0x4798))                                                     # blx r3: its send
    a.label("mi_t")                                                       # the Thru jack
    E(lsls_imm, 0, 5, 15)
    E(b_cond, "mi_go", "pl")                                              # bit 16 clear: the hardware thru
    E(cmp_imm, 5, 0)
    E(b_cond, "mi_f", "lt")                                               # bit 31: Filter
    E(lsls_imm, 0, 5, 1)
    E(b_cond, "mi_go", "pl")                                              # bit 30 clear: Out 2
    E(cmp_imm, 6, 0)                                                      # Merge
    E(b_cond, "mi_go", "ne")
    E(b, "mi_fw")
    a.label("mi_f")                                                       # Filter: a channel message on a listened channel stays
    E(ldrb_imm, 0, 4, 0)
    E(cmp_imm, 0, 0x80)
    E(b_cond, "mi_fw", "lo")
    E(cmp_imm, 0, 0xF0)
    E(b_cond, "mi_fw", "hs")
    E(movs_imm, 1, 0x0F)
    E(ands_reg, 0, 1)                                                     # r0 = its channel
    imm32(5, M.RECV_PTR)
    E(ldr_imm, 5, 5, 0)                                                   # r5 = the receiver
    E(movs_imm, 2, M.O_TABLE)
    a.label("mi_lp")
    E(ldrb_reg, 1, 5, 2)
    E(cmp_reg, 1, 0)
    E(b_cond, "mi_go", "eq")
    E(adds_imm8, 2, 1)
    E(cmp_imm, 2, M.O_TABLE + M.N_TABLE)
    E(b_cond, "mi_lp", "lo")
    a.label("mi_fw")
    port(0, M.PORT2)
    E(mov_reg, 1, 4)
    E(bl, M.PORT_SEND)
    a.label("mi_go")
    E(raw, popw([0, 1, 2, 4, 5, 6], lr=True))
    E(b_w, prev["post"])

    # ---- c_mmtx (port, message): slot 2 of the out ports; Filter drops the unit's own messages to port 2
    a.label("c_mmtx")
    E(push_list, [0, 1, 4], lr=True)
    port(4, M.PORT2)
    E(cmp_reg, 0, 4)
    E(b_cond, "tx_go", "ne")
    p2(0)
    E(cmp_imm, 0, 0)
    E(b_cond, "tx_go", "ge")                                              # not Filter (bit 31)
    E(lsls_imm, 0, 0, 15)
    E(b_cond, "tx_go", "pl")                                              # bit 16 clear: the hardware thru
    E(raw, popw([0, 1, 4], lr=True))
    E(movs_imm, 0, 1)
    E(raw, h(0x4770))
    a.label("tx_go")
    E(raw, popw([0, 1, 4], lr=True))
    E(b_w, M.PORT_SEND)

    # ---- c_mmbtn (r0 = the Setup view): Duplicate in Advanced Setup, Thru -> Out 2 -> Merge -> Filter -> Thru (the caller commits)
    a.label("c_mmbtn")
    E(push_list, [4, 5, 6], lr=True)
    E(mov_reg, 4, 0)
    E(ldr_imm, 0, 4, 0xC)
    E(movs_imm, 1, 2)
    E(bl, M.PARAM_GET)
    E(ldr_imm, 6, 0, 0)                                                   # r6 = the mode now
    E(ldr_imm, 0, 4, 0xC)
    E(movs_imm, 1, 2)
    E(bl, M.PARAM_WPTR)
    E(mov_reg, 5, 0)
    E(ldr_imm, 1, 5, 0)
    imm32(2, M.B16 | M.B30 | M.B31)
    E(bics_reg, 1, 2)
    E(cmp_imm, 6, 0)
    E(b_cond, "tb_w", "lt")                                               # Filter -> Thru (no bit)
    imm32(2, M.B16 | M.B31)
    E(lsls_imm, 0, 6, 1)
    E(b_cond, "tb_o", "mi")                                               # Merge -> Filter
    imm32(2, M.B16 | M.B30)
    E(lsls_imm, 0, 6, 15)
    E(b_cond, "tb_o", "mi")                                               # Out 2 -> Merge
    imm32(2, M.B16)                                                       # Thru -> Out 2
    a.label("tb_o")
    E(orrs_reg, 1, 2)
    a.label("tb_w")
    E(str_imm, 1, 5, 0)
    E(pop_list, [4, 5, 6], pc=True)

    # ---- c_mmdup (r1 = parameter 2, r4 = the Setup view, r5 = the palette) -> r0 = the code of Duplicate's LED, r1 = [view + 4]
    a.label("c_mmdup")
    E(movs_imm, 0, M.COL_FILTER)
    E(cmp_imm, 1, 0)
    E(b_cond, "tl_x", "lt")
    E(movs_imm, 0, M.COL_MERGE)
    E(lsls_imm, 2, 1, 1)
    E(b_cond, "tl_x", "mi")
    E(movw, 0, 0x3D6)
    E(lsls_imm, 2, 1, 15)
    E(b_cond, "tl_p", "mi")
    E(movw, 0, 0x3D8)
    a.label("tl_p")
    E(adds_reg, 0, 0, 5)
    E(raw, h(0x8800))                                                     # ldrh r0, [r0]
    a.label("tl_x")
    E(ldr_imm, 1, 4, 4)
    E(raw, h(0x4770))

    # ---- c_mmpad (the Setup view's slot 0: view, pad, velocity): Advanced Setup pad 23 = USB merge on / off
    a.label("c_mmpad")
    E(cmp_imm, 1, PAD)
    E(b_cond, "up_s", "ne")
    E(push_list, [0, 1, 2, 3, 4, 5], lr=True)
    E(ldrb_w, 3, 0, 0x24)
    E(cmp_imm, 3, 0)
    E(b_cond, "up_p", "eq")                                               # not Advanced
    toggle(E, imm32, USB_BIT)
    E(pop_list, [0, 1, 2, 3, 4, 5], pc=True)
    a.label("up_p")
    E(raw, popw([0, 1, 2, 3, 4, 5], lr=True))
    a.label("up_s")
    E(b_w, prev["pad"])

    # ---- c_mmled (the LED task's calls: ctrl, frame): the chain, pad 23's LED in Advanced Setup, then the save of bits 20-31
    a.label("c_mmled")
    E(push_list, [3, 4, 5, 6], lr=True)
    E(mov_reg, 5, 1)
    E(bl, prev["ledtask"])
    advanced(E, imm32, L, "ml_s")
    p2bit(E, imm32, USB_BIT)
    E(movs_imm, 1, COL_DIM)
    E(cmp_imm, 0, 0)
    E(b_cond, "ml_w", "eq")
    E(movs_imm, 1, COL_ON)
    a.label("ml_w")
    E(strh_imm, 1, 5, 2 * PAD)
    a.label("ml_s")
    E(bl, L["c_ciok"])
    E(cmp_imm, 0, 0)
    E(b_cond, "ss_x", "eq")
    imm32(4, RAM)
    p2(5)
    E(lsrs_imm, 5, 5, 20)
    E(lsls_imm, 5, 5, 20)                                                 # r5 = bits 20-31
    E(ldrb_imm, 0, 4, 4)
    E(cmp_imm, 0, KNOWN)
    E(b_cond, "ss_k", "eq")
    E(movs_imm, 0, KNOWN)                                                 # the first: taken, no save
    E(strb_imm, 0, 4, 4)
    E(str_imm, 5, 4, 0)
    E(pop_list, [3, 4, 5, 6], pc=True)
    a.label("ss_k")
    E(ldr_imm, 0, 4, 0)
    E(cmp_reg, 0, 5)
    E(b_cond, "ss_x", "eq")
    imm32(0, CI.TRANSPORT)
    E(movs_imm, 1, 0)
    E(bl, CI.PARAM_GET)
    E(ldrb_imm, 0, 0, 0)
    E(cmp_imm, 0, 0)
    E(b_cond, "ss_x", "ne")                                               # playing: later
    imm32(6, SAVER)
    E(ldr_imm, 0, 6, 0)
    imm32(1, SAVER_VT)
    E(cmp_reg, 0, 1)
    E(b_cond, "ss_x", "ne")
    E(raw, h(0xF8D0 | 6) + h(O_STORE))                                 # ldr.w r0, [r6, #0xb0]: its store
    imm32(1, M.SETTINGS)
    E(cmp_reg, 0, 1)
    E(b_cond, "ss_x", "ne")
    E(str_imm, 5, 4, 0)
    E(mov_reg, 0, 6)
    E(bl, SAVE)
    a.label("ss_x")
    E(pop_list, [3, 4, 5, 6], pc=True)
    return a.assemble()


def install(img, report, base_addr):
    """The DIN In's post, the out ports' slot 2, Duplicate's toggle and LED in Advanced Setup, the Setup view's pads, the LED calls."""
    import rhbuild
    BASE = rhbuild.BASE
    assert "automation3" not in report, "the ITCM bytes at RAM belong to the automation bank"
    u = lambda a_: struct.unpack_from("<I", img, a_ - BASE)[0]                 # noqa: E731
    lab = lambda m, k: int(report[m]["labels"][k], 16)                         # noqa: E731
    L = dict(c_ciok=lab("countin", "c_ciok"), c_cinew=lab("countin", "c_cinew"))
    prev = dict(post=rhbuild.bl_target(img, M.POST_CALL), pad=u(SETUP_VT) & ~1, ledtask=rhbuild.bl_target(img, CI.LED_CALLS[0]))
    assert prev["post"] == M.POST, "the DIN In's post is already hooked"
    assert all(rhbuild.bl_target(img, c) == prev["ledtask"] for c in CI.LED_CALLS)
    code, labels = arm_code(base_addr, L, prev)
    if base_addr - BASE < len(img):         # in a free gap of the image (hole): it must be blank
        o = base_addr - BASE
        assert all(b == 0xFF for b in img[o:o + len(code)])
        img[o:o + len(code)] = code
    else:
        img += bytes([0xFF]) * (base_addr - BASE - len(img)) + code
        while len(img) % 4:
            img += bytes([0xFF])
    rhbuild.patch(img, M.POST_CALL, f"bl #{M.POST:#x}", bl(M.POST_CALL, labels["c_mmin"]))
    assert u(M.PORT_VT + 8) == M.PORT_SEND | 1
    rhbuild.patch_word(img, M.PORT_VT + 8, M.PORT_SEND | 1, labels["c_mmtx"] | 1)
    rhbuild.patch(img, M.BTN_TOGGLE, "ldr r0, [r4, #0xc]|movs r1, #2|bl #0x803fd26",
                  h(0x4620) + bl(M.BTN_TOGGLE + 2, labels["c_mmbtn"]) + b(M.BTN_TOGGLE + 6, M.BTN_COMMIT))
    rhbuild.patch(img, M.LED_CODE, "ubfx r0, r1, #0x10, #1|cmp r0, #0|ldr r1, [r4, #4]|ite ne|movwne r0, #0x3d6|moveq.w r0, #0x3d8|ldrh r0, [r5, r0]",
                  bl(M.LED_CODE, labels["c_mmdup"]) + h(0xBF00) * 8)
    rhbuild.patch_word(img, SETUP_VT, prev["pad"] | 1, labels["c_mmpad"] | 1)
    for c in CI.LED_CALLS:
        rhbuild.patch(img, c, f"bl #{prev['ledtask']:#x}", bl(c, labels["c_mmled"]))
    report["midimerge"] = dict(base=hex(base_addr), bytes=len(code), ram=hex(RAM), usb_pad=PAD + 1,
                               clock_rule="Clock Tx on: DIN In clock and transport not copied to the Thru jack in Merge or to USB",
                               prev={k: hex(v) for k, v in prev.items()},
                               labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
