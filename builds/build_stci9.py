"""Circuit Rhythm 5706 - STCI9 (test, MIT): the official firmware + tools/fixedrec.py + tools/playfix.py + tools/countin.py (Shift + Clear: the
metronome's four states and the count-in) with our RAM block (ourram.py), + vismet.py (Clear flashes on each silent click) + clkci.py (the
count-in on the music's clock, master or slave, with a held start) + srcount.py (the Sample Rec count-in's pads 23 / 24) + srprobe.py (test:
the sampler's start of recording) + playprobe.py and commitprobe.py (test: Play's work, logged inside our block) + errled.py (the Clear LED
blinks red while one of these features is off) + tools/rdiag.py (remote diagnostics over USB SysEx, read-only use).  Nothing writes to the
SD card."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import ourram  # noqa: E402  (first: the feature modules read its layout)
import rhbuild  # noqa: E402
import rhstate  # noqa: E402
import fixedrec  # noqa: E402
import playfix  # noqa: E402
import countin  # noqa: E402
import vismet  # noqa: E402
import clkci  # noqa: E402
import srcount  # noqa: E402
import srprobe  # noqa: E402
import playprobe  # noqa: E402
import commitprobe  # noqa: E402
import errled  # noqa: E402
import rdiag  # noqa: E402

NAME = "STCI9"
PLOG = rhstate.ST + rhstate.OFF["plog"][0]
playprobe.LOG, playprobe.IN_BLOCK, playprobe.NMAX = PLOG, True, ourram.PLOG_N
commitprobe.CLOG, commitprobe.CN = PLOG + 32 + 16 * playprobe.NMAX, 64
assert commitprobe.CLOG + 16 + 16 * commitprobe.CN == PLOG + rhstate.OFF["plog"][1]


def build(name=NAME):
    b = rhbuild.Build(name)
    b.add("rhstate", rhstate)
    b.add("fixedrec", fixedrec)
    b.add("playfix", playfix)
    b.add("countin", countin, v2=True, bpm0=True)
    b.add("vismet", vismet)
    b.add("clkci", clkci)
    b.add("srcount", srcount)
    b.add("srprobe", srprobe)
    b.add("playprobe", playprobe, listeners=True)
    b.add("commitprobe", commitprobe)
    b.add("rdiag", rdiag)
    b.add("errled", errled)                       # last: it checks the features above
    return b


if __name__ == "__main__":
    build().finish(HERE / "firmware" / NAME.lower())
