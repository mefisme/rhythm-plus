"""Field 13 bit 15 (Scan centred, Freeze off) holds the playhead at Position, on a build's real core 0 program.

Usage: emu_granular_scanhome.py BUILD [REFERENCE without the home bit, default a0266]
"""
import copy
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / p) for p in ('modules', 'tools', 'tests', 'remix/tools')]
import rhdsp, rhdsp1  # noqa: F401,E402  (ours first: they read dsppack images)
import core0  # noqa: F401,E402
import granular_current_layout as CURRENT  # noqa: E402
import granular_pool_candidate as P  # noqa: E402
import emu_granular_pool as POOL  # noqa: E402
from emu_granular_current import read, programs  # noqa: E402

HOME = 1 << 15


def outputs(name, cases):
    image, manifest = read(name)
    g = manifest['report']['granular']
    segs, step = programs(image, manifest['report']), 16 if g.get('fine_controls') else 1
    original = P.code; POOL.FRAMES = 48
    try:
        P.code = lambda **kw: (copy.deepcopy(segs), copy.deepcopy(g['pool']))
        with CURRENT.allocated():
            return [POOL.run((0,), host_mailbox=True, settings={'scan': scan * step, 13: word, 'dens': 100 * step})[0][0]
                    for scan, word in cases], g
    finally:
        P.code = original


def main():
    name, ref = (sys.argv[1:3] + ['a0266'])[:2]
    (still, moving, home, home_still), g = outputs(name, [(0, 0), (40, 0), (40, HOME), (0, HOME)])
    assert g.get('scan_home') == dict(default=64, field13_bit=15), g.get('scan_home')
    assert moving != still, 'Scan moves the playhead'
    assert home == still and home_still == still
    print('PASS bit 15: a moving Scan plays as a centred one (the playhead stays at Position)')
    (old_still, old_moving), _ = outputs(ref, [(0, 0), (40, 0)])
    assert old_still == still and old_moving == moving
    print(f'PASS without bit 15 the output equals {ref}, centred and moving')
    print('ALL PASS')


if __name__ == '__main__':
    main()
