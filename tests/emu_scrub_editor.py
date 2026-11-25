"""Shift + Play held (a scrub) in the Track Parameter Editor: on the Stock and Granular pages K1-K2 go to the scrub, and every light

layer shows K1-K2 green, K3-K8 dark (K3-K4 lit with the cue scrub)."""

import struct

import emu_fx_native_edges as F

from unicorn import UC_HOOK_CODE

G,E,SM=F.G,F.E,F.SM

OUT,FRAME=0x2004FA00,0x2004FD00





def main():

    u=F.setup();r=E.MAN['report'];g=r['granular']

    if not g['ui'].get('scrub_knobs'):

        print('ALL PASS');return

    s=int(g['bridge']['slot'],16);m=int(g['ui']['menu'],16);t=0

    flag=int(r['gfxmix']['scrub_flag'],16);tknob=int(r['gfxmix']['labels']['c_gx_tknob'],16)

    outer=int(r['stretch']['arm']['labels']['c_st_out'],16)

    knob=lambda k:u.mem_read(s+104+8*t+k,1)[0]

    green=lambda v:v and (v>>8)&255 and not v&0xFF00FF

    reached=[]

    u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:reached.append(a),None,tknob,tknob+1)



    def lights(scrub):

        u.mem_write(flag,bytes([scrub]));u.mem_write(FRAME,bytes(140));u.mem_write(OUT,bytes(69*4))

        E.call(u,outer,E.C.CTRL,OUT,FRAME)

        u.mem_write(flag,bytes(1))

        return list(struct.unpack('<69I',u.mem_read(OUT,69*4)))[60:68]



    cues='cues' in r['gfxmix'];cues2=r['gfxmix'].get('cues',{}).get('version')==2



    v3=r['gfxmix'].get('cues',{}).get('v3')
    def scrub_lit(k):   # with cues, K3 and K4 are lit; the held cue scrub's K2 is the scanner (amber); A322: K2-K5 lit, K5 green (sound)
        if v3:
            return green(k[0]) and all(k[1:5]) and not green(k[1]) and green(k[4]) and not any(k[5:])

        return green(k[0]) and (k[1] and not green(k[1]) if cues2 else green(k[1])) and (all(k[2:4]) if cues else not any(k[2:4])) and not any(k[4:])



    lit=g['ui'].get('scrub_lights')

    SM.sel(u,t);u.mem_write(m+E.T.O_OPEN,bytes([1]));u.mem_write(G.CONT+0x264,bytes(1))

    if lit:

        k=lights(1)

        assert scrub_lit(k),('Stock page',[hex(x) for x in k])

        print('PASS Stock page, scrubbing: K1 and K2 green, K3-K8 as the scrub draws them')



    G.pad(u,E.GP);G.unpad(u,E.GP)

    E.press(u,20);E.release(u,20)

    before=knob(0);G.knob(u,0,5)

    assert knob(0)==before+5 and not reached,'no scrub: the Granular page keeps K1'

    print('PASS no scrub: K1 turns Granular Position on the Granular page')

    for n in (0,1):

        u.mem_write(flag,bytes([1]));reached.clear();before=knob(n)

        G.knob(u,n,3)

        u.mem_write(flag,bytes(1))

        assert reached and knob(n)==before,(f'scrub: K{n+1} did not reach it',reached,knob(n),before)

    print('PASS Granular page, scrubbing: K1 and K2 go to the scrub, Granular does not change')

    if lit:

        plain,k=lights(0),lights(1)

        assert scrub_lit(k),('Granular page',[hex(x) for x in k])

        assert not scrub_lit(plain),'without a scrub the page draws its own knobs'

        print('PASS Granular page, scrubbing: K1 and K2 green, K3-K8 as the scrub draws them; its own knob lights again after')

    if cues2:   # a track press while scrubbing runs with the editor guard: every editor path sees no track view

        cr=int(r['gfxmix']['cues']['ram'],16);view=int(r['tmenu']['labels']['c_tmview'],16)

        from unicorn.arm_const import UC_ARM_REG_R0
        E.call(u,view);free=u.reg_read(UC_ARM_REG_R0)
        u.mem_write(cr+9,bytes([1]));E.call(u,view);guarded=u.reg_read(UC_ARM_REG_R0);u.mem_write(cr+9,bytes(1))
        assert free==t and guarded==8,(free,guarded)

        print('PASS a track press while scrubbing: the editor sees no track view (no open, no close); after it, the track again')

    print('ALL PASS')





if __name__=='__main__':main()

