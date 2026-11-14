"""Controlled SD mirror: preserves embedded settings; no production offload."""
from pathlib import Path
import os
import rhbuild
import rhstate
import tmenu
from stepmut import compile_c
from thumb import b_w,bl
ROOT=Path(__file__).resolve().parents[1]
HOOKS=((0x08037366,'apply','push.w {r3, r4, r5, r6, r7, r8, sb, sl, fp, lr}'),
       (0x080472e2,'save','push {r1, r2, r3, r4, r5, lr}|mov r4, r1'),
       (0x08047304,'done','push {r3, r4, r5, lr}|mov r4, r0'),
       (0x0804113a,'backend','push.w {r2, r3, r4, r5, r6, r7, r8, lr}'),
       (0x08022e98,'read','push {r3, r4, r5, r6, r7, lr}|mov r4, r0'),
       (0x08022efc,'write','push {r3, r4, r5, r6, r7, lr}|mov r7, r0'))


def install(img,report,base_addr,offload=False,automation=False):
    slot=rhstate.ST+rhstate.OFF['storageshadow'][0]
    assert slot%32==0 and rhstate.OFF['storageshadow'][1]==1024
    defs=dict(SLOT=slot,C_RST=int(report['rhstate']['labels']['c_rst'],16),
              PREV_OUT=rhbuild.bl_target(img,tmenu.OUT_CALL))
    if os.environ.get('RH_AUTOMATION_TASK_GUARD')=='1':defs['TASK_GUARD']=1
    if automation:
        assert offload and 'automation3' in report
        defs['A3_INIT']=int(report['automation3']['labels']['c_a3_init'],16)
    granular=os.environ.get('RH_GRANULAR_COMPANION')=='1'
    if granular:
        assert automation and offload and 'arm_kernel' in report['granular']
        defs['GR_STORE']=rhstate.ST+rhstate.OFF['granstore'][0]
        defs['GR_STATE']=rhstate.ST+rhstate.OFF['granular'][0]
        for name in ('settings_store','settings_valid'):
            defs['GR_'+name.upper()]=report['granular']['arm_kernel']['labels']['c_gr_runtime_'+name]
    cow=automation and report['automation3'].get('cow',False)
    if cow:
        for name in ('bankfilesize','bankfile','banksnapshot','bankrelease','bankimport','bankmaintain'):
            defs['A3_'+name.upper()]=int(report['automation3']['labels']['c_a3_'+name],16)
    hooks=HOOKS if not offload else tuple(x for x in HOOKS if x[1] not in ('save','done'))+(
        (0x080411d8,'writebackend','push.w {r0, r1, r4, r5, r6, r7, r8, sb, sl, fp, lr}'),)
    prefix=bytearray()
    for addr,name,expected in hooks:
        old=bytes(img[addr-rhbuild.BASE:addr-rhbuild.BASE+4])
        assert '|'.join(rhbuild.disasm(old,addr))==expected
        defs['TR_'+name.upper()]=base_addr+len(prefix)
        prefix+=old+b_w(base_addr+len(prefix)+4,addr+4)
    work=ROOT/'buildtmp/storageshadow';work.mkdir(parents=True,exist_ok=True)
    source=work/'combined.c'
    implementation=ROOT/('modules/stepoffload3.c' if automation else 'modules/stepoffload.c') if offload else Path(__file__).with_suffix('.c')
    if cow:implementation=ROOT/'modules/stepoffload7.c'
    source.write_bytes((ROOT/'modules/projectfile.c').read_bytes()+b'\n'+implementation.read_bytes())
    need=tuple('c_sh_'+name for _,name,_ in hooks)+('c_sh_out', 'c_sh_block' if offload else 'c_sh_complete')
    code,labels=compile_c(base_addr+len(prefix),defs,src=source,name='storageshadow',
                          prefix='c_sh_',need=need,max_code=0x3000)
    img+=bytes([255])*(base_addr-rhbuild.BASE-len(img))+prefix+code
    while len(img)%4:img.append(255)
    for addr,name,expected in hooks:rhbuild.patch(img,addr,expected,b_w(addr,labels['c_sh_'+name]))
    if offload:
        accessor=int(report['stepmut']['labels']['c_sm_store'],16)
        rhbuild.patch(img,accessor,'movs r0, #0|bx lr',b_w(accessor,labels['c_sh_block']))
    if automation:
        accessor=int(report['automation3']['labels']['c_a3_available'],16)
        rhbuild.patch(img,accessor,'movs r0, #0|bx lr',b_w(accessor,labels['c_sh_autobank']))
    rhbuild.patch(img,tmenu.OUT_CALL,f"bl #{defs['PREV_OUT']:#x}",bl(tmenu.OUT_CALL,labels['c_sh_out']))
    report['storageshadow']=dict(slot=hex(slot),bytes=1024,fil=hex(0x400),fil_bytes=4136,
        prev_out=hex(defs['PREV_OUT']),
        bounce=hex(slot+512),offload=offload,native_settings_authoritative=not offload,
        directory='1:/RP_AUTO',format='100-byte SM v2 mirror, CRC32 content filename',
        labels={k:hex(v) for k,v in labels.items()},trampolines={k:hex(v) for k,v in defs.items() if k.startswith('TR_')})
    if offload:report['storageshadow'].update(runtime=hex(0x1440),runtime_bytes=128,
        metadata_offset=276,metadata_bytes=20,reclaimed_offset=404,reclaimed_bytes=100,
        net_project_bytes=80,format='SO v1 metadata + immutable 100-byte SM v2 file')
    if automation:report['storageshadow'].update(format='SO v2 metadata + immutable RA02 bundle; reads SO v1',automation_bytes=4608,bundle_bytes=4736)
    if cow:report['storageshadow'].update(format='SO v3 metadata + streamed RA03 bundle; reads SO v1/v2',bundle_bytes=None,max_bundle_bytes=4784)
    if granular:report['storageshadow'].update(format='SO v4 metadata + RA04 bundle with granular settings; reads SO v1/v2/v3',granular_settings_bytes=224,max_bundle_bytes=5008)
    return labels,code
