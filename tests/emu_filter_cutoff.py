"""Exercise the linked Filter cutoff hook and initialization in FP277."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / folder) for folder in ('modules', 'tools', 'remix/tools')]

import core0
import dsppack
import filter_cutoff as F
import rhdsp1
import rhdspemu


def verify_native_loader(image, stream, program):
    # Substitute only SHI waits and reads. The stock loader still handles
    # segment types, counts, destination addresses, and its jump to P:$100.
    loader = rhdsp1.loader_words(image)
    for wait,read,register in ((0x20,0x22,'a'),(0x23,0x25,'a'),(0x26,0x28,'a'),
                               (0x2d,0x30,'y1'),(0x33,0x35,'r7'),(0x38,0x3a,'x0')):
        assert loader[wait:wait+2]==[0x019191,wait]
        loader[wait:wait+2]=[0,0]
        assert loader[read]&0xff==0x94
        word, _ = core0.asm_at([f'move x:(r5)+,{register}'], read)
        assert len(word)==1
        loader[read]=word[0]

    stub, queue = 0x7000, 0x30000
    setup, _ = core0.asm_at(['move #>$ffffff,m5',f'move #>${queue:x},r5',('jmp',0x20)],stub)
    start,end = min(program),max(program)+1
    values, ran = rhdspemu.run(1,pc=stub,stop=0x100,maxins=400_000,
                               segs=[('p',0,loader),('p',stub,setup)],
                               mem=[('x',queue,stream),('y',F.OFFSET,[0xABCDEF]*F.TRACKS)],
                               dumps=[('p',start,end-start),('y',F.OFFSET,F.TRACKS)])
    assert 'pc=000100' in ran, ran
    assert values['y',F.OFFSET]==[0]*F.TRACKS
    loaded=values['p',start]
    assert all(loaded[address-start]==word for address,word in program.items())


def main():
    import json

    name = sys.argv[1] if len(sys.argv)>1 else 'fp277'
    folder = ROOT / 'firmware' / name
    report = json.loads((folder / 'manifest.json').read_text())['report']
    image = (folder / f'rhythmplus-{name.upper()}.bin').read_bytes()
    stream = rhdsp1.sent(image, report, 'pitchmod')
    segments, _ = rhdsp1.parse(stream)
    origin = int(report['filter_cutoff']['cutoff'], 16)
    baseline = ROOT / 'firmware/a277'
    stock_image = (baseline / 'rhythmplus-A277.bin').read_bytes()
    stock_report = json.loads((baseline / 'manifest.json').read_text())['report']
    stock_segments, _ = rhdsp1.parse(rhdsp1.sent(stock_image, stock_report, 'pitchmod'))
    if 'ring_mod_dsp' not in report:  # Ring Mod's after-filter oscillator is on core 0
        assert dsppack.raw_streams(image)[0] == dsppack.raw_streams(stock_image)[0]
    # The loader zeroes each adapter's Y words; each later adapter's segment goes first.
    zeroed = [('y',F.OFFSET,[0]*F.TRACKS)]
    for key, start in (('pitch_envelope_dsp','offset'), ('ring_mod_before','state'), ('scan_dsp','amount')):
        if key in report:
            zeroed.insert(0, ('y',int(report[key][start],16),[0]*report[key]['data_words']))
    assert [s for s in segments if s[0] != 'p'] == [*zeroed, *[s for s in stock_segments if s[0] != 'p']]
    program = {start + i: word for space, start, words in segments if space == 'p'
               for i, word in enumerate(words)}
    stock_program = {start + i: word for space, start, words in stock_segments if space == 'p'
                     for i, word in enumerate(words)}
    hooks = {F.LOWPASS_CALL}
    if 'pitch_envelope_dsp' in report:
        import pitch_envelope_dsp, pitchmod
        hooks |= {pitch_envelope_dsp.NOTE_CALL, pitchmod.P_RR_CALL}
    if 'ring_mod_before' in report:
        import ring_mod_dsp
        hooks |= {ring_mod_dsp.SOURCE_CALL}
    if 'scan_dsp' in report:
        import scan_dsp
        hooks |= {scan_dsp.TRIGGER}
    assert {address for address in stock_program if program[address] != stock_program[address]} == hooks
    for address, _, replacement in F.patches(origin):
        assert program[address] == replacement
    verify_native_loader(image, stream, program)

    values, _ = rhdspemu.run(1, pc=0x100, stop=0xFFFF, maxins=250_000,
                             dumps=[('y', F.OFFSET, F.TRACKS)], segs=segments)
    assert values['y', F.OFFSET] == [0] * F.TRACKS

    # Run the stock loads and capture n5 and caller registers upon entry to
    # the native low-pass filter in both images.
    voice, result, stub = 0x1000, 0x1E10, 0xE00
    initial = ['move #>$34567,a', 'move #>$1234,a0', 'move #>$765432,x0',
               'move #>$456,r1', 'move #>$17,n1', 'cmp x0,a']
    setup, _ = core0.asm_at([f'move #>${voice:x},r7', *initial, ('jmp', F.STOCK_CUTOFF)], stub)
    outputs = ('n5', 'b0', 'b1', 'b2', *F.SCRATCH_REGISTERS)
    sample, _ = core0.asm_at([f'move {reg},y:>${result+i:x}' for i,reg in enumerate(outputs)], F.LOWPASS)
    for track, cutoff, offset, expected in (
        (0, 53, 0, 53), (1, 53, 17, 70), (2, 53, -17, 36),
        (3, 120, 20, 128), (7, 10, -20, 0),
    ):
        offsets = [32] * F.TRACKS
        offsets[track] = offset & 0xFFFFFF
        memory = [('p', stub, setup), ('p', F.LOWPASS, sample),
                  ('y', F.TRACK, [track]), ('y', F.OFFSET, offsets),
                  ('y', voice + 12, [cutoff, 57])]
        def run(program_segments):
            values, _ = rhdspemu.run(1, pc=stub, stop=F.LOWPASS + len(sample),
                                     mem=memory, dumps=[('y', result, len(outputs))], segs=program_segments)
            return values['y', result]

        original = run(stock_segments)
        actual = run(segments)
        assert actual == [expected, *original[1:]], (track, cutoff, offset, actual, original)
    print('ALL PASS')


if __name__ == '__main__':
    main()
