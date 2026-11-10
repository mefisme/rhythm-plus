"""Compiled virtual page: focus, hold settings, independent knobs and RGB overlay."""
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_granular_owner import build
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *


def main():
    info=build();u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    u.mem_map(info['origin'],0x4000);u.mem_write(info['origin'],Path(info['binary']).read_bytes())
    u.mem_map(0x20000000,0x10000)
    state,out,sp,stop=0x20001000,0x20002000,0x2000ff00,info['origin']+0x3ff0
    for slot in (0x43,0x2f,0x47,0x4b,0x37,0x25,0x12,0x3b):u.mem_write(0x20003974+slot*4,struct.pack('<I',0x22aaff))
    def writes(uc,access,address,size,value,context):
        assert state<=address and address+size<=state+316 or out<=address and address+size<=out+69*4 or 0x2000f000<=address<0x20010000
    hook=[u.hook_add(UC_HOOK_MEM_WRITE,writes)]
    def call(name,*args):
        for k,value in enumerate(args):u.reg_write(UC_ARM_REG_R0+k,value)
        saved=[0x123400+k for k in range(8)]
        for k,value in enumerate(saved):u.reg_write(UC_ARM_REG_R4+k,value)
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,stop|1)
        u.emu_start(info['labels']['c_gr_'+name]|1,stop,count=100000)
        assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==sp
        assert [u.reg_read(UC_ARM_REG_R4+k) for k in range(8)]==saved
        return u.reg_read(UC_ARM_REG_R0)
    def tick(value):u.mem_write(0x20000820,struct.pack('<I',value))
    baseline=[0x123456]*69;baseline[25]=0x808080;baseline[28]=0x0a0b0c;baseline[30]=0x1f1505
    def draw(track,knob):
        # Unicorn skips the ORR after an IT block when this hook fires inside it.
        u.hook_del(hook[0]);guard=b'\xa5'*4
        u.mem_write(out-4,guard);u.mem_write(out+69*4,guard)
        u.mem_write(out,struct.pack('<69I',*baseline));call('runtime_draw',state,track,out,knob)
        assert bytes(u.mem_read(out-4,4))==guard and bytes(u.mem_read(out+69*4,4))==guard
        hook[0]=u.hook_add(UC_HOOK_MEM_WRITE,writes)
        return list(struct.unpack('<69I',u.mem_read(out,69*4)))
    call('runtime_init',state)
    tick(1000);assert call('runtime_pad',state,0,29)==1
    assert call('runtime_page',state,0)==1 and call('runtime_page',state,1)==0
    assert call('owner_mode',state,0)==0
    call('runtime_ui_frame',state,0,1)
    assert call('runtime_release',state,29)==1
    assert call('runtime_release',state,29)==0
    assert call('runtime_turn',state,1,0,10)==0
    assert call('runtime_turn',state,0,0,10)==1
    assert call('params_get',state+104,0,0)==10 and call('params_get',state+104,1,0)==0
    normal=draw(0,0)
    changed=set(range(16,24))|{25,29}|set(range(32,40))|set(range(60,68))
    assert all(normal[i]==baseline[i] for i in range(69) if i not in changed)
    assert normal[29]!=baseline[29] and normal[25]==0x080808
    tick(2000);call('runtime_pad',state,0,29)
    tick(2332);call('runtime_ui_frame',state,0,1);assert u.mem_read(state+96+6,1)==b'\0'
    tick(2333);call('runtime_ui_frame',state,0,1);assert u.mem_read(state+96+6,1)==b'\x01'
    default_settings=draw(0,0)
    assert call('runtime_pad',state,0,17)==1 and u.mem_read(state+168,1)[0]==16|32  # Texture chosen while bypassed.
    assert call('runtime_release',state,17)==1
    assert call('runtime_pad',state,0,16)==1 and call('runtime_release',state,16)==1
    assert call('owner_mode',state,0)==0  # Preference and barrier only, no native start.
    assert u.mem_read(state+168,1)[0]==16|32|2
    assert call('runtime_pad',state,0,16)==1 and u.mem_read(state+168,1)[0]==16|32
    assert call('runtime_pad',state,0,16)==1 and u.mem_read(state+168,1)[0]==16|32|2  # On restores Texture.
    assert call('runtime_pad',state,0,18)==1 and call('runtime_pad',state,0,20)==1
    assert u.mem_read(state+168,1)[0]==16|32|8|64|2
    settings=draw(0,0);assert settings[19] and settings[20] and settings[21] and settings[22]==settings[23]==0
    setting=lambda:u.mem_read(state+292,1)[0]
    for expected in (2,4,6,8,0):assert call('runtime_pad',state,0,21)==1 and setting()==expected and call('runtime_release',state,21)==1
    assert call('runtime_pad',state,0,19)==1 and setting()==1 and draw(0,0)[19]!=settings[19]
    assert call('runtime_pad',state,0,19)==1 and setting()==0 and call('runtime_release',state,19)==1
    assert call('runtime_pad',state,0,22)==1 and u.mem_read(state+168,1)[0]==16|32|8|64|2 and setting()==0 and call('runtime_release',state,22)==1
    assert all(settings[i] and settings[i]!=default_settings[i] for i in (16,17,18,20))
    assert call('runtime_release',state,18)==1 and call('runtime_release',state,20)==1
    call('runtime_release',state,29)
    assert draw(0,0)==normal
    assert call('runtime_pad',state,0,25)==0 and call('runtime_page',state,0)==0
    assert u.mem_read(state+168,1)[0]==32|8|64|2  # Leaving page keeps engine/settings preference.
    stock=draw(0,0)
    assert all(stock[i]==baseline[i] for i in range(69) if i!=29)
    assert call('runtime_pad',state,1,29)==1
    tick(3000);call('runtime_ui_frame',state,0,1)
    assert u.mem_read(state+96+6,1)==b'\0'
    call('runtime_turn',state,1,1,0x7fffffff);assert call('params_get',state+104,1,1)==127
    call('runtime_turn',state,1,1,0x80000000);assert call('params_get',state+104,1,1)==0
    assert call('runtime_clear',state,1,29)==1
    assert call('params_get',state+104,1,1)==64 and call('params_get',state+104,0,0)==10
    call('params_put',state+104,1,2,99)
    assert call('runtime_clear_knob',state,1,2,0)==1 and call('params_get',state+104,1,2)==51
    assert call('runtime_clear_knob',state,0,2,0)==0 and call('runtime_clear_knob',state,1,8,0)==0
    counters=0x2000f100;u.mem_write(counters,bytes(16))
    assert call('clear_step',counters,3,39)==0 and call('clear_step',counters,3,1)==1
    assert call('clear_step',counters,3,5)==0 and u.mem_read(counters+3,1)==b'\x28'
    assert call('clear_step',counters,3,-40)==0 and bytes(u.mem_read(counters+3,1))==b'\0' and u.mem_read(counters+11,1)==b'\x28'
    level=lambda:u.mem_read(state+212+1,1)[0]
    assert level()==64 and call('runtime_shift_turn',state,1,0,1)==1 and level()==65
    call('runtime_shift_turn',state,1,0,0x7fffffff);assert level()==127
    call('runtime_shift_turn',state,1,0,0x80000000);assert level()==0
    assert call('runtime_clear_knob',state,1,6,1)==0 and level()==0
    shift=lambda k:u.mem_read(state+236+7+k,1)[0]
    assert shift(1)==64 and call('runtime_shift_turn',state,1,2,20)==1 and shift(1)==84
    assert call('runtime_shift_turn',state,1,1,9)==1 and shift(0)==9 and call('runtime_shift_turn',state,1,3,7)==1 and shift(2)==7
    assert call('runtime_shift_turn',state,1,6,7)==0 and call('runtime_shift_turn',state,1,7,7)==0
    assert call('runtime_shift_turn',state,1,4,20)==1 and shift(3)==20
    sliced=draw(1,12);assert sum(1 for x in sliced[16:24] if x>0x080808)==2  # 3 slices fill a pad and a half.
    assert call('runtime_clear_knob',state,1,4,1)==1 and shift(3)==0
    assert call('runtime_shift_turn',state,1,5,30)==1 and shift(4)==30
    assert call('runtime_clear_knob',state,1,5,1)==1 and shift(4)==0 and call('runtime_clear_knob',state,1,6,1)==0
    timed=draw(1,10);assert sum(1 for x in timed[20:24] if x>0x080808)>=1 and timed[16:20]==[0]*3+[timed[19]]
    for knob,value in ((1,0),(2,64),(3,0)):assert call('runtime_clear_knob',state,1,knob,1)==1 and shift(knob-1)==value
    assert call('runtime_clear_knob',state,1,0,1)==1 and level()==64
    shifted=draw(1,8)
    assert shifted[60]==draw(1,0)[60] and shifted[66:68]==[0]*2 and all(shifted[61:66])
    assert sum(1 for x in shifted[16:24] if x>0x080808)==4  # Level 64 fills half the bar.
    call('params_put',state+104,1,4,127);bright=draw(1,0)[64]
    call('params_put',state+104,1,4,0);dim=draw(1,0)[64]
    assert bright&255>dim&255>0
    print('PASS compiled virtual page focuses without enabling or stealing another track; stock page selection preserves granular engine preference')
    print('PASS333ms held-page settings temporarily replace value bar; release/context change restore it; choices stage through mode barrier')
    print('PASS Clear + turn returns one knob to its default; Shift + Clear + K1 returns Level to its first step')
    print('PASS knob limits, per-track reset and independent values; RGB overlay touches only its owned LEDs and native output resumes outside page')
    print('LIMIT: compiled UI logic; physical event and output-stage wrappers are a separate integration test')


if __name__=='__main__':main()
