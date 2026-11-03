"""Circuit Rhythm 5706 - STPF1 (test): STFRS (stock + tools/fixedrec.py) + tools/playfix.py (first steps after Play at the real
tempo) + tools/rdiag.py (remote diagnostics over USB SysEx, read-only use) + tools/playprobe.py (timing probes around Play)."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rhbuild  # noqa: E402
import fixedrec  # noqa: E402
import playfix  # noqa: E402
import playprobe  # noqa: E402
import rdiag  # noqa: E402

NAME = "STPF1"


def build(name=NAME):
    b = rhbuild.Build(name)
    b.add("fixedrec", fixedrec)
    b.add("playfix", playfix)
    b.add("rdiag", rdiag)
    b.add("playprobe", playprobe)
    return b


if __name__ == "__main__":
    build().finish(HERE / "firmware" / NAME.lower())
