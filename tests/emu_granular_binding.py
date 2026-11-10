"""Actual DSP proof for experimental grain-owned source descriptors."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'modules'),str(ROOT/'remix/tools')]
from render_granular_reference import fixture,render
import granular0 as G


def main():
    source=fixture()
    for settings in ({},dict(size=35,dens=28,scan=48),
                     dict(size=90,dens=55,pos=42,scan=0,spr=30,pspr=12),
                     dict(size=10,dens=100,pitch=12,rev=64)):
        expected,_=render(source,.2,settings)
        actual,details=render(source,.2,settings,bind_sources=True)
        assert actual==expected
        assert len(details['source_metadata'])==48
    print('PASS fixed-source audio bit-identical to unmodified Remix DSP in4 grain configurations')
    # Switch from a long source to a substantially shorter source while grains live.
    other=[(-((word-(1<<24) if word&0x800000 else word)//2))&0xffffff for word in source[:4096]]
    settings=dict(size=90,dens=100,pos=90,scan=0,spr=0,pspr=0,zone=64)
    fixed,_=render(source,.12,settings,bind_sources=True)
    actual,details=render(source,.12,settings,bind_sources=True,switch=(150,other))
    assert actual[:4800]==fixed[:4800] and actual[4800:]!=fixed[4800:]
    active=[]
    for index in range(16):
        if details['grain_state'][index*G.GW+G.G_TOT]:
            active.append(tuple(details['source_metadata'][index*3:index*3+3]))
    a=(G.PAGES+5*G.PSTRIDE,0,16384);b=(G.PAGES+7*G.PSTRIDE,0,4096)
    assert a in active and b in active and set(active)<={a,b},active
    print('PASS source change: existing grains retain old table/start/length; new grains use shorter new source')
    print('PASS output unchanged before scheduled source change, changes afterward; both sources coexist in active grain state')
    print(f'PASS candidate cost: {details["renderer_words"]-1348} extra DSP program words and48 metadata words')
    print('LIMIT: offline single-engine reference; metadata address ownership, pack lifetime, stock processing and hardware deadlines unproved')
    print('ALL PASS')


if __name__=='__main__':main()
