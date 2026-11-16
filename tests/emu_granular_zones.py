"""Timing, Slice and Lock zones (DSP words and value bar); the value bar matches Stock's levels."""
import struct
import emu_fx_native_edges as F
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_PC,UC_ARM_REG_LR
G,E,SM=F.G,F.E,F.SM
TICK=0x20006f3c

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels']
    s=int(g['bridge']['slot'],16);m=int(g['ui']['menu'],16);t=0
    SM.sel(u,t);u.mem_write(m+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    def bar():
        u.mem_write(TICK,struct.pack('<I',E.u32(u,TICK)+2000))
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16));return E.out(u,int(g['ui']['labels']['c_guout'],16))[16:24]
    near=lambda a,b:all(abs((x>>sh&255)-(y>>sh&255))<=1 for x,y in zip(a,b) for sh in (0,8,16))
    store=E.u32(u,E.C.CTRL+E.T.KSTORES);dim=E.ptr(u,E.u32(u,E.C.CTRL+E.T.O_DIM),E.T.P_DIM)
    if g['ui'].get('stock_bar'):
        cases=[(1,4,v) for v in (0,30,60,63,64,65,70,127)]+[(2,2,v) for v in (0,1,3,20,127)]
        for dimmed in (0,1):
            u.mem_write(dim,struct.pack('<I',E.u32(u,dim)&~1024|(1024 if dimmed else 0)))
            stock={}
            u.mem_write(s+168+t,bytes([u.mem_read(s+168+t,1)[0]&~16]))
            for sk,gk,v in cases:
                u.mem_write(m+8,bytes([sk]));u.mem_write(E.ptr(u,store,sk-1),bytes([v]));stock[sk,v]=bar()
            G.pad(u,E.GP);G.unpad(u,E.GP)
            for sk,gk,v in cases:
                u.mem_write(m+8,bytes([gk]));u.mem_write(s+104+8*t+gk-1,bytes([v]));u.mem_write(s+404+8*t+gk-1,b'\0')
                got=bar();assert near(got,stock[sk,v]),('bar differs from Stock',dimmed,gk,v,[hex(x) for x in got],[hex(x) for x in stock[sk,v]])
                if v in (0,64) and (gk==4)==(v==64):assert got==stock[sk,v],('rest pads not exactly Stock',dimmed,gk,v)
        u.mem_write(dim,struct.pack('<I',E.u32(u,dim)&~1024))
        print('PASS value bar matches Stock: centre and rest pads exact, others within 1 of 255, normal and dimmed')
    z=g.get('easy_zones')
    if not z:print('ALL PASS');return
    G.pad(u,E.GP);G.unpad(u,E.GP);assert u.mem_read(s+168+t,1)[0]&16
    def words(timing,slice_,lock):
        u.mem_write(s+236+7*t+1,bytes([timing]));u.mem_write(s+236+7*t+3,bytes([slice_]));u.mem_write(s+236+7*t+4,bytes([lock]))
        writes={};flags=E.u32(u,s+184);u.mem_write(s+184,struct.pack('<I',flags|3))
        def ret(uc,v=0):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        def dsp(uc,a,n,d):writes[uc.reg_read(UC_ARM_REG_R0)]=uc.reg_read(UC_ARM_REG_R1);ret(uc)
        hooks=[u.hook_add(UC_HOOK_CODE,dsp,None,K['c_gr_dsp_write'],K['c_gr_dsp_write']+1),
               u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:ret(uc),None,K['c_gr_shared_read'],K['c_gr_shared_read']+1),
               u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:ret(uc),None,0x08040814,0x08040815)]
        u.mem_write(s+200,struct.pack('<I',1<<t));E.call(u,K['c_gr_runtime_frame'],s,1,0)
        for h in hooks:u.hook_del(h)
        u.mem_write(s+184,struct.pack('<I',flags));pool=0x2400+256*t
        return writes[pool+1]&0x3ffff,writes[pool+13],writes[pool+7]
    intervals=[words(66+8*i,0,0)[0] for i in range(8)]
    bpm=round(30000*24/intervals[0])
    assert intervals==[30000*q//bpm for q in z['timing_quarter_ticks']],('Timing zones',bpm,intervals)
    word7=z.get('slice_word')==7
    for value in list(range(0,128,8))+[7,15,127]:
        _,flags,zone=words(64,value,0);count=z['slices'][value] if word7 else z['slices'][value>>4]
        got=(zone>>8&31) if word7 else (flags>>15&15)
        assert got==(count-1 if count else 0),('Slice zone',value,got)
        if word7:assert zone&127==127 and not flags>>15,('zone or old slice bits',value)
    for value,amount in ((0,0),(42,0),(43,96),(84,96),(85,127),(127,127)):
        assert (words(64,0,value)[1]>>8&127)==amount,('Lock zone',value)
    names='/'.join(str(n) if n else 'off' for n in dict.fromkeys(z['slices']))
    print(f'PASS Timing zones 1, 2/3, 1/2, 1/3, 1/4, 1/6, 1/8, 1/12 step; Slice {names}; Lock off/loose/locked by thirds')
    E.press(u,19);E.release(u,19)
    coloured=lambda b:[i for i,x in enumerate(b) if x and len({x>>16&255,x>>8&255,x&255})>1]
    white=lambda b:[i for i,x in enumerate(b) if x and len({x>>16&255,x>>8&255,x&255})==1]
    if z.get('zone_pads'):
        for value in (0,7,8,15)+tuple(range(16,128,16))+(127,):
            u.mem_write(s+236+7*t+3,bytes([value]));u.mem_write(m+8,bytes([5]));b=bar()
            want=[] if value<8 else [value>>4]
            assert coloured(b)==want and white(b)==([0] if value<8 else []),('Slice display',value,[hex(x) for x in b])
        for value,pad in ((0,None),(42,None),(43,3),(84,3),(85,7),(127,7)):
            u.mem_write(s+236+7*t+4,bytes([value]));u.mem_write(m+8,bytes([6]));b=bar()
            assert coloured(b)==([] if pad is None else [pad]) and white(b)==([0] if pad is None else []),('Lock display',value,[hex(x) for x in b])
        print('PASS Slice and Lock light one pad: off pad 17 white; Slice 2 pad 17 colour, 3..32 pads 18..24; Lock loose pad 20, locked pad 24')
    else:
        for value in range(0,128,16):
            u.mem_write(s+236+7*t+3,bytes([value]));u.mem_write(m+8,bytes([5]));b=bar()
            assert len(coloured(b))==((value>>4)+1 if value>>4 else 0),('Slice display',value,[hex(x) for x in b])
        for value,pads in ((0,0),(60,4),(127,8)):
            u.mem_write(s+236+7*t+4,bytes([value]));u.mem_write(m+8,bytes([6]));b=bar()
            assert len(coloured(b))==pads,('Lock display',value,[hex(x) for x in b])
        print('PASS Slice lights pads up to its zone; Lock fills none, half or all of the bar')
    if g.get('full_freeze'):freeze(u,s,K,t)
    print('ALL PASS')

def freeze(u,s,K,t):
    pool=0x2400+256*t;cfg=s+168+t;BPM,TICKS=0x20001f00,0x20001f04
    def ret(uc,v=0):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    def frame(dirty,tick=None):
        writes={};flags=E.u32(u,s+184);u.mem_write(s+184,struct.pack('<I',flags|3))
        def dsp(uc,a,n,d):writes[uc.reg_read(UC_ARM_REG_R0)]=uc.reg_read(UC_ARM_REG_R1);ret(uc)
        def getter(uc,a,n,d):ret(uc,BPM if uc.reg_read(UC_ARM_REG_R0)==0x20012788 else TICKS)
        hooks=[u.hook_add(UC_HOOK_CODE,dsp,None,K['c_gr_dsp_write'],K['c_gr_dsp_write']+1),
               u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:ret(uc),None,K['c_gr_shared_read'],K['c_gr_shared_read']+1),
               u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:ret(uc),None,0x08040814,0x08040815),
               u.hook_add(UC_HOOK_CODE,getter,None,0x0803fc6c,0x0803fc6d)]
        if tick is not None:u.mem_write(TICKS,struct.pack('<I',tick))
        u.mem_write(s+200,struct.pack('<I',dirty));E.call(u,K['c_gr_runtime_frame'],s,1,0)
        for h in hooks:u.hook_del(h)
        u.mem_write(s+184,struct.pack('<I',flags));return writes
    u.mem_write(BPM,bytes([120]));u.mem_write(TICKS,struct.pack('<I',1))
    u.mem_write(s+12*t+8,bytes([2]));u.mem_write(s+12*t+10,bytes([0]))   # owner: Texture, settled
    u.mem_write(s+104+8*t+3,bytes([100]));u.mem_write(s+404+8*t+3,bytes(1))  # Scan right: a slice every 8 ticks
    u.mem_write(s+104+8*t+4,bytes([40]));u.mem_write(s+404+8*t+4,bytes(1))   # Position scatter
    u.mem_write(s+236+7*t+3,bytes([72]));u.mem_write(s+236+7*t+4,bytes([0]))  # 8 slices, Lock off
    slice_word=7 if E.MAN['report']['granular']['easy_zones'].get('slice_word')==7 else 13
    for frozen in (0,1):
        u.mem_write(cfg,bytes([u.mem_read(cfg,1)[0]&~64|(64 if frozen else 0)]))
        w=frame(1<<t)
        assert w[pool+11]==40*16,('Freeze changed Position scatter',frozen,w[pool+11])
        assert (w[pool+13]>>8&127)==(127 if frozen else 0),('Freeze lock',frozen)
        if frozen:assert w[pool+6]==0,'Freeze kept the playhead moving'
        stepped=[t8 for t8 in (8,16,24,32) if pool+slice_word in frame(0,t8)]
        assert stepped==([] if frozen else [8,16,24,32]),('slice steps while frozen' if frozen else 'slice steps missing',stepped)
    # Frozen, the knobs still reach the engine; Position scatter widens the held area.
    u.mem_write(cfg,bytes([u.mem_read(cfg,1)[0]|64]))
    for knob,word,value in ((0,4,90),(1,3,80),(5,9,30),(4,11,100)):
        before=frame(1<<t)[pool+word];u.mem_write(s+104+8*t+knob,bytes([value]))
        assert frame(1<<t)[pool+word]!=before,('control dead while frozen',knob)
    u.mem_write(cfg,bytes([u.mem_read(cfg,1)[0]&~64]))
    print('PASS while frozen, Position, Size, Pitch scatter and Position scatter (the held width) still change the engine')
    print('PASS Freeze: playhead still, scatter kept, every random choice locked, slice step held; released, all move again')
if __name__=='__main__':main()
