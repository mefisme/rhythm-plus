"""Installed callback wiring, private recording, controls and native isolation."""
import json,struct,sys
from pathlib import Path
from emu_playfix import machine,call,STACK
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
import automation_bank_helpers as BH
ROOT=Path(__file__).resolve().parents[1]

def main():
    build=sys.argv[1] if len(sys.argv)>1 else 'a0180'
    report=json.loads((ROOT/'firmware'/build/'manifest.json').read_text())['report']
    def labels(module):return {k:int(v,16) for k,v in report[module]['labels'].items()}
    A,G,S=map(labels,('automation3','gfxmix','storageshadow'))
    state=int(report['automation3']['state'],16)
    def bank(offset=0,size=4608):return BH.read(u,report,offset,size)
    tr={k:int(v,16) for k,v in report['storageshadow']['trampolines'].items()}
    u=machine((ROOT/'firmware'/build/f'rhythmplus-{build.upper()}.bin').read_bytes(),
        (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes(),mclass=True)
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def ret(v=0):u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def run(name,*args):
        if len(args)>4:u.mem_write(STACK+0xf0000,struct.pack('<'+'I'*(len(args)-4),*args[4:]))
        call(u,A[name],*args[:4]);return u.reg_read(UC_ARM_REG_R0)
    record=word(0x2003c0cc);session=0x20007000;w(session+0x14,record)
    for a,v in ((0xe000ef90,0x73),(0xe000ed08,0x08010000),(0xe000ed94,0),(0xe000ed14,0)):w(a,v)
    native=[];held=[255];vals={};stores={}
    def make(st,values):
        stores[st]=0x20001000+len(stores)*64
        for i,v in enumerate(values):w(stores[st]+i*4,v)
    make(0x200122b0,[1,1,0])
    t=2;player=0x200470d4+0x190*t
    pos,speed,nextpos,rec,selected=0x20006000,0x20006040,0x20006080,0x20006100,0x20006180
    make(pos,[7,31,0]);make(speed,[0,3]);make(nextpos,[0,0,0]);make(selected,[7])
    packstore=0x20006280;make(packstore,[8]);w(session+0x44,packstore)
    w(player+8,pos);w(player+0xc,nextpos);w(player+0x10,speed)
    w(0x2003d380+4*t,rec);w(rec+0x28,selected)
    w(rec,0x08067864);w(rec+0xc,pos);w(rec+0x30,0x20006200)
    def hook(uc,a,n,d):
        x,y=uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)
        if a==0x0803fc58:
            if x in stores:ret(stores[x]+y*4)
        elif a in (0x08055324,0x0804946c):native.append(a);ret()
        elif a==0x08048cca:ret(3)
        elif a==int(report['tmenu']['labels']['c_tmheld'],16):ret(held[0])
        else:ret()
    for a in (0x0803fc58,0x08055324,0x0804946c,0x08048cca,
              int(report['tmenu']['labels']['c_tmheld'],16),tr['TR_APPLY']):
        u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
    # Native clear/default project application initializes the bank.
    u.mem_write(record+0x29110+276,bytes(20));u.mem_write(record+0x29110+404,bytes(100))
    call(u,S['c_sh_apply'],session,0,0,0)
    slot=int(report['storageshadow']['slot'],16)
    assert run('c_a3_available')==0x1500
    block=record+0x29110+504
    b=bytearray(b'GX\0\3'+bytes([127])*8+bytes([t])+bytes(10)+bytes([127])*3)
    b[2]=(sum(b[4:])^0x5c)&255;u.mem_write(block,bytes(b))
    before=bytes(u.mem_read(record,0x29484))
    run('c_a3_touch',0,24,0);run('c_a3_touch',1,80,0);run('c_a3_touch',2,0,0)
    if 'c_gx_autored' in G:
        for k in range(3):
            call(u,G['c_gx_autored'],k);assert u.reg_read(UC_ARM_REG_R0)==1
    call(u,word(0x08067894)&~1,rec+8,0x20006200,1,0)
    assert native==[0x0804946c]
    assert [bank((k*8+7)*192+31*6,1)[0] for k in range(3)]==[24,80,0]
    assert bank(0,192)==b'\xff'*192
    print('PASS installed recorder vtable captures K1-K3 in private FX-pattern lanes after native callback')
    # Record off allows playback to resume. Sound and LEDs consume the same
    # installed volatile getter, without rewriting the native save buffer.
    w(stores[0x200122b0]+4,0)
    if 'c_gx_autored' in G:
        for k in range(3):
            call(u,G['c_gx_autored'],k);assert u.reg_read(UC_ARM_REG_R0)==0
    run('c_a3_manual',state,0,100,0)
    run('c_a3_play',player,7,31,0)
    assert native[-1]==0x08055324
    outputs=[]
    for k in range(3):
        call(u,G['c_gx_autovalue'],k,127);outputs.append(u.reg_read(UC_ARM_REG_R0))
    assert outputs==[24,80,0]
    after=bytes(u.mem_read(record,0x29484))
    assert before==after
    print('PASS installed DSP/LED getter follows playback; the entire native project buffer remains unchanged')
    run('c_a3_touch',0,100,0);run('c_a3_play',player,7,31,0)
    call(u,G['c_gx_autovalue'],0,127);assert u.reg_read(UC_ARM_REG_R0)==100
    BH.write(u,report,b'\x19',7*192+31*6+1)
    run('c_a3_play',player,7,31,1)
    call(u,G['c_gx_autovalue'],0,127);assert u.reg_read(UC_ARM_REG_R0)==25
    print('PASS manual override holds through unchanged automation and releases on the next changed point')
    # Held-step locks and Clear affect the edited pattern, rather than whichever
    # pattern is currently playing. Other lane/pattern data is preserved.
    held[0]=16;w(stores[0x200122b0]+4,1)
    run('c_a3_touch',1,127,0)
    at=0x1500+(1*8+7)*192+16*6
    assert bank(at-0x1500,6)==bytes([127,255,255,255,255,255])
    if 'heldlocks' in report:
        while_held=bank()
        for pulse in range(6):
            w(stores[pos]+8,pulse)
            call(u,word(0x08067894)&~1,rec+8,0x20006200,1,0)
        assert bank()==while_held
        call(u,G['c_gx_autodisplay'],1,80);assert u.reg_read(UC_ARM_REG_R0)==127
        call(u,G['c_gx_autored'],1);assert u.reg_read(UC_ARM_REG_R0)==1
        print('PASS held private lock displays its own value/red indicator while all live recording remains suspended')
    untouched=bank()
    run('c_a3_touch',1,0,1)
    expected=bytearray(untouched);expected[at-0x1500:at-0x1500+6]=b'\xff'*6
    assert bank()==expected
    held[0]=255;run('c_a3_touch',0,127,1)
    assert bank(7*192,192)==b'\xff'*192
    assert bank((2*8+7)*192+31*6,1)==b'\0'
    print('PASS held-step locks and step/pattern Clear isolate control and pattern')
    # Internal packs and unavailable/corrupt runtime must not record.
    w(stores[packstore],0);call(u,S['c_sh_apply'],session,0,0,0)
    before=bank();run('c_a3_touch',0,42,0)
    assert bank()==before and not run('c_a3_available')
    w(stores[packstore],8);call(u,S['c_sh_apply'],session,0,0,0)
    w(0x3ae0 if report['automation3'].get('cow') else 0x2700,0);run('c_a3_touch',0,42,0)
    assert bank()==before and not run('c_a3_available')
    print('PASS internal packs and corrupt ownership guards fail inactive')
    print('ALL PASS')

if __name__=='__main__':main()
