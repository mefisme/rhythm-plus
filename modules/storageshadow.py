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
# The stock delete request's pack and project deletes: our wrappers also remove the Plus files.
PACK_COPY=0x0802af64                                 # the storage task's copy request: its one top-level call of the item copy
DELETE_CALLS=((0x080413c2,'packdelete',0x0802e938),(0x08041428,'itemdelete',0x0802e8e4))


def install(img,report,base_addr,offload=False,automation=False):
    slot=rhstate.ST+rhstate.OFF['storageshadow'][0]
    assert slot%32==0 and rhstate.OFF['storageshadow'][1]==1024
    defs=dict(SLOT=slot,C_RST=int(report['rhstate']['labels']['c_rst'],16),
              PREV_OUT=rhbuild.bl_target(img,tmenu.OUT_CALL))
    if os.environ.get('RH_AUTOMATION_TASK_GUARD')=='1':defs['TASK_GUARD']=1
    no_a3=automation and 'automation3' not in report
    if no_a3:defs['NO_A3']=1
    elif automation:
        assert offload and 'automation3' in report
        defs['A3_INIT']=int(report['automation3']['labels']['c_a3_init'],16)
    granular=os.environ.get('RH_GRANULAR_COMPANION')=='1'
    if granular:
        assert automation and offload and 'arm_kernel' in report['granular']
        defs['GR_STORE']=rhstate.ST+rhstate.OFF['granstore'][0]
        defs['GR_STATE']=rhstate.ST+rhstate.OFF['granular'][0]
        if os.environ.get('RH_GRANULAR_FINE')=='1':defs.update(GR_SETTINGS_BYTES=288,GR_SINGLE_BUFFER=1)
        for name in ('settings_store','settings_valid'):
            defs['GR_'+name.upper()]=report['granular']['arm_kernel']['labels']['c_gr_runtime_'+name]
    cow=automation and (no_a3 or report['automation3'].get('cow',False))
    pack_files=int(os.environ.get('RH_PACK_FILES') or 0)
    if pack_files:
        assert cow and granular and pack_files in (1,2)
        defs['PACK_FILES']=pack_files
    plus_usb=os.environ.get('RH_PLUS_USB')=='1'
    if plus_usb:
        assert pack_files==2 and report['rdiag'].get('plus_usb')
        defs['PLUS_USB']=1
    file_tools=os.environ.get('RH_FILETOOLS')=='1'
    if file_tools:
        assert plus_usb
        defs['FILE_TOOLS']=1
    if os.environ.get('RH_PX_COLOUR')=='1':
        assert file_tools
        defs['PX_COLOUR']=1
    if os.environ.get('RH_PX_NAME')=='1':
        assert defs.get('PX_COLOUR')
        defs['PX_PROJHEAD']=1
    if cow and not no_a3:
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
    if pack_files:need+=tuple('c_sh_'+name for _,name,_ in DELETE_CALLS)
    if file_tools:need+=('c_sh_packcopy',)
    if plus_usb:need+=('c_sh_pxmidi',)
    code,labels=compile_c(base_addr+len(prefix),defs,src=source,name='storageshadow',
                          prefix='c_sh_',need=need,max_code=0x3000)
    img+=bytes([255])*(base_addr-rhbuild.BASE-len(img))+prefix+code
    while len(img)%4:img.append(255)
    for addr,name,expected in hooks:rhbuild.patch(img,addr,expected,b_w(addr,labels['c_sh_'+name]))
    if offload:
        accessor=int(report['stepmut']['labels']['c_sm_store'],16)
        rhbuild.patch(img,accessor,'movs r0, #0|bx lr',b_w(accessor,labels['c_sh_block']))
    if automation and not no_a3:
        accessor=int(report['automation3']['labels']['c_a3_available'],16)
        rhbuild.patch(img,accessor,'movs r0, #0|bx lr',b_w(accessor,labels['c_sh_autobank']))
    rhbuild.patch(img,tmenu.OUT_CALL,f"bl #{defs['PREV_OUT']:#x}",bl(tmenu.OUT_CALL,labels['c_sh_out']))
    if plus_usb:
        import diagread
        ext=int(report['rdiag']['labels']['rc_ext'],16)
        assert bytes(img[ext-rhbuild.BASE:ext-rhbuild.BASE+4])==diagread.PX_HOLD
        img[ext-rhbuild.BASE:ext-rhbuild.BASE+4]=b_w(ext,labels['c_sh_pxmidi'])
    if pack_files:
        for addr,name,target in DELETE_CALLS:rhbuild.patch(img,addr,f'bl #{target:#x}',bl(addr,labels['c_sh_'+name]))
    if file_tools:rhbuild.patch(img,PACK_COPY,'bl #0x804143e',bl(PACK_COPY,labels['c_sh_packcopy']))
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
    if pack_files==1:report['storageshadow'].update(pack_files=True,directory='<pack>/Sessions/RP_<slot>_<key>.rps; reads 1:/RP_AUTO')
    if no_a3:report['storageshadow'].update(k13_automation=False,format='SO v4 metadata + RA04 bundle with no lanes; reads and drops older lanes')
    if plus_usb:report['storageshadow'].update(plus_usb=dict(commands='0x20 info, 0x21 list, 0x22 read, 0x23 write, 0x24 delete, 0x25 crc, 0x26 rename, 0x27 copy',
        version=1,max_chunk=64,item_kind='0x58555052',content_read='0x8046054',lseek='0x80223d8'))
    if pack_files==2:report['storageshadow'].update(pack_files=2,directory='<pack>/Sessions/RP_<slot>_<name>_<key>.rps; deletes move to 1:/RP_AUTO; Shift + Save accepts defaults')
    if file_tools:
        report['storageshadow']['plus_usb']['commands']+=', 0x28 project meta, 0x29 project copy'
        report['storageshadow']['pack_copy']=hex(PACK_COPY)
    return labels,code
