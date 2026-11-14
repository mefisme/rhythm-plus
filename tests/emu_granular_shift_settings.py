"""Effective Shift is a temporary settings layer owned by the active TPE page."""
import struct
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels'];slot=int(g['bridge']['slot'],16);menu=int(g['ui']['menu'],16)
    UI={k:int(v,16) for k,v in g['ui']['labels'].items()}
    SM.sel(u,0);u.mem_write(menu+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    shift=lambda:E.ptr(u,E.u32(u,E.C.CTRL+0xc),0)
    context=lambda:E.call(u,UI['c_gucontext'])
    G.pad(u,31);G.unpad(u,31)
    u.mem_write(shift(),b'\0');context();assert u.mem_read(slot+102,1)==b'\0'
    # The native Shift store publication is injected (as in emu_tmenu); its
    # asynchronous listeners are not running in this fixture. Both physical
    # held-bit and sticky/no-held-bit cases use the same effective native flag.
    G.held(u,27,True);u.mem_write(shift(),b'\1');context()
    assert u.mem_read(slot+102,1)==b'\1' and u.mem_read(slot+103,1)[0]&2
    before=u.mem_read(slot+235,1)
    E.press(u,19);E.release(u,19);assert u.mem_read(slot+380,1)[0]&128
    assert u.mem_read(slot+235,1)==before,'Shift navigation changed normal knob page'
    E.press(u,20);E.release(u,20);assert not u.mem_read(slot+380,1)[0]&128
    G.held(u,27,False);u.mem_write(shift(),b'\0');context();assert u.mem_read(slot+102,1)==b'\0'
    # Sticky Shift: native effective flag stays on with no physical button held.
    u.mem_write(shift(),b'\1');G.held(u,27,False);context()
    assert u.mem_read(slot+102,1)==b'\1'
    E.press(u,19);E.release(u,19);assert u.mem_read(slot+380,1)[0]&128
    for _ in range(4):context()
    assert u.mem_read(slot+102,1)==b'\1'
    u.mem_write(shift(),b'\0');context();assert u.mem_read(slot+102,1)==b'\0' and not u.mem_read(slot+380,1)[0]&128
    # Changing page while Shift assignments are active drops that page's mode.
    u.mem_write(shift(),b'\1');context();E.press(u,19);E.release(u,19)
    assert u.mem_read(slot+380,1)[0]&128
    G.pad(u,25);G.unpad(u,25);context()
    assert not u.mem_read(slot+380,1)[0]&128,'stock page retained old assignment mode'
    G.pad(u,31);G.unpad(u,31);context()
    assert u.mem_read(slot+102,1)==b'\1' and not u.mem_read(slot+380,1)[0]&128,'returning page inherited old assignments subview'
    E.press(u,19);E.release(u,19);SM.sel(u,7);context()
    assert u.mem_read(slot+102,1)==bytes([bool(g['ui'].get('stock_settings'))]) and not u.mem_read(slot+380,1)[0]&128,'other track inherited granular assignments'
    SM.sel(u,0);u.mem_write(shift(),b'\0');context()
    # Stock opens only its own settings, never granular assignments.
    G.pad(u,25);G.unpad(u,25);u.mem_write(shift(),b'\1');context()
    assert u.mem_read(slot+102,1)==bytes([bool(g['ui'].get('stock_settings'))]) and not u.mem_read(slot+380,1)[0]&128
    E.press(u,19);E.release(u,19);assert not u.mem_read(slot+380,1)[0]&128
    u.mem_write(shift(),b'\0');context()
    # The retained pad-hold latch survives an independent Shift entry/release.
    G.pad(u,31);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
    E.call(u,K['c_gr_runtime_ui_frame'],slot,0,1);G.unpad(u,31)
    assert u.mem_read(slot+102,1)==b'\1'
    u.mem_write(shift(),b'\1');context();u.mem_write(shift(),b'\0');context()
    assert u.mem_read(slot+102,1)==b'\1','Shift release erased pad-held latch'
    G.pad(u,31);G.unpad(u,31);assert u.mem_read(slot+102,1)==b'\0'
    print('PASS physical/sticky Shift: settings, Down assignments, Up settings, release values; knob page preserved')
    print('PASS stock page never opens granular settings; retained pad-hold latch remains independent')
    print('ALL PASS')
if __name__=='__main__':main()
