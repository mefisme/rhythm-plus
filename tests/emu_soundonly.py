"""Lean Track+: archived settings inert; pad migration and retained UI, actual ARM."""
from pathlib import Path
import struct
import sys
import emu_tmenu as E
import fshape as F
import rhrec
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_CODE


def legacy_block(n,marks,defaults):
    data=bytearray(4+16*n);data[:2]=bytes(marks)
    for track in range(8):
        for index in range(n):
            struct.pack_into('<H',data,4+2*(track*n+index),16383^defaults[index])
    data[2]=(sum(data[4:])&255)^F.CHECK
    return bytes(data)


def main():
    _,fw,ram=(Path(p).read_bytes() for p in sys.argv[1:4])
    report=E.MAN['report'];assert report['tmenu'].get('soundonly')
    assert E.PADMAP==[0,None,None,1,None,2]
    assert not any(key in report for key in ('mixmove','grain','acdiag','dsdiag','autoprot','autobank'))
    assert report['rdiag']['readonly'] and report['rdiag']['mapped_ram_only']
    assert not {'autoprot','autobank'}.intersection(E.rhstate.OFF)
    assert not report['pshape']['vol'] and report['c0fx']['mix'] is False
    labels={k:int(v,16) for k,v in report['fshape']['labels'].items()}
    assert not any(k.startswith('c_vl') or k in ('c_flblk','c_flreset','c_flr','c_fl0w','c_flsw') for k in labels)
    for track in range(8):
        uc=E.setup(fw,ram);tail=E.u32(uc,rhrec.REC_OWNER)+rhrec.TAIL
        regions=[];accesses=[];writes=[]
        for offset,data in ((F.BLK_OFF,legacy_block(6,(F.MARK0,F.MARK1),F.DEF)),
                            (F.VBLK_OFF,legacy_block(8,(F.VMARK0,F.VMARK1),F.VDEF_M))):
            start=tail+offset;uc.mem_write(start,data);regions.append((start,data))
            def access(u,kind,address,size,value,context):accesses.append((address,size))
            uc.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,access,None,start,start+len(data)-1)
        def dsp(u,a,n,d):
            writes.append((u.reg_read(E.UC_ARM_REG_R0),u.reg_read(E.UC_ARM_REG_R2)))
            u.reg_write(E.UC_ARM_REG_PC,u.reg_read(E.UC_ARM_REG_LR))
        uc.hook_add(UC_HOOK_CODE,dsp,None,0x08031200,0x08031201)
        E.tap(uc,track);E.led(uc,E.LB['c_tmled'])
        if not E.b8(uc,E.T.O_OPEN):
            E.tap(uc,track);E.led(uc,E.LB['c_tmled'])
        assert E.sel(uc)==track and E.b8(uc,E.T.O_OPEN)
        # Old page IDs3/4 fall back to Normal without writing old Filter/Mix data.
        for old in (3,4):
            E.call(uc,E.LB['c_tmpgset'],track,old)
            E.led(uc,E.LB['c_tmled'])
            assert E.b8(uc,E.T.O_PAGE)==0
        for page in (0,1,2):
            E.pad(uc,E.pp(page));E.unpad(uc,E.pp(page));E.led(uc,E.LB['c_tmled'])
            assert E.b8(uc,E.T.O_PAGE)==page
            for inactive in ((26,27) if report.get('granular',{}).get('ui') else (26,27,29)):
                E.pad(uc,inactive);E.unpad(uc,inactive)
                assert E.b8(uc,E.T.O_PAGE)==page
            if page:
                for knob in range(8):E.knob(uc,knob,1)
        for removed in range(12,26):
            E.call(uc,labels['c_fsval'],track,removed)
            assert uc.reg_read(E.UC_ARM_REG_R0)==0
            E.call(uc,labels['c_fsput'],track,removed,16383)
        # Exercise the retained frame writer with READY and startup wait complete.
        ready=int(report['cthresh']['slot'],16)+1
        uc.mem_write(ready,b'\xa0')
        uc.mem_write(E.rhstate.ST+E.rhstate.OFF['spwait'][0],b'\xc8')
        for _ in range(10):E.led(uc,E.LB['c_tmled'])
        assert writes
        for core,address in writes:
            y=address&0x7fff
            assert not F.FB<=y<F.FB+F.O_M+8
            if core==0:
                assert not F.VB<=y<F.VB+F.O_VX+8 and not F.MB<=y<F.MB+16
        assert not accesses,accesses[:4]
        for address,data in regions:assert bytes(uc.mem_read(address,len(data)))==data
    print('PASS eight tracks: Normal/Pitch/FX retain pad positions; removed pads inert; legacy pages fall back to Normal')
    print('PASS valid nondefault archived Filter/Mix blocks are never read or written by retained gestures/frame writers')
    print('PASS archived DSP modulation writes and automation prototypes absent; retained frame writer active')
    print('LIMIT: emulator UI/transport boundaries; no hardware listening or flash performed')
    print('ALL PASS')


if __name__=='__main__':main()
