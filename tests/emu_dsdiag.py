"""Execute AD002 fixed-window host transfer diagnostics with a bounded DSP model.

Mocks hardware reads/writes and cycle counter only. ARM packing, guards, restore,
ITCM copy, actual decoder, output comparison and protocol execute from the image.
"""
from pathlib import Path
import struct
import sys
import emu_tmenu as E
import acdiag as A
import dsdiag as D
import rdiag as R
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR


def main():
    _,fw,ram=(Path(p).read_bytes() for p in sys.argv[1:4])
    u=E.setup(fw,ram);rep=E.MAN['report']['dsdiag']
    rd={k:int(v,16) for k,v in E.MAN['report']['rdiag']['labels'].items()}
    guards={k:int(v,16) for k,v in rep['guards'].items()}
    memory={base+i:0 for base in D.BANKS for i in range(D.WORDS)}
    calls=[];replies=[];locked=[False];race=[False];corrupt=[False];wrote=[False]
    consecutive=rep.get('consecutive_read',False);selected=[False];pointer=[None];streamwords=[0]
    def ret(value=0):u.reg_write(UC_ARM_REG_R0,value);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,address,size,data):
        x,y,z=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
        if address==D.LOCK:
            assert x==D.LOCK_PTR and not locked[0]
            locked[0]=True
            if race[0]:uc.mem_write(guards['upload'],b'\x01')
            ret()
        elif address==D.UNLOCK:
            assert E.u32(uc,x)==D.LOCK_PTR and locked[0]
            locked[0]=False;ret()
        elif address==D.RD16:
            assert locked[0] and x==0 and y in memory,(x,hex(y))
            calls.append(('read',y));word=memory[y]
            if corrupt[0] and wrote[0]:word^=1
            ret(word<<8)
        elif address==D.WR16:
            assert locked[0] and x==0 and z in memory and y&255==0,(x,hex(z),y)
            calls.append(('write',z));memory[z]=(y>>8)&0xffffff;wrote[0]=True;ret()
        elif consecutive and address in (0x08046414,0x08046534,0x08031020,0x08031032):
            assert locked[0]
            if address==0x08031032:assert not selected[0]
            ret()
        elif consecutive and address==0x08031048:
            assert locked[0] and x==0 and not selected[0]
            selected[0]=True;pointer[0]=None;streamwords[0]=0;ret()
        elif consecutive and address==0x0803107A:
            assert selected[0] and pointer[0] in memory and streamwords[0]>0
            selected[0]=False;ret()
        elif consecutive and address==0x08046510:
            assert locked[0] and selected[0]
            if x==0x80:
                pointer[0]=(y<<8)|z
                assert pointer[0] in memory
                ret()
            else:
                assert (x,y,z)==(0x40,0,0) and pointer[0] in memory
                word=memory[pointer[0]];calls.append(('read',pointer[0]))
                if corrupt[0] and wrote[0]:word^=1
                pointer[0]+=1;streamwords[0]+=1
                assert pointer[0] in memory  # last command may prefetch next cell
                ret(word<<8)
        elif address==R.ROUTER:
            ptr=uc.reg_read(UC_ARM_REG_R2);buf,n=struct.unpack('<II',uc.mem_read(ptr,8))
            replies.append(bytes(uc.mem_read(buf,n)));ret()
    for address in (D.LOCK,D.UNLOCK,D.RD16,D.WR16,R.ROUTER):u.hook_add(UC_HOOK_CODE,hook,None,address,address+1)
    if consecutive:
        for address in (0x08046414,0x08046534,0x08031020,0x08031032,0x08031048,0x0803107A,0x08046510):
            u.hook_add(UC_HOOK_CODE,hook,None,address,address+1)
    cyc=[0]
    def tick(uc,access,address,size,value,data):
        cyc[0]+=100;uc.mem_write(A.CYCCNT,struct.pack('<I',cyc[0]))
    u.hook_add(UC_HOOK_MEM_READ,tick,None,A.CYCCNT,A.CYCCNT+3)
    def w(address,value):u.mem_write(address,struct.pack('<I',value))
    def reset_guards():
        w(guards['magic_addr'],guards['magic'])
        u.mem_write(guards['ready_addr'],bytes([guards['ready']]))
        u.mem_write(guards['wait_addr'],b'\xc8');u.mem_write(guards['upload'],b'\0')
        w(A.ITCMCR,0x73);w(A.VTOR,0x08010000);w(A.MPUCTRL,0)
        w(A.DWTCTRL,0x100);w(A.DEMCR,0x20);w(A.LSR,3)
    reset_guards()
    msg=0x2004d000
    def nibbles(v):return bytes((v>>shift)&15 for shift in range(28,-1,-4))
    def number(b):
        v=0
        for x in b:v=(v<<4)|x
        return v
    def request(cmd,*args,length=R.PAD):
        replies.clear();calls.clear();wrote[0]=False
        b=bytearray(R.PAD);b[:4]=bytes(R.SIG);b[4]=cmd;b[5]=12;b[-1]=0xf7
        for i,arg in enumerate(args):b[6+8*i:14+8*i]=nibbles(arg)
        u.mem_write(msg,bytes(b));u.mem_write(msg-16,struct.pack('<II',msg,length))
        E.call(u,rd['c_rdin'],0,msg-16,0)
        assert not locked[0] and not selected[0]
        if not replies:return None
        r=replies[-1];assert r[:6]==bytes(R.SIG)+bytes([cmd|0x40,12]) and r[-1]==0xf7
        return [number(r[i:i+8]) for i in range(6,len(r)-1,8)]
    record=E.u32(u,0x2003c0cc);project=bytes(u.mem_read(record,0x29484))
    E.check('status describes only fixed windows; no DSP reads/writes',request(40)==[0,int(rep['format'],16),*D.BANKS,D.WORDS,D.CHUNK,D.INPUT,D.INPUT_END,0] and not calls)
    for cmd in (41,42,43):E.check('write/read test commands require separate key',request(cmd,A.KEY,0,0)==[1] and not calls)
    for bank in (2,255,0xffffffff):E.check('invalid bank rejected',request(41,D.KEY,bank,0)==[5] and not calls)
    for chunk in (8,255,0xffffffff):E.check('invalid chunk rejected',request(41,D.KEY,0,chunk)==[5] and not calls)
    for f in (6,255,0xffffffff):E.check('invalid ROM fixture rejected',request(43,D.KEY,0,f)==[5] and not calls)
    for address,value,status in ((guards['magic_addr'],0,7),(guards['ready_addr'],0,8),(guards['wait_addr'],199,8),(guards['upload'],1,9)):
        if address==guards['magic_addr']:w(address,value)
        else:u.mem_write(address,bytes([value]))
        E.check('startup/upload guard rejects before any DSP I/O',request(41,D.KEY,0,0)==[status] and not calls)
        reset_guards()
    race[0]=True
    E.check('upload starts while waiting for lock: guarded AFTER acquisition',request(41,D.KEY,0,0)==[9] and not calls)
    race[0]=False;reset_guards()
    memory[D.BANKS[0]+7]=0x123456
    E.check('fill preflight refuses occupied nonzero RAM before writing',request(41,D.KEY,0,0)==[11] and not any(c[0]=='write' for c in calls))
    memory[D.BANKS[0]+7]=0
    for bank,base in enumerate(D.BANKS):
        for chunk in range(8):
            start=base+chunk*D.CHUNK
            assert request(41,D.KEY,bank,chunk)==[0,start,D.CHUNK,0,0,0]
            assert request(42,D.KEY,bank,chunk)==[0,start,D.CHUNK,0,0,0]
        assert all(memory[base+i]==D.PATTERN^(base+i) for i in range(256))
    E.check('all X/Y chunks fill and check with no access outside fixed windows',True)
    memory[D.BANKS[1]+40]^=0x80
    E.check('check reports first mismatched address/value and does not repair',request(42,D.KEY,1,1)==[0,D.BANKS[1]+32,32,1,D.BANKS[1]+40,memory[D.BANKS[1]+40]])
    memory[D.BANKS[1]+40]^=0x80
    E.check('AD001 canary unarmed: transfer rejected before DSP I/O',request(43,D.KEY,0,0)==[13] and not calls)
    assert request(33,A.KEY)==[0,4032]
    w(D.INPUT,0x12345678)
    E.check('input-window damage not concealed by transfer',request(43,D.KEY,0,1)==[14] and not calls)
    E.check('preflight failure restores trace control',E.u32(u,A.DWTCTRL)==0x100 and E.u32(u,A.DEMCR)==0x20)
    assert request(33,A.KEY)==[0,4032]
    memory[D.BANKS[0]]^=1
    E.check('transfer refuses changed DSP canary without writes',request(43,D.KEY,0,1)==[12] and not any(c[0]=='write' for c in calls))
    E.check('changed-DSP refusal restores trace control',E.u32(u,A.DWTCTRL)==0x100 and E.u32(u,A.DEMCR)==0x20)
    memory[D.BANKS[0]]^=1
    for bank,base in enumerate(D.BANKS):
        for index,fixture in enumerate(E.MAN['report']['acdiag']['fixtures']):
            before=memory.copy();result=request(43,D.KEY,bank,index)
            n=fixture['compressed_bytes'];words=(n+2)//3
            assert result==[0,base,index,n,words,100,100,100,0,0,0,500],result
            assert memory==before
            assert E.u32(u,A.DWTCTRL)==0x100 and E.u32(u,A.DEMCR)==0x20
            assert E.u32(u,D.WRITE_PTR)==0xffff
            assert request(34,A.KEY)==[0,0,E.MAN['report']['acdiag']['canary_words'],0,0]
    E.check('all fixtures x X/Y: exact three-byte packing, read/copy/decode, DSP and ITCM restoration',True)
    corrupt[0]=True
    result=request(43,D.KEY,0,3)
    E.check('corrupt DSP read data is detected',result[8]>0 and (result[9]>0 or result[10]!=0))
    corrupt[0]=False
    assert request(34,A.KEY)==[0,0,E.MAN['report']['acdiag']['canary_words'],0,0]
    for cmd in (6,9,36,39,44,253):E.check('unrelated disabled/unknown commands remain disabled',request(cmd)==[0xffffffff])
    E.check('short packet produces no access/reply',request(41,D.KEY,0,0,length=16) is None and not calls)
    E.check('entire stock project record byte-identical',bytes(u.mem_read(record,0x29484))==project)
    print('ALL PASS' if not E.FAILS else f'{len(E.FAILS)} FAILED')
    if E.FAILS:raise SystemExit(1)

if __name__=='__main__':main()
