"""Crash recorder for test builds: keeps the reset cause, fault state and recent PCs across a restart."""
import struct
from thumb import (Asm,b_w,b_cond,bl,bx_lr,cmp_imm,cmp_reg,mov_reg,movs_imm,movw,movt,
                   ldr_imm,str_imm,adds_imm8,subs_imm8,adds_reg,ands_reg,orrs_reg,tst_reg,lsls_imm,muls,raw,h)
import rhbuild
import rhstate

MAGIC=0x314c5243
RECORDS,RECORD=8,112          # bytes per record
SIZE=16+RECORDS*RECORD
HEAP_CURSOR=0x2004ea98        # highest stock allocation seen on the unit
RCC_CSR,RMVF,FAULT_REGS=0x40023874,1<<24,0xe000ed28
VECTORS=rhbuild.BASE
TICKS_PER_SAMPLE=64           # must be a power of 2
MRS_R0_MSP,MRS_R0_PSP,MRS_R1_IPSR=b'\xef\xf3\x08\x80',b'\xef\xf3\x09\x80',b'\xef\xf3\x05\x81'


def install(img,report,base):
    at=rhstate.ST-SIZE
    assert at>=HEAP_CURSOR+0x100
    vector=lambda index:struct.unpack_from('<I',img,VECTORS-rhbuild.BASE+4*index)[0]
    a=Asm(base);E=a.emit
    def imm(register,value):E(movw,register,value&65535);E(movt,register,value>>16)
    def record():
        # r2 = this boot's record; clobbers r1, r3.
        imm(3,at);E(ldr_imm,1,3,4);E(movs_imm,2,RECORD);E(muls,1,2);E(adds_reg,2,3,1);E(adds_imm8,2,16)
    def frame(name):
        # r0 = the exception frame, from EXC_RETURN in r12; uses no stack.
        E(raw,MRS_R0_MSP);E(mov_reg,1,12);E(lsls_imm,1,1,29);E(b_cond,name,'pl');E(raw,MRS_R0_PSP);a.label(name)

    a.label('c_clreset')
    imm(0,at);E(ldr_imm,1,0,0);imm(2,MAGIC);E(cmp_reg,1,2);E(b_cond,'have','eq')
    E(movs_imm,1,0);E(movw,2,SIZE)
    a.label('wipe');E(subs_imm8,2,4);E(raw,h(0x5081));E(cmp_imm,2,0);E(b_cond,'wipe','ne')   # str r1,[r0,r2]
    imm(2,MAGIC);E(str_imm,2,0,0)
    a.label('have')
    E(ldr_imm,1,0,4);E(adds_imm8,1,1);E(movs_imm,3,RECORDS-1);E(ands_reg,1,3);E(str_imm,1,0,4)
    E(ldr_imm,3,0,8);E(adds_imm8,3,1);E(str_imm,3,0,8)
    E(movs_imm,3,RECORD);E(muls,1,3);E(adds_reg,2,0,1);E(adds_imm8,2,16)
    E(movs_imm,1,0);E(movs_imm,3,RECORD)
    a.label('fresh');E(subs_imm8,3,4);E(raw,h(0x50d1));E(cmp_imm,3,0);E(b_cond,'fresh','ne')  # str r1,[r2,r3]
    # The reset flags are sticky until cleared, so each record must clear them.
    imm(3,RCC_CSR);E(ldr_imm,1,3,0);E(str_imm,1,2,0);imm(0,RMVF);E(orrs_reg,1,0);E(str_imm,1,3,0)
    E(b_w,vector(1)&~1)

    a.label('c_cltick');E(mov_reg,12,14);frame('tick_frame');record()
    E(ldr_imm,1,2,4);E(adds_imm8,1,1);E(str_imm,1,2,4)
    E(movs_imm,3,TICKS_PER_SAMPLE-1);E(tst_reg,1,3);E(b_cond,'tick_x','ne')
    E(ldr_imm,1,2,40);E(adds_imm8,1,1);E(movs_imm,3,7);E(ands_reg,1,3);E(str_imm,1,2,40)
    E(lsls_imm,1,1,3);E(adds_reg,3,2,1)
    E(ldr_imm,1,0,24);E(str_imm,1,3,48);E(ldr_imm,1,0,20);E(str_imm,1,3,52)
    a.label('tick_x');E(mov_reg,14,12);E(b_w,vector(15)&~1)

    a.label('c_clrec');frame('fault_frame');record()
    E(raw,MRS_R1_IPSR);E(str_imm,1,2,8);E(str_imm,0,2,44)
    # A bad stack pointer may be the fault itself: reading its frame would fault again.
    imm(1,0x20000000);E(cmp_reg,0,1);E(b_cond,'regs','lo');imm(1,0x20050000-32);E(cmp_reg,0,1);E(b_cond,'regs','hi')
    E(ldr_imm,1,0,24);E(str_imm,1,2,12);E(ldr_imm,1,0,20);E(str_imm,1,2,16);E(ldr_imm,1,0,28);E(str_imm,1,2,20)
    a.label('regs')
    imm(3,FAULT_REGS);E(ldr_imm,1,3,0);E(str_imm,1,2,24);E(ldr_imm,1,3,4);E(str_imm,1,2,28)
    E(ldr_imm,1,3,16);E(str_imm,1,2,32);E(ldr_imm,1,3,12);E(str_imm,1,2,36);E(bx_lr)
    for index in (3,4,5,6):
        a.label(f'c_clf{index}');E(mov_reg,12,14);E(bl,'c_clrec');E(mov_reg,14,12);E(b_w,vector(index)&~1)

    code,labels=a.assemble()
    img+=b'\xff'*(base-rhbuild.BASE-len(img))+code
    while len(img)%4:img.append(255)
    for index,name in ((1,'c_clreset'),(3,'c_clf3'),(4,'c_clf4'),(5,'c_clf5'),(6,'c_clf6'),(15,'c_cltick')):
        rhbuild.patch_word(img,VECTORS+4*index,vector(index),labels[name]|1)
    report['crashlog']=dict(at=hex(at),records=RECORDS,record_bytes=RECORD,size=SIZE,labels={k:hex(v) for k,v in labels.items()})
    return labels
