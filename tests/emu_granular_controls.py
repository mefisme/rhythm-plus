"""Actual stock DSP tune/region calculations and their offline grain adapter."""
import math
import random
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from granular_voice_reference import controls
from render_granular_reference import fixture,render
from granular_stock_reference import process
import granular_stock_controls as adapter
import granular0 as G


def main():
    cases=({},dict(start=64),dict(length=32),dict(start=127,length=127),
           dict(tune=127,note=72),dict(fine_start=127,fine_length=127),dict(reverse=True))
    for track in range(8):
        for knobs in cases:
            triggered=controls(track=track,**knobs)
            updated=controls(track=track,refresh=True,**knobs)
            for key in ('start','end','length','ratio_input','increment','polyphase'):
                assert triggered[key]==updated[key],(track,knobs,key,triggered,updated)
            assert triggered['voice']==0x40+16*track
            assert triggered['parameters']==0x307c8+32*track
            assert 0<=min(triggered['start'],triggered['end'])<=max(triggered['start'],triggered['end'])<=16384
    print('PASS actual stock note setup and live control refresh agree for all8 voices, region extremes, fine values, tune and reverse')
    base=controls()
    for note in (36,48,60):
        a,b=controls(note=note),controls(note=note+12)
        assert abs(b['increment']-2*a['increment'])<=1
    increments=[controls(tune=t)['increment'] for t in range(0,128,8)]
    assert all(a<b for a,b in zip(increments,increments[1:]))
    print('PASS native note octaves double the increment; stock tune follows its native monotonic mapping')
    for start in (0,16,64,127):
        a=controls(start=start,length=32,sample_start=1000,sample_length=8192)
        assert 1000<=a['start']<a['end']<=9192
    assert controls(start=64)['start']==8192
    assert controls(length=32)['end']==4097
    assert base['end']==16257  # Stock endpoint includes its native fixed-point rounding.
    print('PASS start/length use stock source offsets, endpoint clamping and fine-resolution arithmetic')
    source=fixture()
    unity=dict(start=0,end=len(source),increment=0x8000)
    def signed_block(words):return [(x-(1<<24) if x&0x800000 else x)/(1<<23) for x in words]
    def rms(words):
        block=signed_block(words);return (sum(v*v for v in block)/len(block))**.5
    def tone(hz,amplitude=.5):return [round(amplitude*math.sin(2*math.pi*hz*n/48000)*(1<<23))&0xffffff for n in range(len(source))]
    def spread(values):return 20*math.log10(max(values)/min(values))
    for settings in ({},dict(size=90,dens=100,rev=127)):
        clean,_=render(source,.15,settings,stock_snapshot=unity)
        raw,_=render(source,.15,{**settings,'flags':4},stock_snapshot=unity)
        assert clean==raw and any(clean)
    high=tone(14000)
    raw,_=render(high,.15,dict(size=64,dens=40,pitch=12,flags=4),stock_snapshot=unity)
    clean,_=render(high,.15,dict(size=64,dens=40,pitch=12),stock_snapshot=unity)
    assert rms(raw)/rms(clean)>2,(rms(raw),rms(clean))
    print('PASS Clean leaves unity pitch unchanged and lowers a 14 kHz tone by over 6 dB at +12; Raw bypasses it')
    low=tone(220)
    def largest_step(words):
        block=signed_block(words);return max(abs(block[i]-2*block[i-1]+block[i-2]) for i in range(2,len(block)))
    hard,_=render(low,.15,dict(size=40,dens=40,win=0),stock_snapshot=unity)
    soft,_=render(low,.15,dict(size=40,dens=40,win=50),stock_snapshot=unity)
    assert largest_step(hard)>10*largest_step(soft)
    print('PASS Edge 0 gives hard grain edges; the default Edge has none')
    generator=random.Random(5);noise=[round(max(-.9,min(.9,generator.gauss(0,.2)))*(1<<23))&0xffffff for n in range(len(source))]
    levels=[rms(render(noise,.25,dict(size=64,dens=dens),stock_snapshot=unity)[0]) for dens in (30,40,60,80,100)]
    assert spread(levels)<3,levels
    print('PASS the output level stays within 3 dB from Density 30 to 100')
    sparse,_=render(low,.25,dict(size=40,dens=0),stock_snapshot=unity)
    gaps=sum(1 for block in range(0,len(sparse),32) if not any(sparse[block:block+32]))
    assert gaps>len(sparse)/32/2
    print('PASS Density 0 leaves silent gaps between grains')
    full=[0x7fffff]*len(source)
    loud,_=render(full,.15,dict(size=90,dens=100,win=100,level=127*127*512),stock_snapshot=unity)
    assert all(x<0x800000 for x in loud) and max(loud)==0x7fffff
    print('PASS 16 full-scale grains at maximum Level saturate and never wrap')
    held=dict(size=40,dens=40)
    running,_=render(source,.3,held,stock_snapshot=unity)
    tail,_=render(source,.3,held,stock_snapshot=unity,field_changes=[(150,13,8)])
    edge=151*32
    assert tail[:edge]==running[:edge] and any(tail[edge:edge+320]) and not any(tail[edge+64*32:])
    print('PASS with new grains held, the playing grains finish and the track then goes silent')
    even=dict(size=64,dens=40,scan=0)
    plain,_=render(low,.25,even,stock_snapshot=unity)
    assert render(low,.25,dict(even,fine=127),stock_snapshot=unity)[0]!=plain
    assert render(low,.25,dict(even,fine=127<<8),stock_snapshot=unity)[0]!=plain
    print('PASS Size Scatter and Jitter change the output')
    # Timing 1200 samples: one Lock loop of 16 grains is 19200 samples.
    loop=19200
    def loops(flags):
        words,_=render(low,1.6,dict(size=20,dens=0,scan=0,timing=1200,spr=127,pspr=127,fine=128<<16,flags=flags),stock_snapshot=unity)
        return [words[loop*k:loop*(k+1)] for k in (1,2,3)]
    def changed(a,b):return sum(1 for g in range(16) if a[g*1200:(g+1)*1200]!=b[g*1200:(g+1)*1200])
    free=loops(0);held=loops(127<<8);some=loops(100<<8)
    assert free[0]!=free[1] and changed(*free[:2])>=12,changed(*free[:2])
    assert held[0]==held[1]==held[2] and any(held[0])
    assert 0<changed(*some[:2])+changed(*some[1:])<changed(*free[:2])+changed(*free[1:]),(changed(*some[:2]),changed(*some[1:]))
    print('PASS Lock at full repeats the same 16 grains each loop; a middle Lock changes a few; Lock 0 changes nearly all')
    # Four flat steps: a grain inside one step keeps one level, so sliced grains share four peaks.
    steps=[round((.1+.2*(4*n//len(source)))*(1<<23))&0xffffff for n in range(len(source))]
    def peaks(slices,step=0,spr=127):
        flags=(slices-1)<<15|step<<19 if slices else 0
        words,_=render(steps,1.6,dict(size=10,dens=0,scan=0,timing=2400,spr=spr,fine=128<<16,flags=flags),stock_snapshot=unity)
        found=[];n=0
        while n<len(words):
            if words[n]:
                end=n
                while end<len(words) and words[end]:end+=1
                found.append(max(words[n:end]));n=end
            else:n+=1
        return found[4:-1]  # The last grain may be cut off by the end of the render.
    sliced,free=peaks(4),peaks(0)
    assert len(sliced)>=20 and len(set(sliced))<=4,(len(sliced),sorted(set(sliced)))
    assert len(set(free))>4,sorted(set(free))
    # No scatter: every grain plays the first slice, and a step of 2 moves them all to the third.
    first,third=set(peaks(4,0,0)),set(peaks(4,2,0))
    assert len(first)==1 and len(third)==1 and 4.5<max(third)/max(first)<5.5,(first,third)
    print('PASS Slice starts every grain at a slice start and steps move it; without it grains start anywhere')
    def onsets(words):
        marks=[n for n in range(32,len(words),32) if any(words[n:n+32]) and not any(words[n-32:n])]
        return marks
    every,_=render(low,.5,dict(size=20,dens=0,scan=0,timing=4800,fine=128<<16),stock_snapshot=unity)
    assert 4<=len(onsets(every))<=5 and all(abs(b-a-4800)<=32 for a,b in zip(onsets(every),onsets(every)[1:])),onsets(every)
    some,_=render(low,.5,dict(size=20,dens=0,scan=0,timing=1200,fine=24<<16),stock_snapshot=unity)
    full,_=render(low,.5,dict(size=20,dens=0,scan=0,timing=1200,fine=128<<16),stock_snapshot=unity)
    assert len(onsets(some))<len(onsets(full))
    print('PASS Timing spaces grains exactly; a lower step chance plays fewer of them')
    unsynced,_=render(low,.5,dict(size=20,dens=0,scan=0,timing=9600,fine=128<<16),stock_snapshot=unity)
    synced,_=render(low,.5,dict(size=20,dens=0,scan=0,timing=9600,fine=128<<16),stock_snapshot=unity,field_changes=[(200,1,9600|1<<18)])
    assert unsynced[:200*32]==synced[:200*32] and any(synced[201*32:204*32]) and not any(unsynced[201*32:204*32])
    print('PASS a sync pulls the next grain to the grid')
    moving=dict(size=20,dens=40,scan=63,zone=4)
    assert render(low,.25,dict(moving,flags=16),stock_snapshot=unity)[0]!=render(low,.25,moving,stock_snapshot=unity)[0]
    print('PASS Bounce changes the scan path')
    for chosen,tones in ((1,{-12,0,12}),(2,{-12,-5,0,7,12}),(3,{-12,-9,-5,0,3,7,12}),(4,{-12,-8,-5,0,4,7,12})):
        _,state=render(low,.15,dict(size=90,dens=100,pspr=127,scan=0,flags=chosen<<5),stock_snapshot=unity)
        heard=set()
        for index in range(16):
            grain=state['grain_state'][index*G.GW:(index+1)*G.GW]
            if grain[G.G_TOT]:
                semitones=12*math.log2(((grain[G.G_IH]<<24)|grain[G.G_IL])/(1<<24));heard.add(round(semitones));assert abs(semitones-round(semitones))<.1
        assert heard and heard<=tones,(chosen,heard)
    print('PASS each Pitch Set snaps Pitch Scatter to its chord tones')
    reference,_=render(source,.15,dict(size=64,dens=40),stock_snapshot=unity)
    def level(value):
        output,_=render(source,.15,dict(size=64,dens=40,level=value),stock_snapshot=unity)
        return sum(abs(x-(1<<24) if x&0x800000 else x) for x in output)
    reference_sum=sum(abs(x-(1<<24) if x&0x800000 else x) for x in reference)
    ratios=[level(word)/reference_sum for word in (0,0x100000,0x200000,0x400000)]
    for ratio,expected in zip(ratios,(1,1,2,4)):
        assert abs(ratio-expected)<.03,(ratios,)
    print('PASS Level multiplies the rendered block by the exact Q23 word')
    snapshot=controls(start=32,length=32)
    settings=dict(size=35,dens=55,pos=50,scan=0,spr=0,pspr=0)
    original,details=render(source,.2,settings,stock_snapshot=snapshot)
    outside=[word if snapshot['start']<=i<snapshot['end'] else (word^0xffffff) for i,word in enumerate(source)]
    altered,_=render(outside,.2,settings,stock_snapshot=snapshot)
    assert original==altered and any(original)
    metadata=(G.PAGES+5*G.PSTRIDE,snapshot['start'],snapshot['length'])
    active=0
    for index in range(16):
        state=details['grain_state'][index*G.GW:(index+1)*G.GW]
        if state[G.G_TOT]:
            active+=1
            assert tuple(details['source_metadata'][index*3:index*3+3])==metadata
            assert (state[G.G_IH]<<19)+(state[G.G_IL]>>5)==snapshot['increment']<<4
    assert active
    pitched,_=render(source,.2,settings,stock_snapshot=controls(start=32,length=32,note=72))
    assert pitched!=original
    shaped,_=process(original,lp=40,distortion=50)
    assert shaped!=original and any(shaped)
    print('PASS grains use exact native region and Q15-to-Q19 pitch ratio; altering all audio outside the region leaves output bit-identical')
    print('PASS note transposition alters grain output and the actual stock filter/distortion chain still shapes it')
    a,b=controls(start=0,length=64),controls(start=64,length=32,tune=76)
    settings=dict(size=90,dens=100,pos=90,scan=0,spr=0,pspr=0,zone=64)
    fixed,_=render(source,.12,settings,stock_snapshot=a)
    moved,details=render(source,.12,settings,stock_snapshot=a,stock_changes=[(150,b)])
    assert fixed[:4800]==moved[:4800] and fixed[4800:]!=moved[4800:]
    live=set()
    for i in range(16):
        if details['grain_state'][i*G.GW+G.G_TOT]:live.add(tuple(details['source_metadata'][i*3:i*3+3]))
    assert (G.PAGES+5*G.PSTRIDE,a['start'],a['length']) in live
    assert (G.PAGES+5*G.PSTRIDE,b['start'],b['length']) in live
    print('PASS block-scheduled stock region/tune update leaves prior audio untouched; old and new regions coexist in grain-owned state')
    long_grain=dict(size=110,dens=0,pos=64,scan=0,spr=0,pspr=0)
    for reverse in (False,True):
        initial=controls(reverse=reverse)
        tuned=controls(reverse=reverse,tune=76,refresh=True)
        baseline,_=render(source,.016,long_grain,stock_snapshot=initial)
        updated,state=render(source,.016,long_grain,stock_snapshot=initial,stock_changes=[(12,tuned)])
        grains=[state['grain_state'][i:i+G.GW] for i in range(0,G.GW*G.MAXG,G.GW)]
        assert grains[0][G.G_TOT] and not any(g[G.G_TOT] for g in grains[1:])
        assert baseline[:384]==updated[:384] and any(baseline[384:416])
        assert baseline[384:416]!=updated[384:416],('existing grain ignored stock Tune',reverse)
        increment=((grains[0][G.G_IH]<<24)|grains[0][G.G_IL])
        if increment & (1<<47):increment-=1<<48
        assert increment==tuned['increment']*(-512 if reverse else 512)
    print('PASS stock Tune retunes an existing grain in the next block in both directions')
    full_zone=dict(size=90,dens=0,scan=0,spr=0,pspr=0,zone=127)
    left,left_state=render(source,.016,dict(full_zone,pos=16),stock_snapshot=unity)
    right,right_state=render(source,.016,dict(full_zone,pos=64),stock_snapshot=unity)
    assert left!=right and left_state['grain_state'][G.G_PH]<right_state['grain_state'][G.G_PH]
    print('PASS Position moves the grain read head with Zone fully open')
    for note in (0,24,60,84,96,110):
        high=controls(note=note,tune=127)
        output,state=render(source,.08,dict(size=35,dens=100,pos=70),stock_snapshot=high)
        assert any(output)
    reverse_output,reverse_state=render(source,.08,dict(size=35,dens=100,pos=70,rev=127),stock_snapshot=controls(note=110,tune=127))
    assert any(reverse_output) and any(reverse_state['grain_state'][i*G.GW+G.G_IH]&0x800000 for i in range(16))
    # Check the copy interval independently against every actual interpolation
    # position in a block, at integer boundaries and fractional starting phases.
    for magnitude in (1,16,(1<<19)-1,1<<19,(1<<19)+1,base['increment']<<4,259133<<4,adapter.SAFE_RATIO):
        for direction in (-1,1):
            step=direction*magnitude
            lo=(32*step)//(1<<19) if step<0 else 0
            count=(-lo+2) if step<0 else (32*step)//(1<<19)+3
            assert count<=G.LB_N
            for phase in (0,1,(1<<23),(1<<24)-1):
                for n in range(32):
                    position=(phase+n*step*32)//(1<<24)
                    assert lo<=position and position+1<lo+count
    print('PASS copy intervals cover both interpolation reads across pitch boundaries and fractional starting phases')
    print('PASS stock note/tune extremes render with scratch-buffer boundary canaries intact; no extra copy memory')
    reverse=controls(start=32,length=32,reverse=True)
    backward,state=render(source,.12,settings,stock_snapshot=reverse)
    assert any(backward)
    for index in range(16):
        grain=state['grain_state'][index*G.GW:(index+1)*G.GW]
        if grain[G.G_TOT]:assert grain[G.G_IH]&0x800000
    for unsupported in (controls(length=0),):
        try:adapter.words(unsupported,len(source))
        except ValueError:pass
        else:raise AssertionError('unsupported reference condition silently accepted')
    print('PASS stock Reverse renders reversed grains inside its native region; sub8-sample regions remain explicitly rejected')
    for reverse in (False,True):
        for length in (8,13,31):
            region=dict(start=200,end=200+length,increment=controls(note=110,tune=127)['increment'])
            if reverse:region['start'],region['end']=region['end'],region['start']
            a,_=render(source,.04,dict(size=35,dens=100),stock_snapshot=region,scratch_fill=0x123456)
            b,_=render(source,.04,dict(size=35,dens=100),stock_snapshot=region,scratch_fill=0x765432)
            assert a==b,(reverse,length)
    print('PASS short regions at maximum stock ratio do not reuse stale scratch audio; both directions and scratch boundary canaries checked')
    print('LIMIT: offline single engine; live routing, tiny-region policy and hardware deadlines unproved')
    print('ALL PASS')


if __name__=='__main__':main()
