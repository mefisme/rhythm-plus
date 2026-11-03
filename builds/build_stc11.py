"""Circuit Rhythm 5706 - STC11 (test, MIT): the official firmware + tools/fixedrec.py + tools/playfix.py + tools/countin.py (Shift + Clear: the
metronome's four states and the count-in) with our RAM block (ourram.py, without the probe slots), + vismet.py (Clear flashes on each silent
click) + clkci.py (the count-in on the music's clock, master or slave, with a held start) + srcount.py (the Sample Rec count-in's pads 23 / 24)
+ stepload.py (a faster step load on Play) + errled.py (the Clear LED blinks red while one of these features is off) + tools/rdiag.py (remote
diagnostics over USB SysEx, read-only use).  Nothing writes to the SD card."""
import os
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
os.environ["RH_PROBES"] = "0"
import ourram  # noqa: E402,F401  (first: the feature modules read its layout)
import rhbuild  # noqa: E402
import rhstate  # noqa: E402
import fixedrec  # noqa: E402
import playfix  # noqa: E402
import countin  # noqa: E402
import vismet  # noqa: E402
import clkci  # noqa: E402
import srcount  # noqa: E402
import errled  # noqa: E402
import rdiag  # noqa: E402
import stepload  # noqa: E402

NAME = "STC11"


def build(name=NAME):
    b = rhbuild.Build(name)
    b.add("rhstate", rhstate)
    b.add("fixedrec", fixedrec)
    b.add("playfix", playfix)
    b.add("countin", countin, v2=True, bpm0=True)
    b.add("vismet", vismet)
    b.add("clkci", clkci)
    b.add("srcount", srcount)
    b.add("stepload", stepload)
    b.add("rdiag", rdiag)
    b.add("errled", errled)                       # last: it checks the features above
    return b


if __name__ == "__main__":
    build().finish(HERE / "firmware" / NAME.lower())
