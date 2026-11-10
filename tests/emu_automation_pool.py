"""Actual ARM metadata allocator against independent quota/chain invariants."""
from pathlib import Path
import random
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_automation_core import build
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *


def main():
    info=build();u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    origin=info['origin'];u.mem_map(origin,0x2000)
    u.mem_write(origin,(ROOT/'buildtmp/automation-core/kernel.bin').read_bytes())
    u.mem_map(0x20000000,0x8000)
    pool,out,stack,stop=0x20001000,0x20002000,0x20007f00,origin+0x1ff0
    low_stack=[stack]
    def monitor(uc,access,address,size,value,data):
        if 0x20007000<=address and address+size<=0x20008000:
            low_stack[0]=min(low_stack[0],address);return
        assert (pool<=address and address+size<=pool+2048) or (out<=address and address+size<=out+32)
    u.hook_add(UC_HOOK_MEM_WRITE,monitor)
    def w(a,value,fmt='<I'):u.mem_write(a,struct.pack(fmt,value))
    def raw():return bytes(u.mem_read(pool,2048))
    def call(name,*args):
        for i,value in enumerate(args):u.reg_write(UC_ARM_REG_R0+i,value)
        for i in range(8):u.reg_write(UC_ARM_REG_R4+i,0x5110+i)
        u.reg_write(UC_ARM_REG_SP,stack);u.reg_write(UC_ARM_REG_LR,stop|1)
        u.emu_start(info['labels'][name]|1,stop,count=1000000)
        assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==stack
        assert [u.reg_read(UC_ARM_REG_R4+i) for i in range(8)]==list(range(0x5110,0x5118))
        return u.reg_read(UC_ARM_REG_R0)
    def verify(counts,minimum=1,limit=224):
        data=raw();used=[]
        self_count=0
        for pattern,count in enumerate(counts):
            head,tail,actual,blocks=struct.unpack_from('<HHHB',data,pattern*24)
            assert actual==count and blocks==(count+23)//24
            ids=[];block=head
            for _ in range(blocks):
                assert block<limit and block not in used
                ids.append(block);used.append(block)
                block=struct.unpack_from('<H',data,1536+block*2)[0]
            assert block==65535 and tail==(ids[-1] if ids else 65535)
            self_count+=len(ids)
        bitmap=struct.unpack_from('<7I',data,1984)
        assert set(used)=={i for i in range(224) if bitmap[i//32]>>(i%32)&1}
        assert sum(max(minimum,(n+23)//24) for n in counts)<=limit
        assert call('c_ap_pool_validate',pool)==0
        return self_count
    assert call('c_ap_pool_init',pool,224,1)==0
    assert call('c_ap_runtime_bytes')==8192 and call('c_ap_capture_capacity')==128
    assert call('c_ap_lock_runtime_bytes')==6144
    counts=[0]*64
    # Exact full-bank profile with all patterns retaining their reserved minimum.
    for pattern in range(64):
        count=192 if pattern<22 else 168 if pattern==22 else 24
        assert call('c_ap_pool_resize',pool,pattern,count,out)==0;counts[pattern]=count
    assert verify(counts)==224 and sum(counts)==5376
    before=raw();u.mem_write(out,b'\xa5'*32)
    assert call('c_ap_pool_resize',pool,63,25,out)==1
    assert raw()==before and bytes(u.mem_read(out,32))==b'\xa5'*32
    assert call('c_ap_pool_resize',pool,63,24,out)==0 # Same-count update at capacity.
    assert call('c_ap_pool_resize',pool,0,0,out)==0;counts[0]=0
    assert call('c_ap_pool_resize',pool,63,48,out)==0;counts[63]=48
    verify(counts)
    print('PASS ARM allocator reaches5,376events, preserves reserved capacity, updates full bank and reclaims blocks')
    rng=random.Random(224)
    for minimum,limit in ((1,224),(2,224),(1,138)):
        assert call('c_ap_pool_init',pool,limit,minimum)==0;counts=[0]*64
        for _ in range(1000):
            pattern=rng.randrange(64);count=rng.randrange(385)
            proposed=counts.copy();proposed[pattern]=count
            fits=sum(max(minimum,(n+23)//24) for n in proposed)<=limit
            before=raw();u.mem_write(out,b'\xa5'*32)
            result=call('c_ap_pool_resize',pool,pattern,count,out)
            assert result==(0 if fits else 1)
            if fits:counts=proposed
            else:
                assert raw()==before and bytes(u.mem_read(out,32))==b'\xa5'*32
            verify(counts,minimum,limit)
    print('PASS3,000random ARM resizes match quota arithmetic across both policies and a smaller bank')
    assert call('c_ap_pool_init',pool,224,1)==0
    assert call('c_ap_pool_resize',pool,0,24,out)==0
    good=raw()
    patches=[(0,65535,'<H'),(2,17,'<H'),(4,385,'<H'),(6,2,'<B'),
             (1536,0,'<H'),(1984,3,'<I'),(2012,3,'<I'),(2044,63|(1<<16),'<I')]
    for offset,value,fmt in patches:
        u.mem_write(pool,good);w(pool+offset,value,fmt)
        assert call('c_ap_pool_validate',pool)==2
        before=raw();u.mem_write(out,b'\xa5'*32)
        assert call('c_ap_pool_resize',pool,0,48,out)==2
        assert raw()==before and bytes(u.mem_read(out,32))==b'\xa5'*32
    u.mem_write(pool,good)
    for pattern,count in ((64,0),(0,385),(0,0xffffffff)):
        assert call('c_ap_pool_resize',pool,pattern,count,out)==4 and raw()==good
    assert call('c_ap_pool_init',pool,63,1)==4 and raw()==good
    print('PASS corrupted chains/bitmaps/config and invalid requests reject without metadata/output mutation')
    print(f'PASS fixed2KiBmetadata; maximum observed primitive stack use {stack-low_stack[0]}bytes')
    print('LIMIT: metadata only; payload write rollback, cache publication and actual DSP transfer remain separate')
    print('ALL PASS')


if __name__=='__main__':main()
