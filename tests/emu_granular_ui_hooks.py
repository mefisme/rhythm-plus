"""Actual staged pad/release/knob/frame/RGB wrappers and compiled page logic."""
import os
os.environ['RH_PROBES']='0'
from pathlib import Path
import json
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tests','tools','modules','remix/tools')]
from emu_playfix import machine,call
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *


def main():
    folder=ROOT/'buildtmp/granular-stage';report=json.loads((folder/'manifest.json').read_text())['report']
    u=machine((folder/'image.bin').read_bytes(),(ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    ui=report['granular']['ui'];bridge=report['granular']['bridge'];kernel=report['granular']['arm_kernel']['labels']
    slot,menu=int(bridge['slot'],16),int(ui['menu'],16)
    previous={name:int(address,16) for name,address in ui['previous'].items()}
    selected=[0];events=[];out=0x20004000
    tail=0x20003000;available=[False];tail_reads=[];save_calls=[];reset_calls=[]
    tail_getter=int(report['rhrec']['labels']['c_rrt'],16)
    reset_pages=int(report['pageclear']['labels']['c_pcreset'],16)
    save_targets=(0x080472e2,0x08047270)
    baseline=[0x123456]*69;baseline[25]=0x808080;baseline[28]=0x0a0b0c;baseline[30]=0x1f1505
    def hook(uc,address,size,context):
        args=[uc.reg_read(UC_ARM_REG_R0+k) for k in range(3)]
        for name,target in previous.items():
            if address==target:
                events.append((name,tuple(args)))
                if name=='out':uc.mem_write(args[1],struct.pack('<69I',*baseline))
                break
        if address==int(report['tmenu']['labels']['c_tmview'],16):uc.reg_write(UC_ARM_REG_R0,selected[0])
        if address==tail_getter:
            tail_reads.append(1);uc.reg_write(UC_ARM_REG_R0,tail if available[0] else 0)
        if address==reset_pages:reset_calls.append(tuple(args[:2]))
        if address in save_targets:
            assert bytes(uc.mem_read(tail+296,4))==b'GR\x02\x08'
            save_calls.append((address,tuple(args)));uc.reg_write(UC_ARM_REG_R0,73)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    targets=set(previous.values())|{int(report['tmenu']['labels'][name],16) for name in ('c_tmview','c_tmpgset','c_tmsp')}
    targets.update((tail_getter,reset_pages,*save_targets))
    for address in targets:u.hook_add(UC_HOOK_CODE,hook,None,address,address+1)
    call(u,int(bridge['labels']['c_gstate'],16))
    call(u,kernel['c_gr_runtime_init'],slot)
    u.mem_write(menu,b'\x01');u.mem_write(menu+10,b'\x01')
    u.mem_write(0x200487c8+0xa0,bytes(4))
    def tick(now):u.mem_write(0x20000820,struct.pack('<I',now))
    def event(kind,pad,value=100):
        entry={'pad':0x0803d7fe,'release':0x0803d896,'knob':0x0803dde0}[kind]
        call(u,entry,0x200487c8,pad,value)
    def invoke(name,*args):
        call(u,kernel['c_gr_'+name],*args);return u.reg_read(UC_ARM_REG_R0)
    def frame():call(u,int(ui['labels']['c_guframe'],16),0x200487c8,0x20005000)
    def draw():
        call(u,int(ui['labels']['c_guout'],16),0x200487c8,out,0x20005000)
        return list(struct.unpack('<69I',u.mem_read(out,69*4)))
    tick(1000);event('pad',29)
    assert invoke('runtime_page',slot,0)==1
    assert u.mem_read(menu+10,1)==b'\0' and u.mem_read(menu+8,1)==b'\x01'
    assert not any(name=='pad' for name,args in events)
    assert invoke('owner_mode',slot,0)==0
    event('release',29);assert not any(name=='release' for name,args in events)
    event('knob',0,7);assert invoke('params_get',slot+104,0,0)==7
    assert not any(name=='knob' for name,args in events)
    normal=draw();assert normal[29]!=baseline[29] and normal[25]==0x080808
    tick(2000);event('pad',29)
    assert u.mem_read(menu+8,1)==b'\x01'
    tick(2333);frame();assert u.mem_read(slot+96+6,1)==b'\x01'
    for pad in (17,16):event('pad',pad);event('release',pad)
    assert u.mem_read(slot+168,1)[0]&3==2 and invoke('owner_mode',slot,0)==0
    settings=draw();assert settings[23]==0
    event('release',29);assert draw()==normal
    event('pad',24);event('release',24);assert u.mem_read(menu+8,1)==b'\x02'
    # Track selection does not move engine state or another track's page.
    selected[0]=1;frame();assert invoke('runtime_page',slot,1)==0
    before=len(events);event('knob',0,5)
    assert any(name=='knob' for name,args in events[before:])
    selected[0]=0;event('pad',28)
    assert invoke('runtime_page',slot,0)==0 and u.mem_read(slot+168,1)[0]&3==2
    before=len(events);event('knob',0,5)
    assert any(name=='knob' for name,args in events[before:])
    # Reenter; Clear+page resets its knobs only, without selecting another page
    # or forwarding a reset into stock automation/sample controls.
    event('pad',29);event('release',29)
    u.mem_write(0x200487c8+0xa0,struct.pack('<I',1<<23))
    before=len(events);event('pad',29);event('release',29)
    assert invoke('params_get',slot+104,0,0)==0
    assert not any(name=='pad' for name,args in events[before:])
    event('knob',0,10);assert invoke('params_get',slot+104,0,0)==0
    invoke('runtime_put',slot,0,1,100);invoke('runtime_put',slot,0,2,99)
    u.mem_write(0x20003974+0x0e*4,struct.pack('<I',0x0000ff));u.mem_write(0x20003974+0x55*4,struct.pack('<I',0xff0000))
    before=len(events);event('knob',1,39)
    assert invoke('params_get',slot+104,0,1)==100 and u.mem_read(menu+8,1)==b'\x02'
    event('knob',1,1);assert invoke('params_get',slot+104,0,1)==64
    event('knob',2,-40);assert invoke('params_get',slot+104,0,2)==99 and u.mem_read(menu+8,1)==b'\x03'
    assert not any(name=='knob' for name,args in events[before:])
    lit=draw();level=lit[29]&255
    assert level and lit[61]==level and lit[62]==level<<16
    u.mem_write(menu+36,bytes(16))
    u.mem_write(0x200487c8+0xa0,bytes(4))
    u.mem_write(menu,b'\0')
    assert draw()==baseline
    before=len(events);event('pad',29)
    assert any(name=='pad' for name,args in events[before:])
    # Pending changes survive an unavailable record and are retried on a quiet frame.
    assert invoke('runtime_store_pending',slot)==1
    invoke('runtime_frame',slot,0,0)
    assert invoke('runtime_store_pending',slot)==1
    available[0]=True;frame()
    assert invoke('runtime_store_pending',slot)==0 and bytes(u.mem_read(tail+296,4))==b'GR\x02\x08'
    before=len(tail_reads);frame();assert len(tail_reads)==before
    for index,target in enumerate(save_targets):
        invoke('runtime_put',slot,0,0,41+index)
        call(u,int(ui['labels'][f'c_gusave{index}'],16),11,22,33)
        assert save_calls[-1]==(target,(11,22,33)) and u.reg_read(UC_ARM_REG_R0)==73
        assert u.mem_read(tail+300,1)[0]==41+index and invoke('runtime_store_pending',slot)==0
    invoke('runtime_put',slot,1,0,55)
    call(u,int(ui['labels']['c_gureset'],16),0,6)
    assert reset_calls==[(0,6)] and invoke('params_get',slot+104,0,0)==0
    assert invoke('params_get',slot+104,1,0)==55 and u.mem_read(slot+168,1)[0]&3==0
    assert u.mem_read(tail+300,1)[0]==0 and u.mem_read(tail+308,1)[0]==55
    print('PASS actual stage pad/release/knob hooks focus Granular without enabling it; short tap and held settings consume matching releases')
    print('PASS mode choice stages a barrier, release restores knob bar, knob selection cycles, and another track keeps its native controls')
    print('PASS held Clear: full right turn restores the default and lights blue; full left turn lights red and keeps the value')
    print('PASS stock page selection and closed menu delegate to prior hooks; Clear+Granular resets only granular values; RGB overlay follows output stage')
    print('PASS deferred edits retry when the tail returns; both native save routes flush before writing; confirmed reset is isolated to its target track')
    print('LIMIT: native writer, menu, frame and output boundaries are fixture spies; hardware LEDs and SD persistence are unverified')


if __name__=='__main__':main()
