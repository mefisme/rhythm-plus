"""A0146: A0145 with recording many Grid FX pads on one step, the selected pad pulsing, no Note or Velocity on the FX track, a held step's last pad off deleting it, the Mixer button bright with the FX track selected."""
import os
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
os.environ["RH_PROBES"] = "0"
os.environ["RH_AUTOPROT"] = "0"
os.environ["RH_AUTOBANK"] = "0"
os.environ["RH_STOCKPLUS"] = "0"
os.environ["RH_TMCLICK"] = "3"
os.environ["RH_PAGECLEAR"] = "1"
os.environ["RH_TRACKRESET"] = "1"
os.environ["RH_PSHAPE"] = "0"
os.environ["RH_FSHAPE"] = "0"
os.environ["RH_UPGUARD"] = "1"
os.environ["RH_SMSWITCH"] = "1"
os.environ["RH_GRANULAR"] = "0"
os.environ["RH_MUTSET"] = "11"
os.environ["RH_STEPMUT"] = "1"
os.environ["RH_GFXMIX"] = "1"
import ourram  # noqa: E402,F401  (first: the feature modules read its layout)
import rhbuild  # noqa: E402
import rhstate  # noqa: E402
import fixedrec  # noqa: E402
import playfix  # noqa: E402
import countin  # noqa: E402
import vismet  # noqa: E402
import clkci  # noqa: E402
import srcount  # noqa: E402
import stepload  # noqa: E402
with ourram.remix_imports():
    import dspready  # noqa: E402
    import rhrec  # noqa: E402
    import pitchmod  # noqa: E402
import smswitch  # noqa: E402
import trackreset  # noqa: E402
import pageclear  # noqa: E402
import tmenu  # noqa: E402
import smpads  # noqa: E402
import diagread  # noqa: E402
import upguard  # noqa: E402
import pvloop  # noqa: E402
import mutset  # noqa: E402
import stepmut  # noqa: E402
import gfxmix  # noqa: E402

import rpasm  # noqa: E402
rpasm.use()
import thumb  # noqa: E402

NAME = "A0146"
PITCHMOD = dict(load=True, shift=0x300, clear=True, shiboot=True, loopxf=4)
MUTSET = dict(mutate=True, listpads=True, scenecut=True, pagebyte=True, dimrest=True, clearall=True, liststart=True, scenesave=True,
              greendup=True, pageclr=True, shiftstock=True, shiftpads=True, pclrv=True, scenefix=True, stocktrk=True, cleardark=True,
              clrnone=True, restlvl=6, amount=True, norep=True, keep1=True, hidepause=True, vlock=True, seeds=True, live=True, clrdup=True,
              pending=True, scchain=True, scplay=True, livecol=True, views=True, bounce=True, shtrk=True, shtrkled=True, clrpage=True,
              shkeep=True, shmut=True)
TMENU = dict(stockplus=False, click=True, twoview=True, shiftled=True, bounce=True, pageclear=True, steadyreset=True, resetcue=True,
             stepmarker=True, trackpulse=True, steppage=True, softclear=True, viewlock=True, momhold=True)


POOLED = {"countin", "vismet", "clkci", "smswitch", "pageclear", "smpads", "tmenu", "trackreset", "mutset", "rdiag"}   # 32-bit constants from literal pools


def build(name=NAME):
    smswitch.strip()
    b = rhbuild.Build(name)
    add = b.add

    def pooled(key, module, **kw):
        thumb.COMPACT = key in POOLED
        try:
            add(key, module, **kw)
        finally:
            thumb.COMPACT = False
    b.add = pooled
    b.add("rhstate", rhstate)
    b.add("fixedrec", fixedrec)
    b.add("playfix", playfix)
    b.add("countin", countin, v2=True, bpm0=True)
    b.add("vismet", vismet)
    b.add("clkci", clkci)
    b.add("srcount", srcount)
    b.add("stepload", stepload)
    b.add("cthresh", dspready)                    # the DSP's READY byte under cthresh's name
    b.add("rhrec", rhrec)
    b.add("pitchmod", pitchmod, **PITCHMOD)
    b.add("smswitch", smswitch)
    b.add("pageclear", pageclear, viewsync=True, stockonly=True, allreset=False)
    b.add("smpads", smpads, sm=3)
    b.add("tmenu", tmenu, **TMENU)
    b.add("trackreset", trackreset, viewsync=True, softclear=True)
    b.add("mutset", mutset, **MUTSET)
    b.add("stepmut", stepmut)
    b.add("gfxmix", gfxmix)
    b.add("upguard", upguard)
    b.add("pvloop", pvloop)
    b.add("rdiag", diagread)
    forbidden = {"acdiag", "dsdiag", "autoprot", "autobank", "stockplus", "pshape", "fshape", "c0fx", "granular", "errled"}
    assert not forbidden.intersection(b.report)
    assert b.report["rdiag"]["readonly"] and b.report["rdiag"]["mapped_ram_only"]
    return b


def main():
    out = build().finish(HERE / "firmware" / NAME.lower())
    for f in out.glob(f"circuitrhythm-5706-{NAME}.*"):
        f.replace(out / f"rhythmplus-{NAME}{f.suffix}")


if __name__ == "__main__":
    main()
