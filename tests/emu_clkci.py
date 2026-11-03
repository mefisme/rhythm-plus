"""Unicorn test of clkci.py on the RAM dump: the count-in on the music's clock.
    python tests/emu_clkci.py STOCK.bin BUILT.bin RAM.bin
The stock's Play work is not run: a Play press that reaches the stock is followed here by what Play does to the clock (the transport's
p0 and the set_mode call at 0x0803333A, mode 1 with an external clock; when playing: p0 = 0 and the clock's stop).  The clock ticks every
ms through its thunk; a slave's MIDI clock pulses go through the clock's vtable [0].  Store listener calls are skipped (0x0803FC1C-0x0803FC22).
Master and slave, from countin's Play and from the Sample Rec view's Record (pad 24 on and off, stopped and with the music playing from
each beat of the bar: the stock's beat check called on each pulse here): clicks, the held start and its release on
pulse 96, the sampler's record call, the Record and Clear LEDs, the cancels, nothing recorded and the Play LED as stopped during a held
start, and the stock's behaviour without our block.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import emu_countin as E  # noqa: E402  (ourram first, then countin)
import emu_srcount as ES  # noqa: E402
import clkci as K  # noqa: E402
import countin as C  # noqa: E402
import srcount as S  # noqa: E402
from emu_playfix import call, machine  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1  # noqa: E402

check, u32, w32, setp = E.check, E.u32, E.w32, E.setp
BLK = K.BASE
TICK_LIT = 0x08032D2C                                   # the literal both timer registrations load
TICK_CB = None                                           # the clock timer's callback as the firmware registers it (set in main)
FL = BLK + K.O_FL
PF = K.rhstate.ST + K.rhstate.OFF["playfix"][0] if "playfix" in K.rhstate.OFF else None
LISTENER_LOAD, LISTENER_NEXT, STOP = 0x0803FC1C, 0x0803FC22, 0x08032A06    # the listener call (or playprobe's bl there)
T0 = 10000
RECORDER = 0x20040D88
RT_THIS = 0x2004E8B4                                     # the MIDI-in receivers' object (its vtable at 0x08066654)
DRIVER = 0x2003C200                                      # the transport driver: [+ 8] the clock, [+ 0xC] p3 the metronome
REC_METHODS = ((0x08036A80, 0x08036AAE, 0x08036AC2), (0x08036AC4, 0x08036AF0, 0x08036B02), (0x08036B06, 0x08036B32, 0x08036B52))


def now(uc, t):
    w32(uc, C.HAL_TICK, t)
    w32(uc, K.UWTICK, t)


def fl(uc): return uc.mem_read(FL, 1)[0]
def cstate(uc): return uc.mem_read(K.CLOCK + K.O_STATE, 1)[0]
def logw(uc, k): return u32(uc, BLK + K.O_LOG + 4 * k)


def records(uc):
    """For each record method of the recorder: True when it gets past its transport checks (it is stopped there, at its exit)."""
    setp(uc, C.TRANSPORT, 2, 0)
    out = []
    for fn, at, end in REC_METHODS:
        hit = []
        h = uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d, e=end: (hit.append(1), u.reg_write(UC_ARM_REG_PC, e | 1)), None, at, at + 1)
        call(uc, fn, RECORDER, 16, 100, 16)
        uc.hook_del(h)
        out.append(bool(hit))
    return out


WANT_PLED = {}


def pled(uc):
    """The Play LED's colour in its object's LED buffer (index 1)."""
    return struct.unpack("<H", uc.mem_read(u32(uc, u32(uc, K.PLED_OBJ + 4)) + 2, 2))[0]


def pled_poison(uc): uc.mem_write(u32(uc, u32(uc, K.PLED_OBJ + 4)) + 2, struct.pack("<H", 0xBEEF))


def want_pled(stock, ram):
    """The stock's Play LED colour stopped (p0 = 0) and playing (p0 = 1)."""
    for p0 in (0, 1):
        uc = machine(stock, ram)
        uc.mem_write(0x20000000, ram)
        uc.mem_write(0x20012888, ram[0x12888:0x12889])
        setp(uc, C.TRANSPORT, 0, p0)
        call(uc, K.PLED_DRAW, K.PLED_OBJ)
        WANT_PLED[p0] = pled(uc)


class Rig:
    """The machine, its hooks and the stock's answer to Play."""
    def __init__(self, fw, ram, slave=False, sr=False, mode=1, pad24=0, play=0, rec=1, shift=0):
        if sr:
            self.uc, self.log, _ = ES.setup(fw, ram, mode=mode, play=pad24)
        else:
            self.uc, self.log = E.setup(fw, ram, True)
            self.log.rec = []
            self.uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: (self.log.rec.append((u32(u, K.UWTICK), u.reg_read(UC_ARM_REG_R0))),
                                                               ES.sampler_state(u, 2), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                             None, K.REC_FN, K.REC_FN + 1)
            self.uc.mem_write(E.CI, bytes([C.CI_ON]))
        uc = self.uc
        self.pulse_fn = struct.unpack_from("<I", fw, K.CLOCK_VT0 - 0x08010000)[0] & ~1
        self.setmodes, self.rec_state, self.done = [], [], 0
        uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: u.reg_write(UC_ARM_REG_PC, LISTENER_NEXT | 1), None, LISTENER_LOAD, LISTENER_LOAD + 1)
        uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: self.setmodes.append((u32(u, K.UWTICK), u.reg_read(UC_ARM_REG_R1))), None,
                    K.SETMODE, K.SETMODE + 1)
        uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: self.rec_state.append(u.mem_read(K.CLOCK + K.O_STATE, 1)[0]), None,
                    K.REC_FN, K.REC_FN + 1)
        uc.mem_write(K.CLOCK + K.O_STATE, b"\x00")
        ext = uc.mem_read(K.CLOCK + K.O_EXT, 1)[0]
        uc.mem_write(K.CLOCK + K.O_EXT, bytes([(ext | 2) if slave else (ext & ~2)]))
        self.slave = slave
        setp(uc, C.TRANSPORT, 0, play)
        setp(uc, C.TRANSPORT, 1, rec)
        setp(uc, E.shift_store(uc), 0, shift)
        now(uc, T0)

    def stock(self):
        """The stock's Play for each new Play press: start (p0 = 1, set_mode through 0x0803333A) or stop."""
        uc = self.uc
        for p in self.log.press[self.done:]:
            if p[1] != C.ID_PLAY:
                continue
            if E.newest(uc, C.TRANSPORT, 0) == 0:
                setp(uc, C.TRANSPORT, 0, 1)
                call(uc, K.SETMODE_CALL, K.CLOCK, 1 if self.slave else 0)
            else:
                setp(uc, C.TRANSPORT, 0, 0)
                call(uc, STOP, K.CLOCK)
        self.done = len(self.log.press)

    def press(self, bid):
        E.press(self.uc, bid)
        self.stock()

    def run(self, t_end, t0=T0 + 1, period=20, first=7, on_pulse=None):
        """Each ms: a pulse every `period` ms (slave) from T0 + first, the clock's tick, then the LEDs every 2 ms.  Returns the frames of
        Record and Clear, the times of the pulses and the clock state just after each."""
        uc, rec, clr, pulses = self.uc, [], [], []
        for t in range(t0, t_end):
            now(uc, t)
            if self.slave and t >= T0 + first and (t - T0 - first) % period == 0:
                call(uc, self.pulse_fn, K.CLOCK)
                pulses.append((t, cstate(uc)))
                if on_pulse:
                    on_pulse(self, len(pulses), t)
            call(uc, TICK_CB, 0, K.CLOCK)
            if t % 2 == 0:
                uc.mem_write(E.FRAME, bytes(140))
                E.led(uc)
                self.stock()
                rec.append((t, ES.frame(uc, C.LED_REC)))
                clr.append((t, ES.frame(uc, C.LED_CLEAR)))
        return rec, clr, pulses


def want_master(uc):
    """The clicks (ms after the first) and the release, from the clock's per-ms step at the dump's tempo."""
    bpm = E.newest(uc, C.TEMPO, 0)
    bpm = bpm if bpm >= 30 else 120
    p = lambda ms: (ms * bpm * K.K) >> 32
    clicks = [next(ms for ms in range(20000) if p(ms) >= 24 * k) for k in (1, 2, 3)]
    return bpm, [0] + clicks, next(ms for ms in range(20000) if p(ms) >= 96)


def flash_ok(rec, starts, end, col):
    return all(v == (col if any(0 <= t - s < K.FLASH_MS for s in starts) else 0) for t, v in rec if starts[0] <= t < end)


def test_master(fw, ram):
    r = Rig(fw, ram)
    uc = r.uc
    bpm, clicks, rel = want_master(uc)
    r.press(C.ID_PLAY)
    check("master: the first click at the press", [c[0] for c in r.log.clicks] == [T0], f"{r.log.clicks}")
    check("master: Play reaches the stock at once, once", [(p[0], p[1]) for p in r.log.press] == [(T0, C.ID_PLAY)], f"{r.log.press}")
    check("master: the clock's start held", fl(uc) & K.HELD and not r.setmodes and cstate(uc) == 0 and uc.mem_read(BLK + K.O_MODE, 1)[0] == 0)
    rec, _, _ = r.run(T0 + rel + 300)
    got = [c[0] - T0 for c in r.log.clicks]
    check(f"master ({bpm} BPM): clicks on pulses 0, 24, 48, 72", got == clicks, f"{got} != {clicks}")
    check("master: the bar is 4 beats to the ms", abs(rel - 4 * 60000 / bpm) <= 1, f"{rel}")
    check("master: the start made on pulse 96 (set_mode 0)", r.setmodes == [(T0 + rel, 0)], f"{r.setmodes}")
    check("master: the clock running after", cstate(uc) == 3)
    if PF:
        check("master: playfix's start time = the release", u32(uc, PF + 4) == T0 + rel, f"{u32(uc, PF + 4)}")
    check("master: no second Play press, no sampler call", len(r.log.press) == 1 and not r.log.rec)
    check("master: the count over", fl(uc) == 0)
    check("master: the log (begin, held, clicks, release)", [logw(uc, k) for k in range(7)] == [T0, T0] + [T0 + c for c in clicks] + [T0 + rel],
          f"{[logw(uc, k) for k in range(8)]}")
    check("master: Record red 100 ms from each click, dark between", flash_ok(rec, [T0 + c for c in clicks], T0 + rel, C.COL_REC))
    check("master: clicks heard (level 64): no silent flash kept", u32(uc, E.VM) == 0)

    r = Rig(fw, ram)
    r.press(C.ID_PLAY)
    r.run(T0 + clicks[1] + 50)
    check("master: during the count (playing, Record on) nothing is recorded", records(r.uc) == [False] * 3, f"{records(r.uc)}")
    call(r.uc, K.PLED_DRAW, K.PLED_OBJ)
    check("master: during the count the Play LED drawn as stopped", pled(r.uc) == WANT_PLED[0], f"{pled(r.uc):#x} {WANT_PLED}")
    pled_poison(r.uc)
    r.run(T0 + rel + 300, T0 + clicks[1] + 50)
    check("master: after the count all three record methods record", records(r.uc) == [True] * 3, f"{records(r.uc)}")
    check("master: the Play LED drawn as playing on pulse 96", pled(r.uc) == WANT_PLED[1], f"{pled(r.uc):#x} {WANT_PLED}")
    call(r.uc, K.PLED_DRAW, K.PLED_OBJ)
    check("master: after the count the Play LED drawn as playing", pled(r.uc) == WANT_PLED[1], f"{pled(r.uc):#x}")

    r = Rig(fw, ram)
    r.press(C.ID_PLAY)
    r.run(T0 + clicks[1] + 50)
    r.press(C.ID_PLAY)
    r.run(T0 + rel + 300, T0 + clicks[1] + 50)
    check("master: Play during the count: the stock stops, no start", fl(r.uc) == 0 and len(r.log.press) == 2 and not r.setmodes
          and len(r.log.clicks) == 2 and E.newest(r.uc, C.TRANSPORT, 0) == 0)

    r = Rig(fw, ram)
    r.press(C.ID_PLAY)
    r.run(T0 + clicks[1] + 50)
    setp(r.uc, C.TRANSPORT, 0, 0)
    pled_poison(r.uc)
    r.run(T0 + rel + 300, T0 + clicks[1] + 50)
    check("master: transport stopped elsewhere: the count over, no start", fl(r.uc) == 0 and not r.setmodes and len(r.log.clicks) == 2)
    check("master: transport stopped elsewhere: the Play LED drawn as stopped", pled(r.uc) == WANT_PLED[0], f"{pled(r.uc):#x}")

    r = Rig(fw, ram, shift=1)
    r.press(C.ID_PLAY)
    check("master: Shift + Play reaches the stock with Shift", [p[2] for p in r.log.press] == [1], f"{r.log.press}")

    for name, kw in (("count-in off", dict()), ("Record not armed", dict(rec=0)), ("playing", dict(play=1))):
        r = Rig(fw, ram, **kw)
        if name == "count-in off":
            r.uc.mem_write(E.CI, b"\x00")
        r.press(C.ID_PLAY)
        r.run(T0 + 300)
        check(f"master, {name}: Play straight to the stock, no count", len(r.log.press) == 1 and not r.log.clicks and fl(r.uc) == 0)


def master(r, fw, *events):
    """The master's MIDI through the receivers (the stock's receivers return at once): ("start",), ("cont",), ("stop",), ("spp", value),
    ("pulses", n) before the press, 20 ms apart, ending at T0 - 20."""
    uc = r.uc
    if not getattr(r, "rt_hooked", False):
        for a in (K.RT_START, K.RT_CONT, K.RT_STOP, K.RT_SPP):
            uc.hook_add(UC_HOOK_CODE, lambda u, a_, s, d: u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)), None, a, a + 1)
        r.rt_hooked = True
    slot = {"start": 0, "cont": 1, "stop": 2, "spp": 3}
    for ev in events:
        if ev[0] == "pulses":
            for k in range(ev[1]):
                now(uc, T0 - 20 * (ev[1] - k))
                call(uc, r.pulse_fn, K.CLOCK)
        else:
            fn = struct.unpack_from("<I", fw, K.MIDI_RT_VT + 4 * slot[ev[0]] - 0x08010000)[0] & ~1
            call(uc, fn, RT_THIS, ev[1] if len(ev) > 1 else 0)


def test_master_bar(fw, ram):
    for name, events, phase in (("after Start + 40 pulses", (("start",), ("pulses", 40)), 40),
                                ("after Song Position 4 + Continue + 10 pulses", (("spp", 4), ("cont",), ("pulses", 10)), 34),
                                ("after Start + 96 pulses (on the bar)", (("start",), ("pulses", 96)), 0)):
        r = Rig(fw, ram, slave=True)
        master(r, fw, *events)
        r.press(C.ID_PLAY)
        _, _, pulses = r.run(T0 + 7 + 260 * 20)
        ts = [p[0] for p in pulses]
        j = (96 - phase) % 96
        check(f"slave, {name}: the clicks on the master's next bar", [c[0] for c in r.log.clicks] == [ts[j + 24 * k] for k in range(4)],
              f"{[c[0] for c in r.log.clicks]} first pulse {ts[0]}, want from pulse {j}")
        check(f"slave, {name}: the start on the master's bar after", r.setmodes == [(ts[j + 96], 1)] and pulses[j + 96][1] == 3,
              f"{r.setmodes}")
    for name, events in (("after Start + 40 pulses + Stop", (("start",), ("pulses", 40), ("stop",))),
                         ("no Start seen", (("pulses", 40),))):
        r = Rig(fw, ram, slave=True)
        master(r, fw, *events)
        r.press(C.ID_PLAY)
        _, _, pulses = r.run(T0 + 7 + 120 * 20)
        ts = [p[0] for p in pulses]
        check(f"slave, {name}: the master's bar not known: the first click on the first pulse",
              [c[0] for c in r.log.clicks] == [ts[24 * k] for k in range(4)] and r.setmodes == [(ts[96], 1)], f"{r.log.clicks}")


def test_slave(fw, ram):
    period, first = 20, 7
    r = Rig(fw, ram, slave=True)
    uc = r.uc
    r.press(C.ID_PLAY)
    check("slave: the press kept, no click yet", not r.log.press and not r.log.clicks and fl(uc) & K.WAIT1)
    held_at = []
    rec, _, pulses = r.run(T0 + first + 100 * period, on_pulse=lambda rg, n, t: held_at.append(fl(rg.uc) & K.HELD) if n == 2 else None)
    ts = [p[0] for p in pulses]
    got = [c[0] for c in r.log.clicks]
    check("slave: clicks on the pulses 0, 24, 48, 72 after the press", got == [ts[0], ts[24], ts[48], ts[72]], f"{got}")
    check("slave: Play pressed after the first click (LED task)", len(r.log.press) == 1 and ts[0] < r.log.press[0][0] <= ts[0] + 2,
          f"{r.log.press} {ts[0]}")
    check("slave: the start held (mode 1)", held_at == [K.HELD] and uc.mem_read(BLK + K.O_MODE, 1)[0] == 1)
    check("slave: set_mode(1) on pulse 96, then that pulse starts the clock", r.setmodes == [(ts[96], 1)] and pulses[96][1] == 3
          and all(s == 0 for _, s in pulses[:96]), f"{r.setmodes} {pulses[95:97]}")
    check("slave: the count over", fl(uc) == 0)
    check("slave: Record red 100 ms from each click", flash_ok(rec, got, ts[96], C.COL_REC))

    r = Rig(fw, ram, slave=True, shift=1)
    r.press(C.ID_PLAY)
    r.run(T0 + 60)
    check("slave: Shift + Play: the press after the first click has Shift, Shift up after",
          [p[2] for p in r.log.press] == [1] and E.newest(r.uc, E.shift_store(r.uc), 0) == 0, f"{r.log.press}")

    r = Rig(fw, ram, slave=True)
    r.press(C.ID_PLAY)
    r.run(T0 + 5)
    r.press(C.ID_PLAY)
    r.run(T0 + 500, T0 + 5)
    check("slave: Play before the first pulse: count off, nothing to the stock", fl(r.uc) == 0 and not r.log.press and not r.log.clicks)

    r = Rig(fw, ram, slave=True)
    r.press(C.ID_PLAY)
    r.run(T0 + first + 30 * period)
    call(r.uc, K.SETMODE_CALL, K.CLOCK, 1)                 # the master's Start
    pled_poison(r.uc)
    _, _, pulses = r.run(T0 + first + 100 * period, T0 + first + 30 * period)
    check("slave: a master's Start during the count: it goes through, the count over at the next pulse",
          fl(r.uc) == 0 and len(r.setmodes) == 1 and pulses[0][1] == 3 and len(r.log.clicks) == 2, f"{r.setmodes} {pulses[:1]}")
    check("slave: a master's Start during the count: the Play LED drawn as playing", pled(r.uc) == WANT_PLED[1], f"{pled(r.uc):#x}")

    r = Rig(fw, ram, slave=True)
    r.press(C.ID_PLAY)
    r.run(T0 + 3000, first=10 ** 6)
    check("slave without pulses: the count waits, nothing pressed", fl(r.uc) & K.WAIT1 and not r.log.press and not r.log.clicks)


def test_sample(fw, ram):
    bpm, clicks, rel = want_master(Rig(fw, ram).uc)
    for name in ("SR",):
        r = Rig(fw, ram, sr=True)
        r.press(S.ID_REC)
        check(f"SR {name}: Record kept, the count begun", not r.log.press and fl(r.uc) == K.ACT | K.SAMP)
        rec, clr, _ = r.run(T0 + rel + 300)
        got = [c[0] - T0 for c in r.log.clicks]
        check(f"SR {name}: clicks", got == clicks, f"{got}")
        check(f"SR {name}: the sampler started on pulse 96", r.log.rec == [(T0 + rel, S.SAMPLER)] and logw(r.uc, 7) == T0 + rel, f"{r.log.rec}")
        check(f"SR {name}: no button press, no clock start", not r.log.press and not r.setmodes)
        check(f"SR {name}: Record red 100 ms from each click", flash_ok(rec, [T0 + c for c in clicks], T0 + rel, C.COL_REC))
        check(f"SR {name}: Clear untouched", flash_ok(clr, [T0 + c for c in clicks], T0 + rel, 0))

    r = Rig(fw, ram, sr=True, pad24=1)
    r.press(S.ID_REC)
    r.run(T0 + rel + 300)
    check("SR pad 24, stopped: Play pressed by the LED task", [(p[0] - T0, p[1]) for p in r.log.press] == [(2, C.ID_PLAY)], f"{r.log.press}")
    check("SR pad 24, stopped: the start and the sampler both on pulse 96, the sampler after set_mode",
          r.setmodes == [(T0 + rel, 0)] and r.log.rec == [(T0 + rel, S.SAMPLER)] and r.rec_state == [1], f"{r.setmodes} {r.log.rec} {r.rec_state}")
    check("SR pad 24, stopped: the clock running after", cstate(r.uc) == 3 and fl(r.uc) == 0)

    r = Rig(fw, ram, sr=True, pad24=1, play=1)
    r.press(S.ID_REC)
    r.run(T0 + rel + 300)
    check("SR pad 24, playing: no Play press, the sampler on pulse 96", not r.log.press and r.log.rec == [(T0 + rel, S.SAMPLER)] and not r.setmodes)

    r = Rig(fw, ram, sr=True, pad24=1, slave=True)
    r.press(S.ID_REC)
    _, _, pulses = r.run(T0 + 7 + 100 * 20)
    ts = [p[0] for p in pulses]
    check("SR pad 24, slave: clicks on the pulses, Play after the first",
          [c[0] for c in r.log.clicks] == [ts[0], ts[24], ts[48], ts[72]] and len(r.log.press) == 1 and r.log.press[0][0] > ts[0])
    check("SR pad 24, slave: set_mode(1) and the sampler on pulse 96, the clock started by it",
          r.setmodes == [(ts[96], 1)] and r.log.rec == [(ts[96], S.SAMPLER)] and pulses[96][1] == 3, f"{r.setmodes} {r.log.rec} {pulses[96]}")

    r = Rig(fw, ram, sr=True, slave=True)
    r.press(S.ID_REC)
    _, _, pulses = r.run(T0 + 7 + 100 * 20)
    ts = [p[0] for p in pulses]
    check("SR slave, pad 24 off: the sampler on pulse 96, no press, no start",
          r.log.rec == [(ts[96], S.SAMPLER)] and not r.log.press and not r.setmodes, f"{r.log.rec}")

    r = Rig(fw, ram, sr=True, pad24=1)
    r.press(S.ID_REC)
    r.run(T0 + clicks[1] + 50)
    r.press(S.ID_REC)
    r.run(T0 + rel + 300, T0 + clicks[1] + 50)
    check("SR pad 24: Record again: the count over, Play again (the stock's stop), no sampler",
          fl(r.uc) == 0 and [p[1] for p in r.log.press] == [C.ID_PLAY, C.ID_PLAY] and not r.log.rec and not r.setmodes
          and E.newest(r.uc, C.TRANSPORT, 0) == 0, f"{r.log.press}")

    r = Rig(fw, ram, sr=True)
    r.press(S.ID_REC)
    r.run(T0 + clicks[1] + 50)
    r.press(S.ID_REC)
    r.run(T0 + rel + 300, T0 + clicks[1] + 50)
    check("SR: Record again: the count over, nothing pressed", fl(r.uc) == 0 and not r.log.press and not r.log.rec)

    r = Rig(fw, ram, sr=True)
    r.press(S.ID_REC)
    r.run(T0 + clicks[1] + 50)
    w32(r.uc, C.CTRL + 0x7C, ES.MGR)
    r.press(S.ID_REC)
    r.run(T0 + rel + 300, T0 + clicks[1] + 50)
    check("SR: Record in a step view during the count: the count over, Record never reaches the stock",
          not r.log.press and not r.log.rec and fl(r.uc) == 0, f"{r.log.press}")

    r = Rig(fw, ram, sr=True, pad24=1)
    r.press(S.ID_REC)
    r.run(T0 + clicks[1] + 50)
    w32(r.uc, C.CTRL + 0x7C, ES.MGR)
    r.press(S.ID_REC)
    r.run(T0 + rel + 300, T0 + clicks[1] + 50)
    check("SR pad 24: Record in a step view: the count over, the held start stopped, no Record to the stock",
          fl(r.uc) == 0 and [p[1] for p in r.log.press] == [C.ID_PLAY, C.ID_PLAY] and not r.log.rec and not r.setmodes
          and E.newest(r.uc, C.TRANSPORT, 0) == 0, f"{r.log.press}")

    r = Rig(fw, ram, sr=True)
    r.press(S.ID_REC)
    r.run(T0 + clicks[1] + 50)
    ES.sampler_state(r.uc, 3)
    r.run(T0 + rel + 300, T0 + clicks[1] + 50)
    check("SR: sampler busy at the end: not started, the count over", not r.log.rec and fl(r.uc) == 0)

    r = Rig(fw, ram, sr=True)
    r.uc.mem_write(E.CI, bytes([C.CI_ON]))
    r.press(C.ID_PLAY)
    r.press(S.ID_REC)
    check("SR: Record during the sequencer's count: the stock's", [p[1] for p in r.log.press] == [C.ID_PLAY, S.ID_REC]
          and fl(r.uc) & K.GATE and not fl(r.uc) & K.SAMP)


def song_count(fw, ram, metro, pad24=0, stop_after=None, pulses=250, start=10):
    """Sample Rec's Record with the music playing (clock running) just before pulse `start` (the pulse in the bar = n % 96): a pulse
    every 20 ms, the stock's beat check on each.  Returns the rig and the time of each pulse."""
    r = Rig(fw, ram, sr=True, pad24=pad24, play=1)
    uc = r.uc
    uc.mem_write(K.CLOCK + K.O_STATE, bytes([K.RUNNING]))
    setp(uc, u32(uc, DRIVER + 0xC), K.METRO_P, metro)
    r.press(S.ID_REC)
    r.begin_fl = fl(uc)
    times = {}
    for n in range(start, start + pulses):
        t = T0 + 20 * (n - start + 1)
        now(uc, t)
        times[n] = t
        if stop_after is not None and n == stop_after:
            uc.mem_write(K.CLOCK + K.O_STATE, b"\x00")
            call(uc, TICK_CB, 0, K.CLOCK)
        uc.mem_write(K.CLOCK + K.O_PULSE, bytes([n % 96]))
        call(uc, K.BEAT_FN, DRIVER)
    return r, times


def test_song(fw, ram):
    for start, clicks, one, name in ((0, (0, 24, 48, 72), 96, "just before the bar's 1: 4 clicks"),
                                     (10, (24, 48, 72), 96, "after beat 1: 3 clicks"),
                                     (30, (48, 72), 96, "after beat 2: 2 clicks"),
                                     (60, (72,), 96, "after beat 3: 1 click"),
                                     (80, (96, 120, 144, 168), 192, "after beat 4: the next bar's 4 clicks")):
        r, ts = song_count(fw, ram, metro=0, start=start)
        check(f"SR, music playing, metronome off, Record {name}", [c[0] for c in r.log.clicks] == [ts[n] for n in clicks],
              f"{r.log.clicks}")
        check(f"SR, music playing, Record {name.split(':')[0]}: the sampler on the bar's 1, the count over",
              r.log.rec == [(ts[one], S.SAMPLER)] and fl(r.uc) == 0, f"{r.log.rec}")
    check("SR, music playing: the count follows the song (no click at the press)", r.begin_fl == K.ACT | K.SAMP | K.SONG, f"{r.begin_fl:#x}")
    check("SR, music playing: no button press, no clock start", not r.log.press and not r.setmodes)

    r, ts = song_count(fw, ram, metro=1, start=80)
    beats = [ts[n] for n in range(96, 80 + 250, 24)]
    check("SR, music playing, metronome on: one click per beat (the stock's), none of ours",
          [c[0] for c in r.log.clicks] == beats, f"{[c[0] for c in r.log.clicks]} != {beats}")
    check("SR, music playing, metronome on: the sampler on the bar's 1", r.log.rec == [(ts[192], S.SAMPLER)], f"{r.log.rec}")
    check("SR, music playing, metronome on: Record red from the 4th beat's time",
          u32(r.uc, BLK + K.O_TB) == ts[168] and logw(r.uc, 5) == ts[168], f"{u32(r.uc, BLK + K.O_TB)}")

    r, ts = song_count(fw, ram, metro=0, pad24=1)
    check("SR pad 24, music playing: the same count, no Play press",
          [c[0] for c in r.log.clicks] == [ts[n] for n in (24, 48, 72)] and r.log.rec == [(ts[96], S.SAMPLER)] and not r.log.press)

    r, ts = song_count(fw, ram, metro=0, stop_after=60)
    check("SR, music stopped during the count: the count over, no sampler",
          fl(r.uc) == 0 and [c[0] for c in r.log.clicks] == [ts[24], ts[48]] and not r.log.rec, f"{r.log.clicks} {r.log.rec}")


def test_stock_records(stock, ram):
    uc = machine(stock, ram)
    uc.mem_write(0x20000000, ram)
    uc.mem_write(0x20012888, ram[0x12888:0x12889])
    setp(uc, C.TRANSPORT, 0, 1)
    setp(uc, C.TRANSPORT, 1, 1)
    check("stock: playing with Record on, all three record methods record", records(uc) == [True] * 3, f"{records(uc)}")
    setp(uc, C.TRANSPORT, 1, 0)
    check("stock: Record off, none records", records(uc) == [False] * 3, f"{records(uc)}")


def test_noblock(fw, ram):
    r = Rig(fw, ram)
    w32(r.uc, K.rhstate.HEAP_LIMIT_PTR, 0x20000000)
    r.press(C.ID_PLAY)
    r.run(T0 + 600)
    check("no block: Play to the stock, the clock started at once", [p[1] for p in r.log.press] == [C.ID_PLAY]
          and r.setmodes == [(T0, 0)] and cstate(r.uc) == 3 and not r.log.clicks)
    check("no block: playing with Record on, all three record methods record", records(r.uc) == [True] * 3, f"{records(r.uc)}")
    call(r.uc, K.PLED_DRAW, K.PLED_OBJ)
    check("no block: playing, the Play LED drawn as playing", pled(r.uc) == WANT_PLED[1], f"{pled(r.uc):#x}")
    r = Rig(fw, ram, slave=True)
    w32(r.uc, K.rhstate.HEAP_LIMIT_PTR, 0x20000000)
    r.press(C.ID_PLAY)
    _, _, pulses = r.run(T0 + 100)
    check("no block, slave: Play to the stock, the next pulse starts", r.setmodes == [(T0, 1)] and pulses[0][1] == 3, f"{pulses[:2]}")


def main():
    global TICK_CB
    stock, fw, ram = (open(p, "rb").read() for p in sys.argv[1:4])
    TICK_CB = struct.unpack_from("<I", fw, TICK_LIT - 0x08010000)[0] & ~1
    want_pled(stock, ram)
    check("stock: the Play LED's stopped and playing colours differ", WANT_PLED[0] != WANT_PLED[1], f"{WANT_PLED}")
    test_master(fw, ram)
    test_slave(fw, ram)
    test_master_bar(fw, ram)
    if "srcount" in E.MAN["report"]:
        test_sample(fw, ram)
        test_song(fw, ram)
    test_noblock(fw, ram)
    test_stock_records(stock, ram)
    print("ALL PASS" if not E.fails else f"{len(E.fails)} FAILED")
    sys.exit(1 if E.fails else 0)


if __name__ == "__main__":
    main()
