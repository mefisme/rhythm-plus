"""Actual ARM packet policy and DSP pitch-only Texture update, offline."""
import os
os.environ['RH_PROBES']='0'
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tests','tools','modules','remix/tools')]
from build_granular_owner import build
from emu_playfix import machine,call as native_call
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
import core0
import rhdspemu
import granular_flow_candidate as F
import granular_snapshot_candidate as S
import granular_note_candidate as N
import granular_inplace_candidate as I
from granular_route_reference import segments


def native_messages(track):
    u=machine((ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes(),
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    current=struct.unpack('<I',u.mem_read(0x080408d0,4))[0]
    u.mem_write(current,b'\xff'*16)
    events=[]
    def intercept(uc,address,size,context):
        if address==0x080406a8:
            packet=struct.unpack('<II',uc.mem_read(uc.reg_read(UC_ARM_REG_R0),8))
            events.append((packet,uc.reg_read(UC_ARM_REG_LR)&~1))
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for address in (0x080406a8,0x0803081c,0x08031228):u.hook_add(UC_HOOK_CODE,intercept,None,address,address+1)
    native_call(u,0x08040778,track,60,100)
    native_call(u,0x08040778,track,67,90)
    native_call(u,0x0804070e,track,0,57,0)
    native_call(u,0x08040814,track)
    assert len(events)==5 and events[1][0][1]==3
    assert events[1][1]==0x080407be
    assert events[3][1]==0x0804074a and events[3][0][1]==3
    assert events[-1][1]!=events[1][1]
    return events


def arm_policy():
    info=build();u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    u.mem_map(info['origin'],0x4000);u.mem_write(info['origin'],(ROOT/'buildtmp/granular-owner/kernel.bin').read_bytes())
    u.mem_map(0x20000000,0x10000)
    owner,packet,sp,stop=0x20000100,0x20000200,0x2000ff00,info['origin']+0x3ff0
    def writes(uc,access,address,size,value,context):
        assert packet<=address and address+size<=packet+8 or 0x2000f000<=address<0x20010000
    u.hook_add(UC_HOOK_MEM_WRITE,writes)
    def apply(words,context=0,active=1):
        u.mem_write(packet,struct.pack('<II',*words))
        for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(owner,packet,context,active)):u.reg_write(register,value)
        saved=[0x123400+k for k in range(8)]
        for k,value in enumerate(saved):u.reg_write(UC_ARM_REG_R4+k,value)
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,stop|1)
        before=bytes(u.mem_read(owner,96))
        u.emu_start(info['labels']['c_gr_owner_packet']|1,stop,count=10000)
        assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==sp
        assert [u.reg_read(UC_ARM_REG_R4+k) for k in range(8)]==saved
        assert bytes(u.mem_read(owner,96))==before
        return u.reg_read(UC_ARM_REG_R0),struct.unpack('<II',u.mem_read(packet,8))
    def source(track,resolved,active):
        before=bytes(u.mem_read(owner,96))
        for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(owner,track,resolved,active)):u.reg_write(register,value)
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,stop|1)
        u.emu_start(info['labels']['c_gr_owner_source']|1,stop,count=10000)
        assert u.reg_read(UC_ARM_REG_PC)==stop and bytes(u.mem_read(owner,96))==before
        return u.reg_read(UC_ARM_REG_R0)
    transformed=[]
    for track in range(8):
        events=native_messages(track)
        for mode,phase,flags in ((0,0,0),(1,0,0),(2,1,0),(2,0,2),(2,0,0),(2,0,1)):
            u.mem_write(owner+12*track,struct.pack('<IIBBBB',7,0,mode,mode,phase,flags))
            flow=(mode==2 and not phase and not flags&2)
            for index,(words,caller) in enumerate(events):
                context={0x080407be:1,0x0804074a:3}.get(caller,0)
                accepted,actual=apply(words,context)
                if phase and index in (0,2):assert accepted==0 and actual==words
                elif flow and index in (1,3):assert accepted==0 and actual==words
                elif flow and index in (0,2):
                    assert accepted==1 and actual==((words[0]&~0xf00000)|0xa00000,words[1])
                    if index==2 and flags==0:transformed.append(actual)
                else:assert accepted==1 and actual==words
            # First start/inactive voice needs a real native on, even in Flow.
            for context,active in ((2,1),(0,0)):
                assert apply(events[0][0],context,active)==(0 if phase else 1,events[0][0])
            ordinary=(0x800000|track<<16|track,2)
            assert apply(ordinary)[0]==(0 if mode==2 and not phase else 1)
            # Every stock knob/parameter command remains byte-for-byte intact.
            for parameter in range(128):
                words=(0xb00000|track<<16|parameter<<8|track,parameter*997)
                assert apply(words)==(1,words)
            for active in range(128):
                for resolved in (active,(active+37)%128):
                    fixed=mode!=0 and not phase and not flags&1
                    assert source(track,resolved,active)==(active if fixed else resolved)
            assert source(track,57,255)==(255 if mode!=0 and not phase and not flags&1 else 57)
    assert source(8,57,12)==57
    print('PASS actual stock ARM pre-note and sample-change chokes distinguished from explicit panic by call site; all8 tracks preserve Stop and real Texture start')
    print('PASS Flow rewrites running note-ons and suppresses only implicit choke/ordinary release; Retrigger and other modes preserve native note-ons')
    print('PASS all128 stock parameter command fixtures per track unchanged; ARM policy preserves owner state and callee-saved registers')
    print('PASS Fixed source follows frontend active sample rather than pink-step DSP selection; Sequenced preserves resolved blue/pink sources; missing active sample stays missing')
    return transformed


def dsp_updates(messages):
    segs=segments();segs,_=I.patched(segs);segs,_=S.patched(segs);segs,_=N.patched(segs);segs,meta=F.patched(segs)
    x=[0x110000+i for i in range(128)];y=[0x220000+i for i in range(128)]
    items=[('words',[0x05f420|k,0xffffff]) for k in range(8)]
    for command,value in messages:
        items += [f'move #>${command:x},y1',f'move #>${value&0xffffff:x},y0',('jsr',meta['labels']['flow'])]
    items += [('jmp',0x7ff0)]
    wrapper,_=core0.asm_at(items,0x7000)
    result,_=rhdspemu.run(1,pc=0x7000,stop=0x7ff0,segs=segs+[('p',0x7000,wrapper)],
        mem=[('x',0x40,x),('y',0x40,y),('y',N.SERIAL,[0]*8)],
        dumps=[('x',0x40,128),('y',0x40,128),('y',N.SERIAL,8)],maxins=100000)
    expected=list(y)
    for word,value in messages:expected[(word&7)*16+2]=value&0xffffff
    assert result[('x',0x40)]==x and result[('y',0x40)]==expected
    assert result[('y',N.SERIAL)]==[0]*8
    print(f'PASS actual DSP Flow body changes only native pitch-note field; envelope/source/filter state and accepted-trigger serial untouched; {meta["body_words"]} body words')
    import granular_route_candidate as R
    for enabled,mode in ((True,R.TEXTURE),(False,R.TEXTURE),(True,R.TRIGGERED)):
        controls=sum(([R.KEY if enabled else 0,7,11,mode] for _ in range(8)),[])
        packets=sum(([word,value&0xffffff] for word,value in messages),[])+[0xc00000,0]
        wrapper,_=core0.asm_at([('jsr',0x4cd)]*9+[('jmp',0x7ff0)],0x7000)
        dispatched,_=rhdspemu.run(1,pc=0x7000,stop=0x7ff0,segs=segs+[('p',0x7000,wrapper)],
            mem=[('x',0x40,x),('y',0x40,y),('y',N.SERIAL,[0]*8),('y',R.CONTROL,controls),
                 ('y',0x30410,packets),('y',0x307b5,[9,0])],
            dumps=[('x',0x40,128),('y',0x40,128),('y',N.SERIAL,8),('y',0x307b6,1)],maxins=100000)
        assert dispatched[('x',0x40)]==x
        assert dispatched[('y',0x40)]==(expected if enabled and mode==R.TEXTURE else y)
        assert dispatched[('y',N.SERIAL)]==[0]*8 and dispatched[('y',0x307b6)]==[9]
    print(f'PASS actual native command queue dispatches A0 only for enabled Texture tracks; disabled/Triggered tracks discard it; unknown commands still drain; total{meta["words"]} program words')


def main():
    dsp_updates(arm_policy())
    from granular_lifetime_reference import run
    import granular_route_candidate as R
    base=run(candidate=True,engine_mode=R.TEXTURE,frames=90)
    for note in (48,67,84):
        flow=run(candidate=True,engine_mode=R.TEXTURE,frames=90,note_at=35,note=note,flow=True)
        retrigger=run(candidate=True,engine_mode=R.TEXTURE,frames=90,note_at=35,note=note)
        assert flow['trace']==base['trace']
        assert retrigger['trace']!=base['trace']
        assert flow['voice_y'][:3]==retrigger['voice_y'][:3]
        assert flow['voice_y'][2]==((note-60)<<16)&0xffffff
        assert flow['voice_y'][0]!=base['voice_y'][0]
    print('PASS actual native Texture playback: Flow preserves envelope-stage/gain/reader trace while native pitch refresh follows lower/higher notes; Retrigger restarts envelope')
    print('LIMIT: offline native dispatcher candidate; ARM transport hooks, coherent live activity read and hardware timing not installed or proved')


if __name__=='__main__':main()
