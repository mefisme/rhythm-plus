"""Guarded ARM frame/note/source adapters for the granular staging build."""
from thumb import (Asm,bl,b_w,b_cond,bx_lr,mov_reg,movs_imm,movw,movt,
                   push_list,pop_list,ldr_sp,ldr_imm,ldrb_imm,cmp_imm,cmp_reg,
                   lsrs_imm,lsls_imm,add_sp_imm,adds_imm8,strb_imm,raw)
import rhbuild
import rhstate
import countin as C
import cthresh

MESSAGE,SOURCE,PARAM=0x080406a8,0x0804b060,0x0804070e


def install(img,report,base,current=False):
    kernel=report['granular']['arm_kernel']['labels']
    slot=rhstate.ST+rhstate.OFF['granular'][0]
    assert rhstate.OFF['granular'][1]==(416 if current else 316)
    reset=int(report['rhstate']['labels']['c_rst'],16)
    previous=rhbuild.bl_target(img,C.LED_CALLS[0])
    assert all(rhbuild.bl_target(img,address)==previous for address in C.LED_CALLS)
    ready=rhstate.ST+rhstate.OFF['cthresh'][0]+1
    wait=slot+404 if current else rhstate.ST+rhstate.OFF['spwait'][0]
    upload=rhstate.ST+rhstate.OFF['upguard'][0]
    a=Asm(base);E=a.emit
    def imm(register,value):E(movw,register,value&65535);E(movt,register,value>>16)
    def call(name):E(bl,kernel['c_gr_'+name])
    def restore_and_tail(target):
        E(ldr_sp,3,28);E(mov_reg,14,3)
        E(pop_list,[0,1,2,3,4,5,6]);E(add_sp_imm,4);E(b_w,target)
    a.label('c_gstate');E(push_list,[4],lr=True);E(bl,reset);E(cmp_imm,0,0)
    E(b_cond,'state_x','eq');imm(0,slot)
    a.label('state_x');E(pop_list,[4],pc=True)
    if current:
        a.label('c_ggranular_busy');E(push_list,[4],lr=True);E(mov_reg,4,0)
        E(bl,'c_gstate');E(cmp_imm,0,0);E(b_cond,'busy_done','eq')
        E(mov_reg,1,4);call('runtime_granular_busy')
        a.label('busy_done');E(pop_list,[4],pc=True)
    a.label('c_gready');imm(0,ready);E(ldrb_imm,0,0,0);E(cmp_imm,0,cthresh.READY)
    E(b_cond,'ready_no','ne');imm(0,wait);E(ldrb_imm,0,0,0);E(cmp_imm,0,200)
    E(b_cond,'ready_no','lo');E(movs_imm,0,1);E(bx_lr)
    a.label('ready_no');E(movs_imm,0,0);E(bx_lr)
    if current:
        a.label('c_gboot_tick');imm(0,ready);E(ldrb_imm,0,0,0);E(cmp_imm,0,cthresh.READY)
        E(b_cond,'boot_reset','ne');imm(0,upload);E(ldrb_imm,0,0,0);E(cmp_imm,0,0)
        E(b_cond,'boot_reset','ne');imm(0,wait);E(ldrb_imm,1,0,0);E(cmp_imm,1,200)
        E(b_cond,'boot_done','hs')
        E(adds_imm8,1,1);E(strb_imm,1,0,0);E(bx_lr)
        a.label('boot_reset');imm(0,wait);E(movs_imm,1,0);E(strb_imm,1,0,0)
        a.label('boot_done');E(bx_lr)
    a.label('c_gframe');E(push_list,[0,1,4,5,6],lr=True);E(bl,previous)
    E(bl,'c_gstate');E(cmp_imm,0,0);E(b_cond,'frame_x','eq');E(mov_reg,4,0)
    if current:E(bl,'c_gboot_tick')
    E(bl,'c_gready');E(mov_reg,1,0);E(mov_reg,0,4)
    imm(2,upload);E(ldrb_imm,2,2,0);call('runtime_frame')
    a.label('frame_x');E(pop_list,[0,1,4,5,6],pc=True)
    a.label('c_gmessage');E(push_list,[0,1,2,3,4,5,6],lr=True)
    E(bl,'c_gstate');E(cmp_imm,0,0);E(b_cond,'message_pass','eq');E(mov_reg,4,0)
    E(bl,'c_gready');E(cmp_imm,0,0);E(b_cond,'message_pass','eq')
    imm(0,upload);E(ldrb_imm,0,0,0);E(cmp_imm,0,0);E(b_cond,'message_policy','eq')
    # During raw sample streaming, never issue our DSP reads. Suppress starts;
    # stock stop/parameter handling remains available.
    E(ldr_sp,0,0);E(ldr_imm,0,0,0);E(lsrs_imm,0,0,20)
    E(cmp_imm,0,9);E(b_cond,'message_drop','eq');E(cmp_imm,0,10);E(b_cond,'message_drop','eq')
    E(b_cond,'message_pass','ne')
    a.label('message_policy');E(mov_reg,0,4);E(ldr_sp,1,0);E(ldr_sp,2,28)
    E(lsrs_imm,2,2,1);E(lsls_imm,2,2,1);call('runtime_message');E(cmp_imm,0,0)
    E(b_cond,'message_pass','ne')
    a.label('message_drop');E(pop_list,[0,1,2,3,4,5,6],pc=True)
    a.label('message_pass');restore_and_tail('message_native')
    a.label('message_native');E(push_list,[4,5,6],lr=True)
    pointer=int.from_bytes(img[0x080408c0-rhbuild.BASE:0x080408c4-rhbuild.BASE],'little')
    imm(5,pointer);E(b_w,MESSAGE+4)
    a.label('c_gsource');E(push_list,[0,1,2,3,4,5,6],lr=True)
    E(bl,'c_gstate');E(cmp_imm,0,0);E(b_cond,'source_plain','eq');E(mov_reg,4,0)
    E(mov_reg,0,4);E(ldr_sp,1,0);call('runtime_seq_begin');E(mov_reg,5,0)
    for register in range(4):E(ldr_sp,register,register*4)
    E(bl,'source_native');E(mov_reg,6,0);E(mov_reg,0,4);E(mov_reg,1,5);call('runtime_seq_end')
    # Preserve the original resolver's return value and all caller arguments.
    E(mov_reg,0,6);E(ldr_sp,3,28);E(mov_reg,14,3)
    E(add_sp_imm,4);E(pop_list,[1,2,3,4,5,6]);E(add_sp_imm,4);E(bx_lr)
    a.label('source_plain');restore_and_tail('source_native')
    a.label('source_native');E(raw,bytes(img[SOURCE-rhbuild.BASE:SOURCE-rhbuild.BASE+4]));E(b_w,SOURCE+4)
    a.label('c_gparam');E(push_list,[0,1,2,3,4,5,6],lr=True)
    E(ldr_sp,0,4);E(cmp_imm,0,0);E(b_cond,'param_pass','ne')
    E(bl,'c_gstate');E(cmp_imm,0,0);E(b_cond,'param_pass','eq')
    E(ldr_sp,1,0);E(ldr_sp,2,8);call('runtime_source')
    E(ldr_sp,1,8);E(cmp_reg,0,1);E(b_cond,'param_pass','eq')
    E(cmp_imm,0,128);E(b_cond,'param_drop','hs')
    # Rewrite only the sample parameter argument; all other controls tail-call.
    from thumb import str_sp
    E(str_sp,0,8)
    a.label('param_pass');restore_and_tail('param_native')
    a.label('param_drop');E(pop_list,[0,1,2,3,4,5,6],pc=True)
    a.label('param_native');E(raw,bytes(img[PARAM-rhbuild.BASE:PARAM-rhbuild.BASE+4]));E(b_w,PARAM+4)
    code,labels=a.assemble()
    img += b'\xff'*(base-rhbuild.BASE-len(img))+code
    while len(img)%4:img.append(255)
    if current:
        at=int(report['gfxmix']['labels']['c_gx_granular_busy'],16)
        rhbuild.patch(img,at,'movs r0, #0|bx lr',b_w(at,labels['c_ggranular_busy']))
    for address,label,expected in ((MESSAGE,'c_gmessage','push {r4, r5, r6, lr}|ldr r5, [pc, #0x214]'),
                                    (SOURCE,'c_gsource','push {r3, r4, r5, r6, r7, lr}|mov r4, r0'),
                                    (PARAM,'c_gparam','push.w {r2, r3, r4, r5, r6, r7, r8, lr}')):
        rhbuild.patch(img,address,expected,b_w(address,labels[label]))
    for address in C.LED_CALLS:rhbuild.patch(img,address,f'bl #{previous:#x}',bl(address,labels['c_gframe']))
    report['granular']['bridge']=dict(slot=hex(slot),bytes=len(code),labels={name:hex(address) for name,address in labels.items()},ready=hex(ready),wait=hex(wait),upload=hex(upload),previous_frame=hex(previous))
    return labels
