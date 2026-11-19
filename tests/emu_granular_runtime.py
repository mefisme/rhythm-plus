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
    assigned='--assigned' in sys.argv
    import os
    oneshot='--oneshot-scan' in sys.argv
    if oneshot:os.environ['RH_GRANULAR_ONESHOT_SCAN']='1'
    direct5='--load-direct5' in sys.argv
    direct4='--load-direct4' in sys.argv or direct5
    direct3='--load-direct3' in sys.argv or direct4
    direct2='--load-direct2' in sys.argv or direct3
    direct='--load-direct' in sys.argv or direct2
    if direct:os.environ['RH_GRANULAR_LOAD_DIRECT']='5' if direct5 else '4' if direct4 else '3' if direct3 else '2' if direct2 else '1'
    leave='--leave-sounding' in sys.argv
    times='--load-times' in sys.argv
    if times:os.environ['RH_GRANULAR_LOAD_TIMES']='1'
    queue_gap='--leave-queue' in sys.argv
    if queue_gap:os.environ['RH_GRANULAR_LEAVE_QUEUE']='3'
    replace_ack='--replace-ack' in sys.argv
    if replace_ack:os.environ['RH_GRANULAR_REPLACE_ACK']='1'
    leave_fade='--leave-fade' in sys.argv
    if leave_fade:os.environ['RH_GRANULAR_LEAVE_FADE']='200'
    sweep='--route-sweep' in sys.argv
    if sweep:os.environ['RH_GRANULAR_ROUTE_SWEEP']='1'
    carry='--carry' in sys.argv
    if carry:os.environ['RH_GRANULAR_CARRY']='1'
    soft='--soft-leave' in sys.argv
    if soft:os.environ['RH_GRANULAR_SOFT_LEAVE']='1'
    choke='--keep-choke' in sys.argv
    if choke:os.environ['RH_GRANULAR_KEEP_CHOKE']='1'
    busy='--load-busy' in sys.argv
    if busy:os.environ['RH_GRANULAR_LOAD_BUSY']='1'
    stretch_load='--stretch-load' in sys.argv
    handoff='--stretch-handoff' in sys.argv
    if handoff:os.environ['RH_GRANULAR_STRETCH_HANDOFF']='1'
    stretch_on=0x2004e800 if stretch_load or sweep or handoff else 0
    info=build(pages=assigned,assign=assigned,stretch_on=stretch_on);u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    u.mem_map(0x08000000,0x80000);u.mem_write(info['origin'],Path(info['binary']).read_bytes())
    u.mem_map(0x20000000,0x50000)
    state,packet,sp,stop=0x20001000,0x20002000,0x2004f000,0x0807fff0
    dsp={};writes=[];stops=[];starts=[];samples=[];reads=[];sleeps=[];advance=[True];route_off=[]
    refreshes=[];stock=[5]*8
    queue=[0,0,0]  # the stock message queue: the ARM's write index, core 1's read index, reads since the last stop
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
            if target==0x37400 and not value:route_off.append((len(stops),dsp.get(0x37420),queue[1]==queue[0],len(sleeps)))
        elif address==0x080314d6 and args[1]==0x307b6:
            assert args[0]==0;queue[2]+=1
            if queue[2]>=3:queue[1]=queue[0]
            uc.reg_write(UC_ARM_REG_R0,queue[1]<<8)
        elif address==0x080314d6 and 0x37400<=args[1]<0x37420:
            assert args[0]==0;uc.reg_write(UC_ARM_REG_R0,dsp.get(args[1],0)<<8)
        elif address==0x080314d6:
            assert args[0]==0 and args[1] in sample_x
            uc.reg_write(UC_ARM_REG_R0,sample_x[args[1]]<<8)
        elif address==0x08046410:uc.reg_write(UC_ARM_REG_R0,stock[(args[0]-16)&7]) if args[1]==0 else uc.reg_write(UC_ARM_REG_R0,0)
        elif address==0x0803081c:refreshes.append(args[0])
        elif address==0x08040814:
            stops.append(args[0]);queue[0]=(queue[0]+1)&15;queue[2]=0
            uc.mem_write(0x20006f38,struct.pack('<I',queue[0]))
        elif address==0x08040778:
            starts.append(tuple(args))
            running=struct.unpack('<I',uc.mem_read(state+188,4))[0]|1<<args[0]
            uc.mem_write(state+188,struct.pack('<I',running))
        elif address==0x0804070e:samples.append(tuple(args))
        elif address in (0x0803fc58,0x0803fc6c):
            assert args[1]==0;uc.reg_write(UC_ARM_REG_R0,args[0]+0x20)
        elif address==0x08024150:
            assert args[0]==1;sleeps.append(1)
            if times:uc.mem_write(0x20000820,struct.pack('<I',struct.unpack('<I',uc.mem_read(0x20000820,4))[0]+1))
            if callable(advance[0]):advance[0]()
            elif advance[0]:
                for track in range(8):snapshot(track,dsp[0x37401+4*track])
        else:raise AssertionError(hex(address))
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for address in (*bus,0x08031200,0x080314d6,0x08046410,0x0803081c,0x08040814,0x08040778,0x0804070e,0x0803fc58,0x0803fc6c,0x08024150):
        u.hook_add(UC_HOOK_CODE,native,None,address,address+1)
    def memory_write(uc,access,address,size,value,context):
        assert state<=address and address+size<=state+(404 if assigned else 316) or leave_fade and state+469<=address and address+size<=state+(480 if handoff else 477 if carry else 472) or times and state+472<=address and address+size<=state+480 or packet<=address and address+size<=packet+8 or tail<=address and address+size<=tail+884 or 0x2004e000<=address<0x20050000 or (address,size)==(0x20003684,4)
    u.hook_add(UC_HOOK_MEM_WRITE,memory_write)
    def call(name,*args):
        for k,value in enumerate(args):u.reg_write(UC_ARM_REG_R0+k,value)
        saved=[0x123400+k for k in range(8)]
        for k,value in enumerate(saved):u.reg_write(UC_ARM_REG_R4+k,value)
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,stop|1)
        try:u.emu_start(info['labels']['c_gr_'+name]|1,stop,count=1000000)
        except Exception:
            near=sorted((v,k) for k,v in info['labels'].items() if v<=u.reg_read(UC_ARM_REG_PC))[-1:]
            print('CRASH in',name,'pc',hex(u.reg_read(UC_ARM_REG_PC)),'near',near,'r0-r3',[hex(u.reg_read(UC_ARM_REG_R0+k)) for k in range(4)]);raise
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
    if handoff:return stretch_handoff(u,call,frame,dsp,writes,stops,starts,snapshot,state,tail,playing,message,now)
    if stretch_load:return stretch_project(u,call,frame,dsp,writes,starts,snapshot,state,tail)
    if carry:return carry_test(u,call,frame,dsp,writes,stops,starts,snapshot,state,tail,playing,message,now,refreshes,stock,soft,choke,busy)
    if sweep:return route_sweep(u,call,frame,dsp,writes,snapshot,state,now,leave_fade)
    if leave_fade:return fade_out(u,call,frame,dsp,writes,stops,starts,snapshot,state,tail,advance,playing,sleeps,message,now,oneshot)
    if leave:return leave_sounding(u,call,frame,dsp,stops,starts,snapshot,state,tail,advance,route_off,playing,sleeps,5 if direct5 else 20,times,queue_gap,replace_ack)
    assert call('runtime_size')==(404 if assigned else 316)
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
        u.mem_write(table+1,bytes([play]));frame()
        # --oneshot-scan: the route word stays 0 and field 13 bit 2 marks One Shot
        if oneshot:assert dsp[0x37403]==0 and (dsp[0x240d]>>2&1)==word,(play,dsp[0x37403],hex(dsp[0x240d]))
        else:assert dsp[0x37403]==word
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
    loaded_stops=len(stops)
    # --load-direct2: core 1's own idle state (not yet acknowledged by core 0) counts as quiet
    if direct2:dsp[0x37420]=0x674531
    assert call('runtime_end_replace',state)==1
    assert bytes(u.mem_read(state+104,64))==knobs and bytes(u.mem_read(state+168,8))==configs
    if direct:
        # --load-direct: the setup and the route are out before the first frame, with no stop
        assert dsp[0x2404]==knobs[0] and dsp[0x2403]==knobs[1] and dsp[0x37400]==0x674e31
        assert dsp[0x37401]==saved_epoch and len(stops)==loaded_stops,(dsp[0x37401],saved_epoch,len(stops),loaded_stops)
        frame();assert len(starts)==2 and len(stops)==loaded_stops
        print('PASS a project load sets up Granular at once: its route is on before the first frame, no note is stopped')
    else:
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
    assert len(stops)==ended+1 and dsp[0x240d]&9==1 and not running() and dsp[0x37403]==(not oneshot) and (dsp[0x240d]>>2&1)==oneshot and len(starts)==began
    print('PASS Stop holds new grains, keeps the voice for the tail, then closes it; no start while stopped')
    assert message(0x800000,2)[0]==1
    assert message(0x905a00)[1][0]==0x905a00 and message(0x905a00)[1][0]==0x905a00
    assert message(0x800000,2)[0]==1 and not running()
    print('PASS while stopped, pad notes start and release a Texture track like Triggered')
    now(3000);playing(1);frame()
    assert len(starts)==began+1 and dsp[0x240d]&13==0 and dsp[0x37403]==0 and running()
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
    # Burst (Shift K7) and Burst Speed (Shift K8) in field 7 above Zone 127.
    call('runtime_shift_turn',state,0,6,30);frame();assert dsp[0x2407]==127|3<<8|64<<12,hex(dsp[0x2407])
    call('runtime_shift_turn',state,0,7,40);frame();assert dsp[0x2407]==127|3<<8|104<<12,hex(dsp[0x2407])
    call('runtime_shift_turn',state,0,6,127);frame();assert (dsp[0x2407]>>8)&0xf==15
    call('runtime_clear_knob',state,0,7,1);call('runtime_clear_knob',state,0,6,1);frame();assert dsp[0x2407]==127|64<<12
    # Setting bit 4 Burst fade, bits 5..6 Burst pitch: field 7 bits 19 and 20..21; Pitch Set stays in field 13 bits 5..7.
    u.mem_write(state+292,bytes([4|16|64]));call('runtime_put',state,0,3,63);frame()
    assert dsp[0x2407]==127|64<<12|1<<19|2<<20 and (dsp[0x240d]>>5)&0x3ff==2,(hex(dsp[0x2407]),hex(dsp[0x240d]))
    u.mem_write(state+292,bytes([0]));call('runtime_put',state,0,3,64);frame();assert dsp[0x2407]==127|64<<12
    print('PASS Burst sends its grain count, Speed, fade and pitch to the DSP; Clear sets them to off and the middle')
    print('PASS Timing follows the tempo and syncs on the grid; Scatter, Jitter, Bounce, Pitch Set, Slice steps and Lock reach the DSP')
    if assigned:
        u.mem_write(state+200,struct.pack('<I',255));published=[]
        for _ in range(8):
            dirty=struct.unpack('<I',u.mem_read(state+200,4))[0]
            u.mem_write(state+200,struct.pack('<I',dirty|1));old=len(writes);frame()
            published.extend((a-0x2404)//256 for a,v in writes[old:] if 0x2404<=a<=0x2b04 and (a-0x2404)%256==0)
        assert set(published)==set(range(8)),published
        print('PASS continuously changing track 1 cannot starve other tracks in bounded control publisher')
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


def stretch_project(u,call,frame,dsp,writes,starts,snapshot,state,tail):
    """To a project with Granular on track 0 from one with no Granular and stretch on tracks 0 and 1: with Granular not yet
    set up, and with Granular set up by an earlier project. Track 1 stays stretched.

    The DSP model: a route off answers idle with its epoch, Granular's route answers active, a stretch route (word 15 =
    stretch's key) shows the route key. Stretch's frame hands a track back once Granular wants it."""
    import struct,zlib
    ON,KEY,HOST,GR=0x2004e800,0x674e31,0x675354,0x6a7a4b
    def dsp_block():
        for t in range(8):
            c=dsp.get(0x37400+4*t,0)
            if c==0:snapshot(t,dsp.get(0x37401+4*t,0),tag=0x674732)
            elif dsp.get(0x240f+256*t)==HOST:snapshot(t,dsp.get(0x37401+4*t,0),tag=KEY)
            else:snapshot(t,dsp.get(0x37401+4*t,0),active=True)
    def stretch_frame():
        on=u.mem_read(ON,1)[0]
        for t in range(8):
            if on>>t&1 and call('runtime_granular_busy',state,t):
                dsp.update({0x2400+256*t:t+1,0x2402+256*t:0,0x240f+256*t:GR,0x37403+4*t:0})
                on&=~(1<<t)
        u.mem_write(ON,bytes([on]))
    def stretch_takes(t):
        dsp.update({0x37400+4*t:KEY,0x37403+4*t:2,0x2400+256*t:0,0x2402+256*t:5,0x240f+256*t:HOST})
        u.mem_write(ON,bytes([u.mem_read(ON,1)[0]|1<<t]))
    def load(configs):
        knobs=bytes(64);data=b'GR\x02\x08'+knobs+bytes(configs);data+=struct.pack('<I',zlib.crc32(data))
        record=bytearray(b'\x55'*884)
        offsets=list(range(296,328))+list(range(404,420))+list(range(520,530))+list(range(860,882))
        for offset,value in zip(offsets,data):record[offset]=value
        assert call('runtime_begin_replace',state,1,0)==1
        u.mem_write(tail,bytes(record));assert call('runtime_load',state,tail)==1
        assert call('runtime_end_replace',state)==1
    def granular_project():
        mark=len(writes);starts.clear()
        load((18,0,0,0,0,0,0,0))
        words={k:dsp.get(k) for k in (0x37400,0x37401,0x2400,0x2402,0x240f)}
        assert words=={0x37400:KEY,0x37401:call('owner_epoch',state,0),0x2400:1,0x2402:words[0x2402],0x240f:GR},words
        assert u.mem_read(ON,1)[0]&2,'track 1 is still stretch\'s'
        played=None
        for n in range(40):
            stretch_frame();frame();dsp_block()
            if starts:played=n;break
        track1=[w for w in writes[mark:] if w[0] in (0x37404,0x37405,0x37406,0x37407,0x2500,0x2502,0x250f)]
        assert not track1,('a track stretch keeps got Granular writes',track1)
        assert played==0,('track 0 plays late or never',played)
    for t in range(8):dsp[0x37401+4*t]=0;snapshot(t,0,tag=0x674531)
    u.mem_write(ON,b'\0');stretch_takes(0);stretch_takes(1);dsp_block()
    for _ in range(3):frame();dsp_block()
    assert not writes,writes
    granular_project()
    print('PASS Granular set up for the first time: a stretched track the project makes Granular plays at once, all its words Granular\'s')
    load((0,)*8)
    for _ in range(4):stretch_frame();frame();dsp_block()
    stretch_takes(0);dsp_block()
    for _ in range(3):stretch_frame();frame();dsp_block()
    granular_project()
    print('PASS Granular set up before: the same after a project where stretch took the track')
    print('PASS a track stretch keeps gets no Granular route or word writes')

def stretch_handoff(u,call,frame,dsp,writes,stops,starts,snapshot,state,tail,playing,message,now):
    """--stretch-handoff: to a project that makes a stretched track Granular. Stretch's sound crossfades out (word 3 = 3)
    under the stock stop; Granular takes the track 6 ms later once the voice is quiet (at most 20 ms), and a note-on that
    lands in the fade plays at the take. The stretch model: it leaves a track alone while Granular hands it off."""
    import struct,zlib
    ON,KEY,HOST,GR=0x2004e800,0x674e31,0x675354,0x6a7a4b
    def load(configs):
        data=b'GR\x02\x08'+bytes(64)+bytes(configs);data+=struct.pack('<I',zlib.crc32(data))
        record=bytearray(b'\x55'*884)
        offsets=list(range(296,328))+list(range(404,420))+list(range(520,530))+list(range(860,882))
        for offset,value in zip(offsets,data):record[offset]=value
        assert call('runtime_begin_replace',state,1,0,1)==1
        u.mem_write(tail,bytes(record));assert call('runtime_load',state,tail)==1
        assert call('runtime_end_replace',state)==1
    def stretch_frame():
        on=u.mem_read(ON,1)[0]
        for t in range(8):
            if on>>t&1 and not call('stretch_handoff',state,t) and call('runtime_granular_busy',state,t):
                dsp.update({0x2400+256*t:t+1,0x2402+256*t:0,0x240f+256*t:GR,0x37403+4*t:call('route_word',state,t)})
                on&=~(1<<t)
        u.mem_write(ON,bytes([on]))
    def stretched(t):
        dsp.update({0x37400+4*t:KEY,0x37403+4*t:2,0x2400+256*t:0,0x2402+256*t:5,0x240f+256*t:HOST})
        u.mem_write(ON,bytes([u.mem_read(ON,1)[0]|1<<t]));snapshot(t,dsp.get(0x37401+4*t,0),tag=KEY)
    def note_on(t,note,velocity):return message(0x900000|t<<16|velocity<<8|t,((note-60)<<16)&0xffffffff)[0]
    def taken(t):return dsp[0x240f+256*t]==GR and dsp[0x37400+4*t]==KEY and call('owner_mode',state,t)==1
    u.mem_write(0x080408d4,struct.pack('<I',0x20006860))
    for t in range(8):dsp[0x37400+4*t]=0;dsp[0x37401+4*t]=0;snapshot(t,0,tag=0x674531)
    playing(1);now(1000);u.mem_write(ON,b'\0');stretched(0)
    for _ in range(3):stretch_frame();frame()
    mark,m_stop=len(writes),len(stops)
    load((17,0,0,0,0,0,0,0))
    new=[w for w in writes[mark:] if w[0] in (0x37400,0x37401,0x37403,0x2400,0x2402,0x240f)]
    assert new==[(0x37403,3)] and stops[m_stop:]==[0],('the load cut the stretched sound',new,stops[m_stop:])
    stretch_frame();frame()
    assert dsp[0x240f]==HOST and dsp[0x37403]==3 and not taken(0),'stretch or Granular wrote during the fade'
    print('PASS to Granular from stretch: the load starts the crossfade and the stock stop, and writes nothing else')
    m_start=len(starts)
    assert note_on(0,64,100)==0,'a note in the fade went through'
    now(1003);stretch_frame();frame()
    assert not taken(0) and len(starts)==m_start,'taken before the fade ended'
    now(1006);stretch_frame();frame()
    assert not taken(0),'taken while the voice still sounds'
    snapshot(0,dsp[0x37401],tag=0x674531);stretch_frame();frame()
    assert taken(0) and dsp[0x37403] in (0,1),('not taken after the fade',hex(dsp[0x240f]),dsp[0x37403])
    assert starts[m_start:]==[(0,64,100)],('the held note did not play at the take',starts[m_start:])
    stretch_frame();frame()
    assert taken(0) and not u.mem_read(ON,1)[0]&1,'stretch kept the track after the take'
    print('PASS 6 ms after the load and with the voice quiet, Granular takes the track and plays the note held in the fade')
    load((0,)*8)
    for _ in range(3):stretch_frame();frame()
    now(2000);stretched(0)
    for _ in range(2):stretch_frame();frame()
    m_start=len(starts)
    load((17,0,0,0,0,0,0,0))
    assert note_on(0,62,90)==0 and message(0x800000|0<<16|0,2)[0]==0,'the held note or its note-off went through'
    now(2010);stretch_frame();frame()
    assert not taken(0)
    now(2020);stretch_frame();frame()
    assert taken(0),'the 20 ms cap did not take the track'
    assert starts[m_start:]==[],'a note that ended in the fade played'
    print('PASS a voice that rings on: taken at 20 ms; a note that starts and ends in the fade is dropped')

def leave_sounding(u,call,frame,dsp,stops,starts,snapshot,state,tail,advance,route_off,playing,sleeps,limit,times=False,queue_gap=False,replace_ack=False):
    """A project change while a Granular Texture track sounds: its note stops while Granular still has the route, and the
    route goes back after the stop reached core 1 (queue_gap) or once the voice is idle, at most limit ms. The DSP model:
    the voice stays active until its note stops; core 1 takes a stop on the third read of its queue index."""
    import struct,zlib
    QUIET=(0x674531,0x674732)
    def load(configs,ok=1):
        data=b'GR\x02\x08'+bytes(64)+bytes(configs);data+=struct.pack('<I',zlib.crc32(data))
        record=bytearray(b'\x55'*884)
        offsets=list(range(296,328))+list(range(404,420))+list(range(520,530))+list(range(860,882))
        for offset,value in zip(offsets,data):record[offset]=value
        assert call('runtime_begin_replace',state,1,0)==ok
        if not ok:return
        u.mem_write(tail,bytes(record));assert call('runtime_load',state,tail)==1
        assert call('runtime_end_replace',state)==1
    def sounding():
        load((18,0,0,0,0,0,0,0));frame()
        snapshot(0,dsp[0x37401],active=True)
        return len(stops),len(sleeps)
    for t in range(8):dsp[0x37401+4*t]=0;snapshot(t,0,tag=0x674531)
    playing(1);load((18,0,0,0,0,0,0,0));frame()
    assert starts,'Texture did not start'
    snapshot(0,dsp[0x37401],active=True)
    mark=len(stops)
    def block():
        for t in range(8):
            if t==0 and len(stops)==mark and dsp.get(0x37400)==0x674e31:snapshot(0,dsp[0x37401],active=True)
            else:snapshot(t,dsp[0x37401+4*t])
    advance[0]=block;route_off.clear()
    load((0,)*8)
    assert route_off,'the route never went back'
    stopped,status,caught,_=route_off[0]
    assert stopped>mark,('the route went back before the note stopped',stopped,mark)
    if queue_gap:
        assert caught,'the route went back before core 1 took the stop'
        print('PASS leaving a project with a sounding Granular track: the note stops first, the route goes back once core 1 has the stop')
    else:
        assert status in QUIET,('the route went back while the voice sounded',hex(status))
        print('PASS leaving a project with a sounding Granular track: the note stops first, the route goes back when the voice is idle')
    advance[0]=True;mark,slept0=sounding()
    def never_idle():
        if not route_off:snapshot(0,dsp[0x37401],active=True)
        else:
            for t in range(8):snapshot(t,dsp[0x37401+4*t])
    advance[0]=never_idle;route_off.clear()
    load((0,)*8)
    gap=route_off[0][3]-slept0
    assert route_off and route_off[0][0]>mark and gap==(0 if queue_gap else limit),(gap,limit)
    print('PASS the route goes back with no sleep: core 1 took the stop' if queue_gap else f'PASS a voice that never reports idle gives the route back after {limit} ms')
    if times:
        rec=bytes(u.mem_read(state+472,8))
        assert rec[5]&(1|2|16)==1|2|16 and rec[5]&4 and rec[6]>=2,rec.hex()
        if queue_gap:assert rec[0]==0 and not rec[5]&8 and rec[7]==2,rec.hex()
        else:assert rec[0]==limit and rec[5]&8 and rec[7] in (0x4e,0x43,0x41),rec.hex()
        print(f'PASS the change is timed: leave wait {rec[0]} ms, stop wait {rec[1]} ms, load {rec[2]|rec[3]<<8} ms, loader {rec[4]} ms, flags {rec[5]:#x}')
    # The old note fades for longer than the change may wait: the voice stays active after the route goes back.
    advance[0]=True;mark,slept0=sounding()
    def fading():
        for t in range(8):snapshot(t,dsp[0x37401+4*t],active=t==0)
    advance[0]=fading;route_off.clear()
    if replace_ack:
        load((0,)*8)
        held=len(sleeps)-route_off[0][3]
        assert held<=2,('the change waited for the fade',held)
        print(f'PASS the change goes on once core 1 answers the new epoch ({held} ms), while the old note fades')
    else:
        load((0,)*8,ok=0)
        print('PASS without the epoch answer rule, a fade longer than 100 ms fails the change')

def fade_out(u,call,frame,dsp,writes,stops,starts,snapshot,state,tail,advance,playing,sleeps,message,now,oneshot=False):
    """--leave-fade: a project change while a Granular track sounds keeps Granular's route while the stopped note fades,
    so the plain sample is never heard, and goes on once core 1 answers. The DSP model: the voice stays active until
    the test ends its fade."""
    import struct,zlib
    KEY=0x674e31
    def load(configs):
        data=b'GR\x02\x08'+bytes(64)+bytes(configs);data+=struct.pack('<I',zlib.crc32(data))
        record=bytearray(b'\x55'*884)
        offsets=list(range(296,328))+list(range(404,420))+list(range(520,530))+list(range(860,882))
        for offset,value in zip(offsets,data):record[offset]=value
        assert call('runtime_begin_replace',state,1,0)==1
        u.mem_write(tail,bytes(record));assert call('runtime_load',state,tail)==1
        assert call('runtime_end_replace',state)==1
    leaving=lambda:u.mem_read(state+469,1)[0]&1
    def fading():
        for t in range(8):snapshot(t,dsp[0x37401+4*t],active=t==0)
    def leave(configs):
        for t in range(8):snapshot(t,dsp[0x37401+4*t],tag=0x674531)
        advance[0]=True;load((18,0,0,0,0,0,0,0));frame()
        snapshot(0,dsp[0x37401],active=True)
        advance[0]=fading;mark,slept,stopped=len(writes),len(sleeps),len(stops)
        load(configs)
        new=writes[mark:]
        assert len(stops)>stopped,'the note did not stop'
        assert (0x37400,0) not in new,('the route went back during the change',new)
        assert (0x37403,1) in new and dsp[0x37401]==call('owner_epoch',state,0),new
        assert len(sleeps)-slept<=2,('the change waited for the fade',len(sleeps)-slept)
        if not configs[0]:
            pool=[w for w in new if 0x2400<=w[0]<0x2410]
            assert not pool,('the fading track got new settings during the change',pool)
        return mark
    for t in range(8):dsp[0x37401+4*t]=0;snapshot(t,0,tag=0x674531)
    playing(1);now(1000)
    leave((0,)*8)
    assert dsp[0x37400]==KEY and leaving()
    frame();frame();assert dsp[0x37400]==KEY and leaving(),'the route went back while the note fades'
    print('PASS the change goes on at once and Granular keeps the route while the stopped note fades')
    mark=len(writes);snapshot(0,dsp[0x37401],tag=0x674531);frame()
    assert dsp[0x37400]==0 and dsp[0x37403]==(0 if oneshot else 1) and not leaving()
    assert {w[0] for w in writes[mark:]}>=set(range(0x2400,0x2410)),'the track went back without its settings'
    print("PASS the route goes back once the voice is idle, with the new project's settings")
    now(2000);leave((0,)*8);now(2199);frame();assert dsp[0x37400]==KEY and leaving()
    now(2200);frame();assert dsp[0x37400]==0 and not leaving()
    print('PASS the route goes back after 200 ms if the voice never reports idle')
    now(3000);leave((0,)*8);assert leaving()
    message(0x900000);assert dsp[0x37400]==0 and not leaving()
    print('PASS a note on the track takes the route back before it plays')
    now(4000);mark=leave((18,0,0,0,0,0,0,0))
    assert (0x37400,0) not in writes[mark:] and dsp[0x37400]==KEY and not leaving() and call('owner_mode',state,0)==2,writes[mark:]
    frame();frame();assert (0x37400,0) not in writes[mark:]
    print('PASS a project with Granular on the same track keeps the route: no hand-back, no gap')


def route_sweep(u,call,frame,dsp,writes,snapshot,state,now,leave_fade):
    """--route-sweep: a route left on the key while Granular and stretch are off goes back to the plain player within
    8 frames; a stretched track, a Granular track and (with --leave-fade) a fading track keep theirs."""
    KEY=0x674e31
    for t in range(8):dsp[0x37400+4*t]=0;dsp[0x37401+4*t]=0;snapshot(t,0,tag=0x674531)
    frame()
    dsp[0x37404]=KEY;dsp[0x37408]=KEY;u.mem_write(0x2004e800,bytes((1<<2,)))
    for ms in range(100,116):now(ms);frame()
    assert dsp[0x37404]==0,('the stuck route stayed on',hex(dsp[0x37404]))
    assert dsp[0x37408]==KEY,'a stretched track lost its route'
    print('PASS a route left on the key with Granular and stretch off goes back to the plain player; a stretched track keeps its route')
    u.mem_write(0x2004e800,bytes((0,)))
    if leave_fade:
        snapshot(2,0,active=True)
        u.mem_write(state+469,bytes((1<<2,)));u.mem_write(state+470,(200).to_bytes(2,'little'))
        for ms in range(200,208):now(ms);frame()
        assert dsp[0x37408]==KEY,'a fading track lost its route'
        u.mem_write(state+469,bytes((0,)))
        snapshot(2,0,tag=0x674531)
        print('PASS a track Granular keeps while its note fades keeps its route')
    for ms in range(300,308):now(ms);frame()
    assert dsp[0x37408]==0
    print('PASS the sweep reaches every track within 8 frames')


def carry_test(u,call,frame,dsp,writes,stops,starts,snapshot,state,tail,playing,message,now,refreshes,stock,soft=False,choke=False,busy=False):
    """--carry: a project change keeps a playing Texture track that stays Texture on the same sample; otherwise the
    note fades and the stock's settings for that track wait for the fade or for a note."""
    import struct,zlib
    KEY=0x674e31
    def load(configs,apply=1):
        data=b'GR\x02\x08'+bytes(64)+bytes(configs);data+=struct.pack('<I',zlib.crc32(data))
        record=bytearray(b'\x55'*884)
        offsets=list(range(296,328))+list(range(404,420))+list(range(520,530))+list(range(860,882))
        for offset,value in zip(offsets,data):record[offset]=value
        assert call('runtime_begin_replace',state,1,0,apply)==1
        if apply:u.mem_write(tail,bytes(record));assert call('runtime_load',state,tail)==1
        assert call('runtime_end_replace',state)==1
    def record_for(configs):
        data=b'GR'+bytes(64)+bytes(configs);data+=struct.pack('<I',zlib.crc32(data))
        record=bytearray(b'U'*884)
        offsets=list(range(296,328))+list(range(404,420))+list(range(520,530))+list(range(860,882))
        for offset,value in zip(offsets,data):record[offset]=value
        return record
    GL=lambda:u.mem_read(state+469,1)[0]
    GD=lambda:u.mem_read(state+472,1)[0]
    running=lambda:struct.unpack('<I',u.mem_read(state+188,4))[0]&1
    def sent(sample):u.mem_write(0x20006860,bytes((sample,)))
    def sounding():
        frame();snapshot(0,dsp[0x37401],active=True);frame()
        assert running() and dsp[0x37400]==KEY,(running(),hex(dsp[0x37400]))
    for t in range(8):dsp[0x37400+4*t]=0;dsp[0x37401+4*t]=0;snapshot(t,0,tag=0x674531)
    playing(1);now(1000);sent(5);stock[0]=5
    load((18,0,0,0,0,0,0,0));sounding()
    mark,m_stop,m_start,epoch=len(writes),len(stops),len(starts),dsp[0x37401]
    load((18,0,0,0,0,0,0,0));frame();frame()
    new=writes[mark:]
    assert len(stops)==m_stop and len(starts)==m_start,('the note stopped or restarted',len(stops)-m_stop,len(starts)-m_start)
    assert (0x37400,0) not in new and not [w for w in new if w[0]==0x37401 and w[1]!=epoch] and dsp[0x37400]==KEY and running(),new
    assert {w[0] for w in new}>=set(range(0x2400,0x2410)),'the new settings did not go out'
    assert message(0x800000,3,caller=0x0804074a)[0]==0,'the stock source choke stopped the carried note'
    print('PASS reloading the same project: the Texture note plays on with no stop and no restart')
    stock[0]=6;m_stop,m_start=len(stops),len(starts)
    load((18,0,0,0,0,0,0,0));frame();frame()
    assert len(stops)>m_stop and not GL()&1 and call('owner_mode',state,0)==2 and len(starts)>m_start,(len(stops)-m_stop,GL(),len(starts)-m_start)
    print('PASS a Granular project with another sample: the old note stops and a new one starts')
    sent(6);sounding();m_stop=len(stops);mark,epoch=len(writes),dsp[0x37401]
    load((0,)*8)
    assert len(stops)>m_stop and GL()&1 and dsp[0x37400]==KEY
    if soft:
        held=[w for w in writes[mark:] if w[0] in (0x37400,0x37403) or w[0]==0x37401 and w[1]!=epoch]
        assert not held,('the change wrote the route, epoch or word 3 while the note sounds',held)
        print('PASS leaving: only the stock stop goes out while the note sounds; route, epoch and word 3 wait')
    assert call('runtime_refresh',state,0)==1 and GD()&1 and not refreshes,'the fading track got its new settings'
    assert call('runtime_refresh',state,1)==0,'a track Granular does not fade was held'
    message(0x900000)
    assert refreshes==[0] and not GD() and dsp[0x37400]==0,(refreshes,GD(),hex(dsp[0x37400]))
    if soft:assert dsp[0x37401]!=epoch,'the epoch did not move on when the track went back'
    print('PASS leaving for a project without Granular: the stock settings wait, and a note sends them first')
    refreshes.clear();now(2000);snapshot(0,dsp[0x37401],tag=0x674531);load((18,0,0,0,0,0,0,0));sounding()
    load((0,)*8);assert call('runtime_refresh',state,0)==1 and not refreshes
    snapshot(0,dsp[0x37401],active=True);now(2010);frame();assert not refreshes and dsp[0x37400]==KEY
    snapshot(0,dsp[0x37401],tag=0x674531);frame()
    assert refreshes==[0] and dsp[0x37400]==0,(refreshes,hex(dsp[0x37400]))
    print('PASS with no note, the stock settings go out when the fade ends')
    refreshes.clear();snapshot(0,dsp[0x37401],tag=0x674531);load((18,0,0,0,0,0,0,0));sounding();m_stop=len(stops)
    load((18,0,0,0,0,0,0,0),apply=0)
    assert len(stops)>m_stop,'a sample load did not stop the note'
    print('PASS a sample or pack load stops the note as before')
    if soft:
        u.mem_write(0x080408d4,struct.pack('<I',0x20006860))  # the stock pointer the play mode check reads
        for t in range(8):snapshot(t,dsp[0x37401+4*t],tag=0x674531)
        load((17,0,0,0,0,0,0,0));frame();snapshot(0,dsp[0x37401],active=True);frame()
        assert call('owner_mode',state,0)==1
        mark,m_stop,epoch=len(writes),len(stops),dsp[0x37401]
        load((17,0,0,0,0,0,0,0));frame()
        bad=[w for w in writes[mark:] if w[0] in (0x37400,0x37403) and w[1]!=dsp[w[0]] or w[0]==0x37401 and w[1]!=epoch]
        assert len(stops)==m_stop and not bad and call('owner_mode',state,0)==1 and dsp[0x37400]==KEY,(len(stops)-m_stop,bad)
        print('PASS reloading a project with a Triggered track: no stop, and route, epoch and word 3 stay')
        for t in range(8):snapshot(t,dsp[0x37401+4*t],tag=0x674531)
        load((0,)*8);now(9000);frame()
        dsp[0x37408]=KEY;assert not GL()&4
        for _ in range(8):frame()  # the clock does not move: the sweep must still reach every track
        assert dsp[0x37408]==0,'a stuck route on track 3 stayed with a steady frame clock'
        print('PASS with a steady frame clock the route check still reaches every track')
    if choke:
        for t in range(8):snapshot(t,dsp[0x37401+4*t],tag=0x674531)
        load((26,0,0,0,0,0,0,0));frame();snapshot(0,dsp[0x37401],active=True);frame()
        assert call('owner_mode',state,0)==2 and running()
        m_stop,m_start=len(stops),len(starts)
        load((26,0,0,0,0,0,0,0));frame();frame()
        assert len(stops)==m_stop and len(starts)==m_start and running(),('Retrigger Texture stopped or restarted',len(stops)-m_stop,len(starts)-m_start)
        assert message(0x800000,3,caller=0x0804074a)[0]==0,'the stock source choke after the load got through'
        assert message(0x800000,3,caller=0x0804074a)[0]==1,'a later source choke was dropped'
        print('PASS reloading with Texture and Retrigger: one note plays on; only the source choke after the load is dropped')
    if busy:
        assert call('runtime_begin_replace',state,1,0,1)==1
        during=[call('runtime_granular_busy',state,t) for t in range(8)]
        u.mem_write(tail,bytes(record_for((26,0,0,0,0,0,0,0))));assert call('runtime_load',state,tail)==1
        loaded=[call('runtime_granular_busy',state,t) for t in range(8)]
        assert call('runtime_end_replace',state)==1
        assert during[0] and loaded[0] and not any(during[1:]) and not any(loaded[1:]),(during,loaded)
        print("PASS during a project change only Granular's own tracks count as busy, so stretch keeps its tracks")


if __name__=='__main__':main()
