"""Scan on core 1: the note start moves by amount x (1 - start); amount 0 and every other register stay stock."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / folder) for folder in ('modules', 'tools', 'remix/tools')]

import core0
import rhdsp1
import rhdspemu
import scan_dsp as S


def program(name):
    folder = ROOT / 'firmware' / name
    report = json.loads((folder / 'manifest.json').read_text())['report']
    image = (folder / f'rhythmplus-{name.upper()}.bin').read_bytes()
    return report, rhdsp1.parse(rhdsp1.sent(image, report, 'pitchmod'))[0]


def flat(segments):
    return {a + i: w for space, a, words in segments if space == 'p' for i, w in enumerate(words)}


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else 'a301'
    report, segments = program(name)
    if 'scan_dsp' not in report:
        print('SKIP no Scan in this build')
        return
    _, stock = program('a300')
    words, labels = S.code(int(report['scan_dsp']['entry'], 16))
    actual, before = flat(segments), flat(stock)
    assert actual[S.TRIGGER] == S.JSR_SHORT | labels['scan']
    assert [actual[labels['scan'] + i] for i in range(len(words))] == words
    assert {a for a in before if a < rhdsp1.START and actual[a] != before[a]} == {S.TRIGGER}
    assert ('y', S.AMOUNT, [0] * S.DATA_WORDS) in segments, 'the loader zeroes the amounts'

    registers = ('b0', 'b1', 'b2', 'a0', 'a1', 'a2', 'x0', 'y0', 'r0', 'r1', 'r4', 'r5', 'n3', 'n4')
    result, stub = 0x1E40, 0xE00
    store, _ = core0.asm_at([f'move {reg},y:>${result + i:x}' for i, reg in enumerate(registers)], S.TRIGGER + 1)

    def run(program_segments, track, start, amounts):
        setup, _ = core0.asm_at([
            f'move #>${start:x},b', f'move #>${0x350000 | track:x},n3', 'move #>$456,r1',
            'move #>$12345,a', 'move #>$222,x0', 'move #>$333,y0', 'move #>$1000,r0',
            'move #>$40,r4', 'move #>$307c8,r5', 'move #>$11,n4', ('jmp', S.TRIGGER)], stub)
        values, ran = rhdspemu.run(1, pc=stub, stop=S.TRIGGER + 1 + len(store), maxins=10_000,
                                   mem=[('p', stub, setup), ('p', S.TRIGGER + 1, store), ('y', S.AMOUNT, amounts)],
                                   dumps=[('y', result, len(registers))], segs=program_segments)
        assert ran, 'no RAN line'
        return dict(zip(registers, values['y', result]))

    def expected(start, amount):
        b = (start << 9) << 24
        b -= ((start << 9) * amount) << 1
        b += amount << 24
        return (b >> 24) & 0xFFFFFF

    for track, start, amount in ((0, 0x0000, 0x400000), (3, 0x2000, 0x7A0000), (7, 0x3F80, 0x7A0000), (5, 0x1234, 0x123456)):
        amounts = [0] * 8
        amounts[track] = amount
        plain, moved = run(stock, track, start, amounts), run(segments, track, start, amounts)
        assert moved['b1'] == expected(start, amount), (track, hex(moved['b1']), hex(expected(start, amount)))
        assert moved['b1'] > plain['b1'] and moved['b1'] < 0x7FFFFF
        assert {k: v for k, v in moved.items() if k[0] != 'b'} == {k: v for k, v in plain.items() if k[0] != 'b'}, track
        others = [0x7A0000] * 8
        others[track] = 0
        assert run(segments, track, start, others) == plain, ('amount 0 is the stock start', track)
    print('PASS P:$32D calls Scan; the start moves by amount x (1 - start), per track; amount 0 and other registers stay stock')
    print('ALL PASS')


if __name__ == '__main__':
    main()
