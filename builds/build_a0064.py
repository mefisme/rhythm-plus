"""Rhythm Plus A0064 (MIT): A0063 + Shift + Patterns (View Lock) keeps Track + open; files rhythmplus-A0064.*."""
import os
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
os.environ["RH_PROBES"] = "0"
os.environ["RH_STOCKPLUS"] = "1"
os.environ["RH_TMCLICK"] = "3"
os.environ["RH_PAGECLEAR"] = "1"
os.environ["RH_TRACKRESET"] = "1"
import ourram  # noqa: E402,F401  (first: the feature modules read its layout)
import rhbuild  # noqa: E402
import rhdsppatch  # noqa: E402
import rhstate  # noqa: E402
import fixedrec  # noqa: E402
import playfix  # noqa: E402
import countin  # noqa: E402
import vismet  # noqa: E402
import clkci  # noqa: E402
import srcount  # noqa: E402
import stepload  # noqa: E402
with ourram.remix_imports():
    import kbright  # noqa: E402
    import dspready  # noqa: E402
    import rhrec  # noqa: E402
    import pitchmod  # noqa: E402
    import stockplus_rp  # noqa: E402
import trackreset  # noqa: E402
import pageclear  # noqa: E402
import tmenu  # noqa: E402
import smpads  # noqa: E402
import diagread  # noqa: E402
import errled  # noqa: E402

import rpasm  # noqa: E402
rpasm.use()

NAME = "A0064"
SHIFT = 0x300                                     # Stock+'s core 1 words above voice 7's sample ring (Circuit Remix's track 8 fix)
PITCHMOD = dict(load=True, fx=True, shift=SHIFT, filt=True, clear=True, lite=True, shiboot=True)
STOCKPLUS = dict(shift=SHIFT, v2=True, k6swap=True, wait=True, k8sync=True, k3sync=True, lfodef=True)


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
    b.add("kbright", kbright)
    b.add("cthresh", dspready)                    # the DSP's READY byte under cthresh's name (stockplus reads it so)
    b.add("rhrec", rhrec)
    b.add("pitchmod", pitchmod, **PITCHMOD)
    b.add("stockplus", stockplus_rp, **STOCKPLUS)
    b.add("pageclear", pageclear, viewsync=True)
    b.add("smpads", smpads)
    b.add("tmenu", tmenu, stockplus=True, testpages=True, fpage=True, click=True, twoview=True, shiftled=True, bounce=True, pageclear=True, steadyreset=True, resetcue=True, stepmarker=True, trackpulse=True, steppage=True, softclear=True, viewlock=True)
    b.add("trackreset", trackreset, viewsync=True, softclear=True)
    b.add("rdiag", diagread)
    b.add("errled", errled)                       # last: it checks the features above
    return b


def main():
    out = build().finish(HERE / "firmware" / NAME.lower())
    for f in out.glob(f"circuitrhythm-5706-{NAME}.*"):
        f.replace(out / f"rhythmplus-{NAME}{f.suffix}")


if __name__ == "__main__":
    main()
