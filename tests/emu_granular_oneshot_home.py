"""Triggered + One Shot with Scan centred: the note ends with the sample's playback time, with or without field 13 bit 15 (Scan home).

Runs the build's real core 0 program.  Usage: emu_granular_oneshot_home.py BUILD"""
import copy
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / p) for p in ('modules', 'tools', 'tests', 'remix/tools')]
import rhdsp, rhdsp1  # noqa: F401,E402
import core0  # noqa: F401,E402
import granular_current_layout as CURRENT  # noqa: E402
import granular_pool_candidate as P  # noqa: E402
import emu_granular_pool as POOL  # noqa: E402
from emu_granular_current import read, programs  # noqa: E402

TRIGGERED, FREEZE, ONE_SHOT, HOME = 1, 2, 4, 1 << 15


def last_grain(counts):
    live = [f for f in range(POOL.FRAMES) if counts[f * 8]]
    return live[-1] if live else -1


def main():
    name = sys.argv[1]
    image, manifest = read(name)
    g = manifest['report']['granular']
    segs, step = programs(image, manifest['report']), 16 if g.get('fine_controls') else 1
    original = P.code; POOL.FRAMES = 112; POOL.CAPTURE_COUNTS = 0x6c000
    try:
        P.code = lambda **kw: (copy.deepcopy(segs), copy.deepcopy(g['pool']))
        with CURRENT.allocated():
            def end(word13, scan=0):
                _, meta = POOL.run((0,), bounded=True, host_mailbox=True, region=(32, 2), count=True,
                                   settings={'scan': scan, 'dens': 100 * step, 13: word13})
                return last_grain(meta['block_counts'])
            rows = {k: end(w) for k, w in (('one shot', TRIGGERED | ONE_SHOT), ('one shot + home', TRIGGERED | ONE_SHOT | HOME),
                                           ('one shot + freeze', TRIGGERED | ONE_SHOT | FREEZE),
                                           ('no one shot', TRIGGERED), ('no one shot + home', TRIGGERED | HOME))}
            if g.get('scan_centre'):
                rows['one shot, knob 66'] = end(TRIGGERED | ONE_SHOT, 2 * 16)
    finally:
        P.code = original
    for k, v in rows.items():
        print(f'{k:20s}: last frame with grains {v} of {POOL.FRAMES - 1}')
    ok = 0 <= rows['one shot'] < POOL.FRAMES - 4 and rows['one shot + home'] == rows['one shot'] and rows['one shot + freeze'] < POOL.FRAMES - 4
    if 'one shot, knob 66' in rows:
        ok &= rows['one shot, knob 66'] == POOL.FRAMES - 1     # Scan just past the centre zone still stretches the note
    print('ALL PASS' if ok else 'FAIL: a One Shot note does not end the same way')


if __name__ == '__main__':
    main()
