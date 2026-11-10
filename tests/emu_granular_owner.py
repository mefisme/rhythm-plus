"""Actual Cortex-M7 granular mode owner and stock native start/stop actions."""
import os
os.environ['RH_PROBES']='0'
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
from build_granular_owner import build
from emu_playfix import machine,STACK,SENT,call as native_call
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *


def main():
    info=build()
    image=(ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes()
    ram=(ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes()
    u=machine(image,ram)
    u.mem_write(info['origin'],(ROOT/'buildtmp/granular-owner/kernel.bin').read_bytes())
    owner=0x20001000;size=96;bounds=[False];messages=[]
    read32=lambda address:struct.unpack('<I',u.mem_read(address,4))[0]
    current,parameters=read32(0x080408d0),read32(0x080408d4)
    def observe(uc,access,address,count,value,context):
        if not bounds[0]:return
        assert (owner<=address and address+count<=owner+size) or STACK<=address<STACK+0x100000,(hex(address),count)
    u.hook_add(UC_HOOK_MEM_WRITE,observe)
    def intercept(uc,address,count,context):
        if address==0x080406a8:messages.append(struct.unpack('<II',uc.mem_read(uc.reg_read(UC_ARM_REG_R0),8)))
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for address in (0x080406a8,0x0803081c):u.hook_add(UC_HOOK_CODE,intercept,None,address,address+1)
    def call(name,*args):
        sp=STACK+0xf0000
        for i,arg in enumerate(args[:4]):u.reg_write(UC_ARM_REG_R0+i,arg)
        for i,arg in enumerate(args[4:]):u.mem_write(sp+4*i,struct.pack('<I',arg))
        saved=[0x123400+i for i in range(8)]
        for i,value in enumerate(saved):u.reg_write(UC_ARM_REG_R4+i,value)
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,SENT|1)
        bounds[0]=True
        try:u.emu_start(info['labels']['c_gr_owner_'+name]|1,SENT,count=100000)
        finally:bounds[0]=False
        assert u.reg_read(UC_ARM_REG_PC)==SENT and u.reg_read(UC_ARM_REG_SP)==sp
        assert [u.reg_read(UC_ARM_REG_R4+i) for i in range(8)]==saved
        return u.reg_read(UC_ARM_REG_R0)
    assert call('size')==size
    call('init',owner)
    # A missing DSP reply must not silence stock after cancelling a start.
    packet=owner+0x200
    u.mem_write(packet,struct.pack('<II',0x900000,0))
    assert call('request',owner,0,1,0)==3
    assert call('packet',owner,packet,0,0)==0
    assert call('request',owner,0,0,0)==0
    assert call('packet',owner,packet,0,0)==1
    call('init',owner)
    for track in range(8):
        before=bytes(u.mem_read(owner,size));base=owner+track*12
        assert call('request',owner,track,2,77)==3
        epoch=call('epoch',owner,track)
        assert epoch==2 and call('mode',owner,track)==0
        after=bytes(u.mem_read(owner,size));assert after[:track*12]==before[:track*12] and after[(track+1)*12:]==before[(track+1)*12:]
        native_call(u,0x08040814,track)
        assert messages[-1]==(0x800000|(track<<16)|track,3)
        assert call('observe',owner,track,epoch-1,epoch,0,77)==0
        assert call('observe',owner,track,epoch,epoch-1,0,77)==0
        assert call('observe',owner,track,epoch,epoch,1,77)==0
        assert call('observe',owner,track,epoch,epoch,0,77)==12
        assert call('mode',owner,track)==2
        # Caller applies the route before the returned one-time START action.
        count=sum(word&0xf00000==0x900000 for word,value in messages)
        native_call(u,0x08040778,track,60,127)
        assert sum(word&0xf00000==0x900000 for word,value in messages)==count+1
        assert call('observe',owner,track,epoch,epoch,0,77)==0
        assert call('request',owner,track,2,77)==0
        u.mem_write(parameters+16*track+1,b'\x01')
        native_call(u,0x0804083c,track,60,0,0)
        word,value=messages[-1];assert value==2
        assert call('forward',owner,word,value)==0
        native_call(u,0x08040814,track)
        word,value=messages[-1];assert value==3 and call('forward',owner,word,value)==1
        assert call('observe',owner,track,epoch,epoch,0,77)==0
    print('PASS actual ARM owner: all8 tracks independent; generation invalidation and both DSP ACKs precede activation; Texture starts once')
    print('PASS stock native start/stop commands exercised; Texture ignores ordinary accepted releases while forced stop/panic pass; no automatic restart after force stop')
    # A newer note can precede our queued stop: it cannot prove stop completion.
    assert call('request',owner,0,1,77)==3
    epoch=call('epoch',owner,0)
    assert call('observe',owner,0,epoch,epoch,1,78)==0
    pending_packet=owner+0x200
    u.mem_write(pending_packet,struct.pack('<II',0x900000,0))
    assert call('packet',owner,pending_packet,0,1)==0
    assert call('observe',owner,0,epoch,epoch,0,78)==4
    assert call('mode',owner,0)==1
    # Rapid UI changes coalesce to the last mode without phantom Texture starts.
    assert call('request',owner,1,0,20)==3
    assert call('request',owner,1,2,20)==0
    assert call('request',owner,1,1,20)==0
    epoch=call('epoch',owner,1)
    assert call('observe',owner,1,epoch,epoch,0,20)==4 and call('mode',owner,1)==1
    assert call('forward',owner,0x800001,2)==1
    before=bytes(u.mem_read(owner,size))
    assert call('request',owner,8,2,0)==0 and call('request',owner,0,3,0)==0
    assert bytes(u.mem_read(owner,size))==before
    # Epoch is24-bit; zero is skipped on wrap.
    u.mem_write(owner+7*12,struct.pack('<I',0xffffff))
    assert call('request',owner,7,0,0)==3 and call('epoch',owner,7)==1
    print('PASS newer notes cannot bypass a pending force stop; incoming starts wait for actual idle; rapid requests coalesce and24-bit epoch wrap skips zero')
    assert call('quiesce',owner)==255
    assert call('held',owner)==0 and call('resume',owner)==0
    packet=owner+0x200
    for track in range(8):
        epoch=call('epoch',owner,track)
        assert call('request',owner,track,2,0)==0
        for command,value,accepted in ((0x900000,0,0),(0xa00000,0,0),(0x800000,3,1),(0xb00000,42,1)):
            words=(command|track<<16|track,value)
            u.mem_write(packet,struct.pack('<II',*words))
            assert call('packet',owner,packet,0,1)==accepted
            assert struct.unpack('<II',u.mem_read(packet,8))==words
        # A newer legitimate note is allowed through an ordinary mode barrier,
        # but must never authorize sample memory replacement while still active.
        assert call('observe',owner,track,epoch,epoch,1,999)==0
        assert call('observe',owner,track,epoch-1,epoch,0,999)==0
        assert call('observe',owner,track,epoch,epoch,0,999)==4
        assert call('mode',owner,track)==0
        assert call('observe',owner,track,epoch,epoch,0,999)==0
        u.mem_write(packet,struct.pack('<II',0x900000|track,0))
        assert call('packet',owner,packet,2,0)==0  # START also blocked while held.
        if track<7:
            before=bytes(u.mem_read(owner,size))
            assert call('resume',owner)==0 and bytes(u.mem_read(owner,size))==before
    assert call('held',owner)==1 and call('resume',owner)==1
    assert call('held',owner)==0 and call('packet',owner,packet,0,0)==1
    print('PASS project/pack replacement requires all8 idle DSP acknowledgements; newer notes cannot bypass it; notes stay blocked until explicit resume')
    print('PASS partial replacement barrier cannot resume; explicit Stop and parameter packets remain available; resume leaves engines Off')
    print(f'PASS kernel{info["bytes"]} bytes, owner state{size} bytes, no BSS; RAM bounds and callee-saved registers verified')
    print('LIMIT: action/ACK interface is emulated; no production mode UI, DSP acknowledgement writer or pack-lifecycle hook installed')
    print('ALL PASS')


if __name__=='__main__':main()
