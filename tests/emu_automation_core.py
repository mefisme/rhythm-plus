"""Execute actual Cortex-M7 storage primitives against independent host results.

No firmware install, device connection or SD access. Compile locally first.
"""
from pathlib import Path
import random
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from automation_model import Event, NUMERIC, pack_block
from automation_memory import BankMap
sys.path.insert(0,str(ROOT/'modules'))
from project_layout import encode_identity
from build_automation_core import build
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *


def main():
    info = build()
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    origin = info["origin"]
    u.mem_map(origin, 0x2000)
    u.mem_write(origin, (ROOT / "buildtmp/automation-core/kernel.bin").read_bytes())
    u.mem_map(0x20000000, 0x8000)
    src, dst, stack, stop = 0x20000100, 0x20002000, 0x20007f00, origin+0x1ff0
    bounds, instructions = [None], [0]

    def observe_write(uc, access, address, size, value, data):
        if 0x20007000 <= address and address+size <= 0x20008000:
            return
        bound = bounds[0]
        assert bound is not None and bound[0] <= address and address+size <= bound[1], (
            "unexpected kernel write", hex(address), size)

    def observe_code(uc, address, size, data):
        instructions[0] += 1

    u.hook_add(UC_HOOK_MEM_WRITE, observe_write)
    u.hook_add(UC_HOOK_CODE, observe_code)

    def words(address, values):
        u.mem_write(address, struct.pack("<"+"I"*len(values), *values))

    def read(address, count):
        return list(struct.unpack("<"+"I"*count, u.mem_read(address, count*4)))

    def call(name, *args, output=None):
        bounds[0] = output
        instructions[0] = 0
        for i, value in enumerate(args):
            u.reg_write(UC_ARM_REG_R0+i, value)
        saved = [0xabc004+i for i in range(8)]
        for i, value in enumerate(saved):
            u.reg_write(UC_ARM_REG_R4+i, value)
        u.reg_write(UC_ARM_REG_SP, stack)
        u.reg_write(UC_ARM_REG_LR, stop | 1)
        u.emu_start(info["labels"][name] | 1, stop, count=1000000)
        assert u.reg_read(UC_ARM_REG_PC) == stop
        assert u.reg_read(UC_ARM_REG_SP) == stack
        assert [u.reg_read(UC_ARM_REG_R4+i) for i in range(8)] == saved
        return u.reg_read(UC_ARM_REG_R0)

    rng = random.Random(0x5706)
    for _ in range(1000):
        events = [Event(rng.randrange(192), rng.randrange(64), rng.randrange(16384))
                  for _ in range(24)]
        events[0] = Event(0, 0, 0, 1)
        events[-1] = Event(186, 63, 16383, 1)
        records = [e.word() for e in events]
        words(src, records)
        assert call("c_ap_pack", dst, src, 0xffffffff, 0xffffffff,
                    output=(dst, dst+128)) == 0
        assert read(dst, 32) == pack_block(events)
        words(src, read(dst, 32))
        assert call("c_ap_unpack", dst, src, 0xffffffff, 0xffffffff,
                    output=(dst, dst+96)) == 0
        assert read(dst, 24) == records
    print("PASS ARM packing/unpacking matches host model for 1,000 full blocks")

    # Every bad record location must leave the entire previous destination intact.
    for index in range(24):
        records = [Event(i*6, 0, i, 1).word() for i in range(24)]
        records[index] |= 1 << 30
        words(src, records)
        u.mem_write(dst, b"\xa5"*128)
        assert call("c_ap_pack", dst, src, 0xffffffff, 0xffffffff,
                    output=(dst, dst+128)) == 1
        assert bytes(u.mem_read(dst, 128)) == b"\xa5"*128
    for index in range(32):
        packed = pack_block([Event(0, 0, 8193)]*24)
        packed[index] |= 1 << 24
        words(src, packed)
        u.mem_write(dst, b"\x5a"*96)
        assert call("c_ap_unpack", dst, src, 0xffffffff, 0xffffffff,
                    output=(dst, dst+96)) == 1
        assert bytes(u.mem_read(dst, 96)) == b"\x5a"*96
    words(src, [Event(0, 63, 0).word()]*24)
    assert call("c_ap_pack", dst, src, 0xffffffff, 0x7fffffff,
                output=(dst, dst+128)) == 1
    print("PASS malformed inputs and unavailable destinations reject atomically")

    # Binary lookup is compared to a dictionary, including real zero/extreme values.
    chosen = rng.sample([(p, d) for p in range(192) for d in NUMERIC], 384)
    events = sorted(Event(p, d, rng.randrange(16384)) for p, d in chosen)
    records = [event.word() for event in events]
    words(src, records)
    lo = sum(1 << d for d in NUMERIC)
    assert call("c_ap_validate_stream", src, 384, lo, 0) == 0
    expected = {(e.position, e.destination): e.value for e in events}
    max_lookup = 0
    for position in range(192):
        for destination in NUMERIC:
            actual = call("c_ap_lookup", src, 384, destination, position)
            assert actual == expected.get((position, destination), 65535)
            max_lookup = max(max_lookup, instructions[0])
    words(src, [records[1], records[0]])
    assert call("c_ap_validate_stream", src, 2, lo, 0) == 1
    words(src, [records[0], records[0]])
    assert call("c_ap_validate_stream", src, 2, lo, 0) == 1
    assert call("c_ap_validate_stream", 0xdeadbeef, 385, lo, 0) == 1
    assert call("c_ap_lookup", 0xdeadbeef, 385, 0, 0) == 65535
    assert call("c_ap_lookup", 0xdeadbeef, 0, 0, 0) == 65535
    print(f"PASS 4,224 sparse queries at 384 events; maximum {max_lookup} executed ARM instructions/query")

    for size in (0, 1, 31, 385, 1536):
        data = rng.randbytes(size)
        if data:
            u.mem_write(src, data)
        assert call("c_ap_crc32", src, size, 0) == zlib.crc32(data)
        split = size//2
        partial = call("c_ap_crc32", src, split, 0)
        assert call("c_ap_crc32", src+split, size-split, partial) == zlib.crc32(data)
    print("PASS ARM CRC matches zlib, including empty and incremental buffers")
    mapping=BankMap()
    spans=[value for span in mapping.spans for value in (span.start,span.words)]
    words(src,spans)
    assert call('c_ap_map_validate',src,3)==0
    for index in range(8192):
        assert call('c_ap_map_word',src,3,index)==mapping.physical(index)
    for bad in ([0x2400,8192],[0x2400,32,0x2410,32],
                [0x4400,32],[0x4f80,32],[0x5ff0,32]):
        words(src,bad)
        assert call('c_ap_map_validate',src,len(bad)//2)==1
        assert call('c_ap_map_word',src,len(bad)//2,0)==0xffffffff
    assert call('c_ap_map_validate',0xdeadbeef,0)==1
    assert call('c_ap_map_validate',0xdeadbeef,9)==1
    assert call('c_ap_map_word',0xdeadbeef,3,8192)==0xffffffff
    print('PASS all 8,192 ARM mapped addresses match proposal; stock/Grid FX/overlap/overflow maps reject')
    for _ in range(100):
        token=rng.randbytes(12)
        u.mem_write(src,token)
        assert call('c_ap_identity_encode',dst,src,output=(dst,dst+20))==0
        encoded=bytes(u.mem_read(dst,20))
        assert encoded==encode_identity(token)
        u.mem_write(src,encoded)
        assert call('c_ap_identity_decode',dst,src,output=(dst,dst+12))==0
        assert bytes(u.mem_read(dst,12))==token
    encoded=encode_identity(bytes(range(12)))
    for offset in range(20):
        bad=bytearray(encoded);bad[offset]^=1;u.mem_write(src,bytes(bad))
        u.mem_write(dst,b'\xa5'*20)
        result=call('c_ap_identity_decode',dst,src,output=(dst,dst+12))
        assert result==(1 if offset<2 else 2 if offset<4 else 3)
        assert bytes(u.mem_read(dst,20))==b'\xa5'*20
    u.mem_write(src,bytes(12));u.mem_write(dst,b'\xa5'*20)
    assert call('c_ap_identity_encode',dst,src,output=(dst,dst+20))==4
    assert bytes(u.mem_read(dst,20))==b'\xa5'*20
    print('PASS ARM identity bytes match host; corrupt/version/zero-token cases preserve output')
    # Checked I/O executes real ARM control flow; only the driver boundary is mocked.
    ops,transfer,io_buffer=src,src+0x100,0x20003000
    context=0x5afaf00d
    stubs=[origin+0x1800+4*i for i in range(5)]
    state={}
    def driver(uc,address,size,data):
        x,y,z,q=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        assert x==context
        kind=stubs.index(address)
        state['calls'].append(('seek','read','write','sync','tell')[kind])
        result=0
        if kind==0:
            result=state['seek_error']
            if not result and not state['seek_lies']:state['pos']=y
        elif kind in (1,2):
            result=state['io_error']
            count=min(z,state['short']) if state['short'] is not None else z
            if result:count=0
            words(q,[count])
            if not result:
                if kind==1:uc.mem_write(y,bytes((state['pos']+i)&255 for i in range(count)))
                else:state['written']=bytes(uc.mem_read(y,count))
                if not state['io_lies']:state['pos']+=count
        elif kind==3:result=state['sync_error']
        else:result=state['pos']
        uc.reg_write(UC_ARM_REG_R0,result)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for address in stubs:u.hook_add(UC_HOOK_CODE,driver,None,address,address+1)
    def prepare(offset=20,count=16):
        state.clear();state.update(pos=0,seek_error=0,seek_lies=False,io_error=0,
                                    io_lies=False,short=None,sync_error=0,calls=[])
        words(ops,[address|1 for address in stubs]);words(transfer,[offset,count,0xdeadbeef])
        u.mem_write(io_buffer,bytes(range(256))*2)
    for function in ('c_ap_file_read','c_ap_file_write'):
        prepare()
        assert call(function,ops,context,io_buffer,transfer,output=(transfer+8,transfer+12))==0
        assert read(transfer,3)==[20,16,16] and state['pos']==36
        prepare();state['seek_error']=1
        assert call(function,ops,context,io_buffer,transfer,output=(transfer+8,transfer+12))==1
        assert state['calls']==['tell','seek'] and read(transfer+8,1)==[0]
        prepare();state['seek_lies']=True
        assert call(function,ops,context,io_buffer,transfer,output=(transfer+8,transfer+12))==1
        assert not any(kind in state['calls'] for kind in ('read','write'))
        prepare();state['io_error']=1
        assert call(function,ops,context,io_buffer,transfer,output=(transfer+8,transfer+12))==2
        prepare();state['short']=3
        assert call(function,ops,context,io_buffer,transfer,output=(transfer+8,transfer+12))==3
        assert read(transfer+8,1)==[3]
        prepare();state['io_lies']=True
        assert call(function,ops,context,io_buffer,transfer,output=(transfer+8,transfer+12))==2
        for offset,count in ((0,513),(0xfffffff0,32)):
            prepare(offset,count)
            assert call(function,ops,context,io_buffer,transfer,output=(transfer+8,transfer+12))==4
            assert not state['calls']
        prepare(0,0)
        assert call(function,ops,context,io_buffer,transfer,output=(transfer+8,transfer+12))==0
        assert not state['calls']
    prepare();assert call('c_ap_file_sync',ops,context)==0
    state['sync_error']=1;assert call('c_ap_file_sync',ops,context)==2
    print('PASS ARM checked I/O rejects seek failure, wrong positions, short transfer, driver errors and overflow')
    print(f"PASS kernel {info['bytes']} bytes, no allocated BSS; all calls preserve stack/callee-saved registers and write bounds")
    print("LIMIT: instruction counts are not hardware-cycle or deadline measurements")
    print("ALL PASS")


if __name__ == "__main__":
    main()
