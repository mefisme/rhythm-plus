"""Stock ARM note matching and native DSP accepted-trigger serial, no device access."""
import os
os.environ['RH_PROBES']='0'
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tests','tools','modules','remix/tools')]
from emu_playfix import machine,call
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_LR
from granular_route_reference import segments
import granular_note_candidate as N
import granular_route_candidate as R
import granular_snapshot_candidate as S
import core0
import rhdspemu


def arm_events():
    image=(ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes()
    ram=(ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes()
    u=machine(image,ram);events=[]
    u32=lambda address:struct.unpack('<I',u.mem_read(address,4))[0]
    current,parameters=u32(0x080408d0),u32(0x080408d4)
    u.mem_write(current,b'\xff'*16)
    def intercept(uc,address,size,context):
        if address==0x080406a8:
            pointer=uc.reg_read(UC_ARM_REG_R0)
            events.append(struct.unpack('<II',uc.mem_read(pointer,8)))
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for address in (0x080406a8,0x0803081c):u.hook_add(UC_HOOK_CODE,intercept,None,address,address+1)
    for track in range(8):
        u.mem_write(parameters+16*track+1,b'\x00')
        start=len(events);call(u,0x08040778,track,60,100)
        assert events[start:]==[(0x900000|(track<<16)|(100<<8)|track,0)]
        start=len(events);call(u,0x0804083c,track,60,0,0)
        assert len(events)==start  # One Shot ignores ordinary note-off.
        start=len(events);call(u,0x08040778,track,60,100)
        assert events[start:]==[(0x800000|(track<<16)|track,3),(0x900000|(track<<16)|(100<<8)|track,0)]
        u.mem_write(parameters+16*track+1,b'\x01')
        call(u,0x08040778,track,64,90)
        start=len(events);call(u,0x0804083c,track,60,0,0)
        assert len(events)==start  # The old note cannot release the newer one.
        call(u,0x0804083c,track,64,0,0)
        assert events[-1]==(0x800000|(track<<16)|track,2)
        start=len(events);call(u,0x08040778,track,111,100);assert len(events)==start
        call(u,0x08040814,track)
        assert events[-1]==(0x800000|(track<<16)|track,3)
    return events


def dsp_events(messages,patched):
    segs=segments();segs,_=R.patched(segs);segs,_=S.patched(segs)
    if patched:segs,_=N.patched(segs)
    # The trigger queue and existing drone decision are real. Init itself is a
    # fixture in this test; native sample init/reader are tested separately.
    segs += [('p',N.NATIVE_TRIGGER,[0x00000c])]
    items=[('words',[0x05f420|k,0xffffff]) for k in range(8)]
    for command,value in messages:
        items += [f'move #>${command&0xffffff:x},y1',f'move #>${value&0xffffff:x},y0',
                  ('jsr',0x4f4 if command&0xf00000==0x900000 else 0x509),('jsr',0x2e4)]
    items += [('jmp',0x7ff0)]
    wrapper,_=core0.asm_at(items,0x7100)
    result,ran=rhdspemu.run(1,pc=0x7100,stop=0x7ff0,segs=segs+[('p',0x7100,wrapper)],
        mem=[('y',0x307b7,[0]*17),('y',N.SERIAL,[0]*8)],
        dumps=[('y',N.SERIAL,8),('y',0x307b7,17),('x',0x40,128),('y',0x1830,8)],maxins=100000)
    assert 'pc=007ff0' in ran,ran
    return result


def main():
    events=arm_events()
    print('PASS all8 stock ARM contexts: same-note retrigger, forced stop, One Shot note-off ignore, matching gated release and stale note-off rejection')
    for track in range(8):
        on=0x900000|(track<<16)|(100<<8)|track
        stop=0x800000|(track<<16)|track
        messages=[(on,0),(stop,2),(on,0),(on,4<<16),(stop,3)]
        native=dsp_events(messages,False);actual=dsp_events(messages,True)
        for key in (('y',0x307b7),('x',0x40),('y',0x1830)):assert native[key]==actual[key],(track,key)
        assert actual[('y',N.SERIAL)]==[3 if t==track else 0 for t in range(8)]
    print('PASS DSP serial counts accepted trigger-queue starts, including repeated notes; normal/forced offs do not count; existing native state is unchanged')
    print('LIMIT: no mode-owner ARM hook installed; accepted-trigger initializer is a fixture here; native reader lifetime is a separate actual-DSP test')
    print('ALL PASS')


if __name__=='__main__':main()
