"""Compiled ARM runtime with stock transport boundaries and synthetic DSP state."""
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_granular_owner import build
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *


def main():
    info=build();u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    u.mem_map(0x08000000,0x80000);u.mem_write(info['origin'],Path(info['binary']).read_bytes())
    u.mem_map(0x20000000,0x50000)
    state,packet,sp,stop=0x20001000,0x20002000,0x2004f000,0x0807fff0
    dsp={};writes=[];stops=[];starts=[];samples=[];reads=[];sleeps=[];advance=[True]
    transaction=[];sample_x={0x30001:0x3456}
    bus=(0x08029c8c,0x08031268,0x08030eb8)
    tail=0x20003000
    for track in range(8):
        store=0x20010000+track*0x100
        u.mem_write(0x200470d4+track*0x190+0x60,struct.pack('<I',store))
        u.mem_write(store+0x20,bytes((12+track,)))
        u.mem_write(0x200470d4+track*0x190+0x28,struct.pack('<I',0x20020000+track*0x100))
    def native(uc,address,size,context):
        args=[uc.reg_read(UC_ARM_REG_R0+k) for k in range(3)]
        if address in bus:
            transaction.append(address)
            if address==0x08029c8c:
                assert args[0]==0x20003688
            elif address==0x08031268:
                core,host=args[:2];assert core==0
                if 0xab20<=host<0xab60:target=0x37420+host-0xab20
                elif host in (0xabe0,0xabe1):target=0x372fb+host-0xabe0
                else:assert host==0x8000;target=host
                reads.append(target);uc.reg_write(UC_ARM_REG_R0,dsp.get(target,0)<<8)
            else:
                assert tuple(transaction)==bus
                assert struct.unpack('<I',uc.mem_read(args[0],4))[0]==0x20003688
                assert bytes(uc.mem_read(0x20003684,4))==b'\xff\xff\x00\x00'
                transaction.clear()
        elif address==0x08031200:
            core,value,host=args;assert core==0
            if 0xab00<=host<0xab20:target=0x37400+host-0xab00
            else:
                assert 0xab60<=host<0xabe0
                track,field=divmod(host-0xab60,16)
                target=0x2400+256*track+field
            dsp[target]=value>>8;writes.append((target,value>>8))
        elif address==0x080314d6:
            assert args[0]==0 and args[1] in sample_x
            uc.reg_write(UC_ARM_REG_R0,sample_x[args[1]]<<8)
        elif address==0x08040814:stops.append(args[0])
        elif address==0x08040778:
            starts.append(tuple(args))
            running=struct.unpack('<I',uc.mem_read(state+188,4))[0]|1<<args[0]
            uc.mem_write(state+188,struct.pack('<I',running))
        elif address==0x0804070e:samples.append(tuple(args))
        elif address in (0x0803fc58,0x0803fc6c):
            assert args[1]==0;uc.reg_write(UC_ARM_REG_R0,args[0]+0x20)
        elif address==0x08024150:
            assert args[0]==1;sleeps.append(1)
            if advance[0]:
                for track in range(8):snapshot(track,dsp[0x37401+4*track])
        else:raise AssertionError(hex(address))
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for address in (*bus,0x08031200,0x080314d6,0x08040814,0x08040778,0x0804070e,0x0803fc58,0x0803fc6c,0x08024150):
        u.hook_add(UC_HOOK_CODE,native,None,address,address+1)
    def memory_write(uc,access,address,size,value,context):
        assert state<=address and address+size<=state+316 or packet<=address and address+size<=packet+8 or tail<=address and address+size<=tail+884 or 0x2004e000<=address<0x20050000 or (address,size)==(0x20003684,4)
    u.hook_add(UC_HOOK_MEM_WRITE,memory_write)
    def call(name,*args):
        for k,value in enumerate(args):u.reg_write(UC_ARM_REG_R0+k,value)
        saved=[0x123400+k for k in range(8)]
        for k,value in enumerate(saved):u.reg_write(UC_ARM_REG_R4+k,value)
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,stop|1)
        u.emu_start(info['labels']['c_gr_'+name]|1,stop,count=1000000)
        assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==sp
        assert [u.reg_read(UC_ARM_REG_R4+k) for k in range(8)]==saved
        return u.reg_read(UC_ARM_REG_R0)
    def frame(ready=1,uploading=0):call('runtime_frame',state,ready,uploading)
    transport=0x200122b0+0x20
    def playing(on):u.mem_write(transport,bytes([on]))
    def now(ms):u.mem_write(0x20000820,struct.pack('<I',ms))
    def running():return struct.unpack('<I',u.mem_read(state+188,4))[0]&1
    playing(1)
    def snapshot(track,epoch,active=False,tag=None):
        words=[tag if tag is not None else 0x674331 if active else 0x674732,epoch,100,12+track,0,16384,0x8000,9]
        dsp.update((0x37420+track*8+k,value) for k,value in enumerate(words))
    def message(word,value=0,caller=0):
        u.mem_write(packet,struct.pack('<II',word,value))
        accepted=call('runtime_message',state,packet,caller)
        return accepted,struct.unpack('<II',u.mem_read(packet,8))
    assert call('runtime_size')==316
    dsp[0x30001]=0x9999
    assert call('sample_read',0x30001)==0x3456
    reads.clear()
    frame(0);frame(1,1);assert not writes and not reads
    frame();assert not writes and not reads
    assert call('runtime_mode',state,0,2)==1
    frame();assert not writes and not stops and message(0x905a00)[0]==1
    snapshot(0,1)
    for _ in range(18):
        old=len(writes);frame();assert len(writes)-old==8
    assert len(writes)==144
    frame();assert len(writes)==152 and not starts and not stops
    for track in range(8):
        assert dsp[0x37400+4*track]==0 and dsp[0x37401+4*track]==1
        assert dsp[0x2400+256*track]==track+1 and dsp[0x240f+256*track]==0x6a7a4b
        assert dsp[0x2406+256*track]==8 and dsp[0x2405+256*track]==40
    assert call('runtime_mode',state,0,2)==1
    before=len(writes);frame(1,1);assert len(writes)==before and not stops
    frame();assert stops==[0] and not starts and dsp[0x37400]==0
    epoch=dsp[0x37401];assert epoch==2
    snapshot(0,epoch-1);frame();assert not starts
    snapshot(0,epoch,True);frame();assert not starts
    snapshot(0,epoch);frame();assert starts==[(0,60,127)] and not samples
    assert dsp[0x37400]==0x674e31 and dsp[0x37403]==0
    # Simulate the real native start reaching the message wrapper, then Flow.
    assert message(0x907f00)[1][0]==0x907f00
    snapshot(0,epoch,True)
    assert message(0x905a00,7<<16)==(1,(0xa05a00,7<<16))
    assert message(0x800000,3,0x080407be)[0]==0
    assert message(0x800000,3,0x0804074a)[0]==0
    assert message(0x800000,3)[0]==1
    # Stale active DSP state must not undo the synchronous explicit-stop latch.
    assert message(0x905a00,7<<16)[1][0]==0x905a00
    # A consumed/torn state tag must not make a running Flow randomly retrigger.
    snapshot(0,epoch,True,tag=0)
    assert message(0x905a00,7<<16)[1][0]==0xa05a00
    snapshot(0,epoch)
    assert message(0x905a00,7<<16)[1][0]==0x905a00
    assert call('runtime_put',state,0,3,64)==1
    frame();assert dsp[0x2406]==0
    assert call('runtime_put',state,0,3,100)==1 and call('runtime_put',state,0,4,40)==1
    frame();assert (dsp[0x2406],dsp[0x240b],dsp[0x240d])==(36,40,0)
    config=bytes(u.mem_read(state+168,1));u.mem_write(state+168,bytes([config[0]|128|64|8]))
    assert call('runtime_put',state,0,3,101)==1
    frame();assert (dsp[0x2406],dsp[0x240b],dsp[0x240d])==(0,0,3)
    u.mem_write(state+168,config);call('runtime_put',state,0,3,64);call('runtime_put',state,0,4,0)
    frame();assert (dsp[0x2406],dsp[0x240b],dsp[0x240d])==(0,0,0)
    table=0x2004f800;u.mem_write(0x080408d4,table.to_bytes(4,'little'))
    old_owner=bytes(u.mem_read(state+8,2));old_config=bytes(u.mem_read(state+168,1))
    u.mem_write(state+8,b'\1\1');u.mem_write(state+168,bytes([old_config[0]&~3|1]))
    for play,word in ((1,0),(0,1),(2,0)):
        u.mem_write(table+1,bytes([play]));frame();assert dsp[0x37403]==word
    call('runtime_put',state,0,3,65);frame();assert dsp[0x240d]&1==1
    u.mem_write(state+8,old_owner);u.mem_write(state+168,old_config);call('runtime_put',state,0,3,64);frame()
    assert call('runtime_mode',state,0,0)==1
    frame();epoch=dsp[0x37401];snapshot(0,epoch);frame()
    assert dsp[0x37400]==0 and len(starts)==1
    # Replacement waits for both cores idle, nests across a pack's sample calls,
    # and suppresses frame writes while native memory operations run.
    assert call('runtime_begin_replace',state,1,0)==1
    old=len(writes);old_reads=len(reads)
    assert call('runtime_begin_replace',state,1,1)==1
    frame();assert len(writes)==old and len(reads)==old_reads
    assert call('runtime_store',state,tail)==0
    assert call('runtime_end_replace',state)==1
    assert call('owner_held',state)==1
    import zlib
    knobs=bytes((i*17+7)%128 for i in range(64));configs=bytes((18,0,0,0,0,0,0,0))
    data=b'GR\x02\x08'+knobs+configs;data+=struct.pack('<I',zlib.crc32(data))
    record=bytearray(b'\x55'*884)
    offsets=list(range(296,328))+list(range(404,420))+list(range(520,530))+list(range(860,882))
    for offset,value in zip(offsets,data):record[offset]=value
    u.mem_write(tail,bytes(record));saved_epoch=call('owner_epoch',state,0)
    assert call('runtime_load',state,tail)==1
    assert call('owner_epoch',state,0)==saved_epoch
    assert call('runtime_end_replace',state)==1
    assert bytes(u.mem_read(state+104,64))==knobs and bytes(u.mem_read(state+168,8))==configs
    for _ in range(20):frame()
    assert dsp[0x2404]==knobs[0] and dsp[0x2403]==knobs[1]
    assert dsp[0x37401]>saved_epoch and dsp[0x37400]==0
    snapshot(0,dsp[0x37401]);frame();assert len(starts)==2
    call('runtime_put',state,0,0,(knobs[0]+1)%128)
    assert call('runtime_store',state,tail)==1 and call('runtime_store',state,tail)==0
    u.mem_write(table+1,b'\0')
    began,ended=len(starts),len(stops)
    now(1000);playing(0);frame()
    assert dsp[0x240d]&9==9 and len(starts)==began and len(stops)==ended and dsp[0x37403]==0
    now(2199);frame();assert len(stops)==ended and dsp[0x240d]&8
    now(2200);frame();frame()
    assert len(stops)==ended+1 and dsp[0x240d]&9==1 and not running() and dsp[0x37403]==1 and len(starts)==began
    print('PASS Stop holds new grains, keeps the voice for the tail, then closes it; no start while stopped')
    assert message(0x800000,2)[0]==1
    assert message(0x905a00)[1][0]==0x905a00 and message(0x905a00)[1][0]==0x905a00
    assert message(0x800000,2)[0]==1 and not running()
    print('PASS while stopped, pad notes start and release a Texture track like Triggered')
    now(3000);playing(1);frame()
    assert len(starts)==began+1 and dsp[0x240d]&9==0 and dsp[0x37403]==0 and running()
    now(3100);playing(0);frame();assert dsp[0x240d]&8
    now(3200);playing(1);frame()
    assert dsp[0x240d]&8==0 and len(starts)==began+1 and len(stops)==ended+1
    print('PASS Play starts Texture once; Play during the tail resumes grains without a restart')
    now(3300);snapshot(0,dsp[0x37401])
    for _ in range(9):frame()
    assert len(starts)==began+2 and running()
    print('PASS a Texture voice that ended while playing starts again')
    muted=0x20020000+0x20
    now(4000);u.mem_write(muted,b'\1');frame();assert dsp[0x240d]&9==9
    now(4100);u.mem_write(muted,b'\0');frame();assert dsp[0x240d]&9==0 and len(starts)==began+2
    print('PASS Mute holds new grains on a Texture track and unmute resumes them')
    tempo,ticks=0x20012788+0x20,0x20030020
    u.mem_write(0x2003c410,struct.pack('<I',0x20030000));u.mem_write(tempo,bytes([100]))
    assert call('runtime_shift_turn',state,0,2,30)==1
    frame();assert dsp[0x2401]==14400
    u.mem_write(ticks,struct.pack('<I',24));frame();assert dsp[0x2401]==14400|1<<18
    u.mem_write(ticks,struct.pack('<I',25));frame();assert dsp[0x2401]==14400|1<<18
    assert call('runtime_shift_turn',state,0,2,-40)==1;frame();assert dsp[0x2401]&0x3ffff==13200
    assert call('runtime_clear_knob',state,0,2,1)==1;frame();assert dsp[0x2401]&0x3ffff==0
    call('runtime_shift_turn',state,0,1,10);call('runtime_shift_turn',state,0,3,20);frame()
    assert dsp[0x2408]&0x7f==10 and (dsp[0x2408]>>8)&0x7f==20 and 8<=dsp[0x2408]>>16<=128
    u.mem_write(state+292,bytes([1|4]));call('runtime_put',state,0,3,70);frame();assert dsp[0x240d]&0xf0==0x10|0x40
    u.mem_write(state+292,bytes([0]));call('runtime_clear_knob',state,0,1,1);call('runtime_clear_knob',state,0,3,1);call('runtime_put',state,0,3,64);frame()
    call('runtime_shift_turn',state,0,5,90);frame();assert (dsp[0x240d]>>8)&0x7f==90
    call('runtime_clear_knob',state,0,5,1);frame();assert (dsp[0x240d]>>8)&0x7f==0
    call('runtime_shift_turn',state,0,4,20);frame();assert (dsp[0x240d]>>15)&0xf==2
    # Slice on: Scan sends no free motion and steps a slice per 48 ticks, forward right of the middle.
    call('runtime_put',state,0,3,70);frame();assert dsp[0x2406]==0 and dsp[0x240d]>>19==0
    for tick,step in ((48,1),(96,2),(144,0)):
        u.mem_write(ticks,struct.pack('<I',tick));frame();assert dsp[0x240d]>>19==step,(tick,dsp[0x240d]>>19)
    call('runtime_put',state,0,3,58);u.mem_write(ticks,struct.pack('<I',192));frame();assert dsp[0x240d]>>19==2
    call('runtime_put',state,0,3,64);frame();assert dsp[0x240d]>>19==0
    call('runtime_shift_turn',state,0,4,127);frame();assert (dsp[0x240d]>>15)&0xf==15
    call('runtime_clear_knob',state,0,4,1);frame();assert (dsp[0x240d]>>15)&0xf==0
    print('PASS Timing follows the tempo and syncs on the grid; Scatter, Jitter, Bounce, Pitch Set, Slice steps and Lock reach the DSP')
    # Bounded failure aborts replacement, leaves routes disabled, and restores
    # ordinary stock note handling rather than retaining a stuck held barrier.
    snapshot(0,dsp[0x37401]);frame()  # Ensure an owned Texture for timeout proof.
    advance[0]=False;old=len(sleeps)
    assert call('runtime_begin_replace',state,1,0)==0
    assert len(sleeps)-old==100 and all(dsp[0x37400+4*t]==0 for t in range(8))
    assert all(u.mem_read(state+168+t,1)[0]&3==0 for t in range(8))
    assert call('runtime_end_replace',state)==0
    old=len(writes);frame(0);assert len(writes)==old
    print('PASS actual ARM runtime initializes route/parameter controls in bounded8-word frames; no accesses before DSP ready or during upload')
    print('PASS stale/active acknowledgements cannot activate Texture; current idle applies route before one native start with frontend sample')
    print('PASS explicit Stop latch defeats stale DSP activity; transient consumed tags preserve Flow; real idle permits a new native start')
    print('PASS knob updates route to persistent track controls, mode Off stops without restarting; ARM bounds and callee-saved registers checked')
    print('PASS nested pack/sample barrier yields until both cores idle, blocks frame/save writes, preserves generation across project load and initializes knobs before restart')
    print('PASS bounded100-yield failure leaves all granular routes disabled and stock note operation available; replacement is not authorized')
    print('LIMIT: native accessor/action boundaries are fixtures; firmware wrappers, pack hooks and real DSP scheduling still need integration')


if __name__=='__main__':main()
