"""Circuit Rhythm 5706 - ST2FX (MIT): the official firmware + tools/fixedrec.py (Fixed Recording at the external MIDI clock's tempo)
+ tools/playfix.py (the first steps after Play at the real tempo) and nothing else: no rdiag, no probes, nothing that writes to the SD card."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rhbuild  # noqa: E402
import fixedrec  # noqa: E402
import playfix  # noqa: E402

NAME = "ST2FX"


def build(name=NAME):
    b = rhbuild.Build(name)
    b.add("fixedrec", fixedrec)
    b.add("playfix", playfix)
    return b


if __name__ == "__main__":
    build().finish(HERE / "firmware" / NAME.lower())
