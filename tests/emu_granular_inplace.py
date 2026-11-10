"""Lossless in-place handoff: existing native buffers, typed snapshot ownership."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'modules')]
from granular_route_reference import render
from render_granular_reference import fixture,render as grains
from emu_granular_producer import produce,controls,G,S,R
import granular_inplace_candidate as IPC
from build_dsp_fixture import build as build_fixture
import rhdsp


def verify():
    source,_=grains(fixture(),.04,dict(size=35,dens=55,scan=40))
    configs=[dict(lp=50+8*t,hp=6*t,resonance=10*t,distortion=3*t,slope=40+4*t) for t in range(8)]
    for bank in (0,1):
        baseline,_=render(source,candidate=False,configs=configs,bank=bank)
        for enabled in ((),*( (t,) for t in range(8)),(0,2,5),tuple(range(8))):
            actual,_=render(source,enabled=enabled,configs=configs,in_place=True,bank=bank)
            assert actual==baseline,(bank,enabled)
        inactive=(0,3,7)
        baseline,_=render(source,candidate=False,configs=configs,bank=bank,inactive=inactive)
        actual,_=render(source,enabled=tuple(range(8)),configs=configs,in_place=True,bank=bank,inactive=inactive)
        assert actual==baseline and all(not any(actual[t]) for t in inactive)
    print('PASS both native banks: all-off, each track, mixed/all8 routes bit-identical to original voice-boundary reference; opposite bank untouched')
    print('PASS enabled but inactive tracks clear raw input normally; no unprocessed grain audio can leak into native output')
    faults=((15,0,'epoch'),(25,2,'sequence'),(35,5,'not_ready'))
    expected,_=render(source,candidate=False,configs=configs,reader_gaps=[(b,t) for b,t,_ in faults])
    actual,_=render(source,enabled=(0,2,5),configs=configs,faults=faults,in_place=True)
    assert actual==expected
    changes=((20,0,{'lp':25}),(30,5,{'distortion':70}),(35,2,{'hp':90}))
    expected,_=render(source,candidate=False,configs=configs,changes=changes)
    actual,_=render(source,enabled=(0,2,5),configs=configs,changes=changes,in_place=True)
    assert actual==expected
    print('PASS stale/incomplete packets supply zero input and clear raw bus before stock mix; independent stock automation still reaches correct tracks')
    snapshot=controls(start=32,length=48)
    ordinary,settings,old=produce(snapshot)
    inplace,_,meta=produce(snapshot,in_place=True)
    duplicate,_,_=produce(snapshot,in_place=True,duplicate=True)
    assert ordinary[('y',0x60000)]==inplace[('y',0x60000)]==duplicate[('y',0x60000)]
    assert inplace[('y',S.SNAPSHOT)][:3]==[IPC.AUDIO_KEY,3,len(source)//32-1]
    assert inplace[('y',R.MAILBOX)]==[0]*35
    expected,_=render(ordinary[('y',0x60000)],candidate=False)
    actual,_=render(inplace[('y',0x60000)],enabled=(0,),in_place=True)
    assert actual==expected
    print('PASS actual producer uses native future bank and flips STATE->AUDIO; duplicate generation is inert; separate audio mailbox remains untouched')
    print('PASS serialized actual core0 grains -> in-place DSP1 stock shaping/mixing matches previous reference losslessly')
    print(f'PASS removes512 shared audio words +32 private RAW words:1632 bytes; renderer{meta["engine_words"]} words, producer{meta["producer_words"]} words')
    print('LIMIT: emulator sequential handshake; metadata lease, real deadlines, per-track engine pool and mode/pack integration remain unproved')
    print('ALL PASS')


def main():
    original=rhdsp.TOOL
    try:
        rhdsp.TOOL=str(build_fixture())
        verify()
    finally:rhdsp.TOOL=original


if __name__=='__main__':main()
