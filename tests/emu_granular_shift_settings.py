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
    G.pad(u,E.GP);G.unpad(u,E.GP)
    u.mem_write(shift(),b'\0');context();assert u.mem_read(slot+102,1)==b'\0'
    if g['ui'].get('shift_opens_settings',True) is False:
        hold_mode(u,K,slot,shift,context);return
    if g['ui'].get('shift_tap'):
        tap_mode(u,g,slot,shift,context);return
    if g['ui'].get('sticky_assign'):
        sticky_mode(u,g,K,slot,shift,context);return
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
    G.pad(u,E.GP);G.unpad(u,E.GP);context()
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
    G.pad(u,E.GP);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
    E.call(u,K['c_gr_runtime_ui_frame'],slot,0,1);G.unpad(u,E.GP)
    assert u.mem_read(slot+102,1)==b'\1'
    u.mem_write(shift(),b'\1');context();u.mem_write(shift(),b'\0');context()
    assert u.mem_read(slot+102,1)==b'\1','Shift release erased pad-held latch'
    G.pad(u,E.GP);G.unpad(u,E.GP);assert u.mem_read(slot+102,1)==b'\0'
    print('PASS physical/sticky Shift: settings, Down assignments, Up settings, release values; knob page preserved')
    print('PASS stock page never opens granular settings; retained pad-hold latch remains independent')
    print('ALL PASS')
def hold_mode(u,K,slot,shift,context):
    """Settings open only by holding the page pad; Shift opens nothing and leaves an open page as it is."""
    G.held(u,27,True);u.mem_write(shift(),b'\1');context()
    assert u.mem_read(slot+102,1)==b'\0','Shift opened Settings'
    E.press(u,19);E.release(u,19);assert not u.mem_read(slot+380,1)[0]&128,'Shift + Down opened Assignments'
    G.held(u,27,False);u.mem_write(shift(),b'\0');context()
    G.pad(u,E.GP);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
    E.call(u,K['c_gr_runtime_ui_frame'],slot,0,1);G.unpad(u,E.GP)
    assert u.mem_read(slot+102,1)==b'\1','holding the page pad did not open Settings'
    u.mem_write(shift(),b'\1');context();u.mem_write(shift(),b'\0');context()
    assert u.mem_read(slot+102,1)==b'\1','Shift release closed Settings'
    G.pad(u,E.GP);G.unpad(u,E.GP);assert u.mem_read(slot+102,1)==b'\0','a tap did not close Settings'
    print('PASS Shift opens no Settings or Assignments; holding the page pad opens Settings, Shift leaves them open, a tap closes them')
    print('ALL PASS')
def sticky_mode(u,g,K,slot,shift,context):
    shown=lambda:u.mem_read(slot+102,1)==b'\1'
    assigned=lambda:u.mem_read(slot+380,1)[0]&128
    def hold_shift(on):G.held(u,27,on);u.mem_write(shift(),bytes([on]));context()
    def down_hold():
        G.held(u,19,True);E.press(u,19);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
        E.call(u,K['c_gr_runtime_ui_frame'],slot,0,1);G.held(u,19,False);E.release(u,19)
    # Physical and sticky Shift both show settings while active.
    for physical in (True,False):
        G.held(u,27,physical);u.mem_write(shift(),b'\1');context();assert shown() and u.mem_read(slot+103,1)[0]&2
        G.held(u,27,False);u.mem_write(shift(),b'\0');context();assert not shown()
    hold_shift(1);down_hold();assert assigned(),'held Down did not open assignments'
    hold_shift(0);assert shown() and assigned(),'assignments did not stay open'
    # Changing page while assignments are open drops that page's mode.
    G.pad(u,25);G.unpad(u,25);context();assert not assigned(),'stock page retained old assignment mode'
    G.pad(u,E.GP);G.unpad(u,E.GP);context();assert not assigned(),'returning page inherited old assignments subview'
    hold_shift(1);down_hold();SM.sel(u,7);context()
    assert not assigned(),'other track inherited granular assignments'
    SM.sel(u,0);hold_shift(0);context()
    # Stock opens only its own settings, never granular assignments.
    G.pad(u,25);G.unpad(u,25);hold_shift(1);assert shown()
    down_hold();assert not assigned();hold_shift(0);assert not shown()
    print('PASS physical/sticky Shift show settings while held; held Down opens assignments that stay; page/track changes drop them')
    print('PASS stock page never opens granular assignments')
    print('ALL PASS')

def tap_mode(u,g,slot,shift,context):
    shown=lambda:u.mem_read(slot+102,1)==b'\1'
    assigned=lambda:u.mem_read(slot+380,1)[0]&128
    def tap():G.held(u,27,True);u.mem_write(shift(),b'\1');context();G.held(u,27,False);u.mem_write(shift(),b'\0');context()
    # Sticky Shift alone (no physical press) is a modifier: no settings.
    u.mem_write(shift(),b'\1');context();assert not shown(),'sticky Shift opened settings';u.mem_write(shift(),b'\0');context()
    tap();assert shown()
    before=u.mem_read(slot+235,1)
    E.press(u,19);E.release(u,19);assert assigned()
    assert u.mem_read(slot+235,1)==before,'settings navigation changed normal knob page'
    E.press(u,20);E.release(u,20);assert not assigned()
    tap();assert not shown()
    # Changing page while assignments are open drops that page's mode.
    tap();E.press(u,19);E.release(u,19);assert assigned()
    G.pad(u,25);G.unpad(u,25);context();assert not assigned(),'stock page retained old assignment mode'
    G.pad(u,E.GP);G.unpad(u,E.GP);context();assert not assigned(),'returning page inherited old assignments subview'
    tap();E.press(u,19);E.release(u,19);SM.sel(u,7);context()
    assert not assigned(),'other track inherited granular assignments'
    SM.sel(u,0);context();tap() if shown() else None
    # Stock opens only its own settings, never granular assignments.
    G.pad(u,25);G.unpad(u,25);tap();assert shown()
    E.press(u,19);E.release(u,19);assert not assigned();tap();assert not shown()
    # A pad-hold latch closes with a Shift tap like any open settings.
    G.pad(u,E.GP);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
    E.call(u,int(g['arm_kernel']['labels']['c_gr_runtime_ui_frame'],16) if isinstance(g['arm_kernel']['labels']['c_gr_runtime_ui_frame'],str) else g['arm_kernel']['labels']['c_gr_runtime_ui_frame'],slot,0,1);G.unpad(u,E.GP)
    assert shown();tap();assert not shown(),'Shift tap did not close a pad-held latch'
    print('PASS Shift tap: settings, Down assignments, Up settings, tap closes; sticky Shift alone is a modifier; knob page preserved')
    print('PASS stock page never opens granular settings; page changes drop assignment mode; a tap closes a pad-held latch')
    print('ALL PASS')
if __name__=='__main__':main()
