"""Final native Pitch+ state exported without changing voice or modulation state."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tools','modules','remix/tools')]
from granular_route_reference import segments
import granular_route_candidate as R
import granular_snapshot_candidate as S
import core0
import rhdspemu
import pshape as PS
import pitchmod as PM
import fshape as FS
import voicefilt as VF
from granular_voice_reference import controls

REPORT=json.loads((ROOT/'firmware/a0122/manifest.json').read_text())['report']


def same_native(actual,native,key):
    # The broad modulation capture also includes newly allocated export scratch.
    # Exclude exactly those owned words; compare every remaining word unchanged.
    for offset,(left,right) in enumerate(zip(actual[key],native[key])):
        if key==('y',0x1610) and S.SAVE<=key[1]+offset<S.SAVE+7:continue
        assert left==right,(key,offset,left,right)


def run(track,modulation=(),export=True,disabled=(),inactive=(),update=False,region=None):
    segs=segments();segs,route=R.patched(segs);segs,meta=S.patched(segs)
    rr=int(REPORT['pitchmod']['rr'],16)
    items=[('words',[0x05f420|k,0xffffff]) for k in range(8)]
    if update:
        items += [('jsr',meta['labels']['update'] if export else 0x289)]
    else:
        items += [f'move #>${0x40+track*16:x},r4','move #>$0,y0',('jsr',rr)]
        if export:items += [('jsr',meta['labels']['export'])]
    for k in range(8):
        items += [f'move r{k},y:>${0x3a100+k:x}',f'move n{k},y:>${0x3a108+k:x}',('words',[0x057060|k,0x3a110+k])]
    items += [('jmp',0x7ff0)]
    wrapper,_=core0.asm_at(items,0x7100)
    memory=[('y',0x121,[(track-1)&7])]
    table=PS.table_words(REPORT['pshape'].get('v2',False))
    memory += [('y',PS.ENV_Y+i,[w or 0 for w in table[i:i+64]]) for i in range(0,len(table),64)]
    for t in range(8):
        voice=[0]*16;voice[4]=0 if t in inactive else (t+1)*0x80000;voice[5]=0x307c8+32*t
        parameters=[0]*32;parameters[0]=30+t;parameters[6:9]=[64,32,64]
        state=[0]*16;state[0]=0x8000;state[3]=2001+100*t;state[4]=1+100*t
        if region is not None and t==track:state[4],state[3]=region['start'],region['end']
        memory += [('y',S.SNAPSHOT+8*t+3,[30+t]),('x',0x30000+4*(30+t),[256*t,16384,256*t+16384,0]),('x',0x40+16*t,voice),('y',0x40+16*t,state),('y',0x307c8+32*t,parameters),
                   ('y',R.CONTROL+4*t,[0 if t in disabled else R.KEY,3,11,0])]
    memory += [('y',address,[value]) for address,value in modulation]
    result,ran=rhdspemu.run(1,pc=0x7100,stop=0x7ff0,
        segs=segs+[('p',0x7100,wrapper)],mem=memory,
        dumps=[('y',S.SNAPSHOT,64),('x',0x40,128),('y',0x40,128),('y',0x1610,0x9f0),('y',0x3a100,24)],maxins=100000)
    assert 'pc=007ff0' in ran,ran
    return result,dict(ran=ran,route_words=route['words'],snapshot_words=meta['words'])


def main():
    for track in range(8):
        cases=[(),((PS.YB+PM.OFF_A+track,0xc0000),),
               ((PS.YB+PM.OFF_L+track,0x60000),(PS.SHP_L+track,4)),
               ((FS.RO+track,0x40000),),
               ((FS.GK+track,0x400000),(FS.GP+track,(-0xc0000)&0xffffff))]
        ratios=[]
        for words in cases:
            native,_=run(track,words,export=False)
            actual,meta=run(track,words)
            for key in (('x',0x40),('y',0x40),('y',0x1610),('y',0x3a100)):
                same_native(actual,native,key)
            snapshots=actual[('y',S.SNAPSHOT)]
            for t in range(8):
                state=actual[('y',0x40)][16*t:16*t+16]
                packet=snapshots[8*t:8*t+8]
                assert packet==[R.KEY,3,11,30+t,state[4],state[3],state[0],0],(track,t,packet)
            ratios.append(snapshots[track*8+6])
        assert ratios[1]>ratios[0] and ratios[2]!=ratios[0] and ratios[3]>ratios[0] and ratios[4]<ratios[0],(track,ratios)
    print('PASS all8 voices: exported ratios include actual A0122 pitch envelope, LFO, random offset and glide contributions')
    print('PASS export matches native source/region/ratio/note serial, and preserves all voice state, modulation state and r/n/m registers')
    actual,meta=run(0,disabled=(2,6),inactive=(3,7))
    snapshots=actual[('y',S.SNAPSHOT)]
    for t in range(8):assert snapshots[t*8]==(S.INACTIVE_STATE if t in (3,7) else R.KEY)
    print('PASS native state is exported even when routing is disabled; inactive voices have a distinct non-audio state tag')
    for t in range(8):
        words=((PS.YB+PM.OFF_A+t,0xc0000),)
        native,_=run(t,words,export=False,update=True)
        actual,_=run(t,words,update=True)
        for key in (('x',0x40),('y',0x40),('y',0x1610),('y',0x3a100)):
            same_native(actual,native,key)
        packet=actual[('y',S.SNAPSHOT)][8*t:8*t+8]
        state=actual[('y',0x40)][16*t:16*t+16]
        assert packet[4:7]==[state[4],state[3],state[0]]
        assert packet[2]==1  # Existing completed-block counter0 -> request next frame1.
    print('PASS real round-robin update wrapper exports final native state without changing existing state or registers')
    for t in range(8):
        ordinary=controls(track=t,start=16,length=32,program=segments())
        scanned=controls(track=t,start=16,length=32,program=segments(),
                         extra_memory=[('y',VF.SCANPH+t,[0x400000]),('y',VF.SCAND+t,[0x400000])])
        assert scanned['start']>ordinary['start'] and scanned['length']==ordinary['length']
        actual,_=run(t,region=scanned)
        packet=actual[('y',S.SNAPSHOT)][8*t:8*t+8]
        assert packet[4:6]==[scanned['start'],scanned['end']]
    print('PASS actual A0122 sample-start scan affects trigger region and exported region retains that offset for all8 tracks')
    for t in range(8):
        scan_words=[(VF.SCANPH+t,0x400000),(VF.SCAND+t,0x400000)]
        expected=controls(track=t,sample=30+t,start=32,length=64,sample_start=256*t,program=segments(),
                          extra_memory=[('y',address,[value]) for address,value in scan_words])
        plain=controls(track=t,sample=30+t,start=32,length=64,sample_start=256*t,program=segments())
        assert expected['start']>plain['start']
        enabled,_=run(t,scan_words,update=True)
        state=enabled[('y',0x40)][16*t:16*t+16]
        packet=enabled[('y',S.SNAPSHOT)][8*t:8*t+8]
        assert [state[4],state[3]]==[expected['start'],expected['end']]
        assert packet[4:6]==[expected['start'],expected['end']]
        off,_=run(t,scan_words,update=True,disabled=(t,))
        assert off[('y',0x40)][16*t+4]==plain['start']
    print('PASS native region refresh keeps FX Scan on enabled tracks and leaves disabled tracks stock, all8 tracks')
    print(f'PASS route+snapshot candidates fit{meta["route_words"]+meta["snapshot_words"]} DSP1 program words without changing existing A0122 code placement')
    print('LIMIT: emulator mailbox addresses, coherent control latching and sequential producer; pack lifecycle, real dual-core deadlines and Texture activation unproved')
    print('ALL PASS')


if __name__=='__main__':main()
