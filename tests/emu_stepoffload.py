"""A0179 required storage order and owned settings; disk backends injected."""
import json
import struct
import zlib
from pathlib import Path
from emu_playfix import machine,call,STACK
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]
RECORD=0x29484;TAIL=0x29110;META=TAIL+276;OLD=TAIL+404


def main():
    report=json.loads((ROOT/'firmware/a0179/manifest.json').read_text())['report']
    rep=report['storageshadow'];slot=int(rep['slot'],16)
    L={k:int(v,16) for k,v in rep['labels'].items()}
    tr={k:int(v,16) for k,v in rep['trampolines'].items()}
    u=machine((ROOT/'firmware/a0179/rhythmplus-A0179.bin').read_bytes(),
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
    disk={};saved={};directory=[False];handle=[None];events=[];fault={};incoming=[None]
    def hook(uc,a,n,data):
        x,y,z,q=[uc.reg_read(UC_ARM_REG_R0+i) for i in range(4)]
        sp=uc.reg_read(UC_ARM_REG_SP)
        if a==tr['TR_APPLY']:events.append('apply');ret(0x1234);return
        if a==int(rep['prev_out'],16):ret(0x1234);return
        if a==tr['TR_BACKEND']:
            events.append('native-read');uc.mem_write(z,incoming[0]);w(word(sp),RECORD);ret();return
        if a==tr['TR_WRITEBACKEND']:
            image=bytes(uc.mem_read(z,RECORD));events.append('native-write')
            if image[META:META+2]==b'SO' and image[META+3]:
                key=struct.unpack_from('<I',image,META+4)[0]
                assert disk[f'1:/RP_AUTO/{key:08X}.RPS']==bytes(u.mem_read(slot+176,100))
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
            handle[0]=name;uc.mem_write(x,bytes(4136));w(x,0x20006000);w(x+12,len(disk[name]))
            if fault.get('edit-during-io'):
                put_settings(sm(7));fault.pop('edit-during-io')
            ret();return
        if a in (0x08021f72,0x080220fc):
            kind='read' if a==0x08021f72 else 'write';events.append(kind)
            if fault.get(kind):w(q,0);ret(fault[kind]);return
            if kind=='write':disk[handle[0]].extend(uc.mem_read(y,z))
            else:uc.mem_write(y,bytes(disk[handle[0]][:z]))
            w(q,z);ret();return
        if a==0x080222bc:events.append('sync');ret(fault.get('sync',0));return
        if a==0x08022346:events.append('close');w(x,0);ret();return
    for a in list(tr.values())+[int(rep['prev_out'],16),0x08022788,0x08021d90,0x08021f72,0x080220fc,0x080222bc,0x08022346]:
        u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
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
    accessor=int(report['stepmut']['labels']['c_sm_store'],16)
    call(u,accessor);assert u.reg_read(UC_ARM_REG_R0)==0x1458
    assert save()==0 and word(actual)==RECORD
    first=saved[(2,5,8)]
    assert first[OLD:OLD+100]==bytes(100) and first[META:META+4]==b'SO\1\1'
    assert struct.unpack_from('<I',first,META+4)[0]==zlib.crc32(sm())
    assert struct.unpack_from('<I',first,META+16)[0]==zlib.crc32(first[META:META+16])
    allowed=set(range(META,META+20))|set(range(OLD,OLD+100))
    assert all(a==b for i,(a,b) in enumerate(zip(first,legacy)) if i not in allowed)
    assert events.index('sync')<events.index('read')<events.index('native-write')
    (ROOT/'buildtmp/a0179-offload-status.bin').write_bytes(bytes(u.mem_read(slot,1024)))
    (ROOT/'buildtmp/a0179-offload-native.bin').write_bytes(first)
    print('PASS durable verified companion precedes native write; only 20-byte metadata and reclaimed 100 bytes change')
    put_settings(sm(9));assert load(first)==0 and runtime()==sm()
    assert current()[OLD:OLD+100]==bytes(100) and events[-1]=='apply'
    assert events.index('read')<events.index('apply')
    print('PASS required settings are restored into owned ITCM before native project application; freed area stays empty')
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
    put_settings(sm(6));fault['edit-during-io']=True
    assert save()==0 and runtime()==sm(7)
    latest=saved[(2,9,27)];assert struct.unpack_from('<I',latest,META+4)[0]==zlib.crc32(sm(6))
    print('PASS snapshot stays consistent while live settings change during storage I/O')
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
    defaults=runtime();before_files=dict(disk);assert save()==0 and disk==before_files
    blank=saved[(2,9,27)];assert blank[META:META+4]==b'SO\1\0' and blank[OLD:OLD+100]==bytes(100)
    assert load(blank)==0 and runtime()==defaults and 'read' not in events
    new_feature=bytearray(empty);new_feature[OLD:OLD+100]=future
    apply(bytes(new_feature));assert save()==0
    assert saved[(2,9,27)][OLD:OLD+100]==future
    print('PASS new/cleared/reused project uses fileless defaults on load and first save')
    # Internal pack retains embedded storage, without SD filesystem calls.
    put_settings(sm(11));w(item+8,0);before_files=dict(disk)
    assert save()==0 and disk==before_files
    internal=saved[(2,9,0)];assert internal[OLD:OLD+100]==sm(11) and internal[META:META+20]==bytes(20)
    print('PASS internal pack settings remain embedded with no companion dependency')
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
