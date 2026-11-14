"""ITCM file-buffer extent and candidate SRAM staging, no physical SD access."""
import struct
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tools','tests')]
from build_projectfile import build
from emu_playfix import machine,call,STACK
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *


def main():
    code,info=build()
    u=machine((ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes(),
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    u.mem_write(info['origin'],code)
    bridge,bounce,itcm,native=0x20001000,0x20002000,0x2000,0x20003000
    read,write=0x08000200,0x08000204
    u.mem_write(bridge,struct.pack('<4I',99,read|1,write|1,bounce))
    calls=[];fault=[0]
    disk=bytearray((i*11)&255 for i in range(8192))
    def ret(uc,value=0):
        uc.reg_write(UC_ARM_REG_R0,value)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    def io(uc,address,size,data):
        dev,offset,ptr,count=[uc.reg_read(UC_ARM_REG_R0+i) for i in range(4)]
        assert dev==99 and ptr>=0x20000000
        calls.append((address,offset,ptr,count))
        if fault[0] and len(calls)==fault[0]:ret(uc,7);return
        if address==read:uc.mem_write(ptr,bytes(disk[offset:offset+count]))
        else:disk[offset:offset+count]=uc.mem_read(ptr,count)
        ret(uc)
    for fn in (read,write):u.hook_add(UC_HOOK_CODE,io,None,fn,fn+1)
    def transfer(direction,offset,ptr,size):
        u.mem_write(STACK+0xf0000,struct.pack('<I',size))
        call(u,info['labels']['c_pf_dma'],bridge,direction,offset,ptr)
        return u.reg_read(UC_ARM_REG_R0)
    u.mem_write(itcm,b'\xa5'*4096)
    assert transfer(0,512,itcm,4096)==0
    assert bytes(u.mem_read(itcm,4096))==disk[512:4608]
    assert len(calls)==8 and all(c[2:]==(bounce,512) for c in calls)
    payload=bytes((i*7)&255 for i in range(4096));u.mem_write(itcm,payload)
    calls.clear();assert transfer(1,0,itcm,4096)==0
    assert disk[:4096]==payload and len(calls)==8
    print('PASS complete 4KB ITCM reads/writes use eight SRAM-only 512-byte device calls')
    calls.clear();assert transfer(0,0,native,512)==0
    assert calls==[(read,0,native,512)]
    print('PASS ordinary native buffer follows unchanged direct device call')
    for offset,ptr,size in ((0,0,512),(0,0x3f00,512),(1,itcm,512),(0,itcm,100),(0xffffff00,itcm,512)):
        calls.clear();assert transfer(0,offset,ptr,size)==1 and not calls
    print('PASS protected lower ITCM, out-of-range, unaligned and overflow requests refused')
    u.mem_write(itcm,b'\xa5'*4096);calls.clear();fault[0]=3
    assert transfer(0,0,itcm,4096)==7 and len(calls)==3
    assert bytes(u.mem_read(itcm,1024))==disk[:1024]
    assert bytes(u.mem_read(itcm+1024,3072))==b'\xa5'*3072
    print('PASS failed device transfer stops immediately without publishing failed/later chunks')

    # Run real FatFs open through its successful non-creating branch. Only mount
    # and directory lookup are synthetic; the complete FIL initialization runs.
    fil,path,fs,entry=0x400,0x20005000,0x20006000,0x20007000
    u.mem_write(fil-4,b'\x77'*4144)
    u.mem_write(path,b'1:/RP_AUTO/test.rpa\0')
    u.mem_write(fs,bytes(128));u.mem_write(fs,b'\x03')
    u.mem_write(entry,bytes(32))
    zero_calls=[]
    def open_hook(uc,address,size,data):
        r0=uc.reg_read(UC_ARM_REG_R0);r1=uc.reg_read(UC_ARM_REG_R1)
        if address==0x08021a4c:
            uc.mem_write(r1,struct.pack('<I',fs));ret(uc)
        elif address==0x0802166c:
            uc.mem_write(r0,bytes(48));uc.mem_write(r0,struct.pack('<I',fs))
            uc.mem_write(r0+0x1c,struct.pack('<I',entry));ret(uc)
        else:zero_calls.append((r0,r1))  # Execute the original memset below.
    for fn in (0x08021a4c,0x0802166c,0x08022a90):u.hook_add(UC_HOOK_CODE,open_hook,None,fn,fn+1)
    call(u,0x08021d90,fil,path,1)
    assert u.reg_read(UC_ARM_REG_R0)==0
    assert (fil+40,4096) in zero_calls,zero_calls
    assert bytes(u.mem_read(fil+40,4096))==bytes(4096)
    assert bytes(u.mem_read(fil-4,4))==b'\x77'*4
    assert bytes(u.mem_read(fil+4136,4))==b'\x77'*4
    print('PASS real native open initializes a 4136-byte FIL, including its 4096-byte internal buffer')
    print('LIMIT synthetic filesystem lookup/device I/O; ITCM ownership, DMA bus access and timing need hardware proof')
    print('ALL PASS')


if __name__=='__main__':main()
