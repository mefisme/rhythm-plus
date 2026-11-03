"""No bitcrusher in Rhythm Plus (MIT; Circuit Rhythm 5706).

tools/voicefx.py's lite words (pitchmod lite) hold one drive, the bitcrush (drive type 4).  strip() makes voicefx leave the drive out:
its label goes straight to `done` (jmp P_END), so core 1 never reads the drive words.  Call it before pitchmod installs; stockplus_rp
nocrush writes drive type 0 too.
"""
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import voicefx  # noqa: E402

_ITEMS = voicefx.items


def items(shift=0, pre=None, lite=False):
    out = _ITEMS(shift, pre, lite)
    assert lite, "nocrush strips the lite drive (the bitcrush alone)"
    a, b = out.index(("label", "drive")), out.index(("label", "done"))
    return out[:a + 1] + out[b:]


def strip():
    voicefx.items = items
