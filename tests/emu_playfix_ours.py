"""tools/emu_playfix.py on a build with our RAM block, in the layout its manifest records: python tests/emu_playfix_ours.py BASE.bin BUILT.bin RAM.bin"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import ourram  # noqa: E402,F401  (first: rhstate takes our magic)
import rhstate  # noqa: E402
import emu_playfix  # noqa: E402

blk = json.loads((Path(sys.argv[2]).parent / "manifest.json").read_text())["report"]["rhstate"]
rhstate.ST, rhstate.SIZE = int(blk["block"], 16), blk["size"]
rhstate.OFF = {k: (v, 0) for k, v in blk["off"].items()}
sys.argv.append("--block")
emu_playfix.main()
