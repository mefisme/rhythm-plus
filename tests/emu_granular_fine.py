"""Shift + turn fine primary knobs: real knob input, recorder boundary, resets, DSP words, GS v5; Burst removal."""
import struct,zlib
import emu_fx_native_edges as F
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_PC,UC_ARM_REG_LR
G,E,SM=F.G,F.E,F.SM
SIZE=[int(round(240*100**(v/127))) for v in range(128)]

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels']
    every=len(g['fine_controls']['knobs'])==6
    assert g['fine_controls']['knobs']==(['Position','Size','Density','Scan','Position scatter','Pitch scatter'] if every else ['Position','Size','Scan'])
    s=int(g['bridge']['slot'],16);m=int(g['ui']['menu'],16);t=0
    SM.sel(u,t);u.mem_write(m+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0');G.pad(u,E.GP);G.unpad(u,E.GP)
    E.press(u,20);E.release(u,20)
    context=lambda:E.call(u,int(g['ui']['labels']['c_gucontext'],16))
    def shift(on):u.mem_write(E.ptr(u,E.u32(u,E.C.CTRL+0xc),0),bytes([on]));context()
    def settings(on):
        if not g['ui'].get('shift_tap'):shift(on);return
        if (u.mem_read(s+102,1)[0]==1)!=bool(on):G.held(u,27,True);shift(1);G.held(u,27,False);shift(0)
    knob=lambda k:u.mem_read(s+104+8*t+k,1)[0]
    fine=lambda k:u.mem_read(s+404+8*t+k,1)[0]
    def full(k):return knob(k)*16+fine(k)
    G.knob(u,0,5);assert (knob(0),fine(0))==(5,0)
    shift(1)
    G.knob(u,0,3);assert (knob(0),fine(0))==(5,3)
    G.knob(u,0,20);assert (knob(0),fine(0))==(6,7),'fine did not carry into the knob step'
    G.knob(u,0,-127);assert full(0)==0
    for _ in range(20):G.knob(u,0,127)
    assert (knob(0),fine(0))==(127,15)
    G.knob(u,1,1);assert (knob(1),fine(1))==(64,1)
    home=g.get('scan_home')
    scan0=64 if home else 72
    assert knob(3)==scan0,('Scan default',knob(3))
    G.knob(u,3,-1);assert (knob(3),fine(3))==(scan0-1,15)
    if every:
        G.knob(u,2,2);assert (knob(2),fine(2))==(51,2)
        G.knob(u,4,3);assert (knob(4),fine(4))==(0,3)
        G.knob(u,5,21);assert (knob(5),fine(5))==(1,5)
        for k in (6,7):
            before=knob(k);G.knob(u,k,2);assert (knob(k),fine(k))==(before+2,0),('Edge/Reverse are not fine controls',k)
    else:
        G.knob(u,2,2);assert (knob(2),fine(2))==(53,0),'Density is not a fine control'
    shift(0);G.knob(u,0,-1);assert (knob(0),fine(0))==(126,15),'normal turn changed fine part'
    print(f"PASS Shift + turn moves {', '.join(g['fine_controls']['knobs'])} in sixteenths with carry and limits; other knobs and plain turns unchanged")
    E.press(u,19);E.release(u,19)
    secondary=bytes(u.mem_read(s+404,64));shift(1);G.knob(u,0,1);shift(0)
    assert bytes(u.mem_read(s+404,64))==secondary,'secondary page reached fine values'
    E.press(u,20);E.release(u,20)
    print('PASS secondary page Shift + turn keeps its normal control')
    # DSP words from the real dirty-track frame path.
    writes={};flags=E.u32(u,s+184);u.mem_write(s+184,struct.pack('<I',flags|3))
    def ret(uc,v=0):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    def dsp(uc,a,n,d):writes[uc.reg_read(UC_ARM_REG_R0)]=uc.reg_read(UC_ARM_REG_R1);ret(uc)
    hooks=[u.hook_add(UC_HOOK_CODE,dsp,None,K['c_gr_dsp_write'],K['c_gr_dsp_write']+1),
           u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:ret(uc),None,K['c_gr_shared_read'],K['c_gr_shared_read']+1),
           u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:ret(uc),None,0x08040814,0x08040815)]
    u.mem_write(s+200,struct.pack('<I',1<<t));E.call(u,K['c_gr_runtime_frame'],s,1,0)
    for h in hooks:u.hook_del(h)
    u.mem_write(s+184,struct.pack('<I',flags))
    pool=0x2400+256*t;i,f=divmod(full(1),16)
    assert writes[pool+4]==full(0),'Position word'
    assert writes[pool+3]==SIZE[i]+(SIZE[i+1]-SIZE[i])*f//16,'Size word'
    centre=bool(g.get('scan_centre')) and 63<=knob(3)<=65
    assert writes[pool+6]==(0 if centre else (full(3)-1024)&0xffffff),('Scan word',knob(3),fine(3),hex(writes[pool+6]))
    word=lambda v:(v*100+63)//127
    if every:
        d=knob(2);assert writes[pool+5]==word(d)*16+(word(min(d+1,127))-word(d))*fine(2),'Density word'
        assert writes[pool+11]==full(4) and writes[pool+9]==full(5),'scatter words'
        assert writes[pool+10]==word(knob(6)) and writes[pool+12]==knob(7),'Edge/Reverse words'
    if g.get('burst',True) is False:assert writes[pool+7]==127,'Burst bits still sent'
    assert centre or not writes[pool+13]>>15&1,'Scan away from the centre: no home bit'
    print('PASS DSP words: fine knobs in sixteenths, Size as interpolated grain samples; Edge/Reverse unchanged'+
          (f'; Scan knob {knob(3)} fine {fine(3)} sends centre' if centre else ''))
    if home:
        u.mem_write(s+104+8*t+3,bytes([64]));u.mem_write(s+404+8*t+3,bytes([0]))
        writes.clear();flags=E.u32(u,s+184);u.mem_write(s+184,struct.pack('<I',flags|3))
        hooks=[u.hook_add(UC_HOOK_CODE,dsp,None,K['c_gr_dsp_write'],K['c_gr_dsp_write']+1),
               u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:ret(uc),None,K['c_gr_shared_read'],K['c_gr_shared_read']+1),
               u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:ret(uc),None,0x08040814,0x08040815)]
        u.mem_write(s+200,struct.pack('<I',1<<t));E.call(u,K['c_gr_runtime_frame'],s,1,0)
        for h in hooks:u.hook_del(h)
        u.mem_write(s+184,struct.pack('<I',flags))
        assert writes[pool+6]==0 and writes[pool+13]>>15&1,'Scan centred: the home bit'
        print('PASS Scan starts centred; centred Scan sends the home bit (field 13 bit 15)')
    # Fine turns are manual only: no live queue, no held-step lock, no red feedback.
    u.mem_write(s+316,bytes([1])+bytes(7));auto=E.u32(u,0x20040d88+12)
    p=SM.pat(u,t);u.mem_write(p+0x128,b'\xff'*192)
    u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\1');u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\1');u.mem_write(E.ptr(u,E.C.TRANSPORT,2),b'\0')
    lane=E.u32(u,auto+0x28);u.mem_write(lane,b'\xff');u.mem_write(s+388,bytes(16))
    before=bytes(u.mem_read(p,0xa28));shift(1);G.knob(u,0,-2)
    assert bytes(u.mem_read(p,0xa28))==before and u.mem_read(lane,1)==b'\xff','fine turn recorded'
    assert bytes(u.mem_read(s+388,16))==bytes(16),'fine turn lit recording feedback'
    shift(0);G.knob(u,0,-1);assert u.mem_read(lane,1)!=b'\xff','fixture: plain live turn did not record'
    G.pad(u,4);before=bytes(u.mem_read(p,0xa28));shift(1);G.knob(u,0,3)
    assert bytes(u.mem_read(p,0xa28))==before,'fine turn wrote a held-step lock'
    shift(0);G.knob(u,0,1);assert bytes(u.mem_read(p,0xa28))!=before,'fixture: plain held turn did not lock'
    G.unpad(u,4)
    u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\0');u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\0')
    u.mem_write(s+316,bytes(8))
    # Automation playback sets the knob step and keeps the fine part, like stock fine Start/Length.
    shift(1);G.knob(u,0,5);shift(0);part=fine(0)
    u.mem_write(s+316,bytes([1])+bytes(7));E.call(u,K['c_gr_lane_inner'],0x20043700,16*t,40,3)
    assert (knob(0),fine(0))==(40,part);u.mem_write(s+316,bytes(8))
    print('PASS fine turns never record or lock, even with Record on, playing or a held step; playback keeps fine part')
    # Every reset returns the fine part to 0.
    shift(1);G.knob(u,0,5);shift(0);assert fine(0)
    G.held(u,23,True);G.knob(u,0,40);G.held(u,23,False);E.release(u,23)
    assert (knob(0),fine(0))==(0,0),'Clear + turn kept fine part'
    cfg=u.mem_read(s+168+t,1)[0];u.mem_write(s+168+t,bytes([cfg|4]));u.mem_write(m+8,b'\4')
    u.mem_write(s+404+8*t+3,b'\5');G.pad(u,20);G.unpad(u,20)
    assert (knob(3),fine(3))==(72,0),'value tap kept fine part'
    u.mem_write(s+168+t,bytes([cfg]))
    u.mem_write(s+404+8*t,bytes([3,4,0,5])+bytes(4))
    G.held(u,23,True);G.pad(u,E.GP);G.unpad(u,E.GP);G.held(u,23,False);E.release(u,23)
    assert bytes(u.mem_read(s+404+8*t,8))==bytes(8),'Clear + Granular pad kept fine parts'
    u.mem_write(s+404+8*t,bytes([3,4,0,5])+bytes(4));E.call(u,K['c_gr_runtime_track_reset'],s,t)
    assert bytes(u.mem_read(s+404+8*t,8))==bytes(8),'Clear Track kept fine parts'
    print('PASS Clear + turn, value tap, Clear + Granular pad and Clear Track reset the fine part')
    # GS v5 keeps all 64 fine bytes; v4 imports with fine 0; out-of-range fine fails closed.
    buf=0x20001000;pattern=bytes((7*i)%16 for i in range(64));u.mem_write(s+404,pattern)
    E.call(u,K['c_gr_runtime_settings_store'],s,buf);assert u.reg_read(UC_ARM_REG_R0)==1
    saved=bytes(u.mem_read(buf,288));assert saved[:4]==b'GS\x05\x08' and saved[224:]==pattern
    assert struct.unpack_from('<I',saved,4)[0]==zlib.crc32(saved[8:288])
    u.mem_write(s+404,bytes(64));E.call(u,K['c_gr_runtime_settings_load'],s,buf)
    assert u.reg_read(UC_ARM_REG_R0)==1 and bytes(u.mem_read(s+404,64))==pattern
    old=bytearray(saved[:224]);old[2]=4;struct.pack_into('<I',old,4,zlib.crc32(old[8:]))
    u.mem_write(buf,bytes(old)+b'\x0f'*64);E.call(u,K['c_gr_runtime_settings_load'],s,buf)
    assert u.reg_read(UC_ARM_REG_R0)==1 and bytes(u.mem_read(s+404,64))==bytes(64),'v4 import kept stale fine bytes'
    assert bytes(u.mem_read(s+104,64))==saved[8:72]
    bad=bytearray(saved);bad[224]=16;struct.pack_into('<I',bad,4,zlib.crc32(bad[8:288]))
    u.mem_write(s+404,pattern);u.mem_write(buf,bytes(bad));E.call(u,K['c_gr_runtime_settings_load'],s,buf)
    assert u.reg_read(UC_ARM_REG_R0)==0 and bytes(u.mem_read(s+404,64))==pattern,'invalid fine byte accepted'
    print('PASS GS v5 saves all 64 fine bytes with CRC; GS v4 imports with fine 0; out-of-range fine fails closed')
    if g.get('burst',True) is False:
        # Secondary K7/K8 are not controls; settings pads 23/24 are dark and inert.
        def draw():
            u.mem_write(0x20006f3c,struct.pack('<I',E.u32(u,0x20006f3c)+1000))
            out=0x20002000;u.mem_write(out,struct.pack('<69I',*([0xffffff]*69)))
            E.call(u,K['c_gr_runtime_draw'],s,t,out,u.mem_read(m+8,1)[0]+7)
            return struct.unpack('<69I',u.mem_read(out,69*4))
        G.pad(u,E.GP);G.unpad(u,E.GP);assert u.mem_read(s+168+t,1)[0]&16,'fixture: Granular view not open'
        E.press(u,19);E.release(u,19);shift_bytes=bytes(u.mem_read(s+236,56))
        for k in (6,7):G.knob(u,k,20);G.knob(u,k,-5)
        assert bytes(u.mem_read(s+236,56))==shift_bytes,'K7/K8 secondary still change Burst'
        out=draw();assert out[66]==out[67]==0,'K7/K8 secondary still lit'
        for _ in range(8):G.pad(u,24);G.unpad(u,24)
        assert 1<=u.mem_read(m+8,1)[0]<=6,'knob cycle reached K7/K8 on the secondary page'
        E.press(u,20);E.release(u,20)
        u.mem_write(s+292+t,bytes(1));settings(1);setting=u.mem_read(s+292+t,1)
        each=g.get('scan_each')
        if each:
            # Pad 20 Scan length (white track sample / amber each sample), 21 a gap, 22 Bounce, 23 Freeze, 24 Pitch Set.
            sv=lambda:u.mem_read(s+292+t,1)[0]  # noqa: E731
            cv=lambda:u.mem_read(s+168+t,1)[0]  # noqa: E731
            rgb=lambda v:(v>>16&255,v>>8&255,v&255)  # noqa: E731
            out=draw();r,gg,b=rgb(out[19])
            assert r==gg==b>0 and out[20]==0,('Scan length pad white, gap dark',hex(out[19]),hex(out[20]))
            G.pad(u,19);G.unpad(u,19);out=draw();r,gg,b=rgb(out[19])
            assert sv()&16 and r>gg>b,('pad 20: each sample, amber',hex(sv()),hex(out[19]))
            c0,s0=cv(),sv();G.pad(u,20);G.unpad(u,20);assert (cv(),sv())==(c0,s0),'pad 21 changed a setting'
            G.pad(u,21);G.unpad(u,21);assert sv()^s0==1,'pad 22 is not Bounce'
            G.pad(u,22);G.unpad(u,22);assert cv()^c0==64,'pad 23 is not Freeze'
            G.pad(u,23);G.unpad(u,23);assert (sv()>>1&7)==1,'pad 24 is not Pitch Set'
            out=draw();assert out[21] and out[22] and out[23],'pads 22-24 dark'
            G.pad(u,22);G.unpad(u,22);G.pad(u,21);G.unpad(u,21)
            for _ in range(4):G.pad(u,23);G.unpad(u,23)
            assert (cv(),sv())==(c0,s0|16),'settings not back'
        else:
            for pad in (22,23):G.pad(u,pad);G.unpad(u,pad)
            assert u.mem_read(s+292+t,1)==setting,'Burst settings pads still toggle'
            out=draw();assert u.mem_read(s+102,1)[0]==1 and out[22]==out[23]==0 and out[21],'Burst settings pads still lit'
        settings(0)
        E.call(u,K['c_gr_runtime_settings_store'],s,buf);saved=bytearray(u.mem_read(buf,288))
        saved[144+t]|=0x50;struct.pack_into('<I',saved,4,zlib.crc32(bytes(saved[8:288])));u.mem_write(buf,bytes(saved))
        E.call(u,K['c_gr_runtime_settings_load'],s,buf)
        kept=u.mem_read(s+292+t,1)[0]
        assert u.reg_read(UC_ARM_REG_R0)==1 and kept&(0x60 if each else 0x70)==0 and bool(kept&16)==bool(each),'old Burst setting bits kept'
        print('PASS Burst removed: secondary K7/K8 dark and inert, knob cycle stops at K6, '+
              ('settings pads 20 Scan length, 21 gap, 22 Bounce, 23 Freeze, 24 Pitch Set; Scan length saved, old Burst bits dropped on load'
               if each else 'settings pads 23/24 dark and inert, old Burst bits dropped on load'))
    print('ALL PASS')
if __name__=='__main__':main()
