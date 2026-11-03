"""Rhythm Plus A0001 (alpha, MIT): the contents of build_stc11.py under the Rhythm Plus name; the files are rhythmplus-A0001.*."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import build_stc11  # noqa: E402

NAME = "A0001"


def main():
    out = build_stc11.build(NAME).finish(HERE / "firmware" / NAME.lower())
    for f in out.glob(f"circuitrhythm-5706-{NAME}.*"):
        f.replace(out / f"rhythmplus-{NAME}{f.suffix}")


if __name__ == "__main__":
    main()
