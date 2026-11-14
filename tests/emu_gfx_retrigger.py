"""Actual Beat Repeat DSP state: same-rate press versus a fresh capture."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','tests','remix/tools')]
import gfxsplit as G
import rhdspemu as D

def main():
    build=sys.argv[1] if len(sys.argv)>1 else 'a0181'
    rep=json.loads((ROOT/'firmware'/build/'manifest.json').read_text())['report']['gfxsplit']
    words=G.program((ROOT/'firmware'/build/f'rhythmplus-{build.upper()}.bin').read_bytes(),rep)
    start=int(rep['controls']['capture'],16)
    ring=[0x35000,0x35040,0x35080,0x350c0,0x35100]
    def run(request,command=1,program=words,entry=start):
        return D.run(0,pc=entry,stop=0x16f6,segs=[('p',0,program)],maxins=10000,
            mem=[('x',0x3a,[1]),('x',0x4ad8,[0x123456,0x234567]),('x',G.RETRIGGER,[request]),
                 ('x',0xd4,[command,1]),('x',0x1b8f,[0x1b94]),('x',0x1b93,[1]),('x',0x1b94,ring)],
            dumps=[('x',0x1b94,5),('x',0xd5,1),('x',G.RETRIGGER,1)])
    # Existing A0180 off/on messages collapse to the new on command before the
    # DSP runs. The native same-rate check retains the old captured region.
    _,old=G.DP.core0((ROOT/'firmware/a0180/rhythmplus-A0180.bin').read_bytes())
    oldrep=json.loads((ROOT/'firmware/a0180/manifest.json').read_text())['report']['gfxsplit']
    before,ran=run(0,program=old,entry=int(oldrep['controls']['capture'],16))
    assert 'pc=0016f6' in ran.lower() or 'pc=16f6' in ran.lower(),ran
    assert before['x',0x1b94]==ring
    print('PASS reproduces A0180: back-to-back same-rate on retains old recording despite ARM retrigger messages')
    result,ran=run(1)
    assert result['x',0x1b94]==[ring[0],ring[0],ring[2],ring[0],ring[0]],(result,ran)
    assert result['x',G.RETRIGGER]==[0] and result['x',0xd5][0]&1
    print('PASS non-overlap request is consumed at audio boundary and native press logic resets capture pointers')
    result,ran=run(0)
    assert result['x',0x1b94]==ring and result['x',0xd5]==[1],(result,ran)
    print('PASS overlap without a request preserves the original recording and engine state')
    for command in (0,2):
        result,ran=run(1,command)
        actual=result['x',0x1b94]
        assert actual[1]==ring[1] and actual[3]==ring[3] and result['x',G.RETRIGGER]==[0],(command,result,ran)
    print('PASS later native stop or changed live-pad command cancels an older sequencer recapture request')
    print('ALL PASS')

if __name__=='__main__':main()
