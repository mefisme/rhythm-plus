"""Actual ARM input, native recorder and audition boundaries for TPE settings."""
import struct,zlib
import emu_fx_native_edges as F
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels']
    s=int(g['bridge']['slot'],16);m=int(g['ui']['menu'],16);buf=0x20001000
    SM.sel(u,0);u.mem_write(m+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    context=lambda:E.call(u,int(g['ui']['labels']['c_gucontext'],16))
    def tap(p):G.pad(u,p);G.unpad(u,p)
    def shift(active,physical=False):
        G.held(u,27,active and physical)
        u.mem_write(E.ptr(u,E.u32(u,E.C.CTRL+0xc),0),bytes([active]));context()
    def hold(p):
        G.pad(u,p);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
        E.call(u,K['c_gr_runtime_ui_frame'],s,0,1);G.unpad(u,p)
    def colors():
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16))
        return E.out(u,int(g['ui']['labels']['c_guout'],16))
    tap(25);assert u.mem_read(s+102,1)==b'\0'
    hold(25);assert u.mem_read(s+102,1)==b'\1'
    G.pad(u,16);G.pad(u,16);G.unpad(u,16)
    assert u.mem_read(s+168,1)[0]&4,'tap editing or repeated-down guard failed'
    tap(17);assert u.mem_read(s+168,1)[0]&128
    c=colors();assert c[16] and c[17] and not any(c[18:24])
    # Shared pulse code targets Stock, never the selected track button.
    out=0x20001000;u.mem_write(out,struct.pack('<69I',*([0xffffff]*69)))
    E.call(u,K['c_gr_menu_indicator'],s,0,out)
    assert E.u32(u,out+25*4)!=0xffffff and E.u32(u,out+32*4)==0xffffff
    if g['ui'].get('sticky_assign'):
        shift(True);shift(False);assert u.mem_read(s+102,1)==b'\0','Shift did not close the pad menu'
    else:
        shift(True);shift(False);assert u.mem_read(s+102,1)==b'\1','Shift erased hold latch'
        tap(25);assert u.mem_read(s+102,1)==b'\0'
    if g['ui'].get('shift_tap'):
        # A physical Shift tap toggles; Stock settings never open assignments.
        shift(True,True);assert u.mem_read(s+102,1)==b'\0','holding Shift opened settings'
        shift(False);assert u.mem_read(s+102,1)==b'\1'
        E.press(u,19);E.release(u,19);assert not u.mem_read(s+380,1)[0]&128
        shift(True,True);shift(False);assert u.mem_read(s+102,1)==b'\0'
    else:
        for physical in ((True,False) if g['ui'].get('shift_opens_settings',True) else ()):
            shift(True,physical);assert u.mem_read(s+102,1)==b'\1'
            E.press(u,19);E.release(u,19);assert not u.mem_read(s+380,1)[0]&128
            shift(False);assert u.mem_read(s+102,1)==b'\0'
    print('PASS Stock hold latch, tap exit, physical/sticky Shift, settings LEDs and pulse')
    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\0');u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\0')
    u.mem_write(m+8,b'\1');store=E.u32(u,E.C.CTRL+E.T.KSTORES)
    before=bytes(u.mem_read(SM.pat(u,0),0xa28))
    # Sliding is overlapping down/up reports, not a sequence of isolated taps.
    for i,p in enumerate(range(16,24)):
        G.pad(u,p);assert u.mem_read(E.ptr(u,store,0),1)[0]==(64 if p==20 else i*127//7)
        if i:G.unpad(u,p-1)
    G.unpad(u,23)
    G.pad(u,20);G.pad(u,19);assert u.mem_read(E.ptr(u,store,0),1)==b'@'
    G.unpad(u,20);G.unpad(u,19)
    assert bytes(u.mem_read(SM.pat(u,0),0xa28))==before,'manual taps changed notes/automation with Record off'
    SM.sel(u,1);tap(23);assert not u.mem_read(s+169,1)[0]&0x84,'options leaked to another track'
    SM.sel(u,0)
    # Held locks at stopped and running transport touch only that step/lane.
    for playing in (0,1):
        p=SM.pat(u,0);u.mem_write(p+0x128,b'\xff'*192)
        u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\1');u.mem_write(E.ptr(u,E.C.TRANSPORT,0),bytes([playing]))
        G.pad(u,4);snapshot=bytes(u.mem_read(p,0xa28));tap(22)
        want=bytearray(snapshot);want[0x128+4*6]=108
        assert bytes(u.mem_read(p,0xa28))==bytes(want),('held tap touched other data',playing)
        G.unpad(u,4)
    print('PASS sliding, both center-finger orders, track isolation and exact held locks stopped/playing')
    # Live taps use the native queue and recording feedback, never note data.
    auto=E.u32(u,0x20040d88+12);p=SM.pat(u,0);notes_before=bytes(u.mem_read(p,0x128))
    u.mem_write(E.ptr(u,E.C.TRANSPORT,2),b'\0');tap(23)
    assert u.mem_read(E.u32(u,auto+0x28),1)==b'\x7f'
    assert E.u32(u,m+16)==E.u32(u,E.C.HAL_TICK)
    c=colors();assert c[60]>>16&255>(c[60]>>8&255)*4,'Stock live recording feedback missing'
    assert bytes(u.mem_read(p,0x128))==notes_before
    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\0');u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\0')
    tap(E.GP);u.mem_write(m+8,b'\1');tap(23);assert u.mem_read(s+104,1)==b'\x7f'
    E.press(u,19);E.release(u,19);tap(16);assert u.mem_read(s+212,1)==b'\0'
    G.pad(u,19);G.pad(u,20);assert u.mem_read(s+212,1)==b'@'
    G.unpad(u,19);G.unpad(u,20)
    # Settings and assignment pads remain controls, never value taps.
    tapmode=g['ui'].get('shift_tap')
    shift_settings=g['ui'].get('shift_opens_settings',True)
    if shift_settings:
        shift(True,tapmode)
        if tapmode:shift(False)
    else:hold(E.GP)
    if g['ui'].get('sticky_assign'):
        G.held(u,19,True);E.press(u,19);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
        E.call(u,K['c_gr_runtime_ui_frame'],s,0,1);G.held(u,19,False);E.release(u,19)
    else:E.press(u,19);E.release(u,19)
    manual=bytes(u.mem_read(s+104,64))
    for _ in range(8):tap(24)
    tap(16);assert u.mem_read(s+316,1)==b'\x09' and bytes(u.mem_read(s+104,64))==manual
    if tapmode:shift(True,True)
    if shift_settings:shift(False)
    else:tap(E.GP)
    if g['ui'].get('sticky_assign'):shift(True,True);shift(False);assert u.mem_read(s+102,1)==b'\0','Shift did not close sticky assignments'
    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\1');u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\1')
    p=SM.pat(u,0);u.mem_write(p+0x128,b'\xff'*192)
    G.pad(u,5);snapshot=bytes(u.mem_read(p,0xa28));tap(22)
    want=bytearray(snapshot);want[0x128+5*6]=108
    assert bytes(u.mem_read(p,0xa28))==bytes(want),'secondary tap lock touched other data'
    G.unpad(u,5);tap(25)
    # The borrowed Stock knob remains manual, but cannot write Granular's lane.
    G.pad(u,5);snapshot=bytes(u.mem_read(p,0xa28));tap(16)
    assert bytes(u.mem_read(p,0xa28))==snapshot,'Stock bar overwrote borrowed automation'
    G.unpad(u,5)
    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\0');u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\0')
    print('PASS primary/secondary Granular taps and center; assignment pads never edit values')
    # Seed the native published note store (asynchronous listeners aren't run
    # by this fixture), then exercise the real selection audition call site.
    so=E.u32(u,G.CONT+0x74);notes=E.u32(u,so+0xc)
    u.mem_write(E.ptr(u,notes,0),b'\x40'*4);u.mem_write(E.ptr(u,notes,16),b'\1'*4)
    calls=[];u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:calls.append(a),None,0x0805cc64,0x0805cc65)
    for silent in (False,True):
        u.mem_write(s+168,bytes([4|(128 if silent else 0)]));calls.clear();G.pad(u,0)
        assert E.held_step(u,0)==0 and bool(calls)==(not silent),('audition boundary',silent,calls)
        G.unpad(u,0)
    # Outside TPE the setting must not suppress the native audition.
    u.mem_write(m+E.T.O_OPEN,b'\0');calls.clear()
    u.mem_write(E.ptr(u,E.u32(u,so+0x34),0),b'\1')
    E.call(u,0x0805cb04,so,0,100)
    assert calls,'silent selection escaped TPE'
    u.mem_write(m+E.T.O_OPEN,b'\1')
    print('PASS silent selection keeps held step and suppresses only TPE audition')
    # No additional storage: settings use spare config bits, checked by CRC.
    fine=bool(g.get('fine_controls'))
    shadow=E.MAN['report']['storageshadow']
    version=shadow.get('granular_settings_version',5 if fine else 4)
    size=shadow.get('granular_settings_bytes',288 if fine else 224)
    E.call(u,K['c_gr_runtime_settings_store'],s,buf);saved=bytes(u.mem_read(buf,size))
    assert saved[:4]==b'GS'+bytes([version,8]) and saved[72]&0x84==0x84
    E.call(u,K['c_gr_runtime_settings_load'],s,0);assert u.mem_read(s+168,1)==b'\0'
    E.call(u,K['c_gr_runtime_settings_load'],s,buf);assert u.mem_read(s+168,1)[0]&0x84==0x84
    for version in (2,3):
        old=bytearray(saved[:224]);old[2]=version
        for t in range(8):old[72+t]&=0x6b
        if version==2:old[216:224]=bytes(8)
        struct.pack_into('<I',old,4,zlib.crc32(old[8:]));u.mem_write(buf,bytes(old))
        E.call(u,K['c_gr_runtime_settings_load'],s,buf)
        assert u.reg_read(UC_ARM_REG_R0)==1 and not u.mem_read(s+168,1)[0]&0x84
    E.call(u,K['c_gr_runtime_track_reset'],s,0);assert not u.mem_read(s+168,1)[0]&0x84
    print(f'PASS GS v{saved[2]} exact-size persistence, v2/v3 migration defaults and Clear Track reset')
    print('ALL PASS')
if __name__=='__main__':main()
