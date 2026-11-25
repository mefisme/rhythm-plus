"""MIDI Thru modes, USB merge, the Merge clock rule and the settings save, run on the RAM dump.
    python tests/emu_midimerge.py BUILD
"""
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / d) for d in ("modules", "builds", "tests", "remix/tools")]
from emu_playfix import SENT, STACK, call, machine  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_SP  # noqa: E402
import countin as CI  # noqa: E402
import midimerge as MM  # noqa: E402
import midithru as M  # noqa: E402
import rhbuild  # noqa: E402

FAILS = []
THRU, OUT2, MERGE, FILTER = 0, M.B16, M.B16 | M.B30, M.B16 | M.B31   # bit 16 set: the Thru jack on the unit's second UART


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def main():
    build = sys.argv[1]
    d = HERE / "firmware" / build
    fw = (d / f"rhythmplus-{build.upper()}.bin").read_bytes()
    rep = json.loads((d / "manifest.json").read_text())["report"]
    if "midimerge" not in rep:
        print("SKIP no MIDI merge in this build\nALL PASS")
        return
    mm = rep["midimerge"]
    lab = {k: int(v, 16) for k, v in mm["labels"].items()}
    prev = {k: int(v, 16) for k, v in mm["prev"].items()}
    ram = (HERE / "remix/stock/rhythm-ram-frd1-synced.bin").read_bytes()
    u = machine(fw, ram, mclass=True)
    u32 = lambda a: struct.unpack("<I", u.mem_read(a, 4))[0]  # noqa: E731
    w32 = lambda a, v: u.mem_write(a, struct.pack("<I", v))  # noqa: E731

    check("the DIN In post goes to c_mmin", rhbuild.bl_target(fw, M.POST_CALL) == lab["c_mmin"])
    check("the out ports' slot 2 is c_mmtx", u32(M.PORT_VT + 8) == lab["c_mmtx"] | 1)
    check("the Setup view's pads go to c_mmpad", u32(MM.SETUP_VT) == lab["c_mmpad"] | 1)
    check("the stock drives the Thru switch with !bit 16 (lsrs #16, and #1, eor #1)",
          fw[0x080356C0 - 0x08010000:0x080356CA - 0x08010000] == bytes.fromhex("000c00f0010080f00100"))
    check("every LED call goes to c_mmled", all(rhbuild.bl_target(fw, c) == lab["c_mmled"] for c in CI.LED_CALLS))

    sends, posts, saves, pads, commits = [], [], [], [], []


    def ret(uc, v=None):
        if v is not None:
            uc.reg_write(UC_ARM_REG_R0, v)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def hook(uc, a, n, _):
        r0, r1 = uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)
        if a == M.PORT_SEND:
            sends.append((r0, bytes(uc.mem_read(r1, 3))))
            ret(uc, 1)
        elif a == prev["post"]:
            posts.append(r1)
            ret(uc, 1)
        elif a == MM.SAVE:
            saves.append(r0)
            ret(uc)
        elif a == prev["pad"]:
            pads.append(r1)
            ret(uc)
        elif a == CI.COMMIT:
            commits.append(r0)
            ret(uc)
        elif a == prev["ledtask"]:
            ret(uc)
    for a in (M.PORT_SEND, prev["post"], MM.SAVE, prev["pad"], CI.COMMIT, prev["ledtask"]):
        u.hook_add(UC_HOOK_CODE, hook, None, a, a + 1)

    call(u, M.PARAM_GET, M.SETTINGS, 2)
    p2_at = u.reg_read(UC_ARM_REG_R0)
    ports = u32(u32(M.ROUTER_PTR) + 0x14)
    usb, port2 = u32(ports + 4 * MM.USB), u32(ports + 4 * M.PORT2)
    check("the router has a USB port and port 2", usb != 0 and port2 != 0, f"{usb:#x} {port2:#x}")
    base_p2 = u32(p2_at) & ~(M.B16 | M.B30 | M.B31 | MM.USB_BIT)
    msg = 0x20000400

    def clock_tx(on):
        f = u.mem_read(MM.TX + MM.O_TXF, 1)[0]
        u.mem_write(MM.TX + MM.O_TXF, bytes([(f | MM.CLOCK_TX) if on else (f & ~MM.CLOCK_TX)]))

    def din(mode_bits, data, port=M.DIN_IN):
        w32(p2_at, base_p2 | mode_bits)
        u.mem_write(msg, bytes(data) + b"\0" * (3 - len(data)))
        sends.clear()
        posts.clear()
        call(u, lab["c_mmin"], 0x20000800, port, msg)
        return [p for p, _ in sends], list(posts)

    # a channel the unit listens on, and one it does not
    recv = u32(M.RECV_PTR)
    listened = set(u.mem_read(recv + M.O_TABLE, M.N_TABLE))
    free = next(c for c in range(16) if c not in listened)
    heard = next(iter(listened))
    note = lambda ch: [0x90 | ch, 60, 100]  # noqa: E731

    clock_tx(True)
    check("Thru: no copy, the post", din(THRU, note(free)) == ([], [M.DIN_IN]))
    check("Out 2: no copy", din(OUT2, note(free))[0] == [])
    check("bit 16 clear: the hardware thru, no copy even with bit 30", din(M.B30, note(free))[0] == [])
    check("Merge: a note to port 2", din(MERGE, note(free))[0] == [port2])
    check("Merge: a note on a heard channel to port 2 too", din(MERGE, note(heard))[0] == [port2])
    for b in (0xF8, 0xFA, 0xFB, 0xFC):
        check(f"Merge, Clock Tx on: {b:#x} not copied, still posted", din(MERGE, [b]) == ([], [M.DIN_IN]))
    check("Merge, Clock Tx on: active sensing copied", din(MERGE, [0xFE])[0] == [port2])
    check("Filter: a note on a free channel to port 2", din(FILTER, note(free))[0] == [port2])
    check("Filter: a note on a heard channel stays", din(FILTER, note(heard))[0] == [])
    check("Filter, Clock Tx on: the clock passes", din(FILTER, [0xF8])[0] == [port2])
    check("USB merge: a note to USB", din(MM.USB_BIT | THRU, note(free))[0] == [usb])
    check("USB merge, Clock Tx on: the clock not copied", din(MM.USB_BIT | THRU, [0xF8])[0] == [])
    check("USB merge + Merge: both", din(MM.USB_BIT | MERGE, note(free))[0] == [usb, port2])
    check("USB in: no copies", din(MM.USB_BIT | MERGE, note(free), port=0) == ([], [0]))
    clock_tx(False)
    check("Merge, Clock Tx off: the clock passes", din(MERGE, [0xF8])[0] == [port2])
    check("USB merge, Clock Tx off: the clock passes", din(MM.USB_BIT | THRU, [0xFA])[0] == [usb])
    clock_tx(True)

    def own(mode_bits, port):
        w32(p2_at, base_p2 | mode_bits)
        u.mem_write(msg, bytes(note(free)))
        sends.clear()
        call(u, lab["c_mmtx"], port, msg)
        return [p for p, _ in sends]
    check("Filter: the unit's own MIDI to port 2 dropped", own(FILTER, port2) == [])
    check("Filter: the unit's own MIDI to the MIDI Out sent", own(FILTER, u32(ports + 4)) == [u32(ports + 4)])
    check("Merge: the unit's own MIDI to port 2 sent", own(MERGE, port2) == [port2])

    view = 0x20000600
    u.mem_write(view, b"\0" * 0x40)
    w32(view + 0xC, M.SETTINGS)
    call(u, CI.WPTR, M.SETTINGS, 2)
    staged = u.reg_read(UC_ARM_REG_R0)              # the stock's commit (hooked here) copies it to the settings
    seen = []
    for mode in (THRU, OUT2, MERGE, FILTER):
        w32(p2_at, base_p2 | mode)
        w32(staged, base_p2 | mode)
        call(u, lab["c_mmbtn"], view)
        seen.append(u32(staged) & (M.B16 | M.B30 | M.B31))
    check("Duplicate: Thru -> Out 2 -> Merge -> Filter -> Thru", seen == [OUT2, MERGE, FILTER, THRU], [hex(s) for s in seen])
    check("Duplicate keeps the other bits", u32(staged) & ~(M.B16 | M.B30 | M.B31) == base_p2 & ~(M.B16 | M.B30 | M.B31))

    pal = 0x20000700
    u.mem_write(pal + 0x3D6, struct.pack("<HH", 0x7E, 0x57))
    w32(view + 4, 0x1234)

    def led(p2):
        u.reg_write(UC_ARM_REG_R1, p2)
        u.reg_write(UC_ARM_REG_R4, view)
        u.reg_write(UC_ARM_REG_R5, pal)
        u.reg_write(UC_ARM_REG_SP, STACK + 0xF0000)
        u.reg_write(UC_ARM_REG_LR, SENT | 1)
        u.emu_start(lab["c_mmdup"] | 1, SENT, count=1000)
        return u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1)
    got = [led(base_p2 | b)[0] for b in (THRU, OUT2, MERGE, FILTER)]
    check("Duplicate LED: Thru dim red, Out 2 green, Merge yellow, Filter blue", got == [0x57, 0x7E, M.COL_MERGE, M.COL_FILTER],
          [hex(g) for g in got])
    check("Duplicate LED: r1 = [view + 4]", led(base_p2)[1] == 0x1234)

    w32(p2_at, base_p2)
    w32(staged, base_p2)
    u.mem_write(view + 0x24, b"\1")
    commits.clear()
    pads.clear()
    call(u, lab["c_mmpad"], view, MM.PAD, 100)
    check("Advanced Setup pad 23: USB merge on, committed", u32(staged) & MM.USB_BIT and commits == [M.SETTINGS] and not pads)
    call(u, lab["c_mmpad"], view, MM.PAD, 100)
    check("pad 23 again: off", not u32(staged) & MM.USB_BIT and len(commits) == 2)
    call(u, lab["c_mmpad"], view, 5, 100)
    u.mem_write(view + 0x24, b"\0")
    call(u, lab["c_mmpad"], view, MM.PAD, 100)
    check("other pads, and pad 23 outside Advanced Setup, go to the stock", pads == [5, MM.PAD] and not u32(staged) & MM.USB_BIT)

    w32(MM.SAVER, MM.SAVER_VT)
    w32(MM.SAVER + MM.O_STORE, M.SETTINGS)
    u.mem_write(MM.RAM, b"\0" * 8)
    call(u, CI.PARAM_GET, CI.TRANSPORT, 0)
    playing = u.reg_read(UC_ARM_REG_R0)
    u.mem_write(playing, b"\0")
    frame = 0x20000900
    saves.clear()
    call(u, lab["c_mmled"], 0x200487C8, frame)
    check("LED task: the first frame takes the bits, no save", not saves and u.mem_read(MM.RAM + 4, 1)[0] == MM.KNOWN)
    call(u, lab["c_mmled"], 0x200487C8, frame)
    check("LED task: no change, no save", not saves)
    w32(p2_at, base_p2 | M.B30)
    u.mem_write(playing, b"\1")
    call(u, lab["c_mmled"], 0x200487C8, frame)
    check("LED task: a change while playing waits", not saves)
    u.mem_write(playing, b"\0")
    call(u, lab["c_mmled"], 0x200487C8, frame)
    check("LED task: the change saved once stopped", saves == [MM.SAVER])
    call(u, lab["c_mmled"], 0x200487C8, frame)
    check("LED task: saved once", saves == [MM.SAVER])
    w32(p2_at, base_p2 | M.B30 | 1)
    call(u, lab["c_mmled"], 0x200487C8, frame)
    check("LED task: a stock bit (0-19) is the stock's to save", saves == [MM.SAVER])

    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
