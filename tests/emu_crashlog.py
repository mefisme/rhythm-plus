"""Crash recorder: reset, timer sample and fault paths on the built image."""
from pathlib import Path
import json
import struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]
BASE=0x08010000
STACK=0x2004e000
RCC_CSR=0x40023874
FAULT=0xe000ed28


def machine(image):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    u.mem_map(BASE&~0xfff,0x80000);u.mem_write(BASE,image)
    u.mem_map(0x20000000,0x50000)
    u.mem_map(0x40023000,0x1000);u.mem_map(0xe000e000,0x1000)
    return u


def run(u,start,stop,lr=0,r12=0):
    u.reg_write(UC_ARM_REG_SP,STACK);u.reg_write(UC_ARM_REG_LR,lr);u.reg_write(UC_ARM_REG_R12,r12)
    hit=[]
    handle=u.hook_add(UC_HOOK_CODE,lambda uc,address,size,data:(hit.append(address),uc.emu_stop()) if address==stop else None)
    u.emu_start(start|1,0xffffffff,count=2000)
    u.hook_del(handle)
    assert hit==[stop],(hex(start),[hex(x) for x in hit],hex(u.reg_read(UC_ARM_REG_PC)))


def main():
    folder=ROOT/'buildtmp/granular-stage'
    image=(folder/'image.bin').read_bytes();full=json.loads((folder/'manifest.json').read_text())['report'];report=full['crashlog']
    stock=Path(r'D:/GitHub/CIRCUIT-REMIX/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes()
    vector=lambda data,index:struct.unpack_from('<I',data,4*index)[0]
    at=int(report['at'],16);labels={k:int(v,16) for k,v in report['labels'].items()}
    for index,name in ((1,'c_clreset'),(3,'c_clf3'),(4,'c_clf4'),(5,'c_clf5'),(6,'c_clf6'),(15,'c_cltick')):
        assert vector(image,index)==labels[name]|1,name
    assert at+report['size']<=int(full['rhstate']['block'],16)
    u=machine(image)
    rec=lambda boot:at+16+boot*report['record_bytes']
    words=lambda address,n:list(struct.unpack(f'<{n}I',bytes(u.mem_read(address,4*n))))

    u.mem_write(at,b'\xa5'*report['size']);u.mem_write(RCC_CSR,struct.pack('<I',0x24000003))
    run(u,labels['c_clreset'],vector(stock,1)&~1)
    head=words(at,3)
    assert head[0]==0x314c5243 and head[1]==1 and head[2]==1,head
    r=words(rec(1),28)
    assert r[0]==0x24000003 and not any(r[1:]),r
    assert words(RCC_CSR,1)[0]==0x25000003
    print('PASS reset: wipes garbage, stores the reset cause, clears the flags, goes on to stock')

    u.mem_write(STACK,struct.pack('<8I',1,2,3,4,5,0x08031234,0x08040000,0x21000000))
    for tick in range(1,65):
        u.reg_write(UC_ARM_REG_LR,0xfffffff9)
        run(u,labels['c_cltick'],vector(stock,15)&~1,lr=0xfffffff9)
    r=words(rec(1),28)
    assert r[1]==64 and r[10]==1 and r[14]==0x08040000 and r[15]==0x08031234,r
    assert u.reg_read(UC_ARM_REG_LR)==0xfffffff9
    print('PASS timer: counts ticks, keeps one PC and LR each 64 ticks, restores the return value')

    u.mem_write(FAULT,struct.pack('<5I',0x8200,0x40000000,0,0x11112222,0x33334444))
    run(u,labels['c_clf3'],vector(stock,3)&~1,lr=0xfffffff9)
    r=words(rec(1),28)
    assert r[3]==0x08040000 and r[4]==0x08031234 and r[5]==0x21000000 and r[6]==0x8200 and r[7]==0x40000000,r
    assert r[8]==0x33334444 and r[9]==0x11112222 and r[11]==STACK,r
    assert u.reg_read(UC_ARM_REG_LR)==0xfffffff9
    print('PASS fault: keeps PC, LR, xPSR, fault registers and the stack pointer, then runs the stock handler')

    run(u,labels['c_clreset'],vector(stock,1)&~1)
    assert words(at,2)[1]==2 and words(rec(1),28)[6]==0x8200
    for boot in range(7):run(u,labels['c_clreset'],vector(stock,1)&~1)
    assert words(at,3)[1]==1 and words(at,3)[2]==9
    print('PASS boots: earlier records stay, and the eight records wrap')
    print('crashlog: ALL PASS')


if __name__=='__main__':main()
