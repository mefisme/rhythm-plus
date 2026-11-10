"""Project application and nested pack/sample replacement guards."""
from thumb import (Asm,bl,b_w,b_cond,bx_lr,mov_reg,movs_imm,movw,movt,
                   push_list,pop_list,ldr_sp,ldrb_imm,cmp_imm,add_sp_imm,raw)
import rhbuild
import upguard

APPLY,PACK,FREE,RESET,RECORD=0x080378c6,0x08053e24,0x08064460,0x08064416,0x0806446e


def install(img,report,base):
    kernel=report['granular']['arm_kernel']['labels'];bridge=report['granular']['bridge']
    state=int(bridge['labels']['c_gstate'],16);ready=int(bridge['labels']['c_gready'],16)
    uploader=int(report['upguard']['labels']['c_upw'],16)
    assert all(rhbuild.bl_target(img,address)==uploader for address in upguard.CALLS)
    a=Asm(base);E=a.emit
    def call(name):E(bl,kernel['c_gr_'+name])
    def imm(register,value):E(movw,register,value&65535);E(movt,register,value>>16)
    def tail(target):
        E(ldr_sp,3,28);E(mov_reg,14,3);E(pop_list,[0,1,2,3,4,5,6]);E(add_sp_imm,4);E(b_w,target)
    def finish():
        E(ldr_sp,3,28);E(mov_reg,14,3);E(add_sp_imm,4);E(pop_list,[1,2,3,4,5,6]);E(add_sp_imm,4);E(bx_lr)
    for name,target in (('apply','apply_native'),('pack','pack_native'),('upload',uploader),
                        ('free','free_native'),('reset','reset_native'),('record','record_native')):
        a.label('c_gl'+name);E(push_list,[0,1,2,3,4,5,6],lr=True)
        if name in ('free','record'):
            E(ldr_sp,0,4);E(cmp_imm,0,128);E(b_cond,name+'_pass','hs')
        E(bl,state);E(cmp_imm,0,0);E(b_cond,name+'_pass','eq');E(mov_reg,4,0)
        if name=='record':
            imm(0,int(bridge['upload'],16));E(ldrb_imm,0,0,0);E(cmp_imm,0,0);E(b_cond,'record_guard','ne')
            E(mov_reg,0,4);E(ldr_sp,1,4);call('runtime_replace_needed');E(cmp_imm,0,0);E(b_cond,'record_pass','eq')
            a.label('record_guard')
        E(bl,ready);E(mov_reg,1,0);imm(2,int(bridge['upload'],16));E(ldrb_imm,2,2,0)
        E(mov_reg,0,4);call('runtime_begin_replace');E(cmp_imm,0,0);E(b_cond,name+'_fail','eq')
        for register in range(4):E(ldr_sp,register,register*4)
        E(bl,target);E(mov_reg,6,0)
        if name=='apply':
            E(bl,int(report['rhrec']['labels']['c_rrt'],16));E(mov_reg,1,0);E(mov_reg,0,4);call('runtime_load')
        E(mov_reg,0,4);call('runtime_end_replace');E(mov_reg,0,6);finish()
        a.label(name+'_fail');E(movs_imm,0,0);finish()
        a.label(name+'_pass');tail(target)
    a.label('apply_native');E(raw,bytes(img[APPLY-rhbuild.BASE:APPLY-rhbuild.BASE+4]));E(b_w,APPLY+4)
    a.label('pack_native');E(raw,bytes(img[PACK-rhbuild.BASE:PACK-rhbuild.BASE+2]));E(bl,0x08040e28);E(b_w,PACK+6)
    a.label('free_native');E(raw,bytes(img[FREE-rhbuild.BASE:FREE-rhbuild.BASE+2]));imm(2,0x372fc);E(b_w,FREE+4)
    a.label('reset_native');E(raw,bytes(img[RESET-rhbuild.BASE:RESET-rhbuild.BASE+2]));imm(5,0x37300);E(b_w,RESET+4)
    a.label('record_native');E(raw,bytes(img[RECORD-rhbuild.BASE:RECORD-rhbuild.BASE+4]));E(b_w,RECORD+4)
    code,labels=a.assemble();img+=b'\xff'*(base-rhbuild.BASE-len(img))+code
    while len(img)%4:img.append(255)
    rhbuild.patch(img,APPLY,'push.w {r3, r4, r5, r6, r7, r8, sb, lr}',b_w(APPLY,labels['c_glapply']))
    rhbuild.patch(img,PACK,'push {r4, r5, r6, lr}|bl #0x8040e28',b_w(PACK,labels['c_glpack'])+b'\x00\xbf')
    rhbuild.patch(img,FREE,'lsls r1, r1, #0x18|ldr r2, [pc, #0x12c]',b_w(FREE,labels['c_glfree']))
    rhbuild.patch(img,RESET,'push {r3, r4, r5, lr}|ldr r5, [pc, #0x16c]',b_w(RESET,labels['c_glreset']))
    rhbuild.patch(img,RECORD,'push {r3, r4, r5, lr}|movs r3, #1',b_w(RECORD,labels['c_glrecord']))
    for address in upguard.CALLS:rhbuild.patch(img,address,f'bl #{uploader:#x}',bl(address,labels['c_glupload']))
    report['granular']['lifecycle']=dict(bytes=len(code),labels={name:hex(value) for name,value in labels.items()},
        apply=hex(APPLY),pack=hex(PACK),free=hex(FREE),reset=hex(RESET),record=hex(RECORD),uploads=[hex(address) for address in upguard.CALLS],previous_upload=hex(uploader),
        scope='Idle acknowledgement barrier before native project apply/pack allocator reset/sample upload; nested calls hold until outer completion')
    return labels
