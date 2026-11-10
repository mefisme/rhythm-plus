"""Actual DSP ownership acknowledgements with the grain engine disabled."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tools','modules','remix/tools')]
import core0
import rhdspemu
import granular_producer_candidate as P
import granular_snapshot_candidate as S
import granular_route_candidate as R
import granular_inplace_candidate as I
import granular0 as G


def main():
    segments,meta=P.code(in_place=True)
    tags=[R.KEY,S.INACTIVE_STATE,I.AUDIO_KEY,0,R.KEY,S.INACTIVE_STATE,P.ACK_ACTIVE,P.ACK_IDLE]
    expected=[P.ACK_ACTIVE,P.ACK_IDLE,I.AUDIO_KEY,0,R.KEY,S.INACTIVE_STATE,P.ACK_ACTIVE,P.ACK_IDLE]
    snapshots=[];controls=[]
    for track,tag in enumerate(tags):
        snapshots += [tag,7,123+track,30+track,50,500,0x8000,91+track]
        controls += [0,6 if track in (4,5) else 7,123+track,0]
    wait,_=core0.asm_at(['rts'],0x1a11)
    items=[]
    for k in range(8):
        items += [f'move #>${0x300+k:x},r{k}',f'move #>${10+k:x},n{k}',('words',[0x05f420|k,0xffffff if k==0 else (1<<(k+3))-1])]
    # Repeat the complete hook: acknowledged states must be idempotent.
    items += [('jsr',meta['labels']['after_wait']),('jsr',meta['labels']['after_wait'])]
    for k in range(8):
        items += [f'move r{k},y:>${0x3a220+k:x}',f'move n{k},y:>${0x3a228+k:x}',('words',[0x057060|k,0x3a230+k])]
    items += [('jmp',0x7ff0)]
    wrapper,_=core0.asm_at(items,0x7000)
    result,_=rhdspemu.run(0,pc=0x7000,stop=0x7ff0,
        segs=segments+[('p',0x1a11,wait),('p',0x7000,wrapper)],
        mem=[('x',G.GB+G.P_KEY,[0]),('y',S.SNAPSHOT,snapshots),('y',R.CONTROL,controls)],
        dumps=[('y',S.SNAPSHOT,64),('y',R.CONTROL,32),('y',0x3a220,24)],maxins=100000)
    wanted=list(snapshots)
    for track,tag in enumerate(expected):wanted[track*8]=tag
    assert result[('y',S.SNAPSHOT)]==wanted
    assert result[('y',R.CONTROL)]==controls
    assert result[('y',0x3a220)]==[0x300+k for k in range(8)]+[10+k for k in range(8)]+[0xffffff if k==0 else (1<<(k+3))-1 for k in range(8)]
    print('PASS disabled engine still acknowledges active and idle native voices; stale epochs, AUDIO and incomplete packets remain untouched')
    print('PASS repeated hooks are idempotent; all snapshot payloads, route controls and native r/n/m registers preserved')
    print('LIMIT: serialized register fixture; no concurrent ARM snapshot read or hardware deadline proof')


if __name__=='__main__':main()
