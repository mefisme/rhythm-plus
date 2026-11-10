"""Offline complete DSP1 voice loop with a synthetic sample-reader boundary.

Runs A0122's real P:221 shaping, FX helpers, gain/fade and output mixing. The
native reader is replaced by a deterministic fixture so source routing can be
compared bit-for-bit. Mailbox publication is ordered in one interpreter, NOT a
concurrent dual-core timing or physical shared-memory ownership proof.
"""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','remix/tools')]
import rpasm
rpasm.use()
import core0
import rhdsp1
import rhdspemu
import granular_route_candidate as ROUTE
from granular_stock_reference import distortion_reciprocal

STATE,INPUT,OUTPUT=0x3a000,0x40000,0x60000
WRAPPER,READER,STOP=0x7000,0x7400,0x7ff0


def segments():
    folder=ROOT/'firmware/a0122'
    report=json.loads((folder/'manifest.json').read_text())['report']
    image=bytearray((folder/'rhythmplus-A0122.bin').read_bytes())
    return rhdsp1.parse(rhdsp1.sent(image,report,'pitchmod'))[0]


def render(samples,*,enabled=(),candidate=True,configs=None,faults=(),reader_gaps=(),changes=(),near_end=False,modes=None,in_place=False,bank=0,inactive=()):
    if not samples or len(samples)%32 or len(samples)>12800:raise ValueError('bounded whole source blocks required')
    if bank not in (0,1):raise ValueError('invalid native bank')
    if in_place:
        import granular_inplace_candidate as IPC
        import granular_snapshot_candidate as SNAP
    modes=[ROUTE.TEXTURE]*8 if modes is None else modes
    if len(modes)!=8 or any(mode not in (ROUTE.TEXTURE,ROUTE.TRIGGERED) for mode in modes):raise ValueError('invalid engine modes')
    enabled=set(enabled);blocks=len(samples)//32
    if not enabled<=set(range(8)):raise ValueError('invalid route track')
    assert OUTPUT+len(samples)*8<=0x80000
    configs=configs or [{} for _ in range(8)]
    if len(configs)!=8:raise ValueError('eight voice configurations required')
    fields=dict(slope=9,distortion=10,hp=11,lp=12,resonance=13)
    faults=tuple(faults);reader_gaps=tuple(reader_gaps);changes=tuple(changes)
    if len(faults)>8 or len(reader_gaps)>8 or len(changes)>8:raise ValueError('reference schedule limit')
    segs=segments();metadata={}
    if candidate:segs,metadata=(IPC if in_place else ROUTE).patched(segs)
    # Only sample-reader input is a fixture; stock shaping and mixing remain live.
    reader=['move y:>$1405,a',f'add #>${STATE+4:x},a','move a1,r2','move y:(r2),a',
            'add #>$1,a','move a1,y:(r2)']
    for index,(block,track) in enumerate(reader_gaps):
        reader += [f'move y:>${STATE:x},a',f'cmp #>${block:x},a',('jcc','ne',f'gap_{index}'),
                   'move y:>$1405,a',f'cmp #>${track:x},a',('jcc','eq','zero_reader'),('label',f'gap_{index}')]
    reader += [f'move y:>${STATE+1:x},r5',f'move #>${ROUTE.BUFFER:x},r1',
               'do #$20,${reader_end:x}','move y:(r5)+,a','move a,x:(r1)+',('label','reader_end'),'rts',
               ('label','zero_reader'),'clr a',f'move #>${ROUTE.BUFFER:x},r1',
               'do #$20,${reader_zero_end:x}','move a,x:(r1)+',('label','reader_zero_end'),'rts']
    reader_code,_=core0.asm_at(reader,READER)
    reader_jump,_=core0.asm_at([('jmp',READER)],0x1e5)
    items=[('words',[0x05f420|k,0xffffff]) for k in range(8)]
    items += [('label','block')]
    for track in range(8):
        control=ROUTE.CONTROL+4*track
        mail=SNAP.SNAPSHOT+8*track if in_place else ROUTE.MAILBOX+64*track
        payload=0x304f0+64*track+32*bank if in_place else mail+3
        ready=IPC.AUDIO_KEY if in_place else ROUTE.KEY
        items += ['clr a',f'move a,y:>${mail:x}',f'move y:>${STATE+1:x},r5',
                  f'move #>${payload:x},r3',f'do #$20,${{publish_{track}:x}}',
                  'move y:(r5)+,a','move a,y:(r3)+',('label',f'publish_{track}'),
                  'move #>$1,x0',f'move x0,y:>${mail+1:x}',f'move y:>${STATE:x},a',
                  f'move a1,y:>${mail+2:x}',f'move a1,y:>${control+2:x}',
                  f'move #>${ready:x},x0',f'move x0,y:>${mail:x}']
    for index,(block,track,kind) in enumerate(faults):
        if kind not in ('epoch','sequence','not_ready'):raise ValueError('unknown packet fault')
        offset,value={'epoch':(1,2),'sequence':(2,0xffffff),'not_ready':(0,0)}[kind]
        items += [f'move y:>${STATE:x},a',f'cmp #>${block:x},a',('jcc','ne',f'fault_{index}'),
                  f'move #>${value:x},x0',f'move x0,y:>${(SNAP.SNAPSHOT+8*track if in_place else ROUTE.MAILBOX+64*track)+offset:x}',('label',f'fault_{index}')]
    for index,(block,track,patch) in enumerate(changes):
        if any(key not in fields or not 0<=value<=127 for key,value in patch.items()):raise ValueError('invalid stock control change')
        items += [f'move y:>${STATE:x},a',f'cmp #>${block:x},a',('jcc','ne',f'change_{index}')]
        for key,value in patch.items():items += [f'move #>${value:x},x0',f'move x0,y:>${0x307c8+32*track+fields[key]:x}']
        items += [('label',f'change_{index}')]
    items += [('jsr',0x221),f'move y:>${STATE+2:x},r1']
    for track in range(8):
        items += [f'move #>${0x304f0+64*track+32*bank:x},r5',f'do #$20,${{capture_{track}:x}}',
                  'move y:(r5)+,a','move a,y:(r1)+',('label',f'capture_{track}')]
    items += [f'move r1,y:>${STATE+2:x}',f'move y:>${STATE+1:x},a','add #>$20,a',f'move a1,y:>${STATE+1:x}',
              f'move y:>${STATE:x},a','add #>$1,a',f'move a1,y:>${STATE:x}',
              f'cmp #>${blocks:x},a',('jcc','lt','block'),('jmp',STOP)]
    wrapper,_=core0.asm_at(items,WRAPPER)
    assert WRAPPER+len(wrapper)<=READER
    memory=[('x',1,[32,16]),('x',0x30200,distortion_reciprocal()),('y',0xffffd0,[bank]),
            ('y',STATE,[0,INPUT,OUTPUT,0]+[0]*8)]
    for track,config in enumerate(configs):
        parameters=[0]*32;parameters[6]=64;parameters[8]=127;parameters[9]=64;parameters[12]=127
        for key,value in config.items():
            if key not in fields or not 0<=value<=127:raise ValueError('invalid voice configuration')
            parameters[fields[key]]=value
        voice=[0]*16;voice[4]=0 if track in inactive else (track+1)*0x80000;voice[5]=0x307c8+32*track;voice[6]=1;voice[10]=1;voice[11]=0x7fffff
        memory += [('x',0x40+16*track,voice),('y',0x40+16*track,[0,0,0,0 if near_end else 100000,0]),
                   ('y',0x307c8+32*track,parameters),('y',0x37301+2*track,[0x7fffff,0x7fffff]),
                   ('y',ROUTE.CONTROL+4*track,[ROUTE.KEY if track in enabled else 0,1,0,modes[track]])]
    bus_guard=[0x180000+i for i in range(512)]
    if in_place:memory += [('y',0x304f0,bus_guard)]
    memory += [('y',INPUT+i,samples[i:i+64]) for i in range(0,len(samples),64)]
    result,ran=rhdspemu.run(1,pc=WRAPPER,stop=STOP,
        segs=segs+[('p',0x1e5,reader_jump),('p',READER,reader_code),('p',WRAPPER,wrapper)],
        mem=memory,dumps=[('y',OUTPUT,len(samples)*8),('y',STATE,12)]+([('y',0x304f0,512)] if in_place else []),maxins=120_000_000)
    state=result[('y',STATE)]
    assert state[:3]==[blocks,INPUT+len(samples),OUTPUT+len(samples)*8],ran
    if in_place:
        actual_bus=result[('y',0x304f0)]
        for track in range(8):
            start=64*track+32*(1-bank)
            assert actual_bus[start:start+32]==bus_guard[start:start+32], ('opposite native bank changed',bank,enabled,track,[(i,hex(a),hex(b)) for i,(a,b) in enumerate(zip(actual_bus[start:start+32],bus_guard[start:start+32])) if a!=b][:3])
    captured=result[('y',OUTPUT)]
    tracks=[[word for block in range(blocks) for word in captured[block*256+track*32:block*256+track*32+32]] for track in range(8)]
    return tracks,dict(ran=ran,reader_calls=state[4:12],route=metadata)


if __name__=='__main__':
    from render_granular_reference import fixture,render as grains
    audio,_=grains(fixture(),.02,dict(size=35,dens=55))
    baseline,_=render(audio,candidate=False)
    actual,details=render(audio,enabled=(0,2,5))
    print('equal',actual==baseline,details)
