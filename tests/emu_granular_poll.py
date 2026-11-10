"""Compiled ARM owner consumes DSP acknowledgements through a torn-read fixture."""
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_granular_owner import build
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *


def main():
    info=build();u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    u.mem_map(info['origin'],0x4000);u.mem_write(info['origin'],(ROOT/'buildtmp/granular-owner/kernel.bin').read_bytes())
    u.mem_map(0x20000000,0x10000)
    owner,sp,stop,reader=0x20000100,0x2000ff00,info['origin']+0x3ff0,info['origin']+0x1f00
    base=0x37420;packet=[0]*8;reads=[];change=[None]
    def fetch(uc,address,size,context):
        index=len(reads);address=uc.reg_read(UC_ARM_REG_R0)
        assert base<=address<base+8
        if change[0] is not None and index==change[0]:packet[2]+=1
        reads.append(address)
        uc.reg_write(UC_ARM_REG_R0,packet[address-base]);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,fetch,None,reader,reader+1)
    def writes(uc,access,address,size,value,context):
        assert owner<=address and address+size<=owner+96 or 0x2000f000<=address<0x20010000
    u.hook_add(UC_HOOK_MEM_WRITE,writes)
    def poll(track,tag,epoch=7,serial=78,mutation=None,phase=1):
        u.mem_write(owner,bytes(96));u.mem_write(owner+12*(track&7),struct.pack('<IIBBBB',7,77,0,2,phase,0))
        packet[:]=[tag,epoch,100,5,0,2048,0x8000,serial];reads.clear();change[0]=mutation
        before=bytes(u.mem_read(owner,96))
        for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(owner,track,base,reader|1)):u.reg_write(register,value)
        saved=[0x123400+k for k in range(8)]
        for k,value in enumerate(saved):u.reg_write(UC_ARM_REG_R4+k,value)
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,stop|1)
        u.emu_start(info['labels']['c_gr_owner_poll']|1,stop,count=10000)
        assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==sp
        assert [u.reg_read(UC_ARM_REG_R4+k) for k in range(8)]==saved
        result=u.reg_read(UC_ARM_REG_R0)
        if not result:assert bytes(u.mem_read(owner,96))==before
        return result
    for track in range(8):
        for tag in (0x674132,0x674331,0x674732):
            accepted=12 if tag==0x674732 else 0
            assert poll(track,tag)==accepted
            assert poll(track,tag,epoch=6)==0
            assert poll(track,tag,serial=77)==(12 if tag==0x674732 else 0)
            assert poll(track,tag,mutation=0)==accepted  # Entire new publication precedes read.
            for boundary in range(1,7):assert poll(track,tag,mutation=boundary)==0,(track,tag,boundary)
        for tag in (0,0x674e31,0x674531,0xffffff):assert poll(track,tag)==0
        assert poll(track,0x674732,phase=0)==0 and not reads
    assert poll(8,0x674732)==0 and not reads
    print('PASS compiled ARM poll accepts only both-core completion tags and current epoch; active voices cannot bypass a pending stop even with newer notes')
    print('PASS all8 tracks: publication at every intermediate host-read boundary is rejected; coherent new frame before first read is accepted')
    print('PASS incomplete/native-only/stale snapshots are inert; idle and newer-note cases complete once; ARM register and write bounds checked')
    print('LIMIT: accessor callback emulates reads; locked stock transport, startup/upload guards and live scheduling remain to be installed')


if __name__=='__main__':main()
