"""Actual AD007 command dispatch and fixed-bank kernel; DSP/SPI transport mocked."""
import os
from pathlib import Path
import struct
import sys
os.environ['RH_AUTOPROT']='1'
os.environ['RH_AUTOBANK']='1'
import emu_tmenu as E
import rdiag as R
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.arm_const import *


def main():
    _,fw,ram=(Path(p).read_bytes() for p in sys.argv[1:4])
    u=E.setup(fw,ram)
    rep=E.MAN['report']['autobank']
    C={k:int(v,16) for k,v in rep['config'].items()}
    rd={k:int(v,16) for k,v in E.MAN['report']['rdiag']['labels'].items()}
    ap=E.MAN['report']['autoprot'];ap_labels={k:int(v,16) for k,v in ap['labels'].items()}
    ap_config={k:int(v,16) for k,v in ap['config'].items()}
    memory={address:0 for address in range(0x2400,0x4400)}
    for address in range(0x4000,0x40c0):memory[address]=(address*17)&16383
    prototype={a:v for a,v in memory.items() if 0x4000<=a<0x40c0}
    replies=[];io=[];locked=[False];stream=[0];race=[False];cycles=[0xfffffff0];scope=[0];deliver=[]

    def w(address,value):u.mem_write(address,struct.pack('<I',value))
    def word(address):return E.u32(u,address)
    def ret(value=0):
        u.reg_write(UC_ARM_REG_R0,value)
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,address,size,data):
        x,y,z=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
        if address==0x08029c8c:
            assert x==0x20003688 and not locked[0];locked[0]=True
            if race[0]:uc.mem_write(C['UPLOAD_ADDR'],b'\x01')
            ret()
        elif address==0x08030eb8:
            assert word(x)==0x20003688 and locked[0];locked[0]=False;ret()
        elif address==0x08031268:
            assert locked[0] and x==0 and y in memory
            io.append(('r',y));ret(memory[y]<<8)
        elif address==0x080311da:
            assert locked[0] and x==0 and z in memory
            assert (scope[0] in (47,52)) if 0x4000<=z<0x40c0 else (scope[0] in (42,44,45))
            assert y&255==0;memory[z]=y>>8;io.append(('w',z));ret()
        elif address==0x08046510:
            assert locked[0]
            if x==0x80:stream[0]=(y<<8)|z;ret()
            else:
                assert x==0x40 and stream[0] in memory
                value=memory[stream[0]];io.append(('r',stream[0]));stream[0]+=1;ret(value<<8)
        elif address in (0x08046414,0x08046534,0x08031020,0x08031048,0x0803107a,0x08031032):
            assert locked[0];ret()
        elif address==R.ROUTER:
            buffer,length=struct.unpack('<II',uc.mem_read(z,8))
            replies.append(bytes(uc.mem_read(buffer,length)));ret()
        elif address==ap_config['SP_WRITE']:
            deliver.append((x,y));ret()

    for address in (0x08029c8c,0x08030eb8,0x08031268,0x080311da,0x08046510,
                    0x08046414,0x08046534,0x08031020,0x08031048,0x0803107a,0x08031032,R.ROUTER,ap_config['SP_WRITE']):
        u.hook_add(UC_HOOK_CODE,hook,None,address,address+1)
    def tick(uc,access,address,size,value,data):
        if word(0xe0001000)&1:
            cycles[0]=(cycles[0]+100)&0xffffffff;w(0xe0001004,cycles[0])
    u.hook_add(UC_HOOK_MEM_READ,tick,None,0xe0001004,0xe0001007)

    def transport(value):w(E.ptr(u,0x200122b0,0),value)
    def ready():
        u.mem_write(C['READY_ADDR'],bytes([C['READY_VALUE']]))
        u.mem_write(C['WAIT_ADDR'],b'\xc8');u.mem_write(C['UPLOAD_ADDR'],b'\0')
        w(0xe000ef90,0x73);w(0xe000ed08,0x08010000);w(0xe000ed94,0)
    def request(command,key=0x41424b31,chunk=0,length=R.PAD,extra=()):
        scope[0]=command
        io.clear();replies.clear()
        packet=bytearray(R.PAD);packet[:4]=bytes(R.SIG);packet[4]=command;packet[5]=19;packet[-1]=247
        for offset,value in ((6,key),(14,chunk)):
            packet[offset:offset+8]=bytes((value>>shift)&15 for shift in range(28,-1,-4))
        for i,value in enumerate(extra):
            packet[22+8*i:30+8*i]=bytes((value>>shift)&15 for shift in range(28,-1,-4))
        msg=0x2004d000;u.mem_write(msg,bytes(packet));u.mem_write(msg-16,struct.pack('<II',msg,length))
        E.call(u,rd['c_rdin'],0,msg-16,0)
        assert not locked[0]
        if not replies:return None
        b=replies[-1];assert b[:6]==bytes(R.SIG)+bytes([command|64,19]) and b[-1]==247
        return [sum(b[i+j]<<(28-4*j) for j in range(8)) for i in range(6,len(b)-1,8)]

    ready();transport(0)
    record=word(0x2003c0cc);saved=bytes(u.mem_read(record,0x29484))
    ap_state=bytes(u.mem_read(0x100,452))
    u.mem_write(0x300,b'\xcc'*532);w(0x2fc,0x11223344);w(0x514,0x55667788)
    assert request(40)[0:3]==[0,0xad000007,0] and not io
    assert bytes(u.mem_read(0x300,532))==b'\xcc'*532
    assert request(41,key=0)==[1] and not io
    assert request(41,length=16) is None and not io
    transport(1);assert request(41)==[2] and not io;transport(0)
    u.mem_write(C['UPLOAD_ADDR'],b'\x01');assert request(41)==[3] and not io;ready()
    w(0xe000ed94,1);assert request(41)==[4] and not io;ready()
    assert request(41)==[0] and not io
    assert request(41)==[12] and not io
    assert request(40)[16]==532
    E.check('bank initializes only with explicit key, stopped/ready/ITCM guards; status and repeated init preserve history',True)

    for chunk in (-1 & 0xffffffff,256,0x80000000):
        assert request(42,chunk=chunk)==[5] and not io
    for chunk in range(224,230):
        assert request(42,chunk=chunk)==[9] and not io
    memory[0x241f]=0x123456
    assert request(42)==[8] and not any(op=='w' for op,a in io)
    assert memory[0x241f]==0x123456
    memory[0x241f]=0
    assert request(43)==[10] and not io
    E.check('invalid/excluded chunks rejected; occupied chunk preflights fully before any write',True)

    for chunk in range(256):
        if chunk in range(224,230):continue
        assert request(42,chunk=chunk)==[0]
        assert sum(op=='w' for op,a in io)==32
    assert request(40)[15]==250
    assert all(value==(0x5a7000^address) for address,value in memory.items()
               if not 0x4000<=address<0x40c0)
    assert {a:memory[a] for a in prototype}==prototype
    E.check('all 8,000 candidate words fill; 192 prototype words and its ARM cache remain untouched',bytes(u.mem_read(0x100,452))==ap_state)

    transport(1)
    for chunk in range(256):
        if chunk not in range(224,230):assert request(43,chunk=chunk)==[0]
    assert request(42)==[2] and not io
    assert request(44)==[2] and not io
    assert request(45)==[2] and not io
    before=memory.copy();assert request(46)==[0] and memory==before
    assert len(io)==32 and all(op=='r' for op,a in io)
    E.check('playing checks and consecutive-read timing perform no DSP writes; mutations require stopped transport',True)
    transport(0)

    w(0xe000edfc,0x20);w(0xe0001000,0x100);w(0xe0001fb4,3)
    assert request(45)==[0]
    assert memory==before
    assert sum(op=='r' for op,a in io)==64 and sum(op=='w' for op,a in io)==64
    status=request(40)
    assert all(status[i]>0 for i in (10,11,12,13,14))
    assert word(0xe000edfc)==0x20 and word(0xe0001000)==0x100 and word(0xe0001fb0)==0
    E.check('actual ARM codec / 24-bit SPI roundtrip restores canaries and trace controls; synthetic counters handle wrap',True)

    race[0]=True;assert request(42,chunk=1)==[3] and not io;race[0]=False;ready()
    memory[0x242f]=0xabcdef
    assert request(43,chunk=1)==[8]
    assert request(42,chunk=1)==[8] and not any(op=='w' for op,a in io)
    assert request(44,chunk=1)==[8] and not any(op=='w' for op,a in io)
    assert memory[0x242f]==0xabcdef
    E.check('upload race and later interference never repair or overwrite unexpected contents',True)
    memory[0x242f]=0x5a7000^0x242f  # Reset injected fixture corruption for cleanup check.
    for chunk in range(256):
        if chunk not in range(224,230):assert request(44,chunk=chunk)==[0]
    assert request(40)[15]==0
    assert all(value==0 for address,value in memory.items() if not 0x4000<=address<0x40c0)
    assert {a:memory[a] for a in prototype}==prototype
    assert request(53)[1]==0xad000006
    assert request(9)==[0xffffffff] and not io
    assert word(0x2fc)==0x11223344 and word(0x514)==0x55667788
    assert bytes(u.mem_read(record,0x29484))==saved
    E.check('cleanup bounded; old prototype dispatch preserved; stock project and ITCM boundary guards unchanged',True)

    # Restore is a separate explicitly armed, stopped, Record-off operation.
    assert request(47,extra=[1,8193])==[7] and not io
    w(E.ptr(u,0x200122b0,1),0);w(E.ptr(u,0x200122b0,2),0)
    # Fresh boot/flash starts prototype backing empty; arm must not silently
    # claim the occupied fixture used above to test bank exclusion.
    for address in prototype:memory[address]=0
    assert request(52,key=0x41505431)==[0]
    before=memory.copy()
    for offset,count in ((192,1),(191,2),(0,25),(0,0),(0xffffffff,1)):
        assert request(47,chunk=offset,extra=[count])==[5] and not io and memory==before
    assert request(47,extra=[24,*([0]*23),65536])==[5] and not io
    w(E.ptr(u,0x200122b0,1),1)
    assert request(47,extra=[1,8193])==[2] and not io
    w(E.ptr(u,0x200122b0,1),0)
    restored=[65535 if i%7==0 else (i*79)&16383 for i in range(192)]
    restored[0]=8193;restored[-1]=0
    for offset in range(0,192,24):
        assert request(47,chunk=offset,extra=[24,*restored[offset:offset+24]])==[0]
        assert all(0x4000<=address<0x40c0 for op,address in io)
    assert [memory[0x4000+i] for i in range(192)]==restored
    assert struct.unpack('<192H',u.mem_read(0x128,384))==tuple(restored)
    w(E.ptr(u,word(0x200470d4+0x10),1),3);transport(1)
    deliver.clear();E.call(u,ap_labels['c_applay'],0x200470d4,0,0,0)
    assert deliver[-1]==(192,ap_config['PITCH_AMOUNT_Y'])
    transport(0)
    memory[0x4000]=17
    assert request(47,extra=[1,8193])==[8] and not any(op=='w' for op,a in io)
    assert memory[0x4000]==17
    assert bytes(u.mem_read(record,0x29484))==saved
    E.check('archived locks restore exactly, apply on first Play, and reject bad bounds/values/Record state/backing mismatch',True)
    print('ALL PASS' if not E.FAILS else f'{len(E.FAILS)} FAILED')
    if E.FAILS:raise SystemExit(1)


if __name__=='__main__':main()
