"""Actual DSP per-track context isolation before imposing a shared grain budget."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tests','tools','modules','remix/tools')]
from render_granular_reference import fixture
from granular_voice_reference import controls
from emu_granular_producer import produce
import granular_pool_candidate as P
import granular_route_candidate as R
import granular_snapshot_candidate as S
import granular0 as G
import core0
import rhdspemu

FRAMES,STATE,OUTPUT=64,0x3a200,0x60000
CAPTURE_COUNTS=0x65000


def run(enabled,change=None,bounded=False,late_change=False,rebalance=False,host_mailbox=False):
    enabled=set(enabled);snapshot=controls(start=32,length=48)
    segs,meta=P.code(bounded=bounded,host_mailbox=host_mailbox);memory=[('x',0x3a,[32]),('y',STATE,[0,OUTPUT])]
    bus=[0x210000+i for i in range(512)];memory += [('y',G.TRK_BUF,bus)]
    source=fixture()
    if late_change:
        site=meta['labels']['before_save'];old=None
        for space,address,words in segs:
            if space=='p' and address<=site<address+len(words):
                offset=site-address;old=words[offset:offset+2];words[offset:offset+2]=[0x0af080,0x7400]
        assert old is not None
        patch,_=core0.asm_at([f'move y:>${STATE:x},a','cmp #>$10,a',('jcc','ne','resume'),
                             f'move y:>${P.TEMP:x},a','cmp #>$3,a',('jcc','ne','resume'),
                             'clr a',f'move a,x:>${P.STATE+3*256+G.P_SCAN:x}',
                             ('label','resume'),('words',old),('jmp',site+2)],0x7400)
        segs += [('p',0x7400,patch)]
    for track in range(8):
        values=[0]*256
        for name,value in {**G.DEFAULTS,'trk':track+1,'gate':0,'size':35,'dens':55,'scan':48,'pos':42}.items():values[G.NAMES.index(name)]=value
        values[G.P_KEY]=G.KEY
        if rebalance:values[G.P_DENS]=127
        sample=5+track;page=0x40+track*4
        if host_mailbox:
            memory += [('y',P.HOST_CONTROL+track*4,[R.KEY if track in enabled else 0,3,0,R.TEXTURE]),
                       ('y',P.HOST_PARAMS+track*16,values[:16])]
        memory += [('x',P.STATE+track*256,values),('y',P.META+track*P.META_STRIDE,[0]*P.META_STRIDE),
                   ('y',R.CONTROL+track*4,[R.KEY if track in enabled else 0,3,0,R.TEXTURE]),
                   ('y',S.SNAPSHOT+track*8,[0,3,0,sample,snapshot['start'],snapshot['end'],snapshot['increment'],0]),
                   ('x',G.SMP+4*sample,[0,len(source)]),
                   ('y',G.PAGES+sample*G.PSTRIDE,[(page<<12)|(page+1),((page+2)<<12)|(page+3)])]
        material=source[137*track:]+source[:137*track]
        memory += [('y',0x40000+track*0x4000+i,material[i:i+64]) for i in range(0,len(material),64)]
    wait=[]
    for track in range(8):wait += [f'move #>${R.KEY:x},a',f'move a,y:>${S.SNAPSHOT+track*8:x}']
    wait += ['rts'];wait,_=core0.asm_at(wait,0x1a11)
    items=[('label','frame')]
    for k in range(8):
        items += [f'move #>${0x300+k:x},r{k}',f'move #>${10+k:x},n{k}',('words',[0x05f420|k,0xffffff if k==0 else (1<<(k+3))-1])]
    for track in range(8):
        items += [f'move y:>${STATE:x},a',f'move a1,y:>${R.CONTROL+track*4+2:x}',f'move a1,y:>${S.SNAPSHOT+track*8+2:x}']
    if change is not None:
        track,parameter,value=change
        items += [f'move y:>${STATE:x},a','cmp #>$10,a',('jcc','ne','unchanged'),
                  f'move #>${value:x},a',f'move a1,x:>${P.STATE+track*256+parameter:x}',('label','unchanged')]
    if rebalance:
        for frame,key in ((24,R.KEY),(48,0)):
            label=f'unchanged_{frame}'
            items += [f'move y:>${STATE:x},a',f'cmp #>${frame:x},a',('jcc','ne',label),f'move #>${key:x},a']
            items += [f'move a1,y:>${R.CONTROL+track*4:x}' for track in range(1,8)]
            items += [('label',label)]
    items += [('jsr',meta['labels']['after_wait'])]
    for k in range(8):
        items += [f'move r{k},y:>${0x3a220+k:x}',f'move n{k},y:>${0x3a228+k:x}',('words',[0x057060|k,0x3a230+k]),('words',[0x05f420|k,0xffffff])]
    if rebalance:
        items += [f'move y:>${STATE:x},a','asl #3,a,a',f'add #>${CAPTURE_COUNTS:x},a','move a1,r1',
                  f'move #>${G.GW:x},n0','move #>$1,x0']
        for track in range(8):
            last=f'count_{track}'
            items += [f'move #>${P.STATE+track*P.STATE_STRIDE+G.GR0-G.GB:x},r0','clr b',
                      f'do #$10,${{{last}:x}}','move x:(r0)+n0,a','tst a','tne x0,a',
                      'add a,b',('label',last),'move b1,y:(r1)+']
    items += [f'move y:>${STATE+1:x},r1']
    for track in range(8):
        items += [f'move #>${G.TRK_BUF+64*track:x},r0',f'do #$20,${{capture_{track}:x}}',
                  'move y:(r0)+,a','move a,y:(r1)+',('label',f'capture_{track}')]
    items += [f'move r1,y:>${STATE+1:x}',f'move y:>${STATE:x},a','add #>$1,a',f'move a1,y:>${STATE:x}',
              f'cmp #>${FRAMES:x},a',('jcc','lt','frame'),('jmp',0x7ff0)]
    wrapper,_=core0.asm_at(items,0x7000)
    dumps=[('y',OUTPUT,FRAMES*256),('y',G.TRK_BUF,512),('y',0x3a220,24),('x',P.STATE,2048)]
    if rebalance:dumps.append(('y',CAPTURE_COUNTS,FRAMES*8))
    result,ran=rhdspemu.run(0,pc=0x7000,stop=0x7ff0,segs=segs+[('p',0x1a11,wait),('p',0x7000,wrapper)],
        mem=memory,dumps=dumps,maxins=200_000_000)
    assert 'pc=007ff0' in ran
    assert result[('y',0x3a220)]==[0x300+k for k in range(8)]+[10+k for k in range(8)]+[0xffffff if k==0 else (1<<(k+3))-1 for k in range(8)]
    for track in range(8):assert result[('y',G.TRK_BUF)][track*64+32:track*64+64]==bus[track*64+32:track*64+64]
    flat=result[('y',OUTPUT)]
    streams=[sum((flat[frame*256+track*32:frame*256+track*32+32] for frame in range(FRAMES)),[]) for track in range(8)]
    state=result[('x',P.STATE)]
    meta['live_grains']=[sum(bool(state[track*256+64+grain*G.GW]) for grain in range(16)) for track in range(8)]
    meta['scan_values']=[state[track*256+G.P_SCAN] for track in range(8)]
    if rebalance:meta['block_counts']=result['y',CAPTURE_COUNTS]
    return streams,meta


def main():
    all_tracks,meta=run(range(8))
    for track in range(8):
        alone,_=run((track,))
        assert all_tracks[track]==alone[track],track
        assert any(all_tracks[track])
    single,_,_=produce(controls(start=32,length=48),seconds=FRAMES*32/48000,in_place=True)
    assert all_tracks[0]==single[('y',0x60000)]
    changed,_=run(range(8),(3,G.P_SCAN,0))
    assert changed[3]!=all_tracks[3]
    for track in (0,1,2,4,5,6,7):assert changed[track]==all_tracks[track]
    print('PASS actual DSP eight persistent contexts: each output matches its isolated engine bit-for-bit; track0 also matches prior single-engine reference')
    print('PASS changing one track scan leaves seven others bit-identical; native opposite banks and caller r/n/m registers preserved')
    context_words=meta['state_words']+meta['metadata_words']
    print(f'PASS wrapper{meta["words"]} program words; context storage {context_words} words ({context_words*3} bytes)')
    for count in range(1,9):
        limited,budget=run(range(count),bounded=True)
        cap=16//count
        assert all(n<=cap for n in budget['live_grains']),budget['live_grains']
        assert sum(budget['live_grains'])<=16
        if count==1:assert limited[0]==all_tracks[0]
    print('PASS bounded wrapper: 1..8 active contexts share at most16 live grains; one active track retains the original16-grain sound')
    mirrored,_=run((0,),bounded=True,host_mailbox=True)
    assert mirrored[0]==all_tracks[0] and any(mirrored[0])
    print('PASS narrow host mailbox produces the same nonzero grain audio as the direct controls')
    _,budget=run((0,),bounded=True,rebalance=True)
    counts=budget['block_counts']
    assert counts[23*8]>2 and counts[24*8]<=2
    for frame in range(FRAMES):
        active=8 if 24<=frame<48 else 1
        block=counts[frame*8:frame*8+active]
        assert max(block)<=16//active and sum(block)<=16,(frame,block)
    print('PASS grain budget holds on every block while the active set expands from one to eight and shrinks back')
    concurrent,budget=run(range(8),late_change=True)
    assert budget['scan_values']==[48,48,48,0,48,48,48,48]
    assert concurrent[3]!=all_tracks[3]
    for track in (0,1,2,4,5,6,7):assert concurrent[track]==all_tracks[track]
    print('PASS host knob write injected after render/before context save survives; DSP writes back only its state, never ARM-owned parameter words')
    print('LIMIT: density/cap rebalancing is a candidate musical policy; real CPU deadlines and live host publication still require validation')


if __name__=='__main__':main()
