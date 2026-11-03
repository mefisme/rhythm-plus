"""Circuit Rhythm 5706 - STFRS (MIT): the official firmware + tools/fixedrec.py (Fixed Recording at the external MIDI clock's tempo) and
nothing else: none of Circuit Remix's features, no rdiag, nothing that writes to the SD card (the marker STFRS)."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rhbuild  # noqa: E402
import fixedrec  # noqa: E402

NAME = "STFRS"


def build(name=NAME):
    b = rhbuild.Build(name)
    b.add("fixedrec", fixedrec)
    return b


if __name__ == "__main__":
    build().finish(HERE / "firmware" / NAME.lower())
