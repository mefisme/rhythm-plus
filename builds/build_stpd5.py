"""Circuit Rhythm 5706 - STPD5 (test): STPF1 with tools/playprobe.py's listeners option: every store listener that runs 0.1 ms or more
while the play method runs is logged with its handler's address, to find what Play's ~23 ms of work is (the cause of the late
first step when the Rhythm follows an external clock)."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rhbuild  # noqa: E402
import fixedrec  # noqa: E402
import playfix  # noqa: E402
import playprobe  # noqa: E402
import rdiag  # noqa: E402

NAME = "STPD5"


def build(name=NAME):
    b = rhbuild.Build(name)
    b.add("fixedrec", fixedrec)
    b.add("playfix", playfix)
    b.add("rdiag", rdiag)
    b.add("playprobe", playprobe, listeners=True)
    return b


if __name__ == "__main__":
    build().finish(HERE / "firmware" / NAME.lower())
