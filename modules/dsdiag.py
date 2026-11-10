"""AD002: keyed, fixed-window core-0 X/Y canaries and DSP->ITCM decoder proof.

No SD writes, sample-memory writes, live parameter/sequencer hooks or DSP program
changes. Commands 40..43 extend AD001, whose protocol stays intact. Each command
holds the stock DSP service lock, then checks private RAM/startup/upload guards.
Fill/check are bounded 32-word chunks. Benchmark uses fixed ROM fixtures only.
"""
import struct
import acdiag as A
from thumb import (Asm, add_sp_imm, adds_imm8, adds_reg, b, b_cond, b_w, bl,
                   cmp_imm, cmp_reg, eors_reg, h, ldr_imm, ldr_sp, ldrb_imm,
                   lsls_imm, lsrs_imm, mov_reg, movs_imm, movt, movw,
                   orrs_reg, pop_list, push_list, raw, str_imm, str_sp,
                   strb_imm, sub_sp_imm, subs_imm8, subs_reg)

KEY = 0x44535032  # "DSP2"; separate key from AD001 canary operations
FORMAT = 0xAD000002
BANKS = (0x4000, 0xA800)  # core 0 X:$4000..40FF, Y:$2800..28FF
WORDS, CHUNK = 256, 32
PATTERN = 0x5A1200
INPUT, INPUT_END = 0x2200, 0x2400
LOCK, UNLOCK, LOCK_PTR, WRITE_PTR = 0x08029C8C, 0x08030EB8, 0x20003688, 0x20003684
RD16, WR16 = 0x08031268, 0x080311DA  # unlocked low-level routines; lock held by caller


def code(base, ext, guards, consecutive=False):
    a=Asm(base); E=a.emit; serial=[0]
    inverse=dict(eq='ne',ne='eq',lo='hs',hs='lo',hi='ls',ls='hi')
    def imm(r,v):E(movw,r,v&0xffff);E(movt,r,v>>16)
    def far(label,cond):
        serial[0]+=1;s=f'z{serial[0]}'
        E(b_cond,s,inverse[cond]);E(b_w,label);a.label(s)
    def outreg(r):E(mov_reg,1,r);E(mov_reg,0,6);E(bl,ext['c_p32']);E(mov_reg,6,0)
    def out(v):imm(1,v);outreg(1)
    def sf(off):E(ldr_sp,1,off);outreg(1)
    def arg(off):E(mov_reg,0,4);E(adds_imm8,0,off);E(bl,ext['c_g32'])
    def pattern():
        # r5 host address -> r1 = complete 24-bit pattern, shifted for stock host accessor
        imm(1,PATTERN);E(eors_reg,1,5);E(lsls_imm,1,1,8)
    def rd():
        E(movs_imm,0,0);E(mov_reg,1,5);E(bl,RD16)
        # An address-setting read invalidates the host's auto-increment write cache.
        imm(1,WRITE_PTR);E(movw,2,0xffff);E(str_imm,2,1,0)
    def wr():E(movs_imm,0,0);E(mov_reg,2,5);E(bl,WR16)
    def tick():imm(0,A.CYCCNT);E(ldr_imm,0,0,0)
    def start():tick();E(str_sp,0,52)
    def elapsed(off):tick();E(ldr_sp,1,52);E(subs_reg,0,0,1);E(str_sp,0,off)
    def trace_start():
        for address,off in ((A.DEMCR,40),(A.DWTCTRL,44),(A.LSR,48)):
            imm(0,address);E(ldr_imm,1,0,0);E(str_sp,1,off)
        imm(0,A.DEMCR);E(ldr_imm,1,0,0);imm(2,1<<24);E(orrs_reg,1,2);E(str_imm,1,0,0)
        imm(0,A.LAR);imm(1,0xC5ACCE55);E(str_imm,1,0,0)
        imm(0,A.DWTCTRL);E(ldr_imm,1,0,0);E(movs_imm,2,1);E(orrs_reg,1,2);E(str_imm,1,0,0)
        E(raw,h(0xF3BF)+h(0x8F4F));E(movs_imm,0,1);E(str_sp,0,92)
    def trace_restore(prefix):
        imm(0,A.DWTCTRL);E(ldr_sp,1,44);E(str_imm,1,0,0)
        E(ldr_sp,1,48);E(lsls_imm,1,1,30);E(b_cond,prefix,'pl');imm(0,A.LAR);E(movs_imm,1,0);E(str_imm,1,0,0)
        a.label(prefix);imm(0,A.DEMCR);E(ldr_sp,1,40);E(str_imm,1,0,0)

    a.label('c_dscommand')
    E(cmp_imm,0,40);far('fallback','lo');E(cmp_imm,0,43);far('fallback','hi')
    E(push_list,[4,5,6,7],lr=True);E(sub_sp_imm,108)
    E(mov_reg,5,0);E(mov_reg,4,1);E(mov_reg,6,1)
    E(movs_imm,0,0)
    for off in range(0,108,4):E(str_sp,0,off)
    E(str_sp,5,100)
    E(cmp_imm,5,40);far('status','eq')
    arg(0);imm(1,KEY);E(cmp_reg,0,1);far('badkey','ne')
    arg(8);E(cmp_imm,0,1);far('badarg','hi')
    E(movw,5,BANKS[0]);E(cmp_imm,0,0);E(b_cond,'bankok','eq');E(movw,5,BANKS[1])
    a.label('bankok');E(str_sp,5,4)
    arg(16);E(str_sp,0,8)
    E(ldr_sp,1,100);E(cmp_imm,1,43);far('benchargs','eq')
    E(cmp_imm,0,WORDS//CHUNK);far('badarg','hs')
    E(lsls_imm,0,0,5);E(adds_reg,5,5,0);E(str_sp,5,4)
    E(b_w,'acquire')
    a.label('benchargs')
    E(cmp_imm,0,len(ext['fixtures']));far('badarg','hs')
    E(lsls_imm,1,0,1);E(adds_reg,0,0,1);E(lsls_imm,0,0,2)
    imm(1,ext['table']);E(adds_reg,0,0,1)
    for off,dest in ((0,16),(4,20),(8,24)):
        E(ldr_imm,1,0,off);E(str_sp,1,dest)
    E(ldr_sp,0,20);E(ldr_sp,1,16);E(subs_reg,0,0,1);E(str_sp,0,28)
    E(adds_imm8,0,2);E(movs_imm,1,3);E(raw,h(0xFBB0)+h(0xF0F1))  # udiv r0,r0,r1
    E(movw,1,WORDS);E(cmp_reg,0,1);far('badarg','hi');E(str_sp,0,32)
    E(bl,ext['c_acusable']);E(cmp_imm,0,0);far('baditcm','ne')
    for addr in (A.START,A.START+4):
        imm(0,addr);E(ldr_imm,0,0,0);imm(1,A.PATTERN^addr);E(cmp_reg,0,1);far('unarmed','ne')
    E(b_w,'acquire')
    a.label('status')
    out(0);out(0xAD000003 if consecutive else FORMAT);out(BANKS[0]);out(BANKS[1]);out(WORDS);out(CHUNK);out(INPUT);out(INPUT_END)
    E(bl,'c_dsguard');outreg(0);E(b_w,'return')
    a.label('acquire')
    imm(0,LOCK_PTR);E(str_sp,0,0);E(bl,LOCK)
    E(bl,'c_dsguard');E(cmp_imm,0,0);far('lockederror','ne')
    E(ldr_sp,0,100);E(cmp_imm,0,43);far('bench','eq')
    E(movs_imm,7,CHUNK);E(ldr_sp,5,4)
    a.label('preflight')
    rd();E(mov_reg,2,0);pattern();E(cmp_reg,2,1);E(b_cond,'checkedword','eq')
    E(ldr_sp,0,100);E(cmp_imm,0,41);E(b_cond,'canarybad','ne')
    E(cmp_imm,2,0);E(b_cond,'checkedword','eq')
    E(movs_imm,0,11);E(b_w,'lockederror')  # refuse overwriting nonzero non-canary words
    a.label('canarybad')
    E(ldr_sp,0,80);E(adds_imm8,0,1);E(str_sp,0,80);E(cmp_imm,0,1);E(b_cond,'checkedword','ne')
    E(str_sp,5,84);E(lsrs_imm,2,2,8);E(str_sp,2,88)
    a.label('checkedword')
    E(adds_imm8,5,1);E(subs_imm8,7,1);E(b_cond,'preflight','ne')
    E(ldr_sp,0,100);E(cmp_imm,0,41);E(b_cond,'chunkdone','ne')
    E(ldr_sp,5,4);E(movs_imm,7,CHUNK)
    a.label('fillloop')
    pattern();wr();E(adds_imm8,5,1);E(subs_imm8,7,1);E(b_cond,'fillloop','ne')
    a.label('chunkdone')
    E(bl,'c_dsunlock');out(0);sf(4);out(CHUNK)
    for off in (80,84,88):sf(off)
    E(b_w,'return')

    a.label('bench')
    trace_start();tick();E(str_sp,0,96)
    # Do not conceal pre-existing interference by restoring someone else's data.
    imm(0,INPUT);imm(1,INPUT_END);imm(3,A.PATTERN)
    a.label('inputpreflight')
    E(ldr_imm,2,0,0);E(eors_reg,2,3);E(cmp_reg,2,0);far('inputchanged','ne')
    E(adds_imm8,0,4);E(cmp_reg,0,1);E(b_cond,'inputpreflight','lo')
    E(ldr_sp,7,32);E(cmp_imm,7,0);far('preflightdone','eq')
    E(ldr_sp,5,4)
    a.label('benchpreflight')
    rd();E(mov_reg,2,0);pattern();E(cmp_reg,2,1);far('notcanary','ne')
    E(adds_imm8,5,1);E(subs_imm8,7,1);E(b_cond,'benchpreflight','ne')
    a.label('preflightdone')
    E(ldr_sp,4,16);E(ldr_sp,5,4);E(ldr_sp,7,32);start()
    E(cmp_imm,7,0);far('writedone','eq')
    a.label('writeloop')
    # Read 0..3 valid ROM bytes, pad last DSP word with FF without reading past end.
    E(movs_imm,3,0);E(movs_imm,1,0)
    for n in range(3):
        E(ldr_sp,0,20);E(cmp_reg,4,0);E(b_cond,f'pad{n}','hs')
        E(ldrb_imm,0,4,0);E(adds_imm8,4,1);E(b,f'byte{n}')
        a.label(f'pad{n}');E(movs_imm,0,255)
        a.label(f'byte{n}')
        E(lsls_imm,0,0,8*n);E(orrs_reg,1,0)
    E(lsls_imm,1,1,8);wr();E(adds_imm8,5,1);E(subs_imm8,7,1);E(b_cond,'writeloop','ne')
    a.label('writedone');elapsed(56)
    imm(4,INPUT);E(ldr_sp,5,4);E(ldr_sp,7,32);start()
    E(cmp_imm,7,0);E(b_cond,'readdone','eq')
    if consecutive:
        # Same stock SPI setup/address/read-next commands as RD16, one CS interval.
        # A final read-next may prime one extra word: fixtures max 129 < 256 words.
        for fn in (0x08046414,0x08046534,0x08031020,0x08031048):
            E(movs_imm,0,0);E(bl,fn)
        E(movs_imm,0,0x80);E(lsrs_imm,1,5,8)
        E(mov_reg,2,5);E(raw,h(0xB2D2));E(bl,0x08046510)  # uxtb r2,r2
    a.label('readloop')
    if consecutive:
        E(movs_imm,0,0x40);E(movs_imm,1,0);E(movs_imm,2,0);E(bl,0x08046510)
    else:
        rd()
    E(lsrs_imm,0,0,8)
    for n in range(3):
        E(strb_imm,0,4,n)
        if n!=2:E(lsrs_imm,0,0,8)
    E(adds_imm8,4,3);E(adds_imm8,5,1);E(subs_imm8,7,1);E(b_cond,'readloop','ne')
    if consecutive:
        E(bl,0x08046414)
        for fn in (0x0803107A,0x08031032):E(movs_imm,0,0);E(bl,fn)
        imm(1,WRITE_PTR);E(movw,2,0xffff);E(str_imm,2,1,0)
    a.label('readdone');elapsed(60)
    # Restore only the DSP cells whose original canary was verified before writing.
    E(ldr_sp,5,4);E(ldr_sp,7,32);E(cmp_imm,7,0);E(b_cond,'restored','eq')
    a.label('restoreloop')
    pattern();wr();E(adds_imm8,5,1);E(subs_imm8,7,1);E(b_cond,'restoreloop','ne')
    a.label('restored');tick();E(ldr_sp,1,96);E(subs_reg,0,0,1);E(str_sp,0,96);E(bl,'c_dsunlock')
    # Decoder runs after releasing the DSP lock; stock writers are not blocked by decoding.
    start();imm(0,INPUT);E(ldr_sp,1,28);E(adds_reg,1,1,0);imm(2,A.OUTPUT);E(bl,ext['c_acdecode']);E(str_sp,0,76);elapsed(64)
    imm(4,INPUT);E(ldr_sp,5,16);E(ldr_sp,7,28);E(cmp_imm,7,0);E(b_cond,'comparedbytes','eq')
    a.label('comparebytes')
    E(ldrb_imm,0,4,0);E(ldrb_imm,1,5,0);E(cmp_reg,0,1);E(b_cond,'byteok','eq')
    E(ldr_sp,0,68);E(adds_imm8,0,1);E(str_sp,0,68)
    a.label('byteok');E(adds_imm8,4,1);E(adds_imm8,5,1);E(subs_imm8,7,1);E(b_cond,'comparebytes','ne')
    a.label('comparedbytes')
    imm(4,A.OUTPUT);E(ldr_sp,5,24);E(movs_imm,7,96)
    a.label('comparewords')
    E(ldr_imm,0,4,0);E(ldr_imm,1,5,0);E(cmp_reg,0,1);E(b_cond,'wordok','eq')
    E(ldr_sp,0,72);E(adds_imm8,0,1);E(str_sp,0,72)
    a.label('wordok');E(adds_imm8,4,4);E(adds_imm8,5,4);E(subs_imm8,7,1);E(b_cond,'comparewords','ne')
    # Restore temporary ITCM input window to AD001's previously initialized canary pattern.
    imm(0,INPUT);imm(1,INPUT_END);imm(3,A.PATTERN)
    a.label('itrestore')
    E(mov_reg,2,0);E(eors_reg,2,3);E(str_imm,2,0,0);E(adds_imm8,0,4);E(cmp_reg,0,1);E(b_cond,'itrestore','lo')
    trace_restore('unlocked')
    out(0)
    for off in (4,8,28,32,56,60,64,68,72,76,96):sf(off)
    E(b_w,'return')
    a.label('notcanary');E(movs_imm,0,12);E(b,'lockederror')
    a.label('inputchanged');E(movs_imm,0,14);E(b,'lockederror')
    a.label('lockederror');E(str_sp,0,104)
    E(ldr_sp,0,92);E(cmp_imm,0,0);E(b_cond,'errortraceok','eq')
    trace_restore('errorunlocked')
    a.label('errortraceok');E(bl,'c_dsunlock');E(ldr_sp,0,104);E(b,'error')
    for label,value in (('badkey',1),('badarg',5),('baditcm',6),('unarmed',13)):
        a.label(label);E(movs_imm,0,value);E(b,'error')
    a.label('error');outreg(0)
    a.label('return');E(mov_reg,0,6);E(add_sp_imm,108);E(pop_list,[4,5,6,7],pc=True)
    a.label('fallback');E(b_w,ext['c_accommand'])
    a.label('c_dsunlock')
    E(push_list,[4],lr=True);E(sub_sp_imm,8);imm(0,WRITE_PTR);E(movw,1,0xffff);E(str_imm,1,0,0)
    imm(0,LOCK_PTR);E(str_sp,0,0);E(mov_reg,0,13);E(bl,UNLOCK);E(add_sp_imm,8);E(pop_list,[4],pc=True)
    a.label('c_dsguard')
    imm(0,guards['magic_addr']);E(ldr_imm,0,0,0);imm(1,guards['magic']);E(cmp_reg,0,1);E(b_cond,'guardram','ne')
    imm(0,guards['ready_addr']);E(ldrb_imm,0,0,0);E(cmp_imm,0,guards['ready']);E(b_cond,'guardready','ne')
    imm(0,guards['wait_addr']);E(ldrb_imm,0,0,0);E(cmp_imm,0,200);E(b_cond,'guardready','lo')
    imm(0,guards['upload']);E(ldrb_imm,0,0,0);E(cmp_imm,0,0);E(b_cond,'guardupload','ne')
    E(movs_imm,0,0);E(raw,h(0x4770))
    for label,value in (('guardram',7),('guardready',8),('guardupload',9)):
        a.label(label);E(movs_imm,0,value);E(raw,h(0x4770))
    return a.assemble()


def install(img,report,base_addr,consecutive=False):
    import rhbuild,rh_fw,rhstate,cthresh
    rd={k:int(v,16) for k,v in report['rdiag']['labels'].items()}
    ac=report['acdiag'];labels={k:int(v,16) for k,v in ac['labels'].items()}
    if consecutive:
        # Final stock read-next can prime one additional cell. Reserve it in-window.
        assert all((f['compressed_bytes']+2)//3 < WORDS for f in ac['fixtures'])
    oldsite=int(ac['unknown_site'],16)
    assert rhbuild.bl_target(img,oldsite)==labels['c_accommand']
    # Independent descriptor table points to AD001's fixed ROM fixtures.
    table=b''.join(struct.pack('<III',int(f['source'],16),int(f['end'],16),int(f['expected'],16)) for f in ac['fixtures'])
    ext={**rd,**labels,'table':base_addr,'fixtures':ac['fixtures']}
    guards=dict(magic_addr=rhstate.ST,magic=rhstate.MAGIC,ready_addr=rhstate.ST+rhstate.OFF['cthresh'][0]+1,
                ready=cthresh.READY,wait_addr=rhstate.ST+rhstate.OFF['spwait'][0],upload=int(report['upguard']['flag'],16))
    generated,ls=code(base_addr+len(table),ext,guards,consecutive=consecutive)
    img+=bytes([0xff])*(base_addr-rh_fw.APP_BASE-len(img))+table+generated
    while len(img)%4:img.append(0xff)
    rhbuild.patch(img,oldsite,f"bl #{labels['c_accommand']:#x}",bl(oldsite,ls['c_dscommand']))
    report['dsdiag']=dict(format=hex(0xAD000003 if consecutive else FORMAT),consecutive_read=consecutive,key=hex(KEY),commands=dict(status=40,fill=41,check=42,bench=43),
                         core=0,host_banks=[hex(v) for v in BANKS],words=WORDS,chunk_words=CHUNK,
                         regions=[dict(core=0,space='x',start='0x4000',words=WORDS),dict(core=0,space='y',start='0x2800',words=WORDS)],
                         itcm_input=[hex(INPUT),hex(INPUT_END)],guards={k:hex(v) for k,v in guards.items()},
                         stock_recording_unchanged=True,sd_writes=False,sample_memory_writes=False,
                         dsp_program_unchanged=True,proof_only=True,code_bytes=len(generated),
                         labels={k:hex(v) for k,v in ls.items() if k.startswith('c_')})
