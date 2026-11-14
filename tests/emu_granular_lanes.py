"""Real panel assignment gestures and native recording/routing on restored granular."""
import struct
import emu_fx_native_edges as F
from unicorn.arm_const import UC_ARM_REG_R0
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();g=E.MAN['report']['granular'];K=g['arm_kernel']['labels'];slot=int(g['bridge']['slot'],16);menu=int(g['ui']['menu'],16)
    SM.sel(u,0);u.mem_write(menu+E.T.O_OPEN,b'\x01');u.mem_write(G.CONT+0x264,b'\0')
    G.pad(u,31);G.unpad(u,31)
    E.press(u,19);E.release(u,19)
    assert u.mem_read(slot+380,1)[0]&128==0,'Down alone entered assignment'
    E.press(u,20);E.release(u,20)
    G.pad(u,31);E.press(u,19);E.release(u,19)
    assert u.mem_read(slot+380,1)[0]&128,'held page + Down did not enter assignment'
    rec=SM.obj(u,0);pats=E.u32(u,rec+4);before=bytes(u.mem_read(pats,8*0xa28))
    G.pad(u,16);G.unpad(u,16)
    assert u.mem_read(slot+316,8)==bytes([1,0,0,0,0,0,0,0]),'lane 1 not assigned to Position'
    assert bytes(u.mem_read(pats,8*0xa28))==before,'assignment rewrote native recordings'
    G.pad(u,24);G.unpad(u,24);G.pad(u,17);G.unpad(u,17)
    assert u.mem_read(slot+316,2)==b'\x01\x02','cycle did not select Size'
    G.pad(u,17);G.unpad(u,17);assert u.mem_read(slot+317,1)==b'\0','tap assigned lane did not restore stock'
    G.unpad(u,31);assert u.mem_read(slot+380,1)[0]&128,'assignment did not latch'
    G.pad(u,31);G.unpad(u,31);assert u.mem_read(slot+380,1)[0]&128==0,'tap did not exit assignment settings'
    E.press(u,20);E.release(u,20)
    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\x01')
    u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\0')
    u.mem_write(pats+0x128,b'\xff'*192)
    G.pad(u,4);G.knob(u,0,5)
    value=u.mem_read(slot+104,1)[0]
    lane=bytes(u.mem_read(pats+0x128,192))
    assert lane[24]==value,(value,lane[24],lane[:36].hex())
    assert lane[:24]+lane[25:]==b'\xff'*191,'lock touched other cells'
    E.led(u,int(E.MAN['report']['tmenu']['labels']['c_tmled'],16))
    colors=E.out(u,int(g['ui']['labels']['c_guout'],16))
    r,gc,b=(colors[60]>>16&255,colors[60]>>8&255,colors[60]&255)
    assert r>gc*4 and r>b*4,('held recording LED',hex(colors[60]))
    assert all(not ((c>>16&255)>(c>>8&255)*4 and (c>>16&255)>(c&255)*4) for c in colors[61:68]),'unrelated granular knobs showed red'
    G.unpad(u,4)
    # Native playback-router destination is custom; original stock base stays unchanged.
    E.call(u,K['c_gr_lane_inner'],0x20043700,0,91,3)
    assert u.mem_read(slot+104,1)==b'['
    # Stock recording gate for a borrowed lane cannot overwrite its stored values.
    before=bytes(u.mem_read(pats,8*0xa28))
    E.call(u,K['c_gr_lane_gate'],0x20040d8c,0,20)
    assert bytes(u.mem_read(pats,8*0xa28))==before
    # Playback executes the unmodified native automation player and installed
    # router vtable. Sparse values hold until another point replaces them.
    player=0x200470d4
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def itemset(store,index,v):w(E.ptr(u,store,index),v)
    u.mem_write(pats+0x128,b'\xff'*192)
    u.mem_write(pats+0x128,b'\x25');u.mem_write(pats+0x128+12,b'\x53')
    itemset(E.u32(u,player+0x30),0,1);itemset(E.u32(u,player+0x34),0,0)
    u.mem_write(E.u32(u,player+0x48),b'\xff'*24);u.mem_write(E.u32(u,player+0x4c),b'\xff'*24)
    for step,want in ((0,37),(1,37),(2,83),(3,83)):
        E.call(u,0x08055324,player,0,step,0)
        assert u.mem_read(slot+104,1)==bytes([want]),('native playback',step,u.mem_read(slot+104,1),want)
    # Live Record queues the chosen value into the actual native recorder.
    u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\x01')
    auto=next(a for a in range(0x20040d00,0x20042400,4) if E.u32(u,a)==0x08067864 and E.u32(u,a+0xc)==E.u32(u,player+8))
    G.knob(u,0,-3)
    assert u.mem_read(E.u32(u,auto+0x28),1)==b'P','granular turn did not queue native live value'
    event=E.u32(u,auto+0x30)
    E.call(u,0x0804946c,auto+8,event,0,0)
    assert b'P' in u.mem_read(pats+0x128,192),'native live listener did not record queued granular value'
    # Original stock Clear cannot erase a borrowed lane; granular Clear can.
    before=bytes(u.mem_read(pats+0x128,192))
    E.call(u,0x08047ca8,rec,0,0,0)
    assert bytes(u.mem_read(pats+0x128,192))==before,'stock Clear erased borrowed automation'
    G.held(u,23,True);G.knob(u,0,-40);G.held(u,23,False)
    assert bytes(u.mem_read(pats+0x128,192))==b'\xff'*192,'granular Clear left failed'
    # Manual turning must not leave the native lane permanently suspended.
    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\0')
    u.mem_write(pats+0x128+12,b'S')
    G.knob(u,0,5)
    assert not (E.u32(u,E.ptr(u,E.u32(u,player+0x34),0))&1),'manual turn suspended automation'
    itemset(E.u32(u,player+0x30),0,1)
    E.call(u,0x08055324,player,0,2,0)
    assert u.mem_read(slot+104,1)==b'S','native automation did not resume after manual turn'
    # Every eligible destination is routable independently on every track.
    for t in range(8):
        for d in range(1,17):
            lane=(d-1)%8
            u.mem_write(slot+316+t*8,bytes(d if k==lane else 0 for k in range(8)))
            E.call(u,K['c_gr_lane_inner'],0x20043700,16*t+lane,51,3)
            address=slot+104+t*8+d-1 if d<=8 else slot+212+t if d==9 else slot+236+t*7+d-10
            assert u.mem_read(address,1)==b'3',('destination',t,d,hex(address),u.mem_read(address,1))
    # Full track reset drops ownership before the native Clear operation.
    other=bytes(u.mem_read(slot+324,56))
    u.mem_write(slot+316,bytes(range(1,9)))
    u.mem_write(pats+0x128,b'\x40'*192)
    E.call(u,int(g['ui']['labels']['c_gureset'],16),0,6)
    assert bytes(u.mem_read(slot+316,8))==bytes(8),'Clear Track retained custom assignments'
    assert bytes(u.mem_read(slot+324,56))==other,'Clear Track changed another track'
    assert bytes(u.mem_read(pats+0x128,192))==b'\xff'*192,'borrowed lane protected during Clear Track'
    assert u.mem_read(slot+168,1)==b'\0' and u.mem_read(slot+212,1)==b'\x40'
    # Mixed primary granular, secondary granular and untouched native lane.
    u.mem_write(slot+168,b'\x10');u.mem_write(slot+316,b'\x01\x09'+bytes(6))
    for page in (0,1):
        for playing in (0,1):
            for recording in (0,1):
                u.mem_write(pats+0x128,b'\xff'*(12*192))
                u.mem_write(E.ptr(u,E.C.TRANSPORT,0),bytes([playing]))
                u.mem_write(E.ptr(u,E.C.TRANSPORT,1),bytes([recording]))
                E.press(u,19 if page else 20);E.release(u,19 if page else 20)
                G.pad(u,5);before=bytes(u.mem_read(pats+0x128,12*192));G.knob(u,0,3)
                value=u.mem_read(slot+(212 if page else 104),1)[0]
                expected=bytearray(before)
                if recording:expected[page*192+5*6]=value
                assert bytes(u.mem_read(pats+0x128,12*192))==expected,('mixed lock',page,playing,recording)
                G.unpad(u,5)
    for lane,v in enumerate((37,43,59)):
        u.mem_write(pats+0x128+lane*192,b'\xff'*192)
        u.mem_write(pats+0x128+lane*192,bytes([v]))
    itemset(E.u32(u,player+0x30),0,7);itemset(E.u32(u,player+0x34),0,0)
    u.mem_write(E.u32(u,player+0x48),b'\xff'*24);u.mem_write(E.u32(u,player+0x4c),b'\xff'*24)
    E.call(u,0x08055324,player,0,0,0)
    assert u.mem_read(slot+104,1)==b'%' and u.mem_read(slot+212,1)==b'+'
    E.call(u,0x08046410,0x10,8);assert u.reg_read(UC_ARM_REG_R0)==59,'native stock lane stopped working'
    # Stock held-value lookup ignores borrowed lanes but retains native lanes.
    G.pad(u,0)
    for lane,want in ((0,False),(1,False),(2,True)):
        E.call(u,int(E.MAN['report']['tmenu']['labels']['c_tmlane'],16),0,0,lane,0)
        assert bool(u.reg_read(UC_ARM_REG_R0))==want
    u.mem_write(menu+E.T.O_PAGE,b'\0');u.mem_write(slot+168,b'\0')
    E.led(u,int(E.MAN['report']['tmenu']['labels']['c_tmled'],16))
    colors=E.out(u,int(g['ui']['labels']['c_guout'],16))
    for k in (0,1):
        rgb=colors[60+k];r,gc,b=rgb>>16&255,rgb>>8&255,rgb&255
        assert rgb and not (r>gc*4 and r>b*4),('borrowed stock red',k,hex(rgb))
        assert rgb!=G.scl(0x9eff59,max(r,gc,b)),('borrowed stock green',k,hex(rgb))
    G.unpad(u,0)
    print('PASS mixed primary/secondary/native playback and locks; both transport and Record states')
    print('PASS borrowed stock lanes hide custom held values/red feedback and keep stock colors')
    print('PASS Clear Track resets granular settings/ownership and native automation; other tracks preserved')
    print('PASS native sparse playback holds values, live listener records, stock Clear protected, granular Clear works')
    print('PASS all 16 destinations routed independently on all 8 tracks')
    print('PASS pad 32, held-page assignment chord, lane cycle/toggle, no data changes on reassignment')
    print('PASS native stopped lock, borrowed-lane playback, stock recording exclusion; other cells preserved')
    print('ALL PASS')
if __name__=='__main__':main()
