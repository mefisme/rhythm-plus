"""A0178 installed wrappers + real Content worker/bridge, synthetic FatFs only."""
import json
import struct
from pathlib import Path
from emu_playfix import machine,call,STACK
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]


def main():
    man=json.loads((ROOT/'firmware/a0178/manifest.json').read_text())['report']
    rep=man['storageshadow'];slot=int(rep['slot'],16)
    labels={k:int(v,16) for k,v in rep['labels'].items()}
    tr={k:int(v,16) for k,v in rep['trampolines'].items()}
    u=machine((ROOT/'firmware/a0178/rhythmplus-A0178.bin').read_bytes(),
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes(),mclass=True)
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def metric(i):return word(slot+i*4)
    def ret(value=0):
        u.reg_write(UC_ARM_REG_R0,value)
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    service=word(0x20006ca8)
    item,session,record,message=0x20007000,0x20007100,0x20012c48,0x20007200
    u.mem_write(item,struct.pack('<3I',2,5,8));w(session+0x14,record)
    settings=bytearray(b'SM\0\2'+bytes(range(96)))
    settings[2]=(sum(settings[4:])^0x5c)&255
    tail=record+0x29110+404;u.mem_write(tail,bytes(settings))
    for a,v in ((0xe000ef90,0x73),(0xe000ed08,0x08010000),(0xe000ed94,0),(0xe000ed14,0)):w(a,v)
    disk={};directory=[False];queue=[];posts=[];io=[];current=[None];pos=[0];fault={}
    media_calls=[];forward=[]
    def string(a):return bytes(u.mem_read(a,64)).split(b'\0')[0].decode()
    def hook(uc,a,size,data):
        args=[uc.reg_read(UC_ARM_REG_R0+i) for i in range(4)]
        if a in (tr['TR_SAVE'],tr['TR_DONE'],tr['TR_APPLY'],tr['TR_BACKEND']):
            forward.append((a,args));ret(0x1234);return
        if a==int(rep['prev_out'],16):ret(0x1234);return
        if a==0x08040dc4:
            ptr=word(args[1]+4);queue.append(bytes(u.mem_read(ptr,72)));ret(1);return
        if a==0x080240c0:ret();return
        if a==0x08040e18:ret(int(bool(queue)));return
        if a==0x08040dee:
            out=word(args[1]+4);u.mem_write(out,queue.pop(0));ret(1);return
        if a==0x080419cc:
            posts.append((args[1],bytes(u.mem_read(args[2],30))));ret();return
        if a==0x08022788:
            assert string(args[0])=='1:/RP_AUTO';io.append('mkdir')
            result=8 if directory[0] else 0;directory[0]=True;ret(result);return
        if a==0x08021d90:
            file,path,mode,_=args;name=string(path)
            assert file==0x400 and name.startswith('1:/RP_AUTO/') and len(name)==23
            io.append(('open',name,mode))
            if not directory[0]:ret(5);return
            if mode==7 and name in disk:ret(8);return
            if mode==1 and name not in disk:ret(4);return
            if mode==7:disk[name]=bytearray()
            current[0]=name;pos[0]=0
            u.mem_write(file,bytes(4136));w(file,0x20006000);w(file+12,len(disk[name]))
            ret();return
        if a in (0x08021f72,0x080220fc):
            file,ptr,count,actual=args;assert file==0x400 and count==100
            kind='read' if a==0x08021f72 else 'write';io.append(kind)
            if kind in fault:w(actual,0);ret(fault[kind]);return
            if kind=='write':disk[current[0]].extend(u.mem_read(ptr,count))
            else:u.mem_write(ptr,bytes(disk[current[0]][:count]))
            pos[0]+=count;w(actual,count);ret();return
        if a==0x080222bc:io.append('sync');ret(fault.get('sync',0));return
        if a==0x08022346:io.append('close');w(args[0],0);ret(fault.get('close',0));return
        if a in (tr['TR_READ'],tr['TR_WRITE']):
            media_calls.append((a,args))
            assert args[2]>=0x20000000
            if a==tr['TR_READ']:u.mem_write(args[2],b'\x3c'*args[3])
            uc.reg_write(UC_ARM_REG_R1,args[3]);ret();return
    addresses=list(tr.values())+[int(rep['prev_out'],16),0x08040dc4,0x080240c0,
        0x08040e18,0x08040dee,0x080419cc,0x08022788,0x08021d90,
        0x08021f72,0x080220fc,0x080222bc,0x08022346]
    for a in addresses:u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
    def invoke(name,*args):
        extras=list(args[4:])+[0,0,0]
        u.mem_write(STACK+0xf0000,struct.pack('<3I',*extras[:3]))
        call(u,labels['c_sh_'+name],*args[:4])
        return u.reg_read(UC_ARM_REG_R0)
    tick=[100]
    def drain():
        for _ in range(40):
            tick[0]+=1;w(0x20006f3c,tick[0])
            assert invoke('out',1,2,3,4)==0x1234
            if queue:
                # This is the original Content loop; our backend wrapper handles
                # only the private descriptor and normal completion posting.
                call(u,0x0802ad40,service)
            while posts:
                fn,frame=posts.pop(0);u.mem_write(message,frame)
                call(u,fn&~1,message)
            if metric(1)==0 and metric(2)==0:return
        raise AssertionError('mirror worker did not finish')
    original=bytes(u.mem_read(record,0x29484))
    # No folder/file at startup: preserve native apply and report missing mirror.
    assert invoke('apply',session,0,0,0)==0x1234;drain()
    assert metric(10)==1 and metric(11)==0 and not disk
    print('PASS missing initial mirror never blocks native application or writes a file')
    assert invoke('save',session,item,0,record,0x29484,0x20007500)==0x1234
    assert metric(1)==1 and not queue
    # No SD request can start until actual native save completion succeeds.
    invoke('out',1,2,3,4);assert not queue
    assert invoke('done',item,1,0,record,0x29484,service)==0x1234;drain()
    assert len(disk)==1 and next(iter(disk.values()))==settings
    assert metric(7)==1 and metric(9)==1 and metric(11)==0
    assert bytes(u.mem_read(record,0x29484))==original
    assert metric(20)==0 and word(0x3fc)==0x31534852 and word(0x1428)==0x31534852
    (ROOT/'buildtmp/a0178-mirror-status.bin').write_bytes(bytes(u.mem_read(slot,1024)))
    print('PASS successful native save triggers private Content write, sync, close and exact readback; native bytes unchanged')
    before=list(disk.items());invoke('apply',session,0,0,0);drain()
    assert metric(9)==2 and list(disk.items())==before
    # Saving unchanged settings uses exclusive-create refusal followed by verify.
    invoke('save',session,item,0,record,0x29484,0x20007500)
    invoke('done',item,1,0,record,0x29484,service);drain()
    assert metric(9)==3 and metric(7)==1 and list(disk.items())==before
    print('PASS reload and repeated save verify immutable mirror without overwriting it')
    # Native failure: do not queue a mirror write.
    failures=metric(11);invoke('save',session,item,0,record,0x29484,0x20007500)
    invoke('done',item,1,3,record,16,service);drain()
    assert metric(11)==failures+1 and not queue and list(disk.items())==before
    print('PASS failed/short native save prevents companion creation')
    name=next(iter(disk));disk[name][4]^=1
    failures=metric(11);invoke('apply',session,0,0,0);drain()
    assert metric(11)==failures+1 and metric(13)==0x103
    assert bytes(u.mem_read(record,0x29484))==original
    print('PASS corrupt mirror is detected without changing embedded settings or stock playback state')
    disk[name]=bytearray(settings)+b'extra'
    failures=metric(11);invoke('apply',session,0,0,0);drain()
    assert metric(11)==failures+1
    print('PASS wrong file length is refused and private file is closed')
    # Media bridge only routes this feature's ITCM file buffer through SRAM.
    media_calls.clear();invoke('read',99,0,0x428,4096)
    assert len(media_calls)==8 and all(x[1][2:]==[slot+512,512] for x in media_calls)
    assert bytes(u.mem_read(0x428,4096))==b'\x3c'*4096
    assert u.reg_read(UC_ARM_REG_R1)==4096
    media_calls.clear();invoke('write',99,0,0x20008000,512)
    assert len(media_calls)==1 and media_calls[0][1]==[99,0,0x20008000,512]
    print('PASS installed media wrappers stage ITCM and preserve direct native buffers and 64-bit return shape')
    before_io=len(io);w(0x1428,0xdeadbeef)
    invoke('apply',session,0,0,0);drain()
    assert metric(20)==1 and metric(13)==0x102 and len(io)==before_io
    assert word(0x1428)==0xdeadbeef
    invoke('apply',session,0,0,0);drain()
    assert metric(20)==1 and len(io)==before_io
    print('PASS between-job canary damage is retained and disables further mirror I/O')
    # Unsupported hardware configuration: inactive, no disk dependency.
    before_io=len(io);w(0xe000ef90,0)
    assert invoke('apply',session,0,0,0)==0x1234
    invoke('out',1,2,3,4)
    assert len(io)==before_io and not queue
    print('PASS unsupported ITCM configuration disables mirror I/O while forwarding native operations')
    print('LIMIT FatFs/media/scheduler boundaries injected; real SD timing, bus access and durability unproved')
    print('ALL PASS')


if __name__=='__main__':main()
