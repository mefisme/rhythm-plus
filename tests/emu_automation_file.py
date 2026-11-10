"""Execute stock file wrappers with RAM-only FatFs fault injection.

No disk I/O: confirms exact flags, offsets, short transfer and sync behavior.
"""
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/part) for part in ("tests","modules","builds","remix/tools")]
from emu_playfix import machine,STACK,SENT
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *


def main():
    fw=(ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes()
    ram=(ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes()
    u=machine(fw,ram)
    obj,fil,buffer,path,out=0x20001000,0x20002000,0x20004000,0x20005000,0x20005100
    calls=[];fault={'open':0,'seek':0,'read':0,'write':0,'sync':0,'close':0,'short':None}
    content=bytearray(bytes(range(128))*4)
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def ret(v=0):u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,a,n,d):
        x,y,z,q=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        if a==0x08023690:ret();return
        if a==0x08021d90:
            calls.append(('open',z));w(fil+0x14,0);ret(fault['open']);return
        if a==0x080223d8:
            calls.append(('seek',y))
            if not fault['seek']:w(fil+0x14,y)
            ret(fault['seek']);return
        if a in (0x08021f72,0x080220fc):
            kind='read' if a==0x08021f72 else 'write';pos=word(fil+0x14)
            count=z if fault['short'] is None else min(z,fault['short'])
            calls.append((kind,pos,z,count));w(q,count)
            if not fault[kind]:
                if kind=='read':uc.mem_write(y,bytes(content[pos:pos+count]))
                else:content[pos:pos+count]=uc.mem_read(y,count)
                w(fil+0x14,pos+count)
            ret(fault[kind]);return
        if a==0x080222bc:calls.append(('sync',));ret(fault['sync']);return
        if a==0x08022346:calls.append(('close',));ret(fault['close']);return
    for a in (0x08023690,0x08021d90,0x080223d8,0x08021f72,0x080220fc,0x080222bc,0x08022346):
        u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
    def call(fn,*args):
        sp=STACK+0xf0000
        for i,v in enumerate(args[:4]):u.reg_write(UC_ARM_REG_R0+i,v)
        for i,v in enumerate(args[4:]):w(sp+i*4,v)
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,SENT|1)
        for i in range(8):u.reg_write(UC_ARM_REG_R4+i,0xabcd00+i)
        u.emu_start(fn|1,SENT,count=100000)
        assert u.reg_read(UC_ARM_REG_PC)==SENT and u.reg_read(UC_ARM_REG_SP)==sp
        assert [u.reg_read(UC_ARM_REG_R4+i) for i in range(8)]==list(range(0xabcd00,0xabcd08))
        return u.reg_read(UC_ARM_REG_R0)
    w(obj,0x080685b0);w(obj+8,fil);u.mem_write(obj+12,b'\0');u.mem_write(path,b'1:/Rhythm/30_PACK/RP_AUTO/example.rpa\0')
    assert call(0x0802df1c,obj,path)==0 and calls[-1]==('open',0x13)
    assert u.mem_read(obj+12,1)==b'\x01'
    assert call(0x0802dfb0,obj,buffer,16,7,out)==0 and word(out)==16
    assert bytes(u.mem_read(buffer,16))==bytes(content[7:23])
    fault['short']=3
    assert call(0x0802dfb0,obj,buffer,16,0,out)==0 and word(out)==3
    print('PASS stock open uses mode13; reads report exact transferred bytes including short success')
    fault['short']=None;fault['seek']=1;w(fil+0x14,0);calls.clear()
    assert call(0x0802dfb0,obj,buffer,4,20,out)==0
    assert ('seek',20) in calls and ('read',0,4,4) in calls
    print('PASS observed stock read wrapper ignores seek failure and continues at old position')
    fault['seek']=0;fault['sync']=1
    assert call(0x0802e098,obj)==1
    fault['sync']=0;assert call(0x0802e098,obj)==0
    fault['close']=1;assert call(0x0802df74,obj)==0
    assert u.mem_read(obj+12,1)==b'\0'
    print('PASS sync failure is visible; stock close wrapper ignores close failure')
    print('LIMIT: raw FatFs calls intercepted; no real SD card or durable flush tested')
    print('ALL PASS')


if __name__=='__main__':main()
