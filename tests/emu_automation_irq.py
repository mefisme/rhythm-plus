"""Measure actual PRIMASK across native gestures and compressed RAM work."""
import sys,struct
import emu_fx_native_edges as F
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PRIMASK,UC_ARM_REG_BASEPRI
G,E=F.G,F.E

def main():
    u=F.setup();L={k:int(v,16) for k,v in E.MAN['report']['automation3']['labels'].items()}
    state=int(E.MAN['report']['automation3']['state'],16)
    u.mem_write(E.ptr(u,E.u32(u,E.C.CTRL+0xc),0),b'\x01')
    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\x01');G.pad(u,0)
    spans=[];run=[0];service=[0]
    def count(uc,a,n,d):
        if uc.reg_read(UC_ARM_REG_PRIMASK)&1:run[0]+=1
        else:
            if run[0]:spans.append(run[0]);run[0]=0
            # Model a high-priority panel IRQ being eligible during task guard.
            base=uc.reg_read(UC_ARM_REG_BASEPRI)
            if not base or 0x40<base:service[0]+=1
    h=u.hook_add(UC_HOOK_CODE,count)
    G.knob(u,2,-3)
    for lane in (16,0,16):
        G.knob(u,2,1);E.call(u,L['c_a3_bankmaintain'],lane)
    first=max(spans)
    assert first<=200,('held lock/maintenance blocks panel interrupts',first)
    # Exercise cache replacement and compaction with all patterns populated,
    # then with an immutable saved version while live values change.
    for lane in range(24):
        E.call(u,L['c_a3_bankset'],0x1500,lane*192,(lane*13)%128)
    E.call(u,L['c_a3_banksnapshot'])
    for lane in reversed(range(24)):
        E.call(u,L['c_a3_bankset'],0x1500,lane*192,(lane*19+1)%128)
        E.call(u,L['c_a3_bankmaintain'],lane)
    E.call(u,L['c_a3_bankrelease'])
    u.hook_del(h)
    assert spans and max(spans)<=200,('cache/compaction blocks panel interrupts',max(spans))
    assert service[0]>1000,'panel service was not possible during memory work'
    assert u.reg_read(UC_ARM_REG_PRIMASK)==0 and u.reg_read(UC_ARM_REG_BASEPRI)==0
    for irq,base in ((0,0x80),(0,0xc0),(1,0)):
        u.reg_write(UC_ARM_REG_PRIMASK,irq);u.reg_write(UC_ARM_REG_BASEPRI,base)
        G.knob(u,2,-1)
        assert u.reg_read(UC_ARM_REG_PRIMASK)==irq,'changed caller IRQ mask'
        assert u.reg_read(UC_ARM_REG_BASEPRI)==base,'changed caller task ceiling'
    u.reg_write(UC_ARM_REG_PRIMASK,0);u.reg_write(UC_ARM_REG_BASEPRI,0)
    print('PASS held locks, maintenance, cache eviction, compaction and saved/live copies: max globally masked instructions',max(spans))
    print('PASS peripheral IRQ eligibility and nested PRIMASK/BASEPRI preservation')
    print('ALL PASS')
if __name__=='__main__':main()
