"""Offline stock DSP voice-control calculation, before sample-reader initialization.

Runs stock note setup (P:2FD) or round-robin control refresh (P:289), stopping
before downstream reader state changes. Synthetic descriptors/parameters only;
no device memory allocation or firmware hook.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','remix/tools')]
import rpasm
rpasm.use()
import core0
import rhdspemu

VOICE,PARAM,SAMPLE=0x40,0x307c8,0x30000
CAPTURE,WRAPPER,STOP=0x1f00,0x7000,0x7ff0


def controls(*,track=0,sample=5,start=0,length=127,tune=64,note=60,
             sample_start=0,sample_length=16384,fine_start=0,fine_length=0,
             reverse=False,refresh=False,program=None,extra_memory=()):
    if program is not None and refresh:
        raise ValueError('custom program reference supports trigger-region calculation only; refresh would bypass its pitch hook')
    if not 0<=track<8 or not 0<=sample<128:raise ValueError('invalid track/sample')
    if not 0<=note<111:raise ValueError('note outside stock ARM note-on range')
    if any(not 0<=v<=127 for v in (start,length,tune,fine_start,fine_length)):
        raise ValueError('invalid control')
    if not 0<=sample_start<0x400000 or not 1<=sample_length<=0x400000-sample_start:
        raise ValueError('invalid source descriptor')
    voice_address,parameter_address=VOICE+track*16,PARAM+track*32
    parameters=[0]*32
    parameters[0]=sample;parameters[2]=int(reverse)
    parameters[6:9]=[tune,start,length]
    parameters[14:16]=[fine_start,fine_length]
    parameters[25]=int(reverse)
    # Save the arguments that stock passes to its reader initialization / ratio routine.
    capture,_=core0.asm_at(['move x0,y:>$1f00','move x1,y:>$1f01',
                           'move y0,y:>$1f02','move r4,y:>$1f03',
                           'move r5,y:>$1f04',('jsr',0x1c3),('jmp',STOP)],WRAPPER)
    entry,exit_address=(0x289,0x2d8) if refresh else (0x2fd,0x15a)
    redirect,_=core0.asm_at([('jmp',WRAPPER)],exit_address)
    prelude=[('words',[0x05f420+k,0xffffff]) for k in range(8)]
    # Stock ARM note-on 08040778: command, parameter track, velocity, voice; note relative to60.
    prelude += [f'move #>${0x900000|(track<<16)|(100<<8)|track:x},y1',f'move #>${((note-60)<<16)&0xffffff:x},y0',('jmp',entry)]
    setup,_=core0.asm_at(prelude,0x7100)
    voice=[0]*16;voice[5]=parameter_address
    memory=[('x',voice_address,voice),('y',parameter_address,parameters),
            ('y',voice_address,[0,0,((note-60)<<16)&0xffffff]),('y',0x121,[(track-1)&7]),
            ('x',SAMPLE+sample*4,[sample_start,sample_length,sample_start+sample_length,0])]
    memory += list(extra_memory)
    result,ran=rhdspemu.run(1,pc=0x7100,stop=STOP,
        segs=(rhdspemu.segments(1) if program is None else program)+[('p',exit_address,redirect),('p',WRAPPER,capture),('p',0x7100,setup)],
        mem=memory,dumps=[('y',CAPTURE,5),('y',voice_address,16)],maxins=10000)
    assert ran and 'pc=007ff0' in ran.lower(),ran
    end,begin,ratio_input,r4,r5=result[('y',CAPTURE)]
    state=result[('y',voice_address)]
    if refresh:begin,end=state[4],state[3]
    return dict(start=begin,end=end,length=abs(end-begin),ratio_input=ratio_input,
                increment=state[0],polyphase=state[1],voice=r4,parameters=r5,ran=ran)


if __name__=='__main__':
    for knobs in ({},{'start':64},{'length':32},{'tune':76},{'note':72},{'reverse':True}):
        print(knobs,controls(**knobs))
