"""AD004 volatile single-lane proof; requires an isolated Zig 0.13 ARM compiler.
Generated code is cached with source/config/compiler hash, like DSP asm-cache.
Never installs AD001-3 canary commands over the runtime ITCM/cache windows.
"""
from pathlib import Path
import hashlib,json,os,struct,subprocess
from thumb import Asm,b_w,bl,h,raw,mov_reg,push_list,add_sp_imm,sub_sp_imm
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(__file__).with_suffix('.c')
CACHE=ROOT/'builds/autoprot-cache.json'
KEY=0x41505431

def elf_image(path,origin):
    data=path.read_bytes();header=struct.unpack_from('<16sHHIIIIIHHHHHH',data)
    shoff,entsize,count,shstr=header[6],header[11],header[12],header[13]
    sections=[struct.unpack_from('<10I',data,shoff+i*entsize) for i in range(count)]
    chunks=[];labels={}
    for s in sections:
        _,kind,flags,address,offset,size,link,info,align,entry=s
        if flags&2 and size:
            assert kind!=8,'Unexpected BSS in ROM-only kernel'
            assert address>=origin and address+size<0x08080000
            chunks.append((address,data[offset:offset+size]))
        if kind==2:
            st=sections[link];strings=data[st[4]:st[4]+st[5]]
            for i in range(offset,offset+size,entry):
                name,value,sz,typ,other,index=struct.unpack_from('<IIIBBH',data,i)
                name=strings[name:].split(b'\0',1)[0].decode()
                if name.startswith('c_ap') and index:labels[name]=value&~1
    end=max(a+len(b) for a,b in chunks);image=bytearray(b'\xff'*(end-origin))
    for a,b in chunks:image[a-origin:a-origin+len(b)]=b
    return bytes(image),labels

def compile_kernel(origin,config):
    definitions='\n'.join(f'#define {k} 0x{v:x}u' for k,v in sorted(config.items()))+'\n'
    digest=hashlib.sha256(SOURCE.read_bytes()+definitions.encode()+str(origin).encode()+b'zig0.13-v4').hexdigest()
    cache=json.loads(CACHE.read_text()) if CACHE.exists() else {}
    if digest in cache:return bytes.fromhex(cache[digest]['code']),cache[digest]['labels']
    work=ROOT/'buildtmp/autoprot';work.mkdir(parents=True,exist_ok=True)
    (work/'autoprot_config.h').write_text(definitions)
    link=work/'kernel.ld';link.write_text(f'SECTIONS {{ . = 0x{origin:x}; .text : {{ KEEP(*(.text*)) KEEP(*(.rodata*)) }} /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }} }}')
    zig=Path(os.environ.get('RH_ZIG',ROOT/'buildtmp/zig-toolchain/ziglang/zig.exe'))
    env=os.environ.copy();env['ZIG_GLOBAL_CACHE_DIR']=str(work/'zig-global');env['ZIG_LOCAL_CACHE_DIR']=str(work/'zig-local')
    args=[str(zig),'cc','-target','thumb-freestanding-eabi','-mcpu=cortex_m7','-mthumb','-Oz','-g','-fno-lto','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fno-stack-protector','-nostdlib','-I',str(work),str(SOURCE),'-Wl,-T,'+str(link),'-Wl,--entry=c_apcommand','-o',str(work/'kernel.elf')]
    p=subprocess.run(args,env=env,capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    code,labels=elf_image(work/'kernel.elf',origin)
    cache[digest]=dict(code=code.hex(),labels=labels,source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),compiler='zig0.13.0')
    CACHE.write_text(json.dumps(cache,indent=2)+'\n')
    return code,labels

def install(img,report,base_addr,fix_record_touch=False,audit_batch=False,import_locks=False):
    import rhbuild,rhstate,cthresh,trackreset,tmenu
    assert 'acdiag' not in report and 'dsdiag' not in report
    assert 'autoprot' in rhstate.OFF
    flag=rhstate.ST+rhstate.OFF['autoprot'][0]
    sp={k:int(v,16) for k,v in report['stockplus']['labels'].items()}
    tm={k:int(v,16) for k,v in report['tmenu']['labels'].items()}
    rd={k:int(v,16) for k,v in report['rdiag']['labels'].items()}
    put=int(report['syncbar']['labels']['c_uput'],16)
    def take(a,n=4):return bytes(img[a-rhbuild.BASE:a-rhbuild.BASE+n])
    prefix=bytearray();tramps={}
    heads=[('GET_TRAMP',sp['c_spval']),('RESET_TRAMP',0x080552f6)]
    if audit_batch:heads.append(('PREVIEW_TRAMP',0x0805ce84))
    for name,addr in heads:
        head=take(addr);ins=list(rhbuild.MD.disasm(head,addr))
        assert sum(i.size for i in ins)==4 and all(i.mnemonic in ('push','push.w','mov','movs') for i in ins),[(i.mnemonic,i.op_str) for i in ins]
        tramps[name]=base_addr+len(prefix);prefix+=head+b_w(base_addr+len(prefix)+4,addr+4)
    prevload=rhbuild.bw_target(img,trackreset.LOAD)
    # Preserve all arguments, stack arguments and callee saved registers on load.
    load_stub=base_addr+len(prefix)
    # Reserve wrapper for after C labels are known (24 bytes).
    prefix+=b'\x00\xbf'*12
    instructions=list(rhbuild.MD.disasm(take(tm['c_tmview'],tm['c_tmown']-tm['c_tmview']),tm['c_tmview']))
    clears=[]
    for i,x in enumerate(instructions):
        if x.mnemonic in ('strb.w','strb') and x.op_str in [f'r{r}, [r3, #0x{rhstate.OFF["tmenu"][0]+tmenu.O_CLRR:x}]' for r in (0,)] and i and instructions[i-1].mnemonic=='movs' and instructions[i-1].op_str == 'r0, #0' and instructions[i+1].mnemonic=='b':
            clears.append((x.address,x.bytes,base_addr+len(prefix)))
            prefix+=b'\x00\xbf'*20
    assert len(clears)==3,clears
    while len(prefix)%4:prefix.append(255)
    origin=base_addr+len(prefix)
    config=dict(FLAG_ADDR=flag,PRIVATE_MAGIC_ADDR=rhstate.ST,PRIVATE_MAGIC=rhstate.MAGIC,
      READY_ADDR=rhstate.ST+rhstate.OFF['cthresh'][0]+1,READY_VALUE=cthresh.READY,
      WAIT_ADDR=rhstate.ST+rhstate.OFF['spwait'][0],UPLOAD_ADDR=int(report['upguard']['flag'],16),
      TM_HELD=tm['c_tmheld'],UI_PUT=put,SP_WRITE=sp['c_spw'],PITCH_AMOUNT_Y=report['stockplus'].get('pitch_amount_y',0x1710),
      GET32=rd['c_g32'],PUT32=rd['c_p32'],**tramps)
    # Stock+ report's y base is the authoritative relocated DSP block.
    import stockplus,pitchmod
    config['PITCH_AMOUNT_Y']=stockplus.YB+pitchmod.OFF_A
    if fix_record_touch:config["FIX_RECORD_TOUCH"]=1
    if import_locks:
        assert audit_batch
        config['IMPORT_LOCKS']=1
    if audit_batch:
        import countin
        prev_led=rhbuild.bl_target(img,countin.LED_CALLS[0])
        assert all(rhbuild.bl_target(img,site)==prev_led for site in countin.LED_CALLS)
        config.update(AUDIT_BATCH=1,PREV_LED=prev_led,TM_SLOT=int(report['tmenu']['slot'],16),TM_VIEW=tm['c_tmview'],TM_STEP_PTR=tmenu.CONT+tmenu.STEPOBJ)
    code,labels=compile_kernel(origin,config)
    def wrapper(at,body,target):
        a=Asm(at);E=a.emit
        E(push_list,[0,1,2,3,4],lr=True);E(bl,target)
        # Restore LR without changing the caller's arguments.
        E(raw,h(0xe8bd)+h(0x401f));E(raw,body)
        return a.assemble()[0]
    load_code=wrapper(load_stub,b_w(load_stub+10,prevload),labels['c_apload_disable' if audit_batch else 'c_apdisable'])
    assert len(load_code)==14
    prefix[load_stub-base_addr:load_stub-base_addr+len(load_code)]=load_code
    for site,store,at in clears:
        a=Asm(at);E=a.emit;E(push_list,list(range(8)),lr=True);E(sub_sp_imm,4)
        E(mov_reg,0,6);E(mov_reg,1,7);E(bl,labels['c_apclear']);E(add_sp_imm,4)
        E(raw,h(0xe8bd)+h(0x40ff));E(raw,store);E(raw,h(0x4770));c=a.assemble()[0]
        assert len(c)<=40;prefix[at-base_addr:at-base_addr+len(c)]=c
        rhbuild.patch(img,site,'|'.join(rhbuild.disasm(store,site)),bl(site,at))
    # New standalone command handler replaces only the existing unknown response.
    found=[]
    for at in range(rd['c_rdcmd'],rd['c_rdcmd']+0x180,2):
        ins=list(rhbuild.MD.disasm(take(at,16),at))
        if len(ins)==5 and [(i.mnemonic,i.op_str) for i in ins[:3]]==[('mov','r0, r1'),('movw','r1, #0xffff'),('movt','r1, #0xffff')] and ins[3].mnemonic=='bl' and ins[4].mnemonic=='b':found.append((at,int(ins[4].op_str.removeprefix('#'),16)))
    assert len(found)==1
    site,send=found[0]
    rhbuild.patch(img,site,'|'.join(rhbuild.disasm(take(site,16),site)),bl(site,labels['c_apcommand'])+b_w(site+4,send)+h(0xbf00)*4)
    entries=[('c_apget',sp['c_spval']),('c_apreset',0x080552f6)]
    if audit_batch:entries.append(('c_appreview',0x0805ce84))
    for name,addr in entries:
        rhbuild.patch(img,addr,'|'.join(rhbuild.disasm(take(addr),addr)),b_w(addr,labels[name]))
    rhbuild.patch(img,0x080552ac,'bl #0x8055324',bl(0x080552ac,labels['c_applay']))
    rhbuild.patch_word(img,0x08067894,0x0804946d,labels['c_aprec_listener']|1)
    rhbuild.patch(img,trackreset.LOAD,f'b.w #{prevload:#x}',b_w(trackreset.LOAD,load_stub))
    # Capture only the UI writes, not all project setters/reset paths.
    end=tm['c_tmown'];start=tm['c_tmview'];sites=[]
    for x in rhbuild.MD.disasm(take(start,end-start),start):
        if x.mnemonic=='bl' and int(x.op_str.removeprefix('#'),16)==put:sites.append(x.address)
    assert len(sites)==3,sites
    for at in sites:rhbuild.patch(img,at,f'bl #{put:#x}',bl(at,labels['c_apmanual']))
    if audit_batch:
        for site in countin.LED_CALLS:rhbuild.patch(img,site,f'bl #{prev_led:#x}',bl(site,labels['c_appedled']))
    img+=b'\xff'*(base_addr-rhbuild.BASE-len(img))+prefix+code
    while len(img)%4:img.append(255)
    report['autoprot']=dict(proof_only=True,fix_record_touch=fix_record_touch,audit_batch=audit_batch,import_locks=import_locks,volatile=True,track=0,pattern=0,parameter=0,parameter_name='pitch envelope amount',
      flag=hex(flag),key=hex(KEY),itcm=[hex(0x100),hex(0x100+448+4*audit_batch)],regions=[dict(core=0,space='x',start='0x4000',words=192)],
      config={k:hex(v) for k,v in config.items()},commands=dict(arm=52,status=53,disable=54,refill=55),
      manual_sites=[hex(a) for a in sites],clear_sites=[hex(a) for a,_,_ in clears],code_bytes=len(prefix)+len(code),
      source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),labels={k:hex(v) for k,v in labels.items()})
