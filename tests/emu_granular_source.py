"""Stock step-source and note context proof for granular integration, RAM-only.

Runs original sample resolver/microstep/step dispatch from stock5706 and A0121.
Only parameter-store lookup and sample/note output boundaries are mocked. No new
firmware hook, DSP engine, SD write or unit connection is installed by this test.
"""
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from emu_playfix import machine,STACK,SENT
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *


def verify(firmware):
    u=machine(firmware,(ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    player,patterns,vt=0x20001000,0x20010000,0x20002000
    sink,context,selected,rate,seq,zero=0x20003000,0x20003100,0x20003200,0x20003300,0x20003400,0x20003500
    sample_out,note_out=0x08000180,0x08000190
    events=[];active=[0];current_rate=[3];position=[0,0,0]
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def ret(v=0):
        u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,a,n,d):
        x,y,z,q=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        if a==0x0803fc58:
            if x==selected:w(selected+16,active[0]);ret(selected+16)
            elif x==rate:w(rate+16,current_rate[0]);ret(rate+16)
            elif x==seq:w(seq+16+4*y,position[y]);ret(seq+16+4*y)
            elif x==zero:ret(zero+16+4*y)
            else:raise AssertionError(('unexpected store',hex(x),y))
        elif a==sample_out:events.append(('sample',y,z));ret()
        elif a==0x0804b0d4:
            tie=struct.unpack('<I',bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_SP),4)))[0]
            events.append(('note',y,z,q,tie));ret(q)
        elif a==0x08055324:events.append(('automation',)) # Execute the original zero-lane player.
        elif a in (0x0804b19e,0x0804b1e4):ret()
    for a in (0x0803fc58,sample_out,0x0804b0d4,0x08055324,0x0804b19e,0x0804b1e4):
        u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
    u.mem_write(player,b'\0'*0x190);u.mem_write(player+0xab,b'\xff'*128)
    w(player,vt);w(vt+8,0x0804afbd);w(vt+16,0x0804b061)
    w(player+8,seq);w(player+0x10,rate)
    for off in (0xc,0x30,0x34,0x38):w(player+off,zero)
    w(player+0x50,patterns);w(player+0x58,sink);w(player+0x5c,context);w(player+0x60,selected)
    w(sink,vt+32);w(vt+32,sample_out|1)
    u.mem_write(player+0x8a,b'\xff')
    def call(fn,*args):
        sp=STACK+0xf0000
        for i,v in enumerate(args[:4]):u.reg_write(UC_ARM_REG_R0+i,v)
        for i,v in enumerate(args[4:]):w(sp+4*i,v)
        for i in range(8):u.reg_write(UC_ARM_REG_R4+i,0x4210+i)
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,SENT|1)
        u.emu_start(fn|1,SENT,count=100000)
        assert u.reg_read(UC_ARM_REG_PC)==SENT and u.reg_read(UC_ARM_REG_SP)==sp
        assert [u.reg_read(UC_ARM_REG_R4+i) for i in range(8)]==list(range(0x4210,0x4218))
    def step(pattern,index,source=255,mask=1,probability=7,note=60,velocity=100,gate=6,tie=0):
        u.mem_write(patterns+pattern*0xa28+index*8,bytes((note,gate,mask,velocity,probability,source,tie,0)))
    # Resolve all128 sample choices, across all track contexts, patterns and steps.
    count=0
    for track in range(8):
        u.mem_write(context+0x18,struct.pack('<H',0x10+track))
        for sample in range(128):
            pattern,index=sample%8,sample%32;active[0]=sample
            for explicit in (255,(sample+37)%128):
                step(pattern,index,explicit);events.clear();call(0x0804b060,player,pattern,index,0)
                assert events==[('sample',0x10+track,sample if explicit==255 else explicit)]
                count+=1
    for mask in range(64):
        for chance in range(8):
            for draw in range(8):
                w(player+4,draw);step(7,31,91,mask,chance)
                events.clear();call(0x0804b060,player,7,31,0)
                assert events==([('sample',0x17,91)] if mask and draw<=chance else [])
    print(f'PASS {count} source choices: blue follows active sample; pink assignment remains fixed;8track contexts')
    print('PASS all64 microstep masks x8 probability thresholds x8 draws match stock source eligibility')
    # Real microstep preparation + real per-step dispatcher: sample, automation, note.
    w(player+4,0);active[0]=12;current_rate[0]=3
    for pattern,index,source in ((0,0,255),(0,1,45),(1,0,255),(1,31,67),(0,0,255)):
        active[0]=(active[0]+7)%128;position[:]=[pattern,index,0]
        step(pattern,index,source,0b010101,note=65,velocity=93,gate=4,tie=1)
        for micro in range(6):call(0x0804aeee,player,pattern,index,micro,0)
        for pulse in range(6):
            position[2]=pulse;events.clear();call(0x0805526e,player,0,0,0)
            wanted=[]
            if pulse==0:wanted.append(('sample',0x17,active[0] if source==255 else source))
            wanted.append(('automation',))
            if pulse in (0,2,4):wanted.append(('note',65,93,4,1))
            assert events==wanted,(pattern,index,pulse,events,wanted)
    print('PASS actual dispatch: step-resolved sample precedes automation and notes; gate/velocity/tie and microsteps retained across patterns')
    # Independent skipped hits must not produce a fresh sample or note.
    for mask,chance,draw in ((0,7,0),(63,0,7)):
        w(player+4,draw);step(0,0,51,mask,chance);position[:]=[0,0,0]
        for micro in range(6):call(0x0804aeee,player,0,0,micro,0)
        events.clear();call(0x0805526e,player,0,0,0)
        assert events==[('automation',)]
    active[0]=255;step(0,0);events.clear();call(0x0804b060,player,0,0,0);assert not events
    print('PASS empty/probability-skipped steps emit no sample/note; missing active sample emits no source callback')


if __name__=='__main__':
    for path in ('remix/stock/circuitrhythm-firmware-5706-STOCK.bin','firmware/a0121/rhythmplus-A0121.bin'):
        print(path);verify((ROOT/path).read_bytes())
    print('LIMIT: synthetic stores/output sinks; granular event capture and DSP rendering not installed')
    print('ALL PASS')
