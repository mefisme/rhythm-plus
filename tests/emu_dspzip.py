"""Execute the actual compressed ARM uploader; compare all DSP bytes to A0205.

Hardware DMA is deferred until WAIT, checking buffer lifetime. No physical SPI
timing claim. Cold startup, repeated reload, other modes, ITCM and SRAM guards.
"""
import hashlib,json,random,struct,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','tests','remix/tools')]
import core0,dspzip as Z,rhdsp1
from emu_playfix import machine,call
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *

def read(n):
    d=ROOT/'firmware'/n
    return (d/f'rhythmplus-{n.upper()}.bin').read_bytes(),json.loads((d/'manifest.json').read_text())['report']

def main():
    name=sys.argv[1] if len(sys.argv)>1 else 'dz001'
    image,rep=read(name);old,orep=read('a0205')
    loader,stream=core0.sent(old,orep)
    # Fine builds change only the granular engine; emu_granular_current proves
    # fine 0 renders bit-for-bit like the A0205 engine.
    fine=bool(rep['granular'].get('fine_controls'))
    if fine:
        own_loader,stream=core0.sent(image,rep);assert own_loader==loader
    raw=b''.join(w.to_bytes(3,'big') for w in stream)
    want_loader=b''.join(w.to_bytes(3,'big') for w in loader)
    assert Z.raw_stream(image)==raw
    assert hashlib.sha256(raw).hexdigest()==rep['dspzip']['raw_sha256']
    assert core0.sent(image,rep)==(loader,stream)
    assert rhdsp1.sent(bytearray(image),rep,'pitchmod')==rhdsp1.sent(bytearray(old),orep,'pitchmod')
    print('PASS core0 loader and all core1 words equal A0205; core0 stream decodes exactly' if fine else
          'PASS every core0/core1 program word equals A0205; no sound algorithm or grain capacity change')
    u=machine(image,(ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes(),mclass=True)
    groups=[];pending=[];chunks=[];native=[]
    def ret(v=0):u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,a,n,d):
        x,y=uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)
        assert not uc.reg_read(UC_ARM_REG_PRIMASK)
        assert uc.reg_read(UC_ARM_REG_SP)%8==0,hex(a)
        if a==core0.SEND:native.append((x,y));return
        if a==Z.WAIT:
            if pending:
                p,sz,before=pending.pop()
                assert bytes(uc.mem_read(p,sz))==before,'DMA source changed before completion'
                groups[-1][1].extend(before)
            ret()
        elif a==Z.SELECT:
            assert not pending;groups.append([x,bytearray()]);ret()
        elif a==Z.SPI:
            assert not pending and 0<y<=510 and y%3==0
            pending.append((x,y,bytes(uc.mem_read(x,y))));chunks.append(y);ret()
        elif a==Z.END:
            assert not pending and groups[-1][0]==x;ret()
        else:ret()
    for a in (core0.SEND,Z.WAIT,Z.SELECT,Z.SPI,Z.END):u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
    entry=int(rep['core0']['labels']['c_d0up'],16)
    call(u,entry,core0.BLK0,0)
    assert [bytes(g[1]) for g in groups]==[want_loader,raw]
    assert len(native)==1 and native[0][0]==int(rep['dspzip']['loader'],16)
    assert max(chunks[1:])==240
    print(f'PASS cold native upload: {len(raw)} exact bytes, 240-byte circular history doubles as SPI staging')
    slot=int(rep['dspzip']['scratch'],16);size=rep['dspzip']['scratch_bytes']
    # Preserve all automation ITCM and all SRAM outside the dedicated slot,
    # including unsaved settings, native heap, stack gap and storage DMA buffer.
    rng=random.Random(205)
    itcm=rng.randbytes(0x4000);u.mem_write(0,itcm)
    sram=bytearray(u.mem_read(0x20000000,0x50000))
    block=int(rep['rhstate']['block'],16)
    for k in range(block+4,0x2004f760):sram[k-0x20000000]=rng.randrange(256)
    u.mem_write(0x20000000,bytes(sram))
    for _ in range(3):
        groups.clear();native.clear();call(u,entry,core0.BLK0,0)
        assert [bytes(g[1]) for g in groups]==[want_loader,raw]
        assert bytes(u.mem_read(0,0x4000))==itcm
        after=bytes(u.mem_read(0x20000000,0x50000))
        lo=slot-0x20000000;hi=lo+size
        assert after[:lo]==sram[:lo] and after[hi:]==sram[hi:]
    print('PASS three warm reloads preserve all automation ITCM and SRAM outside the dedicated decoder slot')
    for index in (1,2,3):
        address=struct.unpack_from('<I',image,0x08031658-core0.BASE+index*4)[0]
        off=address-core0.BASE;n=int.from_bytes(image[off:off+3],'big')
        expected=image[off:off+(n+2)*3]
        groups.clear();native.clear();call(u,entry,address,index//2)
        assert native==[(address,index//2)] and bytes(groups[0][1])==expected
    print('PASS other mode/core blocks use the original native sender')
    # Real dispatcher and its original core order, with peripheral/task calls mocked.
    for a in (0x08046538,0x0802b69c,0x0802366c,0x08046534,0x08023416,
              0x080312cc,0x08031338,0x0803136c,0x080311da):
        u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
    for mode in (0,1,0):
        groups.clear();native.clear();call(u,0x08031110,mode,0,0,0)
        if mode==0:
            assert any(bytes(g[1])==raw for g in groups)
            assert native[0]==(0x08031638,0) and native[1][1]==1 and native[-1][1]==1
        else:assert not any(bytes(g[1])==raw for g in groups)
    print('PASS actual startup/reload dispatcher preserves both core upload order and mode selection')
    # Exercise match overlap, literal flags, full/max-length matches, circular
    # wrap, partial final DMA and cross-chunk matches through the ARM decoder.
    decoder=int(rep['core0']['labels']['c_dz'],16)
    patterns=[bytes(3),bytes(240),b'abc'*265,bytes(range(240))*6,
              rng.randbytes(1500),b'a'*1599,(b'aaaabbbbccc'+rng.randbytes(19))*48]
    for payload in patterns:
        assert len(payload)%3==0
        compressed=Z._pack(payload)
        assert Z.unpack_stream(compressed,len(payload))==payload
        blob=Z.MAGIC+struct.pack('<II',len(payload)//3,zlib.crc32(payload))+compressed
        u.mem_write(0x08001000,blob);groups.clear();call(u,decoder,0x08001000,0)
        assert len(groups)==1 and bytes(groups[0][1])==payload
    print('PASS actual ARM decoder edge cases: overlap, 240-byte wrap, long matches, random literals and partial final chunks')
    print('LIMIT physical boot/upload duration and DMA/cache behavior still require hardware confirmation')
    print('ALL PASS')
if __name__=='__main__':main()
