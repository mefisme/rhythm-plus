"""Offline core0 producer: private grain output, snapshot source, and native hook order."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tools','modules','remix/tools')]
from render_granular_reference import fixture,render
from granular_voice_reference import controls
import granular_producer_candidate as P
import granular_stock_controls as C
import granular_route_candidate as R
import granular_snapshot_candidate as S
import granular0 as G
import core0
import rhdspemu

STATE,REGISTERS,STOP=0x3a200,0x3a220,0x7ff0


def produce(snapshot,seconds=.04,valid=True,mode=R.TEXTURE,events=(),in_place=False,duplicate=False,flags=0):
    source=fixture();blocks=round(seconds*48000/32)
    source_id=snapshot.get('sample',5)
    segs,meta=P.code(in_place=in_place);labels=meta['labels']
    settings=dict(size=35,dens=55,pos=42,scan=48,spr=0,pspr=0)
    parameter=[0]*16
    for key,value in {**G.DEFAULTS,**settings,'trk':1,'gate':0}.items():parameter[G.NAMES.index(key)]=value
    parameter[G.P_KEY]=G.KEY;parameter[13]=flags
    region=[R.KEY,3,0,source_id,snapshot['start'],snapshot['end'],snapshot['increment'],snapshot.get('note_serial',0)]
    if not valid:region[3]=128
    bus=[0x210000+i for i in range(512)]
    memory=[('x',G.GB,parameter),('x',0x3a,[32]),('y',G.PAR0,[99]),
            ('x',G.SMP+4*source_id,[0,len(source)]),('y',G.PAGES+source_id*G.PSTRIDE,[0x040041,0x042043]),
            ('y',R.CONTROL,[R.KEY,3,0,mode]),('y',S.SNAPSHOT,region),('y',G.TRK_BUF,bus),
            ('y',STATE,[0,0x60000,0]),('y',0xffffd0,[0]),
            ('x',G.LB+G.LB_N,[0x5a1234,0x6b2345])]
    memory += [('y',0x40000+i,source[i:i+64]) for i in range(0,len(source),64)]
    # Ack boundary is a fixture here. Its ready publication must precede generation.
    memory += [('y',S.SNAPSHOT,[0])]
    wait,_=core0.asm_at([f'move y:>${STATE+2:x},a','add #>$1,a',f'move a1,y:>${STATE+2:x}',
                        f'move #>${R.KEY:x},a',f'move a,y:>${S.SNAPSHOT:x}','rts'],0x1a11)
    items=[]
    for k in range(8):
        items += [f'move #>${0x300+k:x},r{k}',f'move #>${10+k:x},n{k}',('words',[0x05f420|k,0xffffff if k==0 else (1<<(k+3))-1])]
    items += [('label','frame'),f'move y:>${STATE:x},a',f'move a1,y:>${R.CONTROL+2:x}',
              f'move a1,y:>${S.SNAPSHOT+2:x}']
    for index,(block,kind,value) in enumerate(events):
        addresses={'note':(S.SNAPSHOT+7,),'epoch':(S.SNAPSHOT+1,R.CONTROL+1),'mode':(R.CONTROL+3,)}[kind]
        items += [f'move y:>${STATE:x},a',f'cmp #>${block:x},a',('jcc','ne',f'event_{index}')]
        for address in addresses:items += [f'move #>${value:x},a',f'move a1,y:>${address:x}']
        items += [('label',f'event_{index}')]
    items += [('jsr',labels['after_wait'])]
    if duplicate:items += [('jsr',labels['produce'])]
    for k in range(8):items += [f'move r{k},y:>${REGISTERS+k:x}',f'move n{k},y:>${REGISTERS+8+k:x}',('words',[0x057060|k,REGISTERS+16+k])]
    # Registers are deliberately non-linear on entry; capture uses linear pointers.
    items += [('words',[0x05f420|k,0xffffff]) for k in range(8)]
    items += [f'move #>${G.TRK_BUF if in_place else P.RAW:x},r0',f'move y:>${STATE+1:x},r1',
              'do #$20,${capture_end:x}','move y:(r0)+,a','move a,y:(r1)+',('label','capture_end'),
              f'move r1,y:>${STATE+1:x}',f'move y:>${STATE:x},a','add #>$1,a',f'move a1,y:>${STATE:x}',
              f'cmp #>${blocks:x},a',('jcc','lt','frame'),('jmp',STOP)]
    wrapper,_=core0.asm_at(items,0x7000)
    result,ran=rhdspemu.run(0,pc=0x7000,stop=STOP,
        segs=segs+[('p',0x1a11,wait),('p',0x7000,wrapper)],mem=memory,
        dumps=[('y',0x60000,blocks*32),('y',G.TRK_BUF,512),('y',G.PAR0,1),('y',R.MAILBOX,35),('y',S.SNAPSHOT,8),
               ('y',STATE,3),('y',REGISTERS,24),('x',G.LB+G.LB_N,2)],maxins=100_000_000)
    if in_place:
        assert result[('y',G.TRK_BUF)][:32]==result[('y',0x60000)][-32:]
        assert result[('y',G.TRK_BUF)][32:]==bus[32:]
    else:assert result[('y',G.TRK_BUF)]==bus
    assert result[('y',G.PAR0)]==[99]
    assert result[('y',STATE)]==[blocks,0x60000+blocks*32,blocks],ran
    assert result[('x',G.LB+G.LB_N)]==[0x5a1234,0x6b2345]
    return result,settings,meta


def main():
    snapshot=controls(start=32,length=48)
    result,settings,meta=produce(snapshot)
    expected,_=render(fixture(),.04,settings,stock_snapshot=snapshot)
    assert result[('y',0x60000)]==expected
    packet=result[('y',R.MAILBOX)]
    assert packet[:3]==[R.KEY,3,len(expected)//32-1] and packet[3:]==expected[-32:]
    single,_,_=produce(snapshot,seconds=32/48000)
    registers=single[('y',REGISTERS)]
    assert registers==[0x300+k for k in range(8)]+[10+k for k in range(8)]+[0xffffff if k==0 else (1<<(k+3))-1 for k in range(8)]
    rejected,_,_=produce(snapshot,seconds=32/48000,valid=False)
    assert rejected[('y',R.MAILBOX)]==[0]*35
    outside,_,_=produce(dict(snapshot,end=16385),seconds=32/48000)
    assert outside[('y',R.MAILBOX)]==[0]*35
    print('PASS actual core0 producer matches grain reference bit-for-bit, publishes matching generation/frame, and preserves native track buffers')
    print('PASS snapshot sample5 overrides poisoned live selection99 without writing stock parameters; output uses private RAW storage')
    print('PASS ack boundary runs before generation, all r/n/m registers restored, copy guards intact, invalid source or out-of-source region does not publish')
    stock=dict((a+i,w) for sp,a,words in rhdspemu.segments(0) if sp=='p' for i,w in enumerate(words))
    assert [stock[a] for a in (0x20d,0x224,0x225,0x228,0x229)]==[0x0b9040,0x0bf080,0x367,0x0bf080,0x1a11]
    native=dict((a+i,w) for sp,a,words in rhdspemu.segments(1) if sp=='p' for i,w in enumerate(words))
    assert [native[a] for a in (0x11d,0x121,0x122)]==[0x0d0221,0x0d02e4,0x0d0289]
    print('PASS stock hook order: voice processing precedes next-note preparation; ring/mix precedes ack wait; producer can run after wait without nesting mixer saves')
    print(f'PASS core0 candidate: {meta["engine_words"]} renderer words + {meta["producer_words"]} producer words, separately placed beyond existing ring code')
    from emu_granular_snapshot import run as native_snapshot,PS,PM
    from granular_route_reference import render as voice_route
    native,_=native_snapshot(0,((PS.YB+PM.OFF_A,0xc0000),))
    packet=native[('y',S.SNAPSHOT)][:8]
    retained=dict(sample=packet[3],start=packet[4],end=packet[5],increment=packet[6])
    pitched,settings,_=produce(retained)
    pitched_audio=pitched[('y',0x60000)]
    plain=dict(retained,increment=0x8000)
    unmodulated,_,_=produce(plain)
    assert pitched_audio!=unmodulated[('y',0x60000)]
    expected,_=render(fixture(),.04,settings,stock_snapshot=retained)
    assert pitched_audio==expected
    routed,_=voice_route(pitched_audio,enabled=(0,),configs=[dict(lp=65,distortion=30)]+[{} for _ in range(7)])
    reference,_=voice_route(expected,candidate=False,configs=[dict(lp=65,distortion=30)]+[{} for _ in range(7)])
    assert routed==reference and any(routed[0])
    print('PASS serialized chain: actual retained Pitch envelope snapshot -> core0 grains -> actual A0122 source route, stock shaping and mixer')
    print('LIMIT: single engine, synthetic ack/snapshots; no physical mailbox lease, concurrent deadline, real note retrigger or Texture activation proof')
    print('ALL PASS')


if __name__=='__main__':main()
