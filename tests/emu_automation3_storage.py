"""A0180 bundle migration/snapshot/load lifecycle; native/FAT boundaries injected."""
import json
import struct
import zlib
import sys
from pathlib import Path
from emu_playfix import machine,call,STACK
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]
RECORD=0x29484;TAIL=0x29110;META=TAIL+276;OLD=TAIL+404


def main():
    build=sys.argv[1] if len(sys.argv)>1 else 'a0180'
    report=json.loads((ROOT/'firmware'/build/'manifest.json').read_text())['report']
    rep=report['storageshadow'];slot=int(rep['slot'],16)
    L={k:int(v,16) for k,v in rep['labels'].items()}
    cow=report['automation3'].get('cow',False);gbytes=rep.get('granular_settings_bytes',0);gran=bool(gbytes);version=4 if gran else 3 if cow else 2
    A={k:int(v,16) for k,v in report['automation3']['labels'].items()}
    tr={k:int(v,16) for k,v in rep['trampolines'].items()}
    u=machine((ROOT/'firmware'/build/f'rhythmplus-{build.upper()}.bin').read_bytes(),
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes(),mclass=True)
    record,item,session,actual,out=0x20012c48,0x20007000,0x20007100,0x20007200,0x20008000
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def metric(i):return word(slot+4*i)
    def runtime():return bytes(u.mem_read(0x1458,100))
    def sm(seed=0):
        b=bytearray(b'SM\0\2'+bytes((i+seed)&255 for i in range(96)))
        b[2]=(sum(b[4:])^0x5c)&255;return bytes(b)
    def put_settings(b):u.mem_write(0x1458,b)
    def current():return bytes(u.mem_read(record,RECORD))
    def ret(value=0):
        u.reg_write(UC_ARM_REG_R0,value);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    w(0x2003c0cc,record);w(session+0x14,record)
    u.mem_write(item,struct.pack('<3I',2,5,8))
    for a,v in ((0xe000ef90,0x73),(0xe000ed08,0x08010000),(0xe000ed94,0),(0xe000ed14,0)):w(a,v)
    granular_settings=b''
    if gran:
        kernel=report['granular']['arm_kernel']['labels'];gslot=int(report['granular']['bridge']['slot'],16)
        lifecycle={k:int(v,16) for k,v in report['granular']['lifecycle']['labels'].items()}
    disk={};saved={};directory=[False];handle=[None];position=[0];events=[];fault={};incoming=[None]
    def bundle(settings,bank=b'\xff'*4608):
        header=struct.pack('<7I',0x34304152 if gran else 0x33304152 if cow else 0x32304152,4608,3,8,32,6,0)+settings
        if not cow:return header+bank
        lanes=[bank[i:i+192] for i in range(0,4608,192)]
        return header+struct.pack('<24H',*[0 if x==b'\xff'*192 else 0x80c0 for x in lanes])+b''.join(x for x in lanes if x!=b'\xff'*192)+granular_settings
    def bank():
        if not cow:return bytes(u.mem_read(0x1500,4608))
        out=bytearray()
        for lane in range(24):
            call(u,A['c_a3_bankread'],lane,0x20009000);assert u.reg_read(UC_ARM_REG_R0)==0
            out.extend(u.mem_read(0x20009000,192))
        return bytes(out)
    def putbank(raw):
        if not cow:u.mem_write(0x1500,raw);return
        for lane in range(24):
            u.mem_write(0x20009000,raw[lane*192:lane*192+192])
            call(u,A['c_a3_bankimport'],lane,0x20009000,192,1);assert u.reg_read(UC_ARM_REG_R0)==0
    def hook(uc,a,n,data):
        assert uc.reg_read(UC_ARM_REG_PRIMASK)==0,('I/O or native application with interrupts masked',hex(a))
        assert uc.reg_read(UC_ARM_REG_BASEPRI)==0,('task memory guard leaked across native I/O/application',hex(a))
        x,y,z,q=[uc.reg_read(UC_ARM_REG_R0+i) for i in range(4)]
        sp=uc.reg_read(UC_ARM_REG_SP)
        if a==tr['TR_APPLY']:
            events.append('apply')
            if gran:uc.reg_write(UC_ARM_REG_PC,lifecycle['c_glapply']|1)
            else:ret(0x1234)
            return
        if gran and a==lifecycle['apply_native']:ret(0x1234);return
        if a==int(rep['prev_out'],16):ret(0x1234);return
        if a==tr['TR_BACKEND']:
            events.append('native-read');uc.mem_write(z,incoming[0]);w(word(sp),RECORD);ret();return
        if a==tr['TR_WRITEBACKEND']:
            image=bytes(uc.mem_read(z,RECORD));events.append('native-write')
            if image[META:META+2]==b'SO' and image[META+3]:
                key=struct.unpack_from('<I',image,META+4)[0]
                if cow:assert zlib.crc32(disk[f'1:/RP_AUTO/{key:08X}.RPS'])==key
                else:assert disk[f'1:/RP_AUTO/{key:08X}.RPS']==bytes(u.mem_read(0x2720,4736))
                assert 'sync' in events or 'read' in events
            code=fault.get('native-write',0)
            w(word(sp),7 if code else RECORD)
            if not code:saved[tuple(struct.unpack('<3I',uc.mem_read(x,12)))]=image
            ret(code);return
        if a==0x08022788:
            events.append('mkdir');code=8 if directory[0] else 0;directory[0]=True;ret(code);return
        if a==0x08021d90:
            assert x==0x400
            name=bytes(uc.mem_read(y,32)).split(b'\0')[0].decode();events.append(('open',name,z))
            if not directory[0]:ret(5);return
            if z==7 and name in disk:ret(8);return
            if z==1 and name not in disk:ret(4);return
            if fault.get('open'):ret(fault['open']);return
            if z==7:disk[name]=bytearray()
            handle[0]=name;position[0]=0;uc.mem_write(x,bytes(4136));w(x,0x20006000);w(x+12,len(disk[name]))
            if fault.get('edit-during-io'):
                put_settings(sm(7))
                if cow:
                    uc.mem_write(0x3b00,b'\x7f'+b'\xff'*191);w(0x3d40+80,0)
                    w(0x3d40+92,word(0x3d40+92)|1);w(0x3d44,word(0x3d44)+1)
                else:uc.mem_write(0x1500,b'\x7f')
                fault.pop('edit-during-io')
            ret();return
        if a in (0x08021f72,0x080220fc):
            kind='read' if a==0x08021f72 else 'write';events.append(kind)
            if fault.get(kind):w(q,0);ret(fault[kind]);return
            if kind=='write':disk[handle[0]].extend(uc.mem_read(y,z))
            else:uc.mem_write(y,bytes(disk[handle[0]][position[0]:position[0]+z]))
            position[0]+=z
            w(q,z);ret();return
        if a==0x080222bc:events.append('sync');ret(fault.get('sync',0));return
        if a==0x08022346:events.append('close');w(x,0);ret();return
    for a in list(tr.values())+[int(rep['prev_out'],16),0x08022788,0x08021d90,0x08021f72,0x080220fc,0x080222bc,0x08022346]:
        u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
    if gran:u.hook_add(UC_HOOK_CODE,hook,None,lifecycle['apply_native'],lifecycle['apply_native']+1)
    def invoke(name,*args):
        extras=list(args[4:])+[0,0,0]
        u.mem_write(STACK+0xf0000,struct.pack('<3I',*extras[:3]))
        call(u,L['c_sh_'+name],*args[:4]);return u.reg_read(UC_ARM_REG_R0)
    def apply(image):u.mem_write(record,image);return invoke('apply',session,0,0,0)
    def save():events.clear();w(actual,0);return invoke('writebackend',item,0,record,RECORD,actual,0,0)
    def load(image):
        incoming[0]=image;events.clear();result=invoke('backend',item,0,record,RECORD,actual,0,0)
        if word(0x1440+12)==4:assert invoke('block')==0
        invoke('apply',session,0,0,0);return result
    legacy=bytearray((i*31)&255 for i in range(RECORD));legacy[META:META+20]=bytes(20);legacy[OLD:OLD+100]=sm()
    assert apply(bytes(legacy))==0x1234 and runtime()==sm()
    if gran:
        kernel=report['granular']['arm_kernel']['labels'];gslot=int(report['granular']['bridge']['slot'],16)
        call(u,kernel['c_gr_runtime_init'],gslot)
        call(u,kernel['c_gr_runtime_settings_store'],gslot,out)
        assert u.reg_read(UC_ARM_REG_R0)==1
        granular_settings=bytes(u.mem_read(out,gbytes))
    accessor=int(report['stepmut']['labels']['c_sm_store'],16)
    call(u,accessor);assert u.reg_read(UC_ARM_REG_R0)==0x1458
    masked=[0,0]
    def mask_trace(uc,a,n,data):
        if uc.reg_read(UC_ARM_REG_PRIMASK):masked[0]+=1;masked[1]=max(masked)
        else:masked[0]=0
    trace=u.hook_add(UC_HOOK_CODE,mask_trace)
    assert save()==0 and word(actual)==RECORD
    u.hook_del(trace)
    limit=200 if report['automation3'].get('task_guard') else 12000
    assert masked[1]<limit and not u.reg_read(UC_ARM_REG_PRIMASK),masked
    print(f'PASS snapshot IRQ masking bounded to {masked[1]} emulated instructions; filesystem runs unmasked')
    first=saved[(2,5,8)]
    assert first[OLD:OLD+100]==bytes(100) and first[META:META+4]==b'SO'+bytes([version,1])
    assert struct.unpack_from('<I',first,META+4)[0]==zlib.crc32(bundle(sm()))
    assert struct.unpack_from('<I',first,META+16)[0]==zlib.crc32(first[META:META+16])
    allowed=set(range(META,META+20))|set(range(OLD,OLD+100))
    assert all(a==b for i,(a,b) in enumerate(zip(first,legacy)) if i not in allowed)
    assert events.index('sync')<events.index('read')<events.index('native-write')
    print('PASS durable verified companion precedes native write; only 20-byte metadata and reclaimed 100 bytes change')
    put_settings(sm(9));assert load(first)==0 and runtime()==sm()
    assert current()[OLD:OLD+100]==bytes(100) and events[-1]=='apply'
    assert events.index('read')<events.index('apply')
    print('PASS required settings are restored into owned ITCM before native project application; freed area stays empty')
    if gran:
        pointer=invoke('grsettings');assert pointer
        assert bytes(u.mem_read(pointer,gbytes))==granular_settings
        # Change a real granular knob, save, reload, then apply through the
        # canonical runtime loader. Native application is injected in this test.
        call(u,kernel['c_gr_runtime_pad'],gslot,0,report['granular']['ui']['page_pad'])
        call(u,kernel['c_gr_runtime_turn'],gslot,0,0,13)
        call(u,kernel['c_gr_runtime_settings_store'],gslot,out)
        u.mem_write(gslot+316,bytes(range(1,9)))
        if report['granular'].get('navigation_persistent'):
            for t in range(8):u.mem_write(gslot+168+t,bytes([16*(t&1)]))
            u.mem_write(gslot+235,b'\xa6')
        call(u,kernel['c_gr_runtime_settings_store'],gslot,out)
        changed=bytes(u.mem_read(out,gbytes));assert changed!=granular_settings
        result=save();assert result==0,(result,metric(13),word(gslot+204),bytes(u.mem_read(out,4)));granular_project=saved[(2,5,8)]
        call(u,kernel['c_gr_runtime_turn'],gslot,0,0,-7)
        assert load(granular_project)==0
        pointer=invoke('grsettings');assert bytes(u.mem_read(pointer,gbytes))==changed
        assert bytes(u.mem_read(gslot+316,64))==changed[152:216], 'project application did not restore lane assignments'
        assert bytes(u.mem_read(gslot+104,64))==changed[8:72], 'project application did not restore manual positions'
        if report['granular'].get('navigation_persistent'):
            assert bytes((u.mem_read(gslot+168+t,1)[0]>>4)&1 for t in range(8))==bytes(b&1 for b in changed[216:224])
            assert u.mem_read(gslot+235,1)[0]==sum(((changed[216+t]>>1)&1)<<t for t in range(8)), 'application did not restore knob pages'
        call(u,kernel['c_gr_runtime_settings_load'],gslot,pointer)
        assert u.reg_read(UC_ARM_REG_R0)==1
        call(u,kernel['c_gr_runtime_settings_store'],gslot,out)
        assert bytes(u.mem_read(out,gbytes))==changed
        # Return to baseline for the storage fault matrix below.
        assert load(first)==0
        pointer=invoke('grsettings')
        call(u,kernel['c_gr_runtime_settings_load'],gslot,pointer)
        saved[(2,5,8)]=first
        print('PASS granular knob settings persist through companion save/load and restore exactly')
        if gbytes==288:
            # A card saved by A0206 holds a 224-byte GS v4 companion.
            key=struct.unpack_from('<I',granular_project,META+4)[0];new=bytes(disk[f'1:/RP_AUTO/{key:08X}.RPS'])
            v4=bytearray(changed[:224]);v4[2]=4;struct.pack_into('<I',v4,4,zlib.crc32(v4[8:]))
            older=new[:-288]+bytes(v4);okey=zlib.crc32(older);disk[f'1:/RP_AUTO/{okey:08X}.RPS']=bytearray(older)
            project=bytearray(granular_project);struct.pack_into('<II',project,META+4,okey,len(older))
            struct.pack_into('<I',project,META+16,zlib.crc32(project[META:META+16]))
            u.mem_write(gslot+404,b'\x07'*64)
            assert load(bytes(project))==0
            pointer=invoke('grsettings');assert bytes(u.mem_read(pointer,224))==bytes(v4)
            assert bytes(u.mem_read(gslot+104,64))==changed[8:72] and bytes(u.mem_read(gslot+404,64))==bytes(64)
            print('PASS A0206 224-byte GS v4 companion loads on a fine build with fine parts 0')

    # Run the real Content loop and native async completion bridge, not just
    # our wrapper in isolation. Only queue/post boundaries are injected here.
    pending=[];posts=[];observed=[]
    service=word(0x20006ca8);loadobj,observer,vt,frameptr=0x20007300,0x20007400,0x20007500,0x20007600
    target=0x08000200
    def task_hook(uc,a,n,data):
        if a==0x08040e18:ret(int(bool(pending)))
        elif a==0x08040dee:
            ptr=word(uc.reg_read(UC_ARM_REG_R1)+4);uc.mem_write(ptr,pending.pop(0));ret(1)
        elif a==0x080419cc:
            posts.append((uc.reg_read(UC_ARM_REG_R1),bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R2),30))));ret()
        else:observed.append(word(0x1440+12));ret()
    for a in (0x08040e18,0x08040dee,0x080419cc,target):u.hook_add(UC_HOOK_CODE,task_hook,None,a,a+1)
    w(observer,vt);w(vt,target|1);w(loadobj,observer)
    req=bytearray(72);req[0]=6
    struct.pack_into('<3I',req,4,2,5,8);struct.pack_into('<3I',req,16,0,record,RECORD)
    struct.pack_into('<2I',req,60,0x080472a9,loadobj)
    pending.append(bytes(req));incoming[0]=first
    u.mem_write(service+0x10,bytes([0,2]));call(u,0x0802ad40,service)
    assert len(posts)==1 and word(0x1440+12)==4 and runtime()==sm()
    fn,frame=posts.pop();fields=struct.unpack('<I3IBBIII',frame)
    assert fields[5:]==(0,record,RECORD,loadobj)
    u.mem_write(frameptr,frame);call(u,fn&~1,frameptr)
    assert observed==[4] and word(loadobj)==0 and invoke('block')==0
    invoke('apply',session,0,0,0);assert invoke('block')==0x1458
    print('PASS real Content read and async bridge deliver completion only after restore, with activation gated until application')
    # Duplicate on the same card: immutable file is shared until the copy is edited.
    w(item+4,9);w(item+8,27);assert load(first)==0
    put_settings(sm(3));assert save()==0
    clone=saved[(2,9,27)];assert clone[META:META+20]!=first[META:META+20]
    assert load(first)==0 and runtime()==sm()
    assert saved[(2,5,8)]==first
    print('PASS cloned project metadata resolves on same card; edits produce independent file and preserve original')
    future=bytes([0x46,0x55])+bytes(range(98))
    u.mem_write(record+OLD,future);put_settings(sm(12));assert save()==0
    reused=saved[(2,9,27)];assert reused[OLD:OLD+100]==future
    assert load(reused)==0 and runtime()==sm(12) and current()[OLD:OLD+100]==future
    assert load(first)==0
    print('PASS later saves and loads preserve future data placed in the reclaimed region')
    # File failure must not touch the native saved image or its live extension.
    put_settings(sm(4));before=current();prior=dict(saved);fault['sync']=1
    assert save()==5 and 'native-write' not in events and current()==before and saved==prior
    assert runtime()==sm(4) and invoke('block')==0x1458
    fault.clear();assert save()==0
    # Native write error: restore the prior live extension; report failure.
    before=current();put_settings(sm(5));fault['native-write']=3
    assert save()==3 and current()==before and runtime()==sm(5)
    fault.clear()
    print('PASS companion failure blocks native save; native failure restores live extension without discarding edits')
    assert load(first)==0
    frozen=bytearray(b'\xff'*4608);frozen[31*6]=0;frozen[-1]=127
    putbank(bytes(frozen))
    put_settings(sm(6));fault['edit-during-io']=True
    assert save()==0 and runtime()==sm(7)
    latest=saved[(2,9,27)];assert struct.unpack_from('<I',latest,META+4)[0]==zlib.crc32(bundle(sm(6),bytes(frozen)))
    assert bank()[0]==127
    assert load(latest)==0 and bank()==bytes(frozen) and runtime()==sm(6)
    print('PASS snapshot stays consistent while settings and automation change during I/O; complete bank restores')
    # Missing/corrupt required files: no defaults, no overwrite, visible error.
    key=struct.unpack_from('<I',first,META+4)[0];name=f'1:/RP_AUTO/{key:08X}.RPS';old_file=disk.pop(name)
    assert load(first)==0 and invoke('block')==0 and metric(10)>0
    prior=dict(saved);assert save()==5 and saved==prior and 'native-write' not in events
    w(0x20006f3c,256);invoke('out',1,out,0,0)
    assert word(out+57*4)==word(0x20003974+4*0x55)
    disk[name]=bytearray(old_file);disk[name][4]^=1
    assert load(first)==0 and invoke('block')==0
    disk[name]=old_file;assert load(first)==0 and runtime()==sm()
    bad=bytearray(first);bad[META+4]^=1
    assert load(bytes(bad))==0 and invoke('block')==0 and 'read' not in events
    assert load(first)==0 and runtime()==sm()
    print('PASS missing/corrupt companion disables Step Mutate and blocks destructive resave; Save LED signals error')
    # Blank/new pack project uses defaults without a companion and clears old state.
    empty=bytearray(legacy);empty[META:META+20]=bytes(20);empty[OLD:OLD+100]=bytes(100)
    assert apply(bytes(empty))==0x1234
    defaults=runtime();before_files=dict(disk);assert save()==0
    if not gran:assert disk==before_files
    blank=saved[(2,9,27)];assert blank[META:META+4]==b'SO'+bytes([version,int(gran)]) and blank[OLD:OLD+100]==bytes(100)
    assert load(blank)==0 and runtime()==defaults
    if not gran:assert 'read' not in events
    assert bank()==b'\xff'*4608
    # A0179 SO v1 restores settings with empty independent lanes, then migrates on Save.
    v1=bytearray(first);v1[META+2]=1
    struct.pack_into('<II',v1,META+4,zlib.crc32(sm(15)),100)
    struct.pack_into('<I',v1,META+16,zlib.crc32(v1[META:META+16]))
    disk[f'1:/RP_AUTO/{zlib.crc32(sm(15)):08X}.RPS']=sm(15)
    assert load(bytes(v1))==0 and runtime()==sm(15) and bank()==b'\xff'*4608
    assert save()==0 and saved[(2,9,27)][META+2]==version
    print('PASS A0179 companion imports without edits, migrating to bundle only on Save')
    if cow:
        # Import the actual pre-compression RA02 representation without changing
        # any event, including holes, and migrate only on the next explicit Save.
        raw=bytes(255 if i%17==0 else (i*37)&127 for i in range(4608))
        old_payload=struct.pack('<7I',0x32304152,4608,3,8,32,6,0)+sm(18)+raw
        key2=zlib.crc32(old_payload);v2=bytearray(first);v2[META+2]=2
        struct.pack_into('<II',v2,META+4,key2,len(old_payload))
        struct.pack_into('<I',v2,META+16,zlib.crc32(v2[META:META+16]))
        disk[f'1:/RP_AUTO/{key2:08X}.RPS']=old_payload
        assert load(bytes(v2))==0 and bank()==raw and runtime()==sm(18)
        assert save()==0 and saved[(2,9,27)][META+2]==version
        assert disk[f'1:/RP_AUTO/{key2:08X}.RPS']==old_payload
        print('PASS A0180-A0183 RA02 lanes migrate losslessly; earlier immutable companion remains unchanged')
        # Exercise actual Main output maintenance, then the Content save/restore
        # path with compressed descriptors instead of just raw fallback lanes.
        smooth=bytes((lambda v:v if v<128 else 255-v)((i+lane*7)%256)
                     for lane in range(24) for i in range(192))
        putbank(smooth)
        for i in range(24):
            w(0x20006f3c,1000+i*20);invoke('out',1,out,0,0)
        used=word(0x1508);assert used<2200,used
        assert bank()==smooth
        assert save()==0;compressed=saved[(2,9,27)]
        key3=struct.unpack_from('<I',compressed,META+4)[0];payload=disk[f'1:/RP_AUTO/{key3:08X}.RPS']
        assert len(payload)<2400,len(payload)
        assert any(0<x<192 for x in struct.unpack_from('<24H',payload,128))
        assert load(compressed)==0 and bank()==smooth and runtime()==sm(18)
        print(f'PASS scheduled RAM compression and real streamed Save/load: {used} payload RAM bytes, {len(payload)} file bytes')
        # An invalid lane with a valid whole-file checksum must still fail closed.
        broken=bytearray(payload);broken[176]=255;badkey=zlib.crc32(broken)
        badfile=bytearray(compressed);struct.pack_into('<I',badfile,META+4,badkey)
        struct.pack_into('<I',badfile,META+16,zlib.crc32(badfile[META:META+16]))
        disk[f'1:/RP_AUTO/{badkey:08X}.RPS']=broken
        assert load(bytes(badfile))==0 and invoke('block')==0
        assert load(compressed)==0 and bank()==smooth
        assert load(blank)==0
        print('PASS invalid compressed lane fails closed even with matching file CRC')
    new_feature=bytearray(empty);new_feature[OLD:OLD+100]=future
    apply(bytes(new_feature));assert save()==0
    assert saved[(2,9,27)][OLD:OLD+100]==future
    print('PASS new/cleared/reused project defaults and first save preserve reclaimed future fields')
    # Internal pack retains embedded storage, without SD filesystem calls.
    put_settings(sm(11));w(item+8,0);before_files=dict(disk)
    assert save()==0 and disk==before_files
    internal=saved[(2,9,0)];assert internal[OLD:OLD+100]==sm(11) and internal[META:META+20]==bytes(20)
    assert invoke('autobank')==0
    print('PASS internal pack settings remain embedded with no companion dependency')
    # Installed media wrappers stage direct full-sector bundle/FIL transfers.
    media_calls=[];media_data=bytes((i*13)&255 for i in range(8192))
    def media_hook(uc,a,n,data):
        dev,offset,ptr,count=[uc.reg_read(UC_ARM_REG_R0+i) for i in range(4)]
        assert ptr>=0x20000000 and ptr%32==0 and count==512
        media_calls.append((a,offset,ptr,count))
        if a==tr['TR_READ']:uc.mem_write(ptr,media_data[offset:offset+count])
        uc.reg_write(UC_ARM_REG_R1,count);ret()
    for a in (tr['TR_READ'],tr['TR_WRITE']):u.hook_add(UC_HOOK_CODE,media_hook,None,a,a+1)
    for ptr,count in ((0x428,4096),(0x3de0,512) if cow else (0x2720,4608)):
        media_calls.clear();assert invoke('read',99,0,ptr,count)==0
        assert bytes(u.mem_read(ptr,count))==media_data[:count]
        assert len(media_calls)==count//512
        assert u.reg_read(UC_ARM_REG_R1)==count
    print('PASS installed FIL and full-sector bundle transfers reach Media only through aligned SRAM staging')
    assert metric(20)==0
    rst=int(report['rhstate']['labels']['c_rst'],16)
    def unavailable(uc,a,n,data):ret(0)
    u.hook_add(UC_HOOK_CODE,unavailable,None,rst,rst+1)
    before_private=bytes(u.mem_read(slot,1024));before_itcm=bytes(u.mem_read(0x1440,128))
    assert invoke('apply',session,0,0,0)==0x1234
    assert bytes(u.mem_read(slot,1024))==before_private and bytes(u.mem_read(0x1440,128))==before_itcm
    print('PASS unavailable private RAM leaves storage state untouched and forwards native project application')
    print('LIMIT native disk/Media calls injected; hardware timing, audio continuity and native torn-file recovery unproved')
    print('ALL PASS')


if __name__=='__main__':main()
