"""Knob-cycle wrap in Stock, both Granular pages and assignments; Shift reverse where the build has it."""
import struct
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];slot=int(g['bridge']['slot'],16);menu=int(g['ui']['menu'],16)
    SM.sel(u,0);u.mem_write(menu+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    context=lambda:E.call(u,int(g['ui']['labels']['c_gucontext'],16))
    def shift(active,physical=False):
        G.held(u,27,active and physical);u.mem_write(E.ptr(u,E.u32(u,E.C.CTRL+0xc),0),bytes([active]));context()
    def cycle(count,assignment=False,granular=False):
        for reverse,physical in ((False,False),(True,True),(True,False)):
            shift(reverse,physical)
            if assignment:u.mem_write(slot+380,b'\x80')
            u.mem_write(menu+E.T.O_KNOB,b'\1')
            for n in range(2*count):
                G.pad(u,24);G.unpad(u,24)
                stock_settings=g['ui'].get('stock_settings',False) and E.u32(u,int(r['storageshadow']['slot'],16)+88)!=0
                backward=reverse and r['tmenu'].get('reverse_cycle',False) and not (g['ui'].get('settings_cycle_forward',False) and (assignment or granular or stock_settings))
                expected=(count-1-n)%count+1 if backward else (n+1)%count+1
                selected=(u.mem_read(slot+380,1)[0]&15)+1 if assignment else u.mem_read(menu+E.T.O_KNOB,1)[0]
                assert selected==expected,(count,assignment,reverse,n,selected,expected)
            shift(False)
    rec=SM.obj(u,0);pats=E.u32(u,rec+4);before=bytes(u.mem_read(pats,8*0xa28))
    G.pad(u,25);G.unpad(u,25);cycle(8)
    G.pad(u,E.GP);G.unpad(u,E.GP)
    for page in (0,1):
        shift(False);E.press(u,19 if page else 20);E.release(u,19 if page else 20)
        cycle(8 if not page or g.get('burst',True) else 6,granular=True)
        assert bool(u.mem_read(slot+235,1)[0]&1)==bool(page),'cycle changed knob page'
    shift(False);G.pad(u,E.GP);E.press(u,19);E.release(u,19);G.unpad(u,E.GP)
    assert u.mem_read(slot+380,1)[0]&128
    cycle(16 if g.get('burst',True) else 14,True)
    # Native Stock editor also supports reverse cycling in internal packs,
    # where private granular automation/settings access is unavailable.
    shift(False);G.pad(u,E.GP);G.unpad(u,E.GP);G.pad(u,25);G.unpad(u,25)
    u.mem_write(int(r['storageshadow']['slot'],16)+88,struct.pack('<I',0))
    cycle(8)
    assert bytes(u.mem_read(pats,8*0xa28))==before,'cycling changed notes or automation'
    print('PASS contextual held/sticky Shift cycling: Stock value reverse; settings/assignment forward; wrapping twice')
    print('PASS cycle changes selection only; knob page, notes and automation preserved')
    print('ALL PASS')
if __name__=='__main__':main()
