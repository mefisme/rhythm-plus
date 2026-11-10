"""Actual stock core1 processing of actual grain output, no device writes."""
from pathlib import Path
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from render_granular_reference import fixture,render,signed
from granular_stock_reference import process,distortion_reciprocal


def rms(words):return (sum(signed(w)**2 for w in words)/len(words))**.5


def main():
    table=distortion_reciprocal()
    assert hashlib.sha256(b''.join(w.to_bytes(3,'big') for w in table)).hexdigest()==\
        '955d50e8a8f77f3b4d0a684b81c4f8d77075e09f79b7536da771254a2c5cca7e'
    evidence=ROOT/'notes/granular-device-reference/stock-distortion-reciprocal.json'
    if evidence.exists():
        observed=json.loads(evidence.read_text(encoding='utf-8-sig'))
        assert observed['TwoReadsEqual'] and table==observed['Words']
    print('PASS exact512-entry stock distortion lookup formula matches captured table digest')
    grains,_=render(fixture(),.3,dict(size=35,dens=28,scan=48))
    baseline,_=process(grains);level=rms(baseline)
    assert level>0
    for track in range(1,8):
        actual,_=process(grains,track=track)
        assert actual==baseline
    print('PASS all8 stock voice/track contexts produce identical audio for identical grain input/settings')
    low,_=process(grains,lp=40);high,_=process(grains,hp=80)
    moderate,_=process(grains,lp=70)
    resonant,_=process(grains,lp=70,resonance=100)
    distorted,_=process(grains,distortion=100)
    decayed,_=process(grains,slope=20)
    attack,_=process(grains,stage=0,envelope=0,slope=90)
    released,release_state=process(grains,stage=4)
    assert 0<rms(low)<level*.4 and 0<rms(high)<level*.25
    assert rms(resonant)>rms(moderate)*1.2
    assert rms(distorted)>level*3 and distorted!=baseline
    assert 0<rms(decayed)<level*.5
    assert rms(attack[-4096:])>rms(attack[:1024])*2
    assert not any(released[32:]) and release_state['voice'][10]==5
    print('PASS actual stock LP/HP/resonance/distortion and envelope decay/attack/fast-release alter grain output as expected')
    changed,_=process(grains,changes=[(150,{'lp':40})])
    assert changed[:4800]==baseline[:4800] and changed[4800:]!=baseline[4800:]
    print('PASS in-stream cutoff change leaves prior audio identical and affects subsequent audio with persistent filter state')
    # Exercise the largest supported capture; this previously crossed emulator memory.
    long_input=(grains*7)[:96000]
    long_output,_=process(long_input)
    assert len(long_output)==96000 and any(long_output[-1024:])
    print('PASS maximum2-second capture stays in emulator memory and retains nonzero tail audio')
    print('LIMIT: offline stock processor; live cross-core routing, source/tune/region integration and hardware deadlines unproved')
    print('ALL PASS')


if __name__=='__main__':main()
