"""Verify proposed identity/granular tail slots against real current ARM writers."""
import os
from pathlib import Path
import struct
import sys
os.environ.setdefault('RH_BUILD','ad007')
import emu_tmenu as E
from unicorn import UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from unicorn.arm_const import *
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'modules'))
from project_layout import TAIL,IDENTITY,GRANULAR,encode_identity
import fshape as F
import mutset as M
import rhrec


def main():
    fw=Path(sys.argv[2]).read_bytes();ram=Path(sys.argv[3]).read_bytes()
    expected=encode_identity(bytes(range(12)))+bytes([0xa7])*GRANULAR.size
    writes=[];saved=[]
    def guard(uc,access,address,size,value,data):writes.append((address,size,value))
    def save(uc,address,size,data):
        saved.append(uc.reg_read(UC_ARM_REG_R3));uc.reg_write(UC_ARM_REG_R0,0)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    def fixture():
        uc=E.setup(fw,ram);record=E.u32(uc,0x2003c0cc)
        start=record+TAIL+IDENTITY.offset;uc.mem_write(start,expected)
        uc.hook_add(UC_HOOK_MEM_WRITE,guard,None,start,start+len(expected)-1)
        uc.hook_add(UC_HOOK_CODE,save,None,0x080472e2,0x080472e3)
        return uc,record,start
    assert (F.VBLK_OFF,F.VBLK_LEN)==(2,132)
    assert (F.PXBLK_OFF,F.PXBLK_LEN)==(136,36)
    assert (F.FIBLK_OFF,F.FIBLK_LEN)==(172,20)
    assert (M.BLK_OFF,M.BLK_LEN)==(192,84)
    assert (M.SC_TOFF,16*M.SC_TLEN)==(748,112)
    assert (F.SMBLK_OFF,F.SMBLK_LEN)==(384,20)
    assert (F.BLK_OFF,F.BLK_LEN)==(420,100)
    assert (E.T.PG_OFF,E.T.PG_LEN)==(530,10)
    assert rhrec.OFF['stockplus']==(548,132) and rhrec.OFF['stockplus2']==(680,68)
    labels={key:int(value,16) for key,value in E.MAN['report']['fshape']['labels'].items()}
    u,record,start=fixture()
    for track in range(8):
        for parameter in range(30):
            value=F.SMDEF[0] if parameter==29 else (8193+track*83+parameter*17)&16383
            E.call(u,labels['c_fsput'],track,parameter,value)
    assert not writes and bytes(u.mem_read(start,len(expected)))==expected
    E.call(u,0x08037ed0,0x20042ff4,0,0,0)
    assert saved==[record]
    assert not writes and bytes(u.mem_read(start,len(expected)))==expected
    print('PASS all 30 setters on eight tracks and stock save preparation preserve both proposed blocks')
    # Each track uses its own fixture: the file/sample worker is not running in
    # this harness, so unrelated queued sample work must not accumulate across UI cases.
    for track in range(8):
        u,record,start=fixture()
        E.tap(u,E.sel(u));E.led(u,E.LB['c_tmled'])
        if E.sel(u)!=track:E.tap(u,track)
        assert E.b8(u,E.T.O_OPEN)
        for pad in range(E.T.PAD_PAGE0,E.T.PAD_PAGE0+6):
            E.pad(u,pad);E.unpad(u,pad)
            for knob in range(8):E.knob(u,knob,1)
            mask=E.u32(u,E.C.CTRL+0xa0)
            u.mem_write(E.C.CTRL+0xa0,struct.pack('<I',mask|1<<23))
            E.pad(u,pad);E.unpad(u,pad)
            u.mem_write(E.C.CTRL+0xa0,struct.pack('<I',mask))
        assert not writes and bytes(u.mem_read(start,len(expected)))==expected
    print('PASS real page/knob/clear UI preserves proposed slots in eight isolated track fixtures')
    print('LIMIT: no new-project/load/clone migration or actual file I/O tested here')
    print('ALL PASS')


if __name__=='__main__':main()
