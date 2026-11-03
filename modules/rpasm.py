"""The DSP assembly of our code, kept in builds/asm-cache.json: a build needs the DSP assembler (DSPTOOL) only for lines not in it, and
nothing is written into the remix submodule."""
import json
from pathlib import Path

import rhdsppatch

CACHE = Path(__file__).resolve().parents[1] / "builds" / "asm-cache.json"


def use():
    rhdsppatch.CACHE = CACHE
    try:
        rhdsppatch._cache.update(json.loads(CACHE.read_text()))
    except (OSError, ValueError):
        pass
