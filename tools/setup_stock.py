"""Stores the official Circuit Rhythm firmware where the builds read it.

    python tools/setup_stock.py PATH/TO/circuitrhythm-firmware-5706.syx

The file is the Circuit Rhythm 2.0.1 (build 5706) update from Novation (.syx), or its application image (.bin). It is checked
against remix/stock/SHA256SUMS.txt; any other file is refused. It is written to remix/stock/ (git ignores it there).
"""
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "remix" / "tools")]
import patch_official as P  # noqa: E402


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    img, syx = P.load_official(Path(sys.argv[1]))
    P.STOCK_BIN.parent.mkdir(exist_ok=True)
    P.STOCK_BIN.write_bytes(img)
    P.STOCK_SYX.write_bytes(syx)
    print(f"stored: {P.STOCK_BIN}")


if __name__ == "__main__":
    main()
