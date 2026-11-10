"""Compiled ARM knobs and fragmented project codec against independent CRC bytes."""
from pathlib import Path
import struct
import sys
import zlib
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'modules')]
from build_granular_owner import build
import project_layout as L
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *


def main():
    info=build();u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    u.mem_map(info['origin'],0x4000);u.mem_write(info['origin'],(ROOT/'buildtmp/granular-owner/kernel.bin').read_bytes())
    u.mem_map(0x20000000,0x10000)
    params,config,tail,sp,stop=0x20000100,0x20000200,0x20001000,0x2000ff00,info['origin']+0x3ff0
    offsets=list(range(296,328))+list(range(404,420))+list(range(520,530))+list(range(860,882))
    allowed=set(tail+i for i in offsets+list(range(420,508)))
    def writes(uc,access,address,size,value,context):
        assert params<=address and address+size<=params+64 or config<=address and address+size<=config+8 or all(address+i in allowed for i in range(size)) or 0x2000f000<=address<0x20010000
    u.hook_add(UC_HOOK_MEM_WRITE,writes)
    def call(name,*args):
        for k,value in enumerate(args):u.reg_write(UC_ARM_REG_R0+k,value)
        saved=[0x123400+k for k in range(8)]
        for k,value in enumerate(saved):u.reg_write(UC_ARM_REG_R4+k,value)
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,stop|1)
        u.emu_start(info['labels']['c_gr_'+name]|1,stop,count=100000)
        assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==sp
        assert [u.reg_read(UC_ARM_REG_R4+k) for k in range(8)]==saved
        return u.reg_read(UC_ARM_REG_R0)
    L.validate_layout()
    assert len(offsets)==80 and len(set(offsets))==80
    reserved=next(block for block in L.BLOCKS if block.name=='future envelope/waveshape')
    assert not set(offsets)&set(range(reserved.offset,reserved.offset+reserved.size))
    call('params_init',params)
    assert bytes(u.mem_read(params,64))==bytes((0,64,51,72,0,0,64,0))*8
    for t in range(8):
        for k in range(8):
            for value in (0,1,63,64,126,127):
                call('params_put',params,t,k,value)
                assert call('params_get',params,t,k)==value
                expected=(value-64)&0xffffff if k==3 else (value*100+63)//127 if k in (2,6) else value
                assert call('params_word',params,t,k)==expected
    before=bytes(u.mem_read(params,64))
    assert call('params_put',params,8,0,1)==0 and call('params_put',params,0,8,1)==0 and call('params_put',params,0,0,128)==0
    assert call('params_word',params,8,3)==0 and bytes(u.mem_read(params,64))==before
    knobs=bytes((t*19+k*13)%128 for t in range(8) for k in range(8))
    modes=bytes((t%3)|((t%4)<<2)|(16 if t%2 else 0) for t in range(8))
    original=bytes((i*73+11)%256 for i in range(884))
    u.mem_write(params,knobs);u.mem_write(config,modes);u.mem_write(tail,original)
    assert call('project_save',tail,params,config)==1
    encoded=bytes(u.mem_read(tail,884))
    payload=b'GR\x02\x08'+knobs+modes
    expected=payload+struct.pack('<I',zlib.crc32(payload))
    assert bytes(encoded[i] for i in offsets)==expected
    assert all(encoded[i]==original[i] for i in range(884) if i not in offsets)
    u.mem_write(params,bytes(64));u.mem_write(config,bytes(8))
    assert call('project_load',tail,params,config)==1
    assert bytes(u.mem_read(params,64))==knobs and bytes(u.mem_read(config,8))==modes
    # Each byte's corruption is detected before either output buffer changes.
    for index in range(80):
        bad=bytearray(encoded);bad[offsets[index]]^=0x40;u.mem_write(tail,bytes(bad))
        before=bytes(u.mem_read(params,64))+bytes(u.mem_read(config,8))
        assert call('project_load',tail,params,config)==(0 if index<2 else 2)
        assert bytes(u.mem_read(params,64))+bytes(u.mem_read(config,8))==before
    # A valid checksum cannot make invalid knob/mode/reserved bits acceptable.
    for index,value in ((4,128),(68,3),(2,3),(3,7)):
        bad=bytearray(expected);bad[index]=value;bad[76:]=struct.pack('<I',zlib.crc32(bad[:76]))
        record=bytearray(encoded)
        for offset,value in zip(offsets,bad):record[offset]=value
        u.mem_write(tail,bytes(record));assert call('project_load',tail,params,config)==2
    # Format 1 stored Texture retrigger in bit 3 and a source flag in bit 2.
    legacy_modes=bytes((1,2,1|4,2|8,16,1|16,2|4|8|16,0))
    legacy=b'GR\x01\x08'+knobs+legacy_modes
    legacy+=struct.pack('<I',zlib.crc32(legacy));record=bytearray(encoded)
    for offset,value in zip(offsets,legacy):record[offset]=value
    u.mem_write(tail,bytes(record));assert call('project_load',tail,params,config)==1
    assert bytes(u.mem_read(config,8))==bytes((1,2|32,1,2|8|32,16,1|16,2|8|16|32,0))
    levels=bytes((64,0,127,1,2,3,4,5));u.mem_write(params,levels)
    u.mem_write(tail,bytes(884));assert call('levels_save',tail,params)==1
    block=bytes(u.mem_read(tail+420,16));written=b'GL\x01\x08'+levels
    assert block==written+struct.pack('<I',zlib.crc32(written))
    assert all(b==0 for i,b in enumerate(u.mem_read(tail,884)) if not 420<=i<436)
    u.mem_write(params,bytes(8));assert call('levels_load',tail,params)==1 and bytes(u.mem_read(params,8))==levels
    for index in range(16):
        bad=bytearray(block);bad[index]^=1;u.mem_write(tail+420,bytes(bad))
        u.mem_write(params,b'\x55'*8);assert call('levels_load',tail,params)==0 and bytes(u.mem_read(params,8))==b'\x55'*8
    u.mem_write(params,knobs)
    u.mem_write(tail,encoded);u.mem_write(config,b'\x03'+modes[1:])
    assert call('project_save',tail,params,config)==0 and bytes(u.mem_read(tail,884))==encoded
    assert [call('level_word',value) for value in (0,1,64,127)]==[1,512,0x200000,127*127*512]
    shift=bytes((i*5)%128 for i in range(56));setting=bytes((0,1,2,3,4,5,8,9))
    u.mem_write(params,shift);u.mem_write(config,setting);u.mem_write(tail,bytes(884))
    assert call('shift_save',tail,params,config)==1
    record=bytes(u.mem_read(tail+436,72));written=b'GS\x01\x08'+shift+setting
    assert record==written+struct.pack('<I',zlib.crc32(written))
    assert all(b==0 for i,b in enumerate(u.mem_read(tail,884)) if not 436<=i<508)
    u.mem_write(params,bytes(56));u.mem_write(config,bytes(8));assert call('shift_load',tail,params,config)==1
    assert bytes(u.mem_read(params,56))==shift and bytes(u.mem_read(config,8))==setting
    for index in range(72):
        bad=bytearray(record);bad[index]^=1;u.mem_write(tail+436,bytes(bad))
        u.mem_write(params,b'\x55'*56);assert call('shift_load',tail,params,config)==0 and bytes(u.mem_read(params,56))==b'\x55'*56
    print('PASS Shift record round trip, CRC and rejection leave other project bytes alone')
    print('PASS actual ARM seven-bit knob storage and DSP scaling, all8 tracks; defaults and invalid inputs checked')
    print('PASS project codec matches independent CRC32 bytes; 80 bytes in four gaps preserve archived pages, scenes, future reservation and last stock bytes')
    print('PASS every encoded byte corruption plus checksum-valid invalid values rejected without partial load; invalid save leaves project unchanged')
    print('LIMIT: standalone codec; staged save/load hooks are exercised separately')


if __name__=='__main__':main()
