"""Offline reference: feed grain blocks through actual stock core1 voice shaping.

Executes stock P:511 (distortion, HP/LP/resonance, amp-envelope stages), with
synthetic persistent voice state. It does not route live core0 audio into core1,
allocate device memory, process sample selection/tune/region, or install firmware.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','remix/tools')]
import rpasm
rpasm.use()
import core0
import rhdspemu

VOICE,PARAM,BUFFER=0x40,0x307c8,0x2a02
INPUT,OUTPUT=0x40000,0x60000
STATE,WRAPPER,STOP=0x1f00,0x7000,0x7ff0


def distortion_reciprocal():
    """Exact integer formula verified against all512 stock device words twice.

    Evidence notes/granular-device-reference/stock-distortion-reciprocal.json.
    No device or table-file dependency when rendering; no proprietary table blob.
    """
    return [(1<<31)//(512+i) for i in range(512)]


def process(samples,*,hp=0,lp=127,resonance=0,distortion=0,slope=64,
            mode=0,stage=1,envelope=0x7fffff,changes=(),track=0):
    if not samples or len(samples)%32 or len(samples)>96000:raise ValueError('bounded whole blocks required')
    if any(not 0<=v<=127 for v in (hp,lp,resonance,distortion,slope)) or mode not in (0,1,2):
        raise ValueError('invalid stock parameter')
    if not 0<=track<8 or not 0<=stage<=5 or not 0<=envelope<=0x7fffff:
        raise ValueError('invalid voice state')
    voice_address,parameter_address=VOICE+track*16,PARAM+track*32
    blocks=len(samples)//32
    assert INPUT+len(samples)<=OUTPUT and OUTPUT+len(samples)<=0x80000
    fields={'slope':9,'distortion':10,'hp':11,'lp':12,'resonance':13}
    changes=tuple(changes)
    if len(changes)>32 or any(not 0<block<blocks or any(key not in fields or not 0<=value<=127 for key,value in patch.items())
           for block,patch in changes):raise ValueError('invalid parameter-change schedule')
    items=[('words',[0x05f420|k,0xffffff]) for k in range(8)]
    items += [('label','block'),f'move y:>${STATE+1:x},r0',f'move #>${BUFFER:x},r1',
           'do #$20,${input_end:x}','move y:(r0)+,a','move a,x:(r1)+',('label','input_end'),
           f'move r0,y:>${STATE+1:x}',f'move #>${voice_address:x},r6',('jsr',0x511),
           f'move #>${BUFFER:x},r0',f'move y:>${STATE+2:x},r1',
           'do #$20,${output_end:x}','move x:(r0)+,a','move a,y:(r1)+',('label','output_end'),
           f'move r1,y:>${STATE+2:x}',f'move y:>${STATE:x},a','add #>$1,a',f'move a1,y:>${STATE:x}',
           f'cmp #>${blocks:x},a',('jcc','ge',STOP)]
    for index,(block,patch) in enumerate(changes):
        items += [f'cmp #>${block:x},a',('jcc','ne',f'change_{index}')]
        for key,value in patch.items():
            items += [f'move #>${value:x},x0',f'move x0,y:>${parameter_address+fields[key]:x}']
        items += [('label',f'change_{index}')]
    items += [('jmp','block')]
    wrapper,_=core0.asm_at(items,WRAPPER)
    parameters=[0]*32
    parameters[1]=mode;parameters[6]=64;parameters[8]=127
    parameters[9:14]=[slope,distortion,hp,lp,resonance]
    voice=[0]*16;voice[4]=0x7fffff;voice[5]=parameter_address;voice[10]=stage;voice[11]=envelope
    mem=[('x',1,[32,16]),('x',voice_address,voice),('y',parameter_address,parameters),('y',0x1405,[track]),
         ('y',STATE,[0,INPUT,OUTPUT]),('x',0x30200,distortion_reciprocal())]
    mem += [('y',INPUT+i,samples[i:i+64]) for i in range(0,len(samples),64)]
    result,ran=rhdspemu.run(1,pc=WRAPPER,stop=STOP,segs=rhdspemu.segments(1)+[('p',WRAPPER,wrapper)],
                          mem=mem,dumps=[('y',OUTPUT,len(samples)),('y',STATE,3),('x',voice_address,16)],maxins=120_000_000)
    assert result[('y',STATE)]==[blocks,INPUT+len(samples),OUTPUT+len(samples)],ran
    return result[('y',OUTPUT)],dict(ran=ran,voice=result[('x',voice_address)],track=track,
                                   parameters=dict(hp=hp,lp=lp,resonance=resonance,distortion=distortion,
                                                   slope=slope,mode=mode,stage=stage),changes=changes)
