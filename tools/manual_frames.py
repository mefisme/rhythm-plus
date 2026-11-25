"""Writes manual/frames.json: the unit's 69 LED words for the manual's Track Parameter Editor drawings, from the emulator.
    python tools/manual_frames.py [build]      (default a301; needs DSPTOOL for the build's tests)"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = sys.argv[1] if len(sys.argv) > 1 else "a301"
sys.argv = [sys.argv[0], BUILD]
sys.path.insert(0, str(ROOT / "tests"))
import emu_fx_native_edges as fixture  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R0  # noqa: E402

G, E, SM = fixture.G, fixture.E, fixture.SM
UNSET = 0x404040                                   # a word the Granular draw leaves to the stock's output


def main():
    u = fixture.setup()
    gr = E.MAN["report"]["granular"]
    slot, menu = int(gr["bridge"]["slot"], 16), int(gr["ui"]["menu"], 16)
    labels = gr["arm_kernel"]["labels"]
    buf = 0x20001000
    SM.sel(u, 0)
    u.mem_write(menu + E.T.O_OPEN, b"\1")
    u.mem_write(G.CONT + 0x264, b"\0")

    def call(name, *args):
        E.call(u, labels["c_gr_" + name], *args)
        return u.reg_read(UC_ARM_REG_R0)

    def frame(ms=20):
        for address in (0x20000820, 0x20006f3c):
            u.mem_write(address, struct.pack("<I", E.u32(u, address) + ms))
        call("runtime_ui_frame", slot, 0, 1)
        call("runtime_frame", slot, 1, 0)

    def tap(p):
        G.pad(u, p); frame(); G.unpad(u, p); frame()

    def held_clear(on):
        w = E.u32(u, E.C.CTRL + 0xA0)
        u.mem_write(E.C.CTRL + 0xA0, struct.pack("<I", w | 1 << 23 if on else w & ~(1 << 23)))
        G.held(u, 23, on)

    def shot():
        E.led(u, E.LB["c_tmled"])
        base = list(E.out(u))
        u.mem_write(buf, struct.pack("<69I", *([UNSET] * 69)))
        call("runtime_draw", slot, 0, buf, max(u.mem_read(menu + 8, 1)[0], 1) - 1)
        over = struct.unpack("<69I", u.mem_read(buf, 69 * 4))
        full = [o if o != UNSET else b for b, o in zip(base, over)]
        u.mem_write(buf, struct.pack("<69I", *full))
        u.mem_write(buf + 0x200, bytes(8))
        call("clear_views", slot, 0, buf, buf + 0x200)
        return list(struct.unpack("<69I", u.mem_read(buf, 69 * 4)))

    frames = {}
    for name, pad in (("stock", 25), ("granular", 26), ("filter", 27), ("pitch", 28), ("extras", 29)):
        tap(pad)
        frames[name] = shot()
    tap(26)
    G.pad(u, 26)
    for _ in range(40):
        frame()
    G.unpad(u, 26); frame()
    frames["granular_settings"] = shot()
    E.press(u, 19); E.release(u, 19); frame()
    frames["granular_assign"] = shot()
    tap(26); tap(25)
    held_clear(True); frame()
    frames["clear"] = shot()
    held_clear(False); frame()
    out = ROOT / "manual" / "frames.json"
    out.write_text(json.dumps({"build": BUILD, "frames": frames}, indent=0))
    print(out)


if __name__ == "__main__":
    main()
