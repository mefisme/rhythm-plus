"""Visual-only held-step Record indication, compared with the TPE helper."""
import os,sys,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['RH_BUILD']=sys.argv[1] if len(sys.argv)>1 else 'a0182'
sys.path[:0]=[str(ROOT/p) for p in ('modules','tests','builds','remix/tools')]
import emu_tmenu as E
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

def main():
    build=os.environ['RH_BUILD'];fw=(ROOT/'firmware'/build/f'rhythmplus-{build.upper()}.bin').read_bytes()
    u=E.setup(fw,(ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    r=E.MAN['report']['heldlights'];fn=int(r['labels']['c_hp_out'],16);previous=int(r['previous'],16)
    root=E.rhbuild.bl_target(bytearray(fw),E.T.OUT_CALL)
    st=E.MAN['report'].get('stretch',{}).get('arm')
    ft=E.MAN['report'].get('filetools')
    heads={}                                                                                # stretch and file tools call the chain first, in either order
    if st:heads[int(st['labels']['c_st_out'],16)]=int(st['prev']['prev_out'],16)
    if ft:heads[int(ft['labels']['c_ft_out'],16)]=int(ft['prev_out'],16)
    while root in heads:root=heads.pop(root)
    if root!=fn:
        gui=E.MAN['report']['granular']['ui']
        shadow=E.MAN['report']['storageshadow']
        assert root==int(gui['labels']['c_guout'],16)
        assert int(gui['previous']['out'],16)==int(shadow['labels']['c_sh_out'],16) and int(shadow['prev_out'],16)==fn
    output,frame=0x2004fa00,0x2004fd00
    base=[0x102030+i for i in range(69)];t=0
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def setp(st,i,v):u.mem_write(E.ptr(u,st,i),bytes([v]))
    def ret(v=0):u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def previous_hook(uc,a,n,d):uc.mem_write(output,struct.pack('<69I',*base));ret(0x1234)
    hook=u.hook_add(UC_HOOK_CODE,previous_hook,None,previous,previous+1)
    w(E.C.CTRL+0x7c,E.T.CONT);u.mem_write(E.T.CONT+0x264,b'\x03')
    dimptr=E.ptr(u,word(E.C.CTRL+0x88),2);w(dimptr,word(dimptr)&~1024)
    selected=word(E.T.CONT+0x25c);setp(selected,0,t)
    so=word(E.T.CONT+0x74+4*t);rec=word(E.T.AUTO+E.T.AUTO_RECS+4*t)
    def position(step):setp(word(rec+E.T.REC_PLAY),1,step)
    def show():
        E.call(u,fn,E.C.CTRL,output,frame,0)
        assert u.reg_read(UC_ARM_REG_R0)==0x1234
        return list(struct.unpack('<69I',u.mem_read(output,276)))
    # Real controller pad press/release, rather than only seeding a held flag.
    setp(E.C.TRANSPORT,0,1);setp(E.C.TRANSPORT,1,1)
    E.pad(u,4);E.call(u,E.LB['c_tmheld'],t)
    assert u.reg_read(UC_ARM_REG_R0)==4
    position(9)
    o=show();assert o[4]==0xff0000 and o[9]==0xffffff,([hex(v) for v in o[:16]],word(so+E.T.PADS_DOWN))
    E.unpad(u,4);assert show()==base
    print('PASS actual Gate pad press: held step red, playhead white; release restores previous renderer')
    for t in (0,7):
        setp(selected,0,t);so=word(E.T.CONT+0x74+4*t);rec=word(E.T.AUTO+E.T.AUTO_RECS+4*t)
        for page in (0,1):
            h=page*16+4;setp(word(so+0x60),0,page);setp(word(so+0x64),1,h);w(so+E.T.PADS_DOWN,1<<h)
            for mode in range(5):
                u.mem_write(E.T.CONT+0x264,bytes([mode]))
                for playing,record in ((1,1),(0,1),(1,0)):
                    setp(E.C.TRANSPORT,0,playing);setp(E.C.TRANSPORT,1,record)
                    for play in (page*16+9,h,(1-page)*16+9):
                        position(play);want=base.copy()
                        if record:
                            if playing and play//16==page:want[play&15]=0xffffff
                            want[h&15]=0xff0000
                        assert show()==want,(t,page,mode,playing,record,play)
                        if record and playing:
                            u.mem_write(frame,b'\xff'*32);E.call(u,E.LB['c_tmrpad'],t,frame)
                            codes=struct.unpack('<16H',u.mem_read(frame,32))
                            expected=[i for i,v in enumerate(codes) if v!=65535]
                            assert expected==[i for i,(a,b) in enumerate(zip(want,base)) if a!=b]
                            assert all(word(E.T.COLOURS+4*codes[i])==want[i] for i in expected)
            w(so+E.T.PADS_DOWN,0)
    print('PASS stock tracks, all five step views, both step pages, same-pad priority, stopped and Record-off cases match TPE')
    setp(E.C.TRANSPORT,0,1);setp(E.C.TRANSPORT,1,1)
    setp(word(so+0x64),1,20);w(so+E.T.PADS_DOWN,1<<20);setp(word(so+0x60),0,1);position(25)
    u.mem_write(E.T.CONT+0x264,b'\x03')
    for module in ('tmenu','mutset','stepmut'):
        slot=int(E.MAN['report'][module]['slot'],16);old=bytes(u.mem_read(slot,1))
        u.mem_write(slot,b'\x01');assert show()==base;u.mem_write(slot,old)
    w(E.C.CTRL+0x7c,0x2004e090);assert show()==base;w(E.C.CTRL+0x7c,E.T.CONT)
    for mode in (5,6,7,9):u.mem_write(E.T.CONT+0x264,bytes([mode]));assert show()==base
    u.mem_write(E.T.CONT+0x264,b'\x03')
    dimstore=word(E.C.CTRL+0x88);dimptr=E.ptr(u,dimstore,2);old=word(dimptr);w(dimptr,old|1024)
    o=show();assert o[4]==0x8d0000 and o[9]==0x8d8d8d;w(dimptr,old)
    writes=[]
    def written(uc,access,a,size,v,d):
        if 0x20000000<=a<0x20060000:writes.append((a,size))
    watch=u.hook_add(UC_HOOK_MEM_WRITE,written);show();u.hook_del(watch)
    assert all(output<=a and a+n<=output+276 for a,n in writes),writes
    print('PASS modal/expanded/non-track views unchanged; native dimming respected; only output RGB memory is written')
    print('ALL PASS')

if __name__=='__main__':main()
