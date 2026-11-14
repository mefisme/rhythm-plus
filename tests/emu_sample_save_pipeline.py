"""Trace the stock 5706 sample writer with mocked DSP and Content boundaries.
No device, SD access, firmware patch or physical timing claim.
"""
from pathlib import Path
import struct
import sys
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from emu_playfix import machine, call, STACK
ROOT=Path(__file__).resolve().parents[1]


def main():
    u=machine((ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes(),
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    writer,state,sampler,buffer=0x20010B68,0x20010B78,0x20010B60,0x2004D000
    sp=STACK+0xF0000
    total=4096
    copied=[]; queued=[]; released=[]; finals=[]; failures=[]
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def w(a,v):u.mem_write(a,struct.pack('<I',v&0xFFFFFFFF))
    def ret(v=0):u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,a,n,d):
        r=[uc.reg_read(x) for x in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        if a in (0x080643A6,0x080645B0):ret(total);return
        if a in (0x0806455E,0x080644B6):ret(0);return
        if a==0x080645CC:ret(buffer);return
        if a==0x080645D2:released.append(a);ret();return
        if a==0x080674DC:
            count=word(uc.reg_read(UC_ARM_REG_SP));copied.append((r[2],count,r[3]))
            uc.mem_write(r[3],b''.join(((r[2]+i)&0xFFFF).to_bytes(2,'little') for i in range(count)))
            ret(count);return
        if a==0x08023690:ret();return
        if a==0x0804607A:
            at=uc.reg_read(UC_ARM_REG_SP)
            queued.append(dict(item=list(struct.unpack('<II',uc.mem_read(r[0],8)))+[uc.mem_read(r[0]+8,1)[0]],
                offset=r[1],buffer=r[2],size=r[3],callback=word(at),context=word(at+4),payload=bytes(uc.mem_read(r[2],r[3]))))
            ret();return
        if a==0x080460C8:finals.append(r[:3]);ret();return
    for at in (0x080643A6,0x080645B0,0x0806455E,0x080644B6,0x080645CC,0x080645D2,0x080674DC,0x08023690,0x0804607A,0x080460C8):
        u.hook_add(UC_HOOK_CODE,hook,None,at,at+1)
    def reset():
        u.mem_write(state,bytes(0x34));u.mem_write(state+1,b'\x01')
        w(state+0x10,4);w(state+0x14,3);u.mem_write(state+0x18,b'\x01')
        u.mem_write(state+0x24,b'\x03\x00');w(state+0x30,writer)
        copied.clear();queued.clear();released.clear();finals.clear()
    def tick():call(u,0x0802F256,writer)
    def completion(q,result=0,done=None):
        w(sp,q['size'] if done is None else done);w(sp+4,q['context'])
        call(u,q['callback'],state+0x10,4,result,q['buffer'])
    def check(name,ok,info=''):
        print(('PASS ' if ok else 'FAIL ')+name+((' '+str(info)) if not ok else ''))
        if not ok:failures.append(name)
    reset()
    for _ in range(20):
        tick()
        if queued:break
    check('sample writer reads ready DSP audio in batches of at most 256 samples',bool(copied) and all(n<=256 for _,n,_ in copied),copied)
    check('native writer queues PCM data after the 44-byte WAV header',len(queued)==1 and queued[0]['item']==[4,3,1]
          and queued[0]['offset']==44 and 0<queued[0]['size']<=4096,queued)
    q=queued[0];before=bytes(u.mem_read(buffer,4096));reads=len(copied)
    for _ in range(8):tick()
    check('pending Content write prevents buffer refill/reuse',len(copied)==reads and len(queued)==1 and bytes(u.mem_read(buffer,4096))==before)
    check('file progress is not advanced merely by queue submission',word(state+8)==0)
    completion(q)
    check('completion advances acknowledged PCM progress and releases the shared buffer',word(state+8)==q['size']//2
          and bool(released) and word(state+0x28)==0,(word(state+8),released))
    consumed=1
    for _ in range(60):
        tick()
        if len(queued)>consumed:
            req=queued[consumed];consumed+=1
            if req['offset']==0:break
            completion(req)
    headers=[q for q in queued if q['offset']==0]
    check('WAV header is queued only after all PCM data has been acknowledged',bool(headers) and word(state+8)==total)
    if headers:
        h=headers[0]
        check('final WAV header has native PCM metadata and complete data length',h['size']==44 and h['payload'][:4]==b'RIFF'
              and h['payload'][8:12]==b'WAVE' and struct.unpack_from('<I',h['payload'],40)[0]==total*2)
        completion(h)
        check('successful header completion requests native file finalization',bool(finals))
    reset()
    while not queued:tick()
    completion(queued[0],result=3,done=16)
    check('failed/short transfer completion enters failure state without advancing saved progress',u.mem_read(state+1,1)[0]==3 and word(state+8)==0)
    print('LIMIT: DSP callbacks and Content submission mocked; SD latency, audio continuity and durability not tested')
    print('ALL PASS' if not failures else f'{len(failures)} FAILED')
    return bool(failures)


if __name__=='__main__':sys.exit(main())
