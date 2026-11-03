"""A0050's read-only remote diagnostics, with mapped-RAM and startup guards.

Uses stock host accessors and rdiag's established framing. Disables SD and DSP
write dispatch, and rejects unmapped/IO reads and reads before DSP startup.
Reference tools/rdiag.py is not edited.
"""
from pathlib import Path
import sys
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rdiag as RD
import rhbuild
import rhstate
import cthresh as TH
from thumb import (Asm, b, b_w, b_cond, bl, cmp_imm, cmp_reg, mov_reg, movs_imm, movw, movt,
                   ldrb_imm, ldr_imm, adds_imm8, adds_reg, subs_imm8, push_list, pop_list)


def guard_code(base,L):
    a=Asm(base);E=a.emit
    def imm(r,v):E(movw,r,v&0xffff);E(movt,r,v>>16)
    def reject(cond):
        # Fixed unique local labels, independent of the assembler implementation.
        i=serial[0];serial[0]+=1
        E(b_cond,f'bad_{i}',cond);E(b,f'next_{i}');a.label(f'bad_{i}');E(b_w,L['ds_bad']);a.label(f'next_{i}')
    serial=[0]
    a.label('c_drguard')
    # c_rdin has r5=received length. Full dspr request through byte 15 plus F7.
    E(cmp_imm,5,17);reject('lo')
    imm(0,rhstate.ST);E(ldr_imm,0,0,0);imm(1,rhstate.MAGIC);E(cmp_reg,0,1);reject('ne')
    imm(0,rhstate.ST+rhstate.OFF['cthresh'][0]+1);E(ldrb_imm,0,0,0);E(cmp_imm,0,TH.READY);reject('ne')
    imm(0,rhstate.ST+rhstate.OFF['spwait'][0]);E(ldrb_imm,0,0,0);E(cmp_imm,0,200);reject('lo')
    E(ldrb_imm,0,4,6);E(cmp_imm,0,1);reject('hi')
    E(push_list,[0]);E(mov_reg,0,4);E(adds_imm8,0,7);E(bl,L['c_g32']);E(mov_reg,2,0);E(pop_list,[3])
    E(ldrb_imm,1,4,15);E(cmp_imm,1,0);reject('eq')
    E(cmp_imm,1,RD.NR);E(b_cond,'count_ok','ls');E(movs_imm,1,RD.NR);a.label('count_ok')
    E(subs_imm8,1,1);E(adds_reg,1,1,2)  # r1=inclusive end; validate both against one bank
    imm(0,0x30000);E(cmp_reg,2,0);E(b_cond,'shared','hs')
    imm(0,0x8000);E(cmp_reg,2,0);E(b_cond,'y','hs')
    E(cmp_imm,3,0);E(b_cond,'x1','ne');imm(0,0x6000);E(b,'end')
    a.label('x1');imm(0,0x3000);E(b,'end')
    a.label('y');E(cmp_imm,3,0);E(b_cond,'y1','ne');imm(0,0xc000);E(b,'end')
    a.label('y1');imm(0,0xa000);E(b,'end')
    a.label('shared');imm(0,0x38000)
    a.label('end');E(cmp_reg,1,0);reject('hs')
    # No arithmetic wrap can pass: input is bounded by the end test (count <=24),
    # except a huge input wrapping end; compare end >= start too.
    E(cmp_reg,1,2);reject('lo')
    # Replay the overwritten four bytes and continue rdiag's core validation.
    E(ldrb_imm,0,4,6)
    from thumb import str_imm
    E(str_imm,0,7,28);E(b_w,L['rc_dspr']+4)
    return a.assemble()


def install(img,report,base_addr):
    saved=RD.arm_code
    L={}
    def capture(*args,**kw):
        code,labels=saved(*args,**kw)
        L.update(labels)
        return code,labels
    RD.arm_code=capture
    try:
        RD.install(img,report,base_addr,dsp=2)
    finally:
        RD.arm_code=saved
    # The dispatcher compares r0 against the request command immediately before rc_ping.
    unknown=L['rc_ping']-16
    assert rhbuild.disasm(bytes(img[unknown-rhbuild.BASE:unknown-rhbuild.BASE+2]),unknown)==['mov r0, r1']
    for cmd in (6,9):
        sites=[]
        for ins in rhbuild.MD.disasm(bytes(img[L['c_rdcmd']-rhbuild.BASE:L['rc_ping']-rhbuild.BASE]),L['c_rdcmd']):
            if ins.mnemonic=='cmp' and ins.op_str==f'r0, #{cmd}':sites.append(ins.address)
        assert len(sites)==1,(cmd,sites)
        # Keep the command comparison; redirect its taken branch to the existing
        # unknown-command reply. No alternate command number can reach a writer.
        branch=sites[0]+4
        off=branch-rhbuild.BASE
        assert rhbuild.disasm(bytes(img[off:off+2]),branch)[0].startswith('b ')
        img[off:off+2]=b(branch,unknown)
    at=(rhbuild.BASE+len(img)+3)&~3
    code,labels=guard_code(at,L)
    entry=L['rc_dspr'];off=entry-rhbuild.BASE
    assert rhbuild.disasm(bytes(img[off:off+4]),entry)==['ldrb r0, [r4, #6]','str r0, [r7, #0x1c]']
    img[off:off+4]=b_w(entry,labels['c_drguard'])
    img+=b'\xff'*(at-rhbuild.BASE-len(img))+code
    while len(img)%4:img.append(0xff)
    report['rdiag'].update(readonly=True,guard=hex(labels['c_drguard']),mapped_ram_only=True,
                          writes_disabled=[6,9],max_dsp_words=RD.NR)
