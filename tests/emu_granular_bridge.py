"""Actual staging ARM hooks with native note queue, sample setter and resolver."""
import os
os.environ['RH_PROBES']='0'
from pathlib import Path
import json
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tests','modules','tools','remix/tools')]
from emu_playfix import machine,call
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from thumb import Asm,mov_reg,movs_imm,b_w
import cthresh


def main():
    folder=ROOT/'buildtmp/granular-stage';report=json.loads((folder/'manifest.json').read_text())['report']
    image=(folder/'image.bin').read_bytes()
    u=machine(image,(ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    bridge=report['granular']['bridge'];kernel=report['granular']['arm_kernel']['labels']
    slot=int(bridge['slot'],16);previous=int(bridge['previous_frame'],16)
    read32=lambda address:struct.unpack('<I',u.mem_read(address,4))[0]
    def w(address,value):u.mem_write(address,struct.pack('<I',value))
    dsp={};writes=[];reads=[]
    shared_read=kernel['c_gr_shared_read'];dsp_write=kernel['c_gr_dsp_write']
    def boundary(uc,address,size,context):
        if address==dsp_write:
            target=uc.reg_read(UC_ARM_REG_R0);value=uc.reg_read(UC_ARM_REG_R1)
            writes.append((target,value));dsp[target]=value
        elif address in (0x08031200,0x08031228):
            target=uc.reg_read(UC_ARM_REG_R2);value=uc.reg_read(UC_ARM_REG_R1)>>8
            writes.append((target,value));dsp[target]=value
        elif address==shared_read:
            target=uc.reg_read(UC_ARM_REG_R0);reads.append(target)
            uc.reg_write(UC_ARM_REG_R0,dsp.get(target,0))
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for address in (0x08031200,0x08031228,shared_read,dsp_write,0x0803081c,previous):u.hook_add(UC_HOOK_CODE,boundary,None,address,address+1)
    def invoke(label,*args):
        address=kernel['c_gr_'+label] if not label.startswith('c_g') else int(bridge['labels'][label],16)
        call(u,address,*args);return u.reg_read(UC_ARM_REG_R0)
    assert invoke('c_gstate')==slot
    u.mem_write(int(bridge['ready'],16),bytes((cthresh.READY,)))
    u.mem_write(int(bridge['wait'],16),b'\xc8')
    u.mem_write(int(bridge['upload'],16),b'\0')
    invoke('c_gframe',0x200487c8,0x20003000)
    assert not writes and not reads
    current=read32(0x080408d0);u.mem_write(current,b'\xff'*16)
    call(u,0x08040778,0,60,100)
    assert any(value==0x906400 for address,value in writes if 0x30410<=address<0x30430)
    assert invoke('runtime_mode',slot,0,2)==1
    dsp[0x37420]=0x674732
    for _ in range(19):invoke('c_gframe',0x200487c8,0x20003000)
    invoke('c_gframe',0x200487c8,0x20003000)
    epoch=dsp[0x37401]
    dsp.update({0x37420:0x674732,0x37421:epoch,0x37422:123,0x37427:9})
    # Native active sample getter boundary: other native store methods still run.
    selected=0x20003200;selected_value=0x20003300;u.mem_write(selected_value,b'\x0c')
    real_store=read32(0x200470d4+0x60)
    def getter(uc,address,size,context):
        if uc.reg_read(UC_ARM_REG_R0) in (selected,real_store) and uc.reg_read(UC_ARM_REG_R1)==0:
            uc.reg_write(UC_ARM_REG_R0,selected_value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,getter,None,0x0803fc58,0x0803fc59)
    invoke('c_gframe',0x200487c8,0x20003000)
    assert dsp[0x37400]==0x674e31
    dsp[0x37420]=0x674331
    before=len(writes);call(u,0x08040778,0,67,90)
    commands=[value for address,value in writes[before:] if 0x30410<=address<0x30430]
    assert 0xa05a00 in commands and 0x905a00 not in commands and 0x800000 not in commands,commands
    # Synthetic resolver object; its native virtual callback tail-calls the real
    # sample setter, including native current-note bookkeeping and command path.
    player,patterns,sink,vt,context=0x20008000,0x20010000,0x20003400,0x20003500,0x20003600
    u.mem_write(player,bytes(0x190));u.mem_write(patterns,bytes(0xa28))
    w(player+0x50,patterns);w(player+0x58,sink);w(player+0x5c,context);w(player+0x60,selected)
    w(sink,vt);w(vt,0x08000181);u.mem_write(context+0x18,b'\x10\0')
    a=Asm(0x08000180);a.emit(mov_reg,0,1);a.emit(movs_imm,1,0);a.emit(b_w,0x0804070e)
    callback,_=a.assemble();u.mem_write(0x08000180,callback)
    u.mem_write(patterns,bytes((60,6,1,100,7,57,0,0)))
    before=len(writes);call(u,0x0804b060,player,0,0,0)
    assert dsp[0x307c8]==57
    assert all(value!=0x800000 for address,value in writes[before:] if 0x30410<=address<0x30430)
    assert invoke('runtime_source',slot,0,57)==57  # Scope restored after callback.
    u.mem_write(patterns+5,b'\xff');call(u,0x0804b060,player,0,0,0);assert dsp[0x307c8]==12
    before=len(reads);u.mem_write(int(bridge['upload'],16),b'\x01')
    old=len(writes);call(u,0x08040778,0,69,80)
    assert len(reads)==before
    assert not any(value&0xf00000 in (0x900000,0xa00000) for address,value in writes[old:] if 0x30410<=address<0x30430)
    u.mem_write(int(bridge['upload'],16),b'\0')
    before=len(writes);call(u,0x08040814,0)
    assert any(value==0x800000 for address,value in writes[before:] if 0x30410<=address<0x30430)
    call(u,0x0804070e,0,0,255,0)
    assert dsp[0x307c8]==255  # Unscoped stock "no sample" must not be swallowed.
    call(u,0x0804070e,0,7,127,0);assert dsp[0x307cf]==127
    print('PASS actual staging frame and message hooks run compiled runtime with original native note bookkeeping/queue; Flow reaches A0 without implicit stops')
    print('PASS actual resolver -> virtual sink -> sample setter: grains follow pink and blue steps, source choke is suppressed and scope restores')
    print('PASS upload guard prevents custom DSP reads and note starts; explicit native Stop still queues; private slot uses existing heap reservation')
    print('LIMIT: locked DSP accessors and selected-sample getter are fixture boundaries; physical UI, project/pack wrappers and hardware timing remain')


if __name__=='__main__':main()
