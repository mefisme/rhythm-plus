"""Offline actual-DSP Remix grain reference, NOT a Rhythm Plus firmware build.

Synthetic source pages and a repeated32-sample block harness live only inside
dsptool's memory. No stock shaping or new trigger/source bridge is implemented.
All output uses the same fixed scale; there is no per-clip normalization.
"""
from pathlib import Path
import argparse
import json
import math
import struct
import sys
import wave
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','remix/tools')]
import rpasm
rpasm.use()
import core0
import granular0 as G
import rhdspemu

RATE=48000
SOURCE_WORDS=16384
CAPTURE=0x60000
COUNT,POINTER=0x1f00,0x1f01
STOP=0x3ff0


def fixture():
    result=[]
    for n in range(SOURCE_WORDS):
        t=n/RATE
        phase=2*math.pi*(130.8128*t+70*t*t)
        body=(.36*math.sin(phase)+.12*math.sin(2*phase)+.06*math.sin(5*phase))
        decay=math.exp(-13*(t%.085))
        attack=min(1,(n%4080)/80)
        tick=.10*math.sin(2*math.pi*1700*t)*math.exp(-180*(t%.085))
        value=(body*decay+tick)*attack
        result.append(round(value*(1<<23))&0xffffff)
    return result


def signed(word):return word-(1<<24) if word&0x800000 else word


def wav(path,words):
    # DSP values are Q23;16bit PCM conversion only, same gain for all clips.
    samples=[max(-32768,min(32767,signed(word)>>8)) for word in words]
    with wave.open(str(path),'wb') as stream:
        stream.setparams((1,2,RATE,len(samples),'NONE','not compressed'))
        stream.writeframes(struct.pack('<'+'h'*len(samples),*samples))
    return dict(samples=len(samples),peak=max(map(abs,samples),default=0)/32768,
                rms=(sum(x*x for x in samples)/max(1,len(samples)))**.5/32768,
                clipped=sum(x in (-32768,32767) for x in samples))


def render(source,seconds,settings,bind_sources=False,switch=None,stock_snapshot=None,stock_changes=(),scratch_fill=None,field_changes=()):
    if stock_snapshot is not None and switch is not None:
        raise ValueError('combined sample/stock snapshot switching needs an atomic handoff proof')
    if len(stock_changes)>32:raise ValueError('too many stock reference changes')
    blocks=round(seconds*RATE/32)
    if not 1<=blocks<=3000:raise ValueError('render length must be <=2 seconds')
    assert CAPTURE+blocks*32<=0x80000, 'capture exceeds dsptool memory'
    if stock_snapshot is not None:
        import granular_stock_controls as stock_controls
        import granular_source_binding as binding
        bind_sources=True
        words,labels,tables=stock_controls.code()
    elif bind_sources:
        import granular_source_binding as binding
        words,labels,tables=binding.code(note=True)
    else:words,labels,tables=G.code(note=True)
    wrapper=[f'move #>${G.TRK_BUF:x},r0',f'move y:>${POINTER:x},r1',
             'do #$20,${capture_end:x}','move y:(r0)+,a','move a,y:(r1)+',
             ('label','capture_end'),f'move r1,y:>${POINTER:x}',
             f'move y:>${COUNT:x},a','add #>$1,a',f'move a1,y:>${COUNT:x}',
             f'cmp #>${blocks:x},a',('jcc','ge',STOP)]
    if switch:
        switch_block,new_source=switch
        wrapper += [f'cmp #>${switch_block:x},a',('jcc','ne','no_switch'),
                    'move #>$7,a',f'move a1,y:>${G.PAR0:x}',('label','no_switch')]
    if stock_changes and stock_snapshot is None:raise ValueError('stock changes require an initial snapshot')
    for index,(block,snapshot) in enumerate(stock_changes):
        if not 0<block<blocks:raise ValueError('stock change outside render')
        wrapper += [f'cmp #>${block:x},a',('jcc','ne',f'stock_change_{index}')]
        for offset,value in enumerate(stock_controls.words(snapshot,len(source))):
            wrapper += [f'move #>${value:x},x0',f'move x0,y:>${stock_controls.CONTROL+offset:x}']
        wrapper += [f'move #>${int(snapshot["start"]>snapshot["end"]):x},x0',f'move x0,y:>${stock_controls.REVERSE:x}']
        wrapper += [('label',f'stock_change_{index}')]
    for index,(block,field,word) in enumerate(field_changes):
        wrapper += [f'cmp #>${block:x},a',('jcc','ne',f'field_change_{index}'),
                    f'move #>${word:x},x0',f'move x0,x:>${G.GB+field:x}',('label',f'field_change_{index}')]
    wrapper += [('jmp',labels['gr'])]
    harness,_=core0.asm_at(wrapper,G.MIX)
    control=[0]*16
    values={**G.DEFAULTS,**settings,'trk':1,'gate':0}
    level,flags,timing=values.pop('level',0),values.pop('flags',0),values.pop('timing',0)
    for name,value in values.items():control[G.NAMES.index(name)]=value&0xffffff
    control[1]=timing;control[13]=flags;control[14]=level
    control[G.P_KEY]=G.KEY
    pages=[((0x40+2*i)<<12)|(0x41+2*i) for i in range(2)]
    memory=[('x',G.GB,control),('x',0x3a,[32]),('y',G.PAR0,[5]),
            ('x',G.LB+G.LB_N,[0x5a1234,0x6b2345]),('x',G.SMP+4*5,[0,len(source)]),('y',G.PAGES+5*G.PSTRIDE,pages),
            ('y',COUNT,[0,CAPTURE]),('y',0xffffd0,[0])]
    if stock_snapshot is not None:
        memory += [('y',stock_controls.CONTROL,stock_controls.words(stock_snapshot,len(source)))]
        memory += [('y',stock_controls.REVERSE,[int(stock_snapshot['start']>stock_snapshot['end'])])]
    if scratch_fill is not None:memory += [('x',G.LB,[scratch_fill&0xffffff]*G.LB_N)]
    memory.extend(('y',0x40000+i,source[i:i+64]) for i in range(0,len(source),64))
    if switch:
        other=switch[1]
        assert len(other)%4096==0 and 256<=len(other)<=SOURCE_WORDS
        memory += [('x',G.SMP+4*7,[0,len(other)]),
                   ('y',G.PAGES+7*G.PSTRIDE,[((0x50+2*i)<<12)|(0x51+2*i) for i in range((len(other)+8191)//8192)])]
        memory.extend(('y',0x50000+i,other[i:i+64]) for i in range(0,len(other),64))
    dumps=[('y',CAPTURE,blocks*32),('y',COUNT,2),('x',G.LB+G.LB_N,2)]
    if bind_sources:dumps += [('y',binding.META,binding.WORDS),('x',G.GR0,G.GW*G.MAXG)]
    result,ran=rhdspemu.run(0,pc=labels['gr'],stop=STOP,
                          segs=[('p',G.CODE,words),('p',G.MIX,harness)],mem=memory,
                          dumps=dumps,maxins=120_000_000)
    assert result[('y',COUNT)]==[blocks,CAPTURE+blocks*32],ran
    assert result[('x',G.LB+G.LB_N)]==[0x5a1234,0x6b2345], 'grain copy exceeded scratch buffer'
    output=result[('y',CAPTURE)]
    assert len(output)==blocks*32 and any(output)
    details=dict(settings=values,ran=ran,renderer_words=len(words),tables=tables)
    if bind_sources:
        details['source_metadata']=result[('y',binding.META)]
        details['grain_state']=result[('x',G.GR0)]
    return output,details


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=float,default=1.5)
    args=parser.parse_args()
    directory=ROOT/'buildtmp/granular-reference';directory.mkdir(parents=True,exist_ok=True)
    source=fixture();count=round(args.seconds*RATE/32)*32
    if not 32<=count<=96000:parser.error('seconds must resolve to32..96000samples')
    reference=[(signed(source[n%len(source)])//2)&0xffffff for n in range(count)]
    report={'scope':'Unmodified Remix DSP renderer; synthetic source; no new stock-control integration; not firmware',
            'sample_rate':RATE,'gain':'fixed Q23-to-PCM16; source half-scale matches renderer output convention',
            'source':wav(directory/'source.wav',reference)}
    for name,settings in (
        ('scan',dict(size=35,dens=28,pos=0,scan=48,spr=0,pspr=0,win=50)),
        ('cloud',dict(size=90,dens=55,pos=42,scan=0,spr=30,pspr=12,win=50))):
        output,details=render(source,args.seconds,settings)
        report[name]={**details,**wav(directory/(name+'.wav'),output)}
    (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    print(directory)


if __name__=='__main__':main()
