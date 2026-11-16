"""Returning a recorded lane to stock moves playback and feedback with ownership."""
import struct
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM
from unicorn.arm_const import UC_ARM_REG_R0

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels'];slot=int(g['bridge']['slot'],16);menu=int(g['ui']['menu'],16)
    SM.sel(u,0);u.mem_write(menu+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    G.pad(u,E.GP);G.unpad(u,E.GP)
    rec=SM.obj(u,0);pat=SM.pat(u,0);player=0x200470d4
    u.mem_write(slot+316,b'\1'+bytes(7))
    u.mem_write(pat+0x128,b'\x40'+b'\xff'*191)
    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\1');G.pad(u,0);G.knob(u,0,3);G.unpad(u,0)
    assert E.u32(u,slot+388)&1,'recorded custom control did not set feedback'
    # Native ownership gesture: selected Position -> tap its assigned lane off.
    before=bytes(u.mem_read(pat+0x128,192))
    G.pad(u,E.GP);E.press(u,19);E.release(u,19);G.unpad(u,E.GP)
    G.pad(u,16);G.unpad(u,16);assert u.mem_read(slot+316,1)==b'\0'
    G.pad(u,E.GP);G.unpad(u,E.GP)
    G.pad(u,0)
    E.led(u,int(r['tmenu']['labels']['c_tmled'],16))
    E.out(u,int(g['ui']['labels']['c_guout'],16))
    assert not E.u32(u,slot+388)&1,'unassigned granular recording light remained active'
    E.call(u,K['c_gr_lane_stockview'],0,0,0,0)
    assert u.reg_read(UC_ARM_REG_R0),'stock held-value lookup did not recover its lane'
    G.unpad(u,0)
    custom=u.mem_read(slot+104,1)
    for offset in (0x30,0x34):
        u.mem_write(E.ptr(u,E.u32(u,player+offset),0),struct.pack('<I',1 if offset==0x30 else 0))
    u.mem_write(E.u32(u,player+0x48),b'\xff'*24);u.mem_write(E.u32(u,player+0x4c),b'\xff'*24)
    E.call(u,0x08055324,player,0,0,0)
    assert u.mem_read(slot+104,1)==custom,'stock playback continued changing granular'
    E.call(u,0x08046410,0x10,6);assert u.reg_read(UC_ARM_REG_R0)==before[0],'stock did not play preserved lane'
    assert bytes(u.mem_read(pat+0x128,192))==before,'unassign erased automation'
    print('PASS unassign preserves recording, restores stock lookup/playback, stops granular updates and clears stale red with Record armed')
    print('ALL PASS')
if __name__=='__main__':main()
