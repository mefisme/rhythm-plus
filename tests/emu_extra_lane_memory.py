"""Check the proposed extra-lane DSP RAM against selected A296 execution paths."""

import sys

from emu_granular_current import B, D, core0, dspmap, programs, read
import gfxsplit as G
import ring_mod_dsp as R

START, END = 0x2C00, 0x4000


def main():
    image, manifest = read(sys.argv[1] if len(sys.argv) > 1 else 'a296')
    report = manifest['report']
    regions = dspmap.regions(report)
    assert not dspmap.overlaps(regions)
    assert any(lo <= START and END <= hi for lo, hi in dspmap.free(regions, 0, 'y'))
    program = programs(image, report)
    bank = [((i * 0x45D9F3) ^ 0xA17E53) & 0xFFFFFF for i in range(END - START)]
    memory = [('y', START, bank)]
    inspect = [('y', START, len(bank))]

    def preserve(name, *, segments=program, setup=(), **run):
        result, status = D.run(0, segs=segments, mem=[*memory, *setup], dumps=inspect, **run)
        assert result['y', START] == bank, name
        stop = D.STUB + 2 if "call" in run else run["stop"]
        assert status and f"pc={stop:06x}" in status, (name, status)
        print(f'PASS {name}: all {len(bank)} candidate words preserved')

    preserve('packed core 0 startup', pc=0, stop=0x100, maxins=100000)
    granular = report['granular']
    first = int(granular['first_pass'], 16)
    body = granular['pool']['labels']['after_wait'] + 2
    preserve('Granular first pass private-state clear',
             segments=[*program, ('p', B.STOCK_WAIT, [0xC])],
             setup=[('y', B.FLAG, [0])], pc=first, stop=body, maxins=200000)

    fx = report['gfxsplit']
    mixer = [('x', 0x3A, [32]), ('x', G.SRC, [0x200000] * 512),
             ('y', G.GAIN, [0x600000] * 512),
             ('x', int(fx['cut'], 16), [0x400000] * 8)]
    preserve('Grid FX split and native mix', call=int(fx['pre'], 16),
             setup=mixer, maxins=30000)
    ring = report.get('ring_mod_dsp')
    if ring:
        preserve('Ring Mod on all tracks, Grid FX and native mix',
                 call=int(ring['entry'], 16), maxins=30000,
                 setup=[*mixer, ('y', R.BANK, [0x200000] * 512),
                         ('y', R.STATE, [0] * 8 + [0x40000] * 8 + [0x600000] * 8)])

    project_max = 64 * 193 + 130
    cache = 9 * 192
    budget = len(bank) * 3
    assert project_max + cache <= budget
    print(f'{budget} B candidate, {project_max} B packed worst case + {cache} B decoded caches')
    print('LIMIT: targeted DSP emulation; no hardware ownership or DSP-to-ARM access timing proven')


if __name__ == '__main__':
    main()
