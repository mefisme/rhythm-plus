"""Execute A0050's real remote dispatcher and guard in Unicorn, stubbing hardware only."""
from pathlib import Path
import struct
import sys
import emu_tmenu as E
import rdiag as R
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R4,
                               UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_PC,UC_ARM_REG_LR)


def nibbles(v,n=8):return bytes((v>>(4*(n-1-i)))&15 for i in range(n))
def number(b):
    v=0
    for x in b:v=v*16+x
    return v


def main():
    stock,fw,ram=(Path(p).read_bytes() for p in sys.argv[1:4])
    u=E.setup(fw,ram);reads=[];replies=[];locks=[];forbidden=[]
    L={k:int(v,16) for k,v in E.MAN['report']['rdiag']['labels'].items()}
    ready=int(E.MAN['report']['cthresh']['slot'],16)+1
    wait=E.rhstate.ST+E.rhstate.OFF['spwait'][0]
    def ret(u,value=0):u.reg_write(UC_ARM_REG_R0,value);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def rd(u,a,n,d):
        c=u.reg_read(UC_ARM_REG_R0);addr=u.reg_read(UC_ARM_REG_R1)
        reads.append((c,addr))
        if a==R.DSP_READ:u.mem_write(R.DSP_WADDR,struct.pack('<I',0xffff))
        ret(u,((0xabcdef ^ addr ^ c)&0xffffff)<<8)
    def router(u,a,n,d):
        p=u.reg_read(UC_ARM_REG_R2);buf,sz=struct.unpack('<II',u.mem_read(p,8))
        replies.append(bytes(u.mem_read(buf,sz)));ret(u)
    def lock(u,a,n,d):locks.append(a);ret(u)
    def bad(u,a,n,d):forbidden.append(a);ret(u)
    for a in (R.DSP_RD16,R.DSP_READ):u.hook_add(UC_HOOK_CODE,rd,None,a,a+1)
    for a in (R.DSP_LOCK,R.DSP_UNLOCK):u.hook_add(UC_HOOK_CODE,lock,None,a,a+1)
    for a in (R.DSP_WR16,R.DSP_WRITE,R.WRITE):u.hook_add(UC_HOOK_CODE,bad,None,a,a+1)
    u.hook_add(UC_HOOK_CODE,router,None,R.ROUTER,R.ROUTER+1)
    msg=0x2004d000
    def request(cmd=3,core=0,addr=0x9400,count=1,length=R.PAD):
        reads.clear();replies.clear();locks.clear();forbidden.clear()
        b=bytearray(R.PAD);b[:4]=bytes(R.SIG);b[4]=cmd;b[5]=7
        b[6]=core;b[7:15]=nibbles(addr);b[15]=count;b[-1]=0xf7
        u.mem_write(msg,bytes(b));u.mem_write(msg-16,struct.pack('<II',msg,length))
        E.call(u,L['c_rdin'],0,msg-16,0)
        if not replies:return None,b''
        reply=replies[-1]
        return number(reply[6:14]),reply[14:-1]
    u.mem_write(ready,bytes([E.TH.READY]));u.mem_write(wait,bytes([200]))
    for core,addr,count in ((0,0,1),(0,0x5fff,1),(0,0x8000,1),(0,0xbfff,1),
                            (1,0x2fff,1),(1,0x9fff,1),(0,0x30000,1),(1,0x37fff,1),
                            (0,0x9400,24),(1,0x96e0,3),(1,0x9400,25)):
        st,payload=request(core=core,addr=addr,count=count)
        expected=min(count,24)
        words=[number(payload[i:i+6]) for i in range(0,len(payload),6)]
        E.check(f'allowed core {core} address {addr:x}, count {count}',st==0 and reads==[(core,addr+i) for i in range(expected)]
                and words==[(0xabcdef^(addr+i)^core)&0xffffff for i in range(expected)])
        E.check('host pointer invalidated; read locks balanced',E.u32(u,R.DSP_WADDR)==0xffff and locks.count(R.DSP_LOCK)==locks.count(R.DSP_UNLOCK))
    for core,addr,count in ((2,0x9400,1),(0,0x6000,1),(0,0xc000,1),(1,0x3000,1),(1,0xa000,1),
                            (0,0x5fff,2),(0,0xbfff,2),(1,0x2fff,2),(1,0x9fff,2),
                            (0,0x37fff,2),(0,0x38000,1),(0,0xffff84,1),(0,0xfffffff8,24),
                            (0,0x9400,0),(0,0x10000,1),(0,0x2ffff,1)):
        st,_=request(core=core,addr=addr,count=count)
        E.check(f'reject unmapped/cross-bank core {core}, {addr:x}, count {count}',st==1 and not reads and not forbidden)
    for flag in (0,E.TH.BLOCKED):
        u.mem_write(ready,bytes([flag]));st,_=request()
        E.check('no DSP access before ready / in alternate DSP mode',st==1 and not reads)
    u.mem_write(ready,bytes([E.TH.READY]));u.mem_write(wait,bytes([199]));st,_=request()
    E.check('startup settling guard',st==1 and not reads)
    u.mem_write(wait,bytes([200]));u.mem_write(E.rhstate.ST,b'\0'*4);st,_=request()
    E.check('invalid private RAM magic blocks DSP reads',st==1 and not reads)
    u.mem_write(E.rhstate.ST,struct.pack('<I',E.rhstate.MAGIC))
    for cmd in (6,9,253,254):
        st,_=request(cmd=cmd)
        E.check(f'write command {cmd} disabled',st==0xffffffff and not reads and not forbidden)
    st,p=request(cmd=1)
    E.check('ping remains available',st==0x5213)
    st,_=request(length=16)
    E.check('short request produces no access or reply',st is None and not reads)
    print('ALL PASS' if not E.FAILS else f'{len(E.FAILS)} FAILED')
    if E.FAILS:raise SystemExit(1)


if __name__=='__main__':main()
