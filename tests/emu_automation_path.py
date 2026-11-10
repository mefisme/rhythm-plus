"""Stock absolute pack paths and raw exclusive-create branch, without disk I/O."""
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from emu_playfix import machine,STACK,SENT
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *


def main():
    u=machine((ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes(),
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    out,fil,path,fs=0x20005000,0x20006000,0x20007000,0x20008000
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def call(fn,*args):
        for i,v in enumerate(args):u.reg_write(UC_ARM_REG_R0+i,v)
        u.reg_write(UC_ARM_REG_SP,STACK+0xf0000);u.reg_write(UC_ARM_REG_LR,SENT|1)
        u.emu_start(fn|1,SENT,count=100000)
        assert u.reg_read(UC_ARM_REG_PC)==SENT
        assert u.reg_read(UC_ARM_REG_SP)==STACK+0xf0000
        return u.reg_read(UC_ARM_REG_R0)
    def string(a):return bytes(u.mem_read(a,256)).split(b'\0')[0]
    pack=0x2000e98c
    call(0x08045844,pack,out,0,0)
    assert string(out)==b'1:/Rhythm/30_PACK'
    # Exercise real parent traversal with a new, unindexed child node in RAM.
    node=0x20004000;u.mem_write(node,b'\0'*64)
    u.mem_write(node+1,b'RP_AUTO\0');w(node+0x24,pack)
    call(0x08045844,node,out,0,0)
    assert string(out)==b'1:/Rhythm/30_PACK/RP_AUTO'
    print('PASS real stock node traversal builds absolute pack/private-folder paths')
    scans=[]
    def skip(uc,a,n,d):
        if a==0x08045648:scans.append(uc.reg_read(UC_ARM_REG_R0))
        uc.reg_write(UC_ARM_REG_R0,0)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    hooks=[u.hook_add(UC_HOOK_CODE,skip,None,a,a+1)
           for a in (0x08045568,0x08045648)]
    call(0x0802e6f8,pack,0,0,0)
    expected=list(struct.unpack('<5I',bytes(u.mem_read(pack+0x28,20))))
    assert scans==expected and node not in scans
    names=[string(address+1) for address in scans]
    assert names==[b'Sessions',b'Patches',b'PCM',b'meta',b'GridFx'],names
    for handle in hooks:u.hook_del(handle)
    print('PASS stock pack indexing submits exactly five known collections; no private sibling scan')
    exists=[True];creates=[]
    def ret(value):
        u.reg_write(UC_ARM_REG_R0,value)
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,a,n,d):
        x,y=uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)
        if a==0x08021a4c: # Mount resolution only, never enters disk driver.
            w(y,fs);ret(0)
        elif a==0x0802166c: # Synthetic lookup result; actual open branch runs.
            uc.mem_write(x,b'\0'*48);w(x,fs)
            ret(0 if exists[0] else 4)
        elif a==0x08021178:
            creates.append(x);ret(1) # Abort creation before any media mutation.
    for a in (0x08021a4c,0x0802166c,0x08021178):
        u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
    u.mem_write(path,b'1:/Rhythm/30_PACK/RP_AUTO/token.rpa\0')
    u.mem_write(fil,b'\xa5'*64)
    assert call(0x08021d90,fil,path,7)==8 and not creates
    assert bytes(u.mem_read(fil,4))==b'\0'*4
    exists[0]=False
    assert call(0x08021d90,fil,path,3)==4 and not creates
    assert call(0x08021d90,fil,path,7)==1 and len(creates)==1
    print('PASS raw mode7 rejects existing file with result8; creates only when missing')
    print('LIMIT: collection scanner/mount/lookup/create intercepted; no real SD write or export tested')
    print('ALL PASS')


if __name__=='__main__':main()
