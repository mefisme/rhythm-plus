"""Compare audio from the A277 and Filter-probe native DSP voice loops."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / folder) for folder in ('modules', 'tools')]

import filter_cutoff as F
from granular_route_reference import render, segments


def verify_encoder_audio(name, offset):
    source = [0x180000 if i % 31 == 0 else 0 for i in range(32*12)]
    configs = [dict(lp=64, hp=8, resonance=32) for _ in range(8)]
    program = segments(name)
    neutral = [('y', F.OFFSET, [0]*8)]
    modulated = [('y', F.OFFSET, [offset&0xffffff]+[0]*7)]
    before, _ = render(source,candidate=False,configs=configs,program=program,initial_memory=neutral)
    after, _ = render(source,candidate=False,configs=configs,program=program,initial_memory=modulated)
    assert before[0]!=after[0] and before[1:]==after[1:]


def main():
    name = sys.argv[1] if len(sys.argv)>1 else 'fp277'
    # An impulse train so the low-pass, high-pass and resonance all have
    # energy to act on. The harness supplies only the sample reader output.
    source = [0x180000 if i % 31 == 0 else 0 for i in range(32 * 12)]
    configs = [dict(lp=35+8*t, hp=8+t, resonance=10+8*t) for t in range(8)]
    stock_program, filter_program = segments('a277'), segments(name)

    def run(program, offsets=None, **options):
        memory = () if offsets is None else (('y', F.OFFSET, [value&0xffffff for value in offsets]),)
        return render(source,candidate=False,configs=configs,program=program,initial_memory=memory,**options)[0]

    neutral = [0]*8
    expected = run(stock_program)
    assert all(any(track) for track in expected)
    assert run(filter_program,neutral) == expected, 'neutral Filter changes native audio'

    # Change native cutoff and resonance during playback in both images.
    moves = ((4,2,{'lp':27}), (6,4,{'resonance':110}))
    stock_turns = run(stock_program,changes=moves)
    assert run(filter_program,neutral,changes=moves) == stock_turns
    for track in range(8):
        assert (stock_turns[track]!=expected[track]) == (track in (2,4)), track

    # A fixed modulation offset should be the same as asking the stock
    # voice loop for the corresponding native cutoff.
    offsets = [0,0,-16,0,24,0,0,0]
    modulated = run(filter_program,offsets)
    for track, config in enumerate(configs):
        config['lp'] += offsets[track]
    assert modulated == run(stock_program)
    for track in range(8):
        assert (modulated[track]!=expected[track]) == bool(offsets[track]), track
    print('PASS neutral audio, native cutoff and resonance changes, and track-scoped modulation through the complete voice loop')
    print('ALL PASS')


if __name__ == '__main__':
    main()
