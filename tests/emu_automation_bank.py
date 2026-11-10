"""Replay core-0 mixer checks with a full candidate X bank occupied.

This is a bounded emulator noninterference check, not hardware ownership proof.
It reuses real firmware routines and checks both bank preservation and outputs.
"""
import contextlib
import io
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / part) for part in ("tests", "modules", "builds", "remix/tools")]
os.environ.setdefault("DSPTOOL", str(ROOT.parent / "CIRCUIT-HACKS-RC/ext/bin/dsptool.exe"))
os.environ.setdefault("TEMP", str(ROOT / "buildtmp"))
os.environ.setdefault("TMP", str(ROOT / "buildtmp"))
import rhdspemu
import emu_mixmove

START, END = 0x2400, 0x4400


def main():
    original = rhdspemu.run
    calls = [0]
    checks = [0]

    def replay(core, *args, **kwargs):
        baseline, ran = original(core, *args, **kwargs)
        if core != 0:
            return baseline, ran
        for space, address, values in kwargs.get("mem", ()):
            if space == "x" and max(address, START) < min(address+len(values), END):
                raise AssertionError("fixture overlaps proposed bank; cannot infer ownership")
        for space, address, path in kwargs.get("files", ()):
            if space == "x" and max(address, START) < min(address+Path(path).stat().st_size//3, END):
                raise AssertionError("file fixture overlaps proposed bank")
        calls[0] += 1
        for seed in (0x5a12c3, 0xa5ed3c):
            canary = [(seed ^ (index*0x10301)) & 0xffffff for index in range(END-START)]
            trial = dict(kwargs)
            trial["mem"] = list(kwargs.get("mem", ())) + [("x", START, canary)]
            trial["dumps"] = list(kwargs.get("dumps", ())) + [("x", START, END-START)]
            result, trial_ran = original(core, *args, **trial)
            if result.pop(("x", START)) != canary:
                raise AssertionError(f"bank overwritten by P call {kwargs.get('call')} seed {seed:x}")
            if result != baseline:
                raise AssertionError(f"bank contents affect outputs at P call {kwargs.get('call')}")
            if not trial_ran or not ran:
                raise AssertionError("missing emulator completion")
            checks[0] += 1
        return baseline, ran

    rhdspemu.run = replay
    old = sys.argv
    sys.argv = ["emu_mixmove.py", *old[1:]] if len(old) > 1 else ["emu_mixmove.py", "ad006"]
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            try:
                emu_mixmove.main()
            except SystemExit as error:
                if error.code:
                    raise
    finally:
        rhdspemu.run = original
        sys.argv = old
    if "ALL PASS" not in output.getvalue():
        raise AssertionError(output.getvalue())
    print(f"PASS {calls[0]} core-0 routine calls, {checks[0]} full-bank canary replays")
    print("PASS both canary contents preserved and all requested outputs unchanged")
    print("LIMIT: mixer/pan/send test paths only; excludes boot, DMA, other modes and physical timing")
    print("ALL PASS")


if __name__ == "__main__":
    main()
