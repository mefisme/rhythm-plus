"""Actual ARM hold-to-settings bar: timing, per-track options and temporary display."""
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_granular_owner import build
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *


def main():
    info=build();u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    u.mem_map(info['origin'],0x4000);u.mem_write(info['origin'],(ROOT/'buildtmp/granular-owner/kernel.bin').read_bytes())
    u.mem_map(0x20000000,0x10000)
    owner,ui,sp,stop=0x20000100,0x20000200,0x2000ff00,info['origin']+0x3ff0
    def writes(uc,access,address,size,value,context):
        assert (owner<=address and address+size<=owner+96) or (ui<=address and address+size<=ui+8) or 0x2000f000<=address<0x20010000,(hex(address),size)
    u.hook_add(UC_HOOK_MEM_WRITE,writes)
    def call(name,*args):
        for i,value in enumerate(args[:4]):u.reg_write(UC_ARM_REG_R0+i,value)
        for i,value in enumerate(args[4:]):u.mem_write(sp+4*i,struct.pack('<I',value))
        saved=[0x111100+k for k in range(8)]
        for k,value in enumerate(saved):u.reg_write(UC_ARM_REG_R4+k,value)
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,stop|1)
        u.emu_start(info['labels']['c_gr_'+name]|1,stop,count=100000)
        assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==sp
        assert [u.reg_read(UC_ARM_REG_R4+k) for k in range(8)]==saved
        return u.reg_read(UC_ARM_REG_R0)
    assert call('owner_size')==96 and call('ui_size')==8
    call('owner_init',owner);call('ui_init',ui)
    for track in range(8):
        before=bytes(u.mem_read(owner,96))
        call('ui_down',ui,track,1000,1)
        assert call('ui_tick',ui,track,1332,1)==0
        assert call('ui_pad',ui,owner,track,18,77)==0
        call('ui_release',ui)
        assert bytes(u.mem_read(owner,96))==before
        call('ui_down',ui,track,2000,1)
        assert call('ui_tick',ui,track,2333,1)==1
        assert call('ui_pad',ui,owner,track,16,77)==275
        assert call('owner_mode',owner,track)==0  # Merely selected; barrier still pending.
        assert call('ui_pad',ui,owner,track,16,77)==272
        epoch=call('owner_epoch',owner,track)
        assert call('owner_observe',owner,track,epoch,epoch,0,77)==12
        assert call('ui_pad',ui,owner,track,16,77)==275
        epoch=call('owner_epoch',owner,track)
        assert call('owner_observe',owner,track,epoch,epoch,0,77)==4
        assert call('owner_mode',owner,track)==0
        assert call('ui_pad',ui,owner,track,17,77)==272
        assert call('ui_pad',ui,owner,track,18,77)==272
        assert call('owner_flags',owner,track)==3
        state=bytes(u.mem_read(owner,96))
        assert call('ui_pad',ui,owner,track,23,77)==256  # Spare slot remains inert but consumed.
        assert call('ui_pad',ui,owner,track,15,77)==0 and call('ui_pad',ui,owner,track,24,77)==0
        assert bytes(u.mem_read(owner,96))==state
        call('ui_release',ui)
        assert call('ui_pad',ui,owner,track,16,77)==0
        # Return this track to defaults before checking another context.
        call('owner_init',owner)
    print('PASS all8 tracks: short tap only focuses page;333ms hold opens settings; release restores normal display ownership')
    print('PASS mode choices stage through owner ACK barrier; Fixed/Sequenced and Flow/Retrigger choices are independent per-track settings')
    print('PASS spare slot stays dark/inert; settings-pad events are consumed only while overlay is shown; no stock parameter or automation memory writes')
    call('ui_down',ui,3,0xffffff00,1)
    assert call('ui_tick',ui,3,0x4c,1)==0 and call('ui_tick',ui,3,0x4d,1)==1
    assert call('ui_tick',ui,4,0x4e,1)==0
    assert call('ui_pad',ui,owner,4,18,0)==0
    call('ui_down',ui,4,0,1);assert call('ui_tick',ui,4,400,0)==0
    assert call('ui_tick',ui,4,800,1)==0
    print('PASS clock wrap, track change and context/modifier cancellation cannot leave a stuck settings overlay')
    print(f'PASS owner+UI kernel{info["bytes"]} bytes; runtime state104 bytes; actual ARM callee-saved registers and write bounds verified')
    print('LIMIT: standalone input/display-state candidate; physical tmenu pad/LED hooks and project persistence not installed')
    print('ALL PASS')


if __name__=='__main__':main()
