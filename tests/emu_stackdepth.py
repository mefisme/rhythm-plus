"""The UI task's stack: the deepest use of its entries (LED frame, output stage, buttons, pads, knobs) on every editor page, in Settings
and Assignments, kept under LIMIT.  The UI task's stack is 2 048 B; the dump's task waits 104 B deep (its saved context included), and an
interrupt with the FPU on pushes up to 104 B more.

usage: emu_stackdepth.py <build>      (RH_STACK_LIMIT overrides LIMIT)"""
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / "tests"), str(HERE / "modules"), str(HERE / "remix" / "tools")]
import emu_fx_native_edges as F  # noqa: E402   (sets RH_BUILD from argv[1])
M, G, SM = F.E, F.G, F.SM
from emu_playfix import STACK  # noqa: E402
from unicorn import UC_HOOK_MEM_WRITE  # noqa: E402

LIMIT = int(os.environ.get("RH_STACK_LIMIT", 1280))
TICK = 0x20000820                                         # the ms counter the Granular page's hold timer reads
DOWN = 19
SP0 = STACK + 0xF0000


def main():
    fw = (HERE / "firmware" / os.environ["RH_BUILD"] / f"rhythmplus-{os.environ['RH_BUILD'].upper()}.bin").read_bytes()
    uc = F.setup()
    gr = M.MAN["report"]["granular"]
    menu, slot = int(gr["ui"]["menu"], 16), int(gr["bridge"]["slot"], 16)
    ui_frame = gr["arm_kernel"]["labels"]["c_gr_runtime_ui_frame"]
    low = [SP0]
    uc.hook_add(UC_HOOK_MEM_WRITE, lambda u, k, a, n, v, d: low.__setitem__(0, min(low[0], a)), None, STACK, SP0)
    head = M.rhbuild.bl_target(bytearray(fw), M.C.LED_CALLS[0])
    out_fn = M.rhbuild.bl_target(bytearray(fw), M.T.OUT_CALL)
    deep, settings = {}, {}

    def note(name, fn):
        low[0] = SP0
        fn()
        deep[name] = max(deep.get(name, 0), SP0 - low[0])

    def frame():
        M.led(uc, head)
        M.out(uc, out_fn)

    def hold(p):
        G.pad(uc, p)
        uc.mem_write(TICK, struct.pack("<I", M.u32(uc, TICK) + 400))
        M.call(uc, ui_frame, slot, 0, 1)
        G.unpad(uc, p)

    SM.sel(uc, 0)
    note("LED + output, track view", frame)
    uc.mem_write(menu + M.T.O_OPEN, bytes([1]))          # the Track Parameter Editor open
    note("LED + output, editor", frame)
    for p in (25, 26, 27, 28, 29):                       # page pads 26-30
        note("pad: page", lambda: (G.pad(uc, p), G.unpad(uc, p)))
        note("LED + output, page", frame)
        note("knob turns, page", lambda: [M.knob(uc, k, 2) for k in range(8)])
        note("hold page pad: Settings", lambda: hold(p))
        settings[p] = uc.mem_read(slot + 102, 1)[0]
        note("LED + output, Settings", frame)
        note("knob turn, Settings", lambda: M.knob(uc, 1, 2))
        note("button: Down, Assignments", lambda: M.tap(uc, DOWN))
        note("LED + output, Assignments", frame)
        note("knob turn, Assignments", lambda: M.knob(uc, 1, 2))
        note("pad: close", lambda: (G.pad(uc, p), G.unpad(uc, p)))
    note("button: Clear", lambda: M.press(uc, 23))
    note("LED + output, Clear held", frame)
    note("knob turn, Clear held", lambda: M.knob(uc, 1, 3))
    note("button: Clear release", lambda: M.release(uc, 23))
    uc.mem_write(menu + M.T.O_OPEN, bytes([0]))
    for b in (46, 45):                                   # Mixer, Patterns
        note("button: view", lambda: M.tap(uc, b))
        note("LED + output, view", frame)
    worst = max(deep, key=deep.get)
    rep = M.MAN["report"]
    want = [26, 27] + ([28, 29, 30] if all(k in rep for k in ("filter_cutoff", "pitch_envelope_dsp", "ring_mod_dsp")) else [])
    opened = [p + 1 for p, v in settings.items() if v == 1]
    print(("PASS" if opened == want else "FAIL") + f" Settings open on the page pads {opened}")
    ok = deep[worst] <= LIMIT and opened == want
    print(("PASS" if ok else "FAIL") + f" the UI task's deepest entry: {worst}, {deep[worst]} B (limit {LIMIT} B of 2 048)")
    print("ALL PASS" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
