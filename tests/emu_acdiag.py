"""Execute AD001's ROM decoder/diagnostic dispatcher in Unicorn (MIT).

No physical timing claim: cycle counter is mocked; decoded output, bounds,
canary guards, ABI, protocol and restored trace control are checked for real.
"""
from pathlib import Path
import random
import struct
import sys
import emu_tmenu as ET
import acdiag as A
import rdiag as R
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R2


def main():
    _, fw, ram = (Path(p).read_bytes() for p in sys.argv[1:4])
    u = ET.setup(fw, ram)
    rep = ET.MAN['report']['acdiag']
    labels = {k: int(v,16) for k,v in rep['labels'].items()}
    rd = {k: int(v,16) for k,v in ET.MAN['report']['rdiag']['labels'].items()}
    src, dst = 0x20058000, A.OUTPUT
    active = [False]; bounds = [0]; bad = []; insns = [0]; max_insns = [0]

    def monitor(uc, access, address, size, value, data):
        if not active[0]: return
        if access == 16:  # UC_MEM_READ
            if 0x20000000 <= address < 0x20060000 and not (src <= address and address+size <= src+bounds[0]):
                bad.append(('read', address,size))
        else:
            if address < 0x20060000 and not (dst <= address and address+size <= dst+384):
                bad.append(('write',address,size))
    u.hook_add(UC_HOOK_MEM_READ, monitor)
    u.hook_add(UC_HOOK_MEM_WRITE, monitor)
    def count(uc,address,size,data):
        if active[0]: insns[0] += 1
    u.hook_add(UC_HOOK_CODE,count,None,labels['c_acdecode'],labels['c_acdecode']+rep['decoder_bytes']-1)

    cases = []
    for name,vals,payload in A.fixtures(): cases.append((name,vals,payload))
    rng = random.Random(121)
    for i in range(80):
        vals = [0xFFFF if rng.random()<.4 else rng.randrange(16384) for _ in range(192)]
        cases.append((f'random sparse {i}',vals,A.packed(vals)))
    for i in range(10):
        vals = [rng.randrange(16384)]*192
        cases.append((f'constant {i}',vals,A.packed(vals)))
    def decode(payload, want=None):
        u.mem_write(src,payload or b'\0')
        u.mem_write(dst-16,b'\xa5'*416)
        bounds[0]=len(payload); bad.clear(); insns[0]=0; active[0]=True
        ET.call(u,labels['c_acdecode'],src,src+len(payload),dst)
        active[0]=False; max_insns[0]=max(max_insns[0],insns[0])
        assert not bad,bad
        assert bytes(u.mem_read(dst-16,16))==b'\xa5'*16
        assert bytes(u.mem_read(dst+384,16))==b'\xa5'*16
        status=u.reg_read(UC_ARM_REG_R0)
        if want is not None:
            assert status==0
            assert bytes(u.mem_read(dst,384))==struct.pack('<192H',*want)
        return status
    for name, vals, payload in cases: decode(payload,vals)
    ET.check('96 fixture/random cases: exact 14-bit values, empty markers, bounds and ABI',True)
    malformed=0
    for name,vals,payload in A.fixtures():
        if not payload: continue
        for n in range(1,len(payload)):
            assert decode(payload[:n])==1,(name,n)
            malformed+=1
        assert decode(payload+b'\0')==1
        malformed+=1
    for payload in (b'\x01', b'\x02', b'\x03', b'\xff',
                    b'\x04'+bytes(24)+b'\x10\0\0',
                    b'\x04'+bytes(24)+b'\0\0\0',
                    b'\0'+b'\0\x40'*192):
        assert decode(payload)==1
        malformed+=1
    ET.check(f'{malformed} malformed/truncated payloads rejected with bounded reads/writes',True)
    print('Decoder max executed instructions (emulator, not CPU cycles):',max_insns[0])

    replies=[]
    def ret(uc): uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    def router(uc,address,size,data):
        ptr=uc.reg_read(UC_ARM_REG_R2);buf,n=struct.unpack('<II',uc.mem_read(ptr,8))
        replies.append(bytes(uc.mem_read(buf,n)));ret(uc)
    u.hook_add(UC_HOOK_CODE,router,None,R.ROUTER,R.ROUTER+1)
    cyc=[100]
    def cycle(uc,access,address,size,value,data):
        cyc[0]+=100
        uc.mem_write(A.CYCCNT,struct.pack('<I',cyc[0]))
    u.hook_add(UC_HOOK_MEM_READ,cycle,None,A.CYCCNT,A.CYCCNT+3)
    msg=0x2004d000
    def nibbles(v):return bytes((v>>shift)&15 for shift in range(28,-1,-4))
    def word(data):
        v=0
        for byte in data:v=(v<<4)|byte
        return v
    def request(cmd,*args,length=R.PAD):
        replies.clear();b=bytearray(R.PAD);b[:4]=bytes(R.SIG);b[4]=cmd;b[5]=11;b[-1]=0xf7
        for i,arg in enumerate(args):b[6+8*i:14+8*i]=nibbles(arg)
        u.mem_write(msg,bytes(b));u.mem_write(msg-16,struct.pack('<II',msg,length))
        ET.call(u,rd['c_rdin'],0,msg-16,0)
        if not replies:return None
        reply=replies[-1]
        assert reply[:6]==bytes(R.SIG)+bytes([cmd|0x40,11]) and reply[-1]==0xf7
        payload=reply[6:-1]
        assert len(payload)%8==0
        return [word(payload[i:i+8]) for i in range(0,len(payload),8)]
    def w(address,value):u.mem_write(address,struct.pack('<I',value))
    w(A.ITCMCR,0x73);w(A.VTOR,0x08010000);w(A.MPUCTRL,0)
    w(A.DWTCTRL,0x100);w(A.DEMCR,0x20);w(A.LSR,3)
    record=ET.u32(u,0x2003c0cc);project=bytes(u.mem_read(record,0x29484))
    u.mem_write(0,b'\xCC'*A.END)
    ET.check('status reports registers/layout without changing ITCM',request(32)==[
        0,A.FORMAT,0x73,0x08010000,0,0x100,0x20,A.START,A.END,len(A.fixtures())] and bytes(u.mem_read(0,A.END))==b'\xCC'*A.END)
    for cmd in (33,34,35):ET.check(f'command {cmd} requires key',request(cmd,0)==[1])
    ET.check('check requires explicitly initialized canary',request(34,A.KEY)==[4])
    for cr in (0,0x28,0x19):
        w(A.ITCMCR,cr);ET.check(f'ITCM disabled/too-small ({cr:x}): no writes',request(33,A.KEY)==[2] and bytes(u.mem_read(0,A.END))==b'\xCC'*A.END)
    w(A.ITCMCR,0x73)
    for vector in (0,0x100,0x3f00):
        w(A.VTOR,vector);ET.check('low vector table blocks canary writes',request(33,A.KEY)==[3])
    w(A.VTOR,0x08010000)
    ET.check('fill only bounded ITCM region, low 256 bytes preserved',request(33,A.KEY)==[0,4032] and bytes(u.mem_read(0,256))==b'\xCC'*256)
    expected=b''.join(struct.pack('<I',a^A.PATTERN) for a in range(A.START,A.END,4))
    assert bytes(u.mem_read(A.START,A.END-A.START))==expected
    ET.check('canary check clean (decoder workspace excluded)',request(34,A.KEY)==[0,0,rep['canary_words'],0,0])
    w(0x140,123);w(0x3000,456)
    ET.check('canary check counts damage and first address/value; does not repair',request(34,A.KEY)==[0,2,rep['canary_words'],0x140,123] and ET.u32(u,0x140)==123)
    request(33,A.KEY)
    for index in range(len(A.fixtures())):
        for repeats in (1,8):
            result=request(35,A.KEY,index,repeats)
            assert result==[0,index,repeats,0,100*repeats,100,0,rep['fixtures'][index]['compressed_bytes']],result
            assert ET.u32(u,A.DWTCTRL)==0x100 and ET.u32(u,A.DEMCR)==0x20
            assert ET.u32(u,A.LAR)==0
    ET.check('all ROM fixtures x 1/8 decode batches match, trace controls restored',True)
    ET.check('bench leaves canaries intact outside workspace',request(34,A.KEY)==[0,0,rep['canary_words'],0,0])
    for index,repeats in ((len(A.fixtures()),1),(0,0),(0,9),(0,0xffffffff)):
        ET.check('invalid fixture/repeat count rejected',request(35,A.KEY,index,repeats)==[5])
    for cmd in (6,9,31,36,253,254):ET.check('existing disabled/unknown commands remain disabled',request(cmd)==[0xffffffff])
    ET.check('short request has no reply',request(33,A.KEY,length=16) is None)
    ET.check('all commands leave project record byte-identical',bytes(u.mem_read(record,0x29484))==project)
    print('ALL PASS' if not ET.FAILS else f'{len(ET.FAILS)} FAILED')
    if ET.FAILS:raise SystemExit(1)


if __name__=='__main__':main()
