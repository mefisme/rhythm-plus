"""Core 0's Granular engine of two builds on random settings: the same audio without field 13 bit 15; with it, a centred Scan plays
as without it.  Usage: emu_granular_dsp_same.py BUILD REFERENCE [CASES]"""
import copy
import random
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

HOME = 1 << 15


def run_all(name, cases):
    image, manifest = read(name)
    g = manifest['report']['granular']
    segs = programs(image, manifest['report'])
    original = P.code; POOL.FRAMES = 32
    try:
        P.code = lambda **kw: (copy.deepcopy(segs), copy.deepcopy(g['pool']))
        with CURRENT.allocated():
            return [POOL.run((0, 1), host_mailbox=True, settings=c)[0][:2] for c in cases]
    finally:
        P.code = original


def main():
    build, ref = sys.argv[1:3]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    rng = random.Random(266)
    cases = []
    for _ in range(n):
        c = {'pos': rng.randrange(2048), 'size': rng.choice((240, 2000, 9000, rng.randrange(240, 24000))),
             'dens': rng.randrange(1601), 'scan': rng.choice((0, rng.randrange(-1023, 1024) & 0xffffff)),
             'pitch': rng.choice((0, rng.randrange(-24 * 64, 24 * 64) & 0xffffff)), 'pspr': rng.randrange(2048),
             'spr': rng.randrange(2048), 'win': rng.randrange(101), 'rev': rng.randrange(128),
             13: rng.choice((0, 1, 2, 16, 0x7f00, rng.randrange(1 << 15))), 14: rng.randrange(1, 127) ** 2 * 512}
        cases.append(c)
    still = [dict(c, scan=0) for c in cases]
    homes = [{**c, 'scan': 0, 13: c[13] | HOME} for c in cases]
    new = run_all(build, cases + still + homes)
    old = run_all(ref, cases + still)
    assert new[:2 * n] == old, [k for k in range(2 * n) if new[k] != old[k]]
    print(f'PASS {n} random settings (and each with Scan centred), 2 tracks, 32 blocks: the audio equals {ref}')
    assert new[2 * n:] == new[n:2 * n], [k for k in range(n) if new[2 * n + k] != new[n + k]]
    print('PASS with bit 15 set and Scan centred the audio is the centred audio')
    print('ALL PASS')


if __name__ == '__main__':
    main()
