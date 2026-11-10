"""Explicit event ownership in the actual DSP0 grain producer, not signal-peak gating."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from emu_granular_producer import produce,controls,R


def audio(result):return result[('y',0x60000)]


def main():
    snapshot=controls(start=32,length=48)
    base,_,_=produce(snapshot,seconds=.08,mode=R.TRIGGERED)
    retrigger,_,_=produce(snapshot,seconds=.08,mode=R.TRIGGERED,events=((60,'note',1),))
    normal=audio(base);hit=audio(retrigger);split=60*32
    assert hit[:split]==normal[:split] and hit[split:]==normal[:split]
    assert hit[split:]!=normal[split:]
    print('PASS accepted same-note event restarts actual grain state/playhead deterministically in Triggered mode')
    texture,_,_=produce(snapshot,seconds=.08,mode=R.TEXTURE,events=((60,'note',1),))
    assert audio(texture)==normal
    print('PASS Texture keeps its grain cursor through note events; native downstream envelope may still retrigger independently')
    flow,_,_=produce(snapshot,seconds=.08,mode=R.TEXTURE,events=((60,'note',1),),flags=1)
    assert audio(flow)[split:]==normal[:split] and audio(flow)[split:]!=normal[split:]
    print('PASS Retrigger restarts Texture grains on a note')
    frozen,_,_=produce(snapshot,seconds=.08,mode=R.TRIGGERED,events=((60,'note',1),),flags=2)
    assert audio(frozen)==normal
    frozen,_,_=produce(snapshot,seconds=.08,mode=R.TEXTURE,events=((60,'note',1),),flags=3)
    assert audio(frozen)==normal
    print('PASS Freeze keeps the grain state through notes in both modes')
    for kind,value in (('epoch',4),('mode',R.TRIGGERED)):
        changed,_,_=produce(snapshot,seconds=.08,mode=R.TEXTURE,events=((60,kind,value),))
        assert audio(changed)[:split]==normal[:split] and audio(changed)[split:]==normal[:split]
    print('PASS generation and mode changes clear old grain state before rendering; stale sample descriptors are not carried across the reset')
    print('LIMIT: monophonic hard-retrigger candidate; per-track pools, mode entry/exit ACKs and sample lifetime still need production integration')
    print('ALL PASS')


if __name__=='__main__':main()
