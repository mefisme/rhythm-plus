"""Our RAM block on the Circuit Rhythm 5706 (MIT): the top of the free gap under the stock heap's limit, slots placed from the top down.

It reuses tools/rhstate.py's c_rst (reserves the block by lowering the heap limit to it, zeroes it, magic at + 0) with our own size, magic and
layout.  Import this module before any feature module, so their `import rhstate` sees our layout.  The magic sits at the block's lowest word,
nearest the firmware's memory.
"""
import contextlib
import importlib
import os
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rhstate  # noqa: E402
import rodisk  # noqa: E402,F401  (countin reads rodisk's constants; rodisk must import while rhstate still has its own layout)

PROBES = os.environ.get("RH_PROBES", "1") != "0"  # RH_PROBES=0: the layout without the probe slots (plog, srprobe)
PLOG_N = 100                                      # playprobe's entries (a build sets playprobe.NMAX to it)
PLOG = (32 + 16 * PLOG_N) + (16 + 16 * 64)        # playprobe's log, then commitprobe's (test builds)
STOCKPLUS = os.environ.get("RH_STOCKPLUS") == "1"  # RH_STOCKPLUS=1: the slots of Circuit Remix's Stock+ (tools/stockplus.py and its helpers)
TMCLICK = int(os.environ.get("RH_TMCLICK") or 0)     # RH_TMCLICK=1: tmenu's slot with its click count; 2: and its Clear counts; 3: and the held button's press
PAGECLEAR = os.environ.get("RH_PAGECLEAR") == "1"
SP_SLOTS = (("spwait", 4), ("stockplus", 4), ("k8tick", 4), ("cthresh", 4), ("kbright", 28))  # stockplus: 0 < its offset - cthresh's + 1, - kbright's < 256; spwait within 31 above it
TRACKRESET = os.environ.get("RH_TRACKRESET") == "1"
PSHAPE = os.environ.get("RH_PSHAPE") == "1"          # RH_PSHAPE=1: pshape's slot (the shape tables' next word)
FSHAPE = os.environ.get("RH_FSHAPE") == "1"          # RH_FSHAPE=1: fshape's slot (the filter's tracks to write, the round, the tick)
GRAIN = os.environ.get("RH_GRAIN") == "1"            # RH_GRAIN=1: grain_rp's slot (the granular's words to core 0)
SLOTS = (("trackreset", 220),) * TRACKRESET + (("pageclear", 8),) * PAGECLEAR + (("plog", PLOG),) * PROBES + SP_SLOTS * STOCKPLUS + (("grain", 4),) * GRAIN + (("pshape", 4),) * PSHAPE + (("fshape", 8),) * FSHAPE + (("tmenu", 32 + 4 * (TMCLICK > 0) + 16 * (TMCLICK > 1) + 4 * (TMCLICK > 2)), ("clkci", 52), ("playfix", 16), ("countin", 8), ("vismet", 4), ("srcount", 8)) + (("srprobe", 8),) * PROBES
# from the top down: the last slots get the smallest offsets (byte loads reach 31, word loads 124); sizes are multiples of 4
MAGIC = 0x3152554F                                 # "OUR1"

_UPSTREAM = dict(rhstate.OFF)

if os.environ.get("RH_LINE") == "remix":             # the Remix line: Circuit Remix's blocks, our slots in their free space
    rhstate.OFF["vismet"] = (232, 4)
    rhstate.OFF2["clkci"] = (1820, 52)
    rhstate.OUR_LIMIT = rhstate.ST2                       # the heap limit once its blocks are set up
    rhstate.check_layout()
else:
    SIZE = 4 + sum(n for _, n in SLOTS)
    ST = rhstate.HEAP_LIMIT - SIZE
    OFF = {"magic": (0, 4)}
    _top = rhstate.HEAP_LIMIT
    for _name, _n in SLOTS:
        _top -= _n
        OFF[_name] = (_top - ST, _n)
    assert all(n % 4 == 0 for _, n in SLOTS) and _top - ST == 4
    rhstate.SIZE, rhstate.ST, rhstate.MAGIC, rhstate.OFF = SIZE, ST, MAGIC, OFF
    rhstate.OUR_LIMIT = ST
    rhstate.OFF2 = {k: v for k, v in rhstate.OFF2.items() if k not in rhstate.SHARED}  # Circuit Remix's slots in latdiag's room (clkci, ...): not ours
    rhstate.SHARED = {}

# tools/ holds upstream copies of some of our modules, and tools/' own modules put tools/ first on import: load ours now, by name
_HERE = str(Path(__file__).resolve().parent)
for _m in ("vismet", "clkci", "stepload", "errled"):
    sys.path.insert(0, _HERE)
    importlib.import_module(_m)
    assert Path(sys.modules[_m].__file__).resolve().parent == Path(_HERE), _m


@contextlib.contextmanager
def remix_imports():
    """Circuit Remix's modules read other modules' slots when imported (stockplus -> sckn -> patchain -> qmute ...).  While they import,
    the slots we do not have sit far above our block, where an offset immediate does not assemble; removed afterwards."""
    extra = {k: (0x10000 + 0x100 * i, n) for i, (k, (_, n)) in enumerate(_UPSTREAM.items()) if k not in rhstate.OFF}
    rhstate.OFF.update(extra)
    try:
        yield
    finally:
        for k in extra:
            del rhstate.OFF[k]
