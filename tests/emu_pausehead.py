"""Unicorn test of pausehead.py on the RAM dump: the conversion's output against the stock's, pad by pad.
    python tests/emu_pausehead.py STOCK.bin BUILT.bin RAM.bin
The paused step's pad fades to white over 510 ms (dimmed white with the dim bit); every other case and pad is the stock's output; while
playing the "played" flag is set; nothing without our block.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import emu_countin as E  # noqa: E402  (ourram first, then countin)
import countin as C  # noqa: E402
import pausehead as P  # noqa: E402
import rhstate  # noqa: E402
from emu_playfix import call, machine  # noqa: E402

E.MAN = __import__("json").loads((HERE / "firmware" / "stci8" / "manifest.json").read_text())
C_RST = int(E.MAN["report"]["rhstate"]["labels"]["c_rst"], 16)
C_PHCONV = int(E.MAN["report"]["pausehead"]["labels"]["c_phconv"], 16)
MGR = 0x20048B9C
FRAME, OUT = 0x2004FD00, 0x2004F900                     # scratch in the dump's unused stack area
SLOT = rhstate.ST + rhstate.OFF["pausehd"][0]
check, u32, w32, setp = E.check, E.u32, E.w32, E.setp


def state(uc, played=1, playing=0, mode=0, track=0, page=0, step=5, frame_ok=True, view=MGR, dim=0):
    if played is not None:
        uc.mem_write(SLOT, bytes([played]))
    setp(uc, C.TRANSPORT, 0, playing)
    w32(uc, C.CTRL + P.O_VIEW, view)
    uc.mem_write(MGR + P.O_MODE, bytes([mode]))
    setp(uc, u32(uc, MGR + 0x25C), 0, track)
    obj = u32(uc, MGR + P.O_STEPVIEWS + 4 * track)
    setp(uc, u32(uc, obj + P.O_PAGE), 0, page)
    setp(uc, u32(uc, obj + P.O_STEP), 1, step)
    codes = uc.mem_read(u32(uc, u32(uc, obj + 4)) + 32 * page, 32)
    uc.mem_write(FRAME, bytes(codes) + bytes(138 - 32))
    if not frame_ok:
        uc.mem_write(FRAME + 6, struct.pack("<H", struct.unpack("<H", codes[6:8])[0] ^ 1))
    if dim is not None:
        store = u32(uc, C.CTRL + P.DIM_STORE)
        for o in (0xC, 0x10):
            a = u32(uc, store + o) + 8
            w32(uc, a, (u32(uc, a) & ~(1 << P.DIM_BIT)) | (dim << P.DIM_BIT))


def outs(uc, fn):
    uc.mem_write(OUT, bytes(69 * 4))
    call(uc, fn, C.CTRL, OUT, FRAME)
    return [u32(uc, OUT + 4 * i) for i in range(69)]


def run(fw, ram, t, block=True, **kw):
    """(the stock conversion's output, ours) for one frame at HAL ms t."""
    uc = machine(fw, ram)
    E.tick(uc, t)
    if block:
        call(uc, C_RST)
    state(uc, **({} if block else {"played": None}) | kw)
    return outs(uc, P.CONV), outs(uc, C_PHCONV), uc


def faded(c, t, white=0xFF):
    w = t % P.FADE_MS
    f = w if w <= 255 else P.FADE_MS - w
    ch = [((c >> 8 * k & 0xFF) * (255 - f) + white * f) // 255 for k in range(3)]
    return c & 0xFF000000 | ch[2] << 16 | ch[1] << 8 | ch[0]


def only_pad(ref, got, pad, want):
    return got[pad] == want and all(got[i] == ref[i] for i in range(69) if i != pad)


def main():
    stock, fw, ram = (open(p, "rb").read() for p in sys.argv[1:4])
    for t, name in ((20400, "0 ms into the fade: the step's colour"), (20400 + 255, "255 ms: white"), (20400 + 100, "100 ms: mixed"),
                    (20400 + 400, "400 ms: on the way back")):
        ref, got, _ = run(fw, ram, t)
        check(f"stopped, step 6: pad 6 {name}, the rest as stock", only_pad(ref, got, 5, faded(ref[5], t)), f"{got[5]:#x} vs {faded(ref[5], t):#x}")
    ref, got, _ = run(fw, ram, 20400 + 255)
    check("dim off: full white", got[5] & 0xFFFFFF == 0xFFFFFF, hex(got[5]))
    ref, got, _ = run(fw, ram, 20400 + 255, dim=1)
    check("dim on: white dimmed as the pads (0x8C)", only_pad(ref, got, 5, faded(ref[5], 20400 + 255, P.DIM_WHITE)), hex(got[5]))
    ref, got, _ = run(fw, ram, 20400 + 255, step=20, page=1)
    check("step 21 on the page 17-32: pad 5", only_pad(ref, got, 4, faded(ref[4], 20400 + 255)))
    ref, got, _ = run(fw, ram, 20400 + 255, track=3, step=9)
    check("track 4 selected: its step view, pad 10", only_pad(ref, got, 9, faded(ref[9], 20400 + 255)))
    ref, got, _ = run(fw, ram, 20400 + 255, mode=2)
    check("mode 2 (a step view too): faded", got[5] != ref[5])
    for name, kw in (("step 21, page 1-16 shown", dict(step=20, page=0)), ("not played since power-on", dict(played=0)),
                     ("mode 4 (not a step view)", dict(mode=4)), ("mode 7", dict(mode=7)), ("the top pads show something else", dict(frame_ok=False)),
                     ("no view manager", dict(view=0)), ("another view", dict(view=0x20048B4C)), ("step store 40", dict(step=40))):
        ref, got, _ = run(fw, ram, 20400 + 255, **kw)
        check(f"{name}: as stock", got == ref)
    ref, got, uc = run(fw, ram, 20400 + 255, played=0, playing=1)
    check("playing: as stock", got == ref)
    check("playing: the played flag set", uc.mem_read(SLOT, 1)[0] == 1)
    ref, got, uc = run(fw, ram, 20400 + 255, block=False)
    check("block not set up: as stock", got == ref)
    before = bytes(machine(fw, ram).mem_read(rhstate.ST, rhstate.SIZE))
    check("block not set up: nothing written there", bytes(uc.mem_read(rhstate.ST, rhstate.SIZE)) == before)

    sm, bm = machine(stock, ram), machine(fw, ram)
    for uc in (sm, bm):
        E.tick(uc, 20400 + 255)
        state(uc, played=None, dim=None)
    a = outs(sm, P.CONV)
    b = outs(bm, C_PHCONV)
    check("stock image vs built, block not set up: same output", a == b)
    skip = set(range(OUT, OUT + 276))
    ra, rb = bytes(sm.mem_read(0x20000000, 0x50000)), bytes(bm.mem_read(0x20000000, 0x50000))
    diff = [0x20000000 + i for i in range(len(ra)) if ra[i] != rb[i] and 0x20000000 + i not in skip]
    check("stock image vs built: same RAM", not diff, f"{len(diff)} bytes, first {diff[:4]}")
    print("ALL PASS" if not E.fails else f"{len(E.fails)} FAILED")
    sys.exit(1 if E.fails else 0)


if __name__ == "__main__":
    main()
