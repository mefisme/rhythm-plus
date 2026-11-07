"""Rhythm Plus A0105 (MIT): A0104 with Duplicate green on the Patterns page with Shift and on the mutate page (mutset greendup); files rhythmplus-A0105.*."""
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
os.environ["RH_PSHAPE"] = "1"
os.environ["RH_FSHAPE"] = "1"
os.environ["RH_UPGUARD"] = "1"
os.environ["RH_MUTSET"] = "2"
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
import nocrush  # noqa: E402
import pshape  # noqa: E402
import fshape  # noqa: E402
import syncbar  # noqa: E402
import mixmove  # noqa: E402
import upguard  # noqa: E402
import pvloop  # noqa: E402
import nocomb  # noqa: E402
import c0fx  # noqa: E402
import mutset  # noqa: E402

import rpasm  # noqa: E402
rpasm.use()

NAME = "A0105"
K78WHITE = True                                   # the filter page's K7 / K8 white, as the stock's knobs
SHIFT = 0x300                                     # Stock+'s core 1 words above voice 7's sample ring (Circuit Remix's track 8 fix)
PITCHMOD = dict(load=True, fx=True, shift=SHIFT, filt=True, clear=True, lite=True, shiboot=True, loopxf=4)
STOCKPLUS = dict(shift=SHIFT, v2=True, k6swap=True, wait=True, k8sync=True, k3sync=True,
                 lfodef={stockplus_rp.stockplus.K3: 14080, stockplus_rp.stockplus.K8: syncbar.K8_1BAR})


def build(name=NAME):
    nocrush.strip()
    nocomb.strip()
    c0fx.strip()
    pshape.strip()
    fshape.strip(vol=True, move=True, px=True, glide=True, fade=True, loopfade=True, sm=True, loopxf=True, drone=True, nfollow=True)
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
    b.add("stockplus", stockplus_rp, nocrush=True, **STOCKPLUS)
    b.add("nocomb", nocomb)
    b.add("pshape", pshape, v2=True, once=True, vol=True)
    b.add("mixmove", mixmove, vol=True)
    b.add("c0fx", c0fx)
    b.add("fshape", fshape, vol=True, move=True, px=True, glide=True, fade=True, sm=True)
    b.add("syncbar", syncbar, move=True)
    b.add("pageclear", pageclear, viewsync=True, nocrush=True, shapes=True, filt=True, vol=True, scanfx=True, pageorder=True, px=True, fade=True)
    b.add("smpads", smpads, sm=3)
    b.add("tmenu", tmenu, stockplus=True, testpages=True, fpage=True, click=True, twoview=True, shiftled=True, bounce=True, pageclear=True, steadyreset=True, resetcue=True, stepmarker=True, trackpulse=True, steppage=True, softclear=True, viewlock=True, momhold=True, nocrush=True, perpage=True, pagecols=True, shapes=True, shapebar="page", filtpage=True, k78white=K78WHITE, volpage=True, syncbar=True, depthfirst=True, scanfx=True, pageorder=True, mixpage=True, pxrand=True, glide=True, fade=True, fclr=True, fadetan=True)
    b.add("trackreset", trackreset, viewsync=True, softclear=True)
    b.add("mutset", mutset, mutate=True, listpads=True, scenecut=True, pagebyte=True, dimrest=True, clearall=True, liststart=True, scenesave=True, greendup=True)
    b.add("upguard", upguard, route=c0fx.routes())
    b.add("pvloop", pvloop)
    b.add("rdiag", diagread)
    b.add("errled", errled)                       # last: it checks the features above
    return b


def main():
    out = build().finish(HERE / "firmware" / NAME.lower())
    for f in out.glob(f"circuitrhythm-5706-{NAME}.*"):
        f.replace(out / f"rhythmplus-{NAME}{f.suffix}")


if __name__ == "__main__":
    main()
