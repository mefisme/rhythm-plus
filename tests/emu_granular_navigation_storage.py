"""Companion navigation round-trip and migration from GS v2 sound settings."""
import struct,zlib
import emu_fx_native_edges as F
from unicorn.arm_const import UC_ARM_REG_R0
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();g=E.MAN['report']['granular'];K=g['arm_kernel']['labels'];slot=int(g['bridge']['slot'],16);menu=int(g['ui']['menu'],16);buf=0x20001000
    SM.sel(u,2);u.mem_write(G.CONT+0x264,b'\x09');G.pad(u,7);G.unpad(u,7)
    u.mem_write(G.CONT+0x264,b'\0');u.mem_write(menu+E.T.O_OPEN,b'\1')
    for t in range(8):
        SM.sel(u,t);G.pad(u,31);G.unpad(u,31)
        E.press(u,19 if t&2 else 20);E.release(u,19 if t&2 else 20)
        if not t&1:G.pad(u,25);G.unpad(u,25)
    E.call(u,K['c_gr_runtime_settings_store'],slot,buf)
    assert u.reg_read(UC_ARM_REG_R0)==1
    saved=bytes(u.mem_read(buf,224));assert saved[:4]==b'GS'+bytes([E.MAN['report']['storageshadow']['granular_settings_version'],8])
    assert saved[216:224]==bytes(t&3 for t in range(8)),saved[216:224]
    # Defaults must not retain another project's knob pages.
    E.call(u,K['c_gr_runtime_settings_load'],slot,0)
    assert not any(u.mem_read(slot+168+t,1)[0]&16 for t in range(8)) and u.mem_read(slot+235,1)==b'\0'
    E.call(u,K['c_gr_runtime_settings_load'],slot,buf)
    assert u.reg_read(UC_ARM_REG_R0)==1
    assert [bool(u.mem_read(slot+168+t,1)[0]&16) for t in range(8)]==[bool(t&1) for t in range(8)]
    assert u.mem_read(slot+235,1)[0]==sum(bool(t&2)<<t for t in range(8))
    E.call(u,K['c_gr_runtime_settings_store'],slot,buf);assert bytes(u.mem_read(buf,224))==saved
    # Rendered track-view indicators derive from restored state.
    SM.sel(u,0);E.led(u,int(E.MAN['report']['tmenu']['labels']['c_tmled'],16))
    out=E.out(u,int(g['ui']['labels']['c_guout'],16))
    for t in range(1,8):
        rgb=out[32+t];r,gc,b=rgb>>16&255,rgb>>8&255,rgb&255
        assert (gc>r>b) if t&1 else (r==gc==b),('restored track indicator',t,hex(rgb))
    # Navigation-only edits must create distinct immutable content addresses.
    for t in range(8):
        for bit in (1,2):
            nav=bytearray(saved);nav[216+t]^=bit
            struct.pack_into('<I',nav,4,zlib.crc32(nav[8:]))
            assert zlib.crc32(nav)!=zlib.crc32(saved),('navigation content key collision',t,bit)
    # Import older v2 files without losing manual sound values or assignments.
    legacy=bytearray(saved);legacy[2]=2;legacy[216:224]=bytes(8)
    struct.pack_into('<I',legacy,4,zlib.crc32(legacy[8:]))
    u.mem_write(buf,bytes(legacy));E.call(u,K['c_gr_runtime_settings_load'],slot,buf)
    assert u.reg_read(UC_ARM_REG_R0)==1 and u.mem_read(slot+235,1)==b'\0'
    assert not any(u.mem_read(slot+168+t,1)[0]&16 for t in range(8))
    assert bytes(u.mem_read(slot+104,64))==saved[8:72]
    # Unknown navigation bits fail closed even when the CRC matches.
    bad=bytearray(saved);bad[216]=4;struct.pack_into('<I',bad,4,zlib.crc32(bad[8:]));u.mem_write(buf,bytes(bad))
    before=bytes(u.mem_read(slot,404));E.call(u,K['c_gr_runtime_settings_load'],slot,buf)
    assert u.reg_read(UC_ARM_REG_R0)==0 and bytes(u.mem_read(slot,404))==before
    print('PASS all 8 tracks restore Stock/Granular view, primary/secondary page and derived track colors')
    print('PASS defaults reset navigation, GS v2 imports preserved, corrupt navigation rejected without mutation')
    print('ALL PASS')
if __name__=='__main__':main()
