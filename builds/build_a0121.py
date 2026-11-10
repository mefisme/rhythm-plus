"""A0121: archive Filter/Mix; keep Normal, Pitch, ring and sample-start scan."""
import os
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
os.environ["RH_PROBES"] = "0"
os.environ["RH_AUTOPROT"] = "0"
os.environ["RH_AUTOBANK"] = "0"
os.environ["RH_STOCKPLUS"] = "1"
os.environ["RH_TMCLICK"] = "3"
os.environ["RH_PAGECLEAR"] = "1"
os.environ["RH_TRACKRESET"] = "1"
os.environ["RH_PSHAPE"] = "1"
os.environ["RH_FSHAPE"] = "1"
os.environ["RH_UPGUARD"] = "1"
os.environ.setdefault("RH_MUTSET", "2")                  # "3": the mutate's seeds, Live and Clear + Duplicate (AG016); "4": the next list at the end (AG019); "5": scenes with lists (AG020); "6": a chain's scene at Play, Live on column 1, the other views (AG021); "7": the page back after a held button (AG022); "8": Shift + a track over the page (AG023); "9": with a track view's look (AG024); "10": Down / Up in the Clear preview, no Shift layer on a track held (AG025); "11": Shift + Duplicate on the page mutates (AG026)
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
import scanonly  # noqa: E402
import upguard  # noqa: E402
import pvloop  # noqa: E402
import nocomb  # noqa: E402
import c0fx  # noqa: E402
import mutset  # noqa: E402

import rpasm  # noqa: E402
rpasm.use()

NAME = "A0121"
SHIFT = 0x300                                     # Stock+'s core 1 words above voice 7's sample ring (Circuit Remix's track 8 fix)
PITCHMOD = dict(load=True, fx=True, shift=SHIFT, filt=True, clear=True, lite=True, shiboot=True, loopxf=4)
STOCKPLUS = dict(shift=SHIFT, v2=True, k6swap=True, wait=True, k8sync=True, k3sync=True,
                 lfodef={stockplus_rp.stockplus.K3: 14080, stockplus_rp.stockplus.K8: syncbar.K8_1BAR})


def build(name=NAME, error_led=True):
    nocrush.strip()
    nocomb.strip()
    c0fx.strip(mix=False)
    scanonly.strip()
    pshape.strip()
    fshape.strip(vol=False, move=False, px=True, glide=True, fade=True, loopfade=True, sm=True, loopxf=True, drone=True, nfollow=False, filt=False, aux=True)
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
    b.add("pshape", pshape, v2=True, once=True)
    b.add("scanonly", scanonly)
    b.add("c0fx", c0fx)
    b.add("fshape", fshape, px=True, glide=True, fade=True, sm=True, filt=False, aux=True)
    b.add("syncbar", syncbar, soundonly=True)
    b.add("pageclear", pageclear, viewsync=True, nocrush=True, shapes=True, scanfx=True, pageorder=True, px=True, fade=True, soundonly=True)
    b.add("smpads", smpads, sm=3)
    b.add("tmenu", tmenu, stockplus=True, testpages=False, fpage=True, click=True, twoview=True, shiftled=True, bounce=True, pageclear=True, steadyreset=True, resetcue=True, stepmarker=True, trackpulse=True, steppage=True, softclear=True, viewlock=True, momhold=True, nocrush=True, perpage=True, pagecols=False, shapes=True, shapebar="page", filtpage=False, k78white=False, volpage=False, syncbar=True, depthfirst=True, scanfx=True, pageorder=True, mixpage=False, pxrand=True, glide=True, fade=True, fclr=False, fadetan=True, soundonly=True)
    b.add("trackreset", trackreset, viewsync=True, softclear=True)
    b.add("mutset", mutset, mutate=True, listpads=True, scenecut=True, pagebyte=True, dimrest=True, clearall=True, liststart=True, scenesave=True, greendup=True, pageclr=True, shiftstock=True, shiftpads=True, pclrv=True, scenefix=True, stocktrk=True, cleardark=True, clrnone=True, restlvl=6, amount=True, norep=True, keep1=True, hidepause=True, vlock=True,
          **({"seeds": True, "live": True, "clrdup": True} if os.environ["RH_MUTSET"] in ("3", "4", "5", "6", "7", "8", "9", "10", "11") else {}),
          **({"pending": True} if os.environ["RH_MUTSET"] in ("4", "5", "6", "7", "8", "9", "10", "11") else {}),
          **({"scchain": True} if os.environ["RH_MUTSET"] in ("5", "6", "7", "8", "9", "10", "11") else {}),
          **({"scplay": True, "livecol": True, "views": True} if os.environ["RH_MUTSET"] in ("6", "7", "8", "9", "10", "11") else {}),
          **({"bounce": True} if os.environ["RH_MUTSET"] in ("7", "8", "9", "10", "11") else {}),
          **({"shtrk": True} if os.environ["RH_MUTSET"] in ("8", "9", "10", "11") else {}),
          **({"shtrkled": True} if os.environ["RH_MUTSET"] in ("9", "10", "11") else {}),
          **({"clrpage": True, "shkeep": True} if os.environ["RH_MUTSET"] in ("10", "11") else {}),
          **({"shmut": True} if os.environ["RH_MUTSET"] == "11" else {}))
    b.add("upguard", upguard, route=c0fx.routes())
    b.add("pvloop", pvloop)
    b.add("rdiag", diagread)
    if error_led:
        b.add("errled", errled)                   # historical optional error reporter
    # Production base for granular work: keep the original read-only diagnostics,
    # never inherit automation/ITCM probe state or device-write test commands.
    forbidden = {"acdiag", "dsdiag", "autoprot", "autobank"}
    assert not forbidden.intersection(b.report)
    assert not {"autoprot", "autobank"}.intersection(rhstate.OFF)
    assert b.report["rdiag"]["readonly"] and b.report["rdiag"]["mapped_ram_only"]
    return b


def main():
    out = build().finish(HERE / "firmware" / NAME.lower())
    for f in out.glob(f"circuitrhythm-5706-{NAME}.*"):
        f.replace(out / f"rhythmplus-{NAME}{f.suffix}")


if __name__ == "__main__":
    main()
