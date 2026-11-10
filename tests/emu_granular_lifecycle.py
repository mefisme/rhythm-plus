"""Actual staging lifecycle wrappers: nested upload, project load and abort."""
import os
os.environ['RH_PROBES']='0'
from pathlib import Path
import json
import struct
import sys
import zlib
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tests','tools','modules','remix/tools')]
from emu_playfix import machine,call
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from thumb import Asm,bl,movs_imm,push_list,pop_list
import cthresh


def main():
    folder=ROOT/'buildtmp/granular-stage';report=json.loads((folder/'manifest.json').read_text())['report']
    u=machine((folder/'image.bin').read_bytes(),(ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    bridge=report['granular']['bridge'];life=report['granular']['lifecycle'];kernel=report['granular']['arm_kernel']['labels']
    state=int(bridge['slot'],16);tail=0x20003000;dsp={};writes=[];reads=[];stops=[];uploads=[];pack_calls=[];apply_calls=[];sleeps=[];auto_ack=[True]
    def r32(address):return struct.unpack('<I',u.mem_read(address,4))[0]
    def held():return all(u.mem_read(state+12*t+10,1)[0] in (3,5) for t in range(8))
    direct={int(life['labels'][name+'_native'],16):name for name in ('free','reset','record')}
    direct_calls=[]
    allocator_wait=[0]
    shared_read=kernel['c_gr_shared_read'];dsp_write=kernel['c_gr_dsp_write']
    sample_read=kernel['c_gr_sample_read']
    def snapshot(track,epoch,active=False):
        values=[0x674331 if active else 0x674732,epoch,100+len(sleeps),12+track,0,16384,0x8000,9]
        dsp.update((0x37420+track*8+i,value) for i,value in enumerate(values))
    data=b'GR\x02\x08'+bytes((i*13+7)%128 for i in range(64))+bytes((18,0,0,0,0,0,0,0))
    data+=struct.pack('<I',zlib.crc32(data))
    encoded=bytearray(b'\x55'*884)
    offsets=list(range(296,328))+list(range(404,420))+list(range(520,530))+list(range(860,882))
    for offset,value in zip(offsets,data):encoded[offset]=value
    pack_native=int(life['labels']['pack_native'],16);apply_native=int(life['labels']['apply_native'],16)
    a=Asm(0x08000180);a.emit(push_list,[4],lr=True)
    for sample in (5,6):a.emit(movs_imm,0,sample);a.emit(bl,int(life['labels']['c_glupload'],16))
    a.emit(movs_imm,0,1);a.emit(pop_list,[4],pc=True)
    stub,_=a.assemble();u.mem_write(0x08000180,stub)
    def hook(uc,address,size,context):
        args=[uc.reg_read(UC_ARM_REG_R0+k) for k in range(3)]
        if address==dsp_write:
            dsp[args[0]]=args[1];writes.append((args[0],args[1]))
        elif address in (0x08031200,0x08031228):
            dsp[args[2]]=args[1]>>8;writes.append((args[2],args[1]>>8))
        elif address in (shared_read,sample_read):
            reads.append(args[0]);uc.reg_write(UC_ARM_REG_R0,dsp.get(args[0],0))
        elif address==0x080314d6:
            reads.append(args[1]);uc.reg_write(UC_ARM_REG_R0,(dsp.get(args[1],0)<<8)&0xffffffff)
        elif address==0x08040814:stops.append(args[0])
        elif address==0x08024150:
            sleeps.append(1)
            if allocator_wait[0]:
                assert held() and r32(state+208)==1
                allocator_wait[0]-=1
                if not allocator_wait[0]:dsp[0x372fb]=dsp[0x372fc]=0
            if auto_ack[0]:
                for track in range(8):snapshot(track,dsp[0x37401+4*track])
        elif address==0x0803fc58:
            uc.reg_write(UC_ARM_REG_R0,0x20002000)
        elif address in (0x08040778,0x0804070e):pass
        elif address==int(report['rhrec']['labels']['c_rrt'],16):uc.reg_write(UC_ARM_REG_R0,tail)
        elif address==pack_native:
            assert held() and r32(state+208)==1 and all(dsp[0x37400+4*t]==0 for t in range(8))
            pack_calls.append(1);uc.reg_write(UC_ARM_REG_PC,0x08000181);return
        elif address==0x08053e8c:
            assert held() and r32(state+208)==2
            assert u.mem_read(int(bridge['upload'],16),1)==b'\x01'
            uploads.append((args[0],len(reads)));uc.reg_write(UC_ARM_REG_R0,1234+args[0])
        elif address==apply_native:
            assert held() and r32(state+208)==1
            apply_calls.append(1);u.mem_write(tail,bytes(encoded));uc.reg_write(UC_ARM_REG_R0,42)
        elif address in direct:
            name=direct[address]
            depth=r32(state+208)
            direct_calls.append((name,args[1],depth))
            if depth:
                assert held() and depth==1
                dsp[0x372fb if name=='record' else 0x372fc]=1
                allocator_wait[0]=2
            uc.reg_write(UC_ARM_REG_R0,73)
        else:raise AssertionError(hex(address))
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    boundaries=(0x08031200,0x08031228,shared_read,dsp_write,sample_read,0x080314d6,0x08040814,0x08024150,0x0803fc58,0x08040778,0x0804070e,
                int(report['rhrec']['labels']['c_rrt'],16),pack_native,apply_native,0x08053e8c,*direct)
    for address in boundaries:u.hook_add(UC_HOOK_CODE,hook,None,address,address+1)
    call(u,int(bridge['labels']['c_gstate'],16));call(u,kernel['c_gr_runtime_init'],state)
    u.mem_write(int(bridge['ready'],16),bytes((cthresh.READY,)));u.mem_write(int(bridge['wait'],16),b'\xc8')
    u.mem_write(int(bridge['upload'],16),b'\0');u.mem_write(0x20002000,b'\x0c')
    call(u,kernel['c_gr_runtime_mode'],state,0,2)
    snapshot(0,1)
    for _ in range(19):call(u,kernel['c_gr_runtime_frame'],state,1,0)
    call(u,kernel['c_gr_runtime_frame'],state,1,0);snapshot(0,dsp[0x37401]);call(u,kernel['c_gr_runtime_frame'],state,1,0)
    snapshot(0,dsp[0x37401],True)
    record=int(life['record'],16)
    before=len(stops)
    call(u,record,0,128)
    call(u,record,0,5)
    assert direct_calls==[('record',128,0),('record',5,0)] and len(stops)==before
    assert dsp[0x37400]!=0
    before=len(stops);call(u,0x08053e24)
    assert u.reg_read(UC_ARM_REG_R0)==1 and len(stops)-before==1
    assert pack_calls==[1] and [sample for sample,count in uploads]==[5,6]
    assert uploads[0][1]==uploads[1][1] and r32(state+208)==0
    assert u.mem_read(int(bridge['upload'],16),1)==b'\0'
    call(u,0x080378c6,0x2003c380,2,3,4)
    assert u.reg_read(UC_ARM_REG_R0)==42 and apply_calls==[1]
    assert bytes(u.mem_read(state+104,64))==data[4:68]
    assert bytes(u.mem_read(state+168,8))==data[68:76] and bytes(u.mem_read(tail,884))==bytes(encoded)
    assert r32(state+208)==0
    # Once initialized again, simulate an unresponsive acknowledgement source.
    for _ in range(20):call(u,kernel['c_gr_runtime_frame'],state,1,0)
    snapshot(0,dsp[0x37401]);call(u,kernel['c_gr_runtime_frame'],state,1,0)
    for name in ('record','free','reset'):
        dsp[0x30001+4*5]=16384
        snapshot(0,dsp[0x37401],True)
        old=len(sleeps)
        call(u,int(life[name],16),0,5)
        assert direct_calls[-1]==(name,5,1) and u.reg_read(UC_ARM_REG_R0)==73
        assert len(sleeps)>=old+2 and not allocator_wait[0] and r32(state+208)==0
        call(u,kernel['c_gr_runtime_frame'],state,1,0)
        snapshot(0,dsp[0x37401]);call(u,kernel['c_gr_runtime_frame'],state,1,0)
    snapshot(0,dsp[0x37401],True)
    auto_ack[0]=False;before=len(pack_calls);old=len(sleeps)
    call(u,0x08053e24)
    assert u.reg_read(UC_ARM_REG_R0)==0 and len(pack_calls)==before and len(sleeps)-old==100
    assert r32(state+208)==0 and all(dsp[0x37400+4*t]==0 for t in range(8))
    print('PASS actual pack wrapper holds the granular owner before allocator entry; nested uploads keep the barrier and streaming flag')
    print('PASS temporary-slot and empty-slot recording pass through; occupied record/free/reset hold through pending allocator requests')
    print('PASS actual project-apply wrapper loads saved granular parameters/page preference after native apply and preserves its return value; project bytes untouched')
    print('PASS acknowledgement timeout prevents native pack operation and returns stock failure; no stuck replacement depth or enabled granular routes')
    print('LIMIT: native allocator and locked transport boundaries are fixtures; hardware timing remains unproved')


if __name__=='__main__':main()
