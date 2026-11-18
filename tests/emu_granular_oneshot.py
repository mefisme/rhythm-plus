"""A One Shot Granular note (field 13 bit 2) ends once both the stock playback time and one scan of the zone are over.

Runs the firmware's own core 0 program. Usage: emu_granular_oneshot.py <build>, e.g. a0240.
"""
import copy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','tools','tests','remix/tools')]
import core0,rhdsp1,dspmap
import granular_bundle
import granular_current_layout as CURRENT
import granular_pool_candidate as P
import emu_granular_pool as POOL
from emu_granular_current import read,programs

TRIGGERED,FREEZE,ONE_SHOT=1,2,4       # field 13 bits: notes restart grains, Freeze, One Shot ends itself


def last_grain_frame(counts):
    live=[f for f in range(POOL.FRAMES) if counts[f*8]]
    return live[-1] if live else -1


def main():
    name=sys.argv[1] if len(sys.argv)>1 else 'a0240'
    image,manifest=read(name);report=manifest['report'];g=report['granular']
    segs=programs(image,report);fine=bool(g.get('fine_controls'))
    step=16 if fine else 1
    original=P.code;POOL.FRAMES=112;POOL.CAPTURE_COUNTS=0x6c000
    try:
        P.code=lambda **kwargs:(copy.deepcopy(segs),copy.deepcopy(g['pool']))
        with CURRENT.allocated():
            def end(scan,word13=TRIGGERED|ONE_SHOT,**extra):
                _,meta=POOL.run((0,),bounded=True,host_mailbox=True,region=(32,2),count=True,
                                settings={'scan':scan*step,'dens':100*step,13:word13},**extra)
                return meta['block_counts']
            still=last_grain_frame(end(0))
            slow=last_grain_frame(end(24))
            back=last_grain_frame(end(-24))
            fast=last_grain_frame(end(60))
            held=end(24,TRIGGERED)
            again=end(24,serial_at=slow+8)
            frozen=end(0,TRIGGERED|FREEZE|ONE_SHOT,serial_at=still+12)
    finally:P.code=original
    print(f'last frame with grains: scan 0 {still}, 24 {slow}, -24 {back}, 60 {fast}')
    assert 0<=still<slow<POOL.FRAMES-1,(still,slow)
    print('PASS scan still: the note ends with the stock playback time')
    assert slow>still+8 and abs(back-slow)<=2,(still,slow,back)
    print('PASS slow scan: the note runs past the stock playback time until the scan is over, both directions')
    assert abs(fast-still)<=2,(fast,still)
    print('PASS fast scan: the stock playback time sets the end, as before')
    assert all(held[f*8] for f in range(4,POOL.FRAMES)),'grains stopped without the One Shot bit'
    print('PASS without the One Shot bit the grains run on')
    assert any(again[f*8] for f in range(slow+9,slow+14)),'a new note after the end made no grains'
    print('PASS a new note after the end plays again')
    assert not any(frozen[f*8] for f in range(still+4,still+12)),'Freeze: the first note did not end'
    assert any(frozen[f*8] for f in range(still+13,still+18)),'Freeze: a new note after the end made no grains'
    print('PASS Freeze: each note ends with the stock playback time, and a new note plays again')
    print('ALL PASS')


if __name__=='__main__':main()
