"""Virtual granular page over native Normal; no legacy page IDs reactivated."""
from thumb import (Asm,bl,b_w,b_cond,bx_lr,mov_reg,movs_imm,movw,movt,
                   push_list,pop_list,ldr_sp,ldr_imm,ldrb_imm,strb_imm,
                   cmp_imm,cmp_reg,add_sp_imm,adds_imm8,subs_imm8,ands_reg,
                   adds_reg,tst_reg)
import rhbuild
import countin as C
import tmenu as T

# Both stock session-record writers, as documented in remix/tools/mfsess.py.
SAVE_CALLS = {0x08037fd6: 0x080472e2, 0x08038734: 0x08047270}


def install(img,report,base):
    labels=report['granular']['arm_kernel']['labels'];bridge=report['granular']['bridge']
    native_state=int(bridge['labels']['c_gstate'],16);state='c_gustate'
    menu=int(report['tmenu']['slot'],16);root=int(report['rhstate']['block'],16)
    previous={key:rhbuild.bw_target(img,address) for key,address in (('pad',T.PP_ENTRY),('release',T.PR_ENTRY),('knob',T.KN_ENTRY))}
    previous['frame']=rhbuild.bl_target(img,C.LED_CALLS[0]);previous['out']=rhbuild.bl_target(img,T.OUT_CALL)
    reset_site=int(report['trackreset']['labels']['c_trreset_pages_call'],16)
    reset_pages=int(report['pageclear']['labels']['c_pcreset'],16)
    a=Asm(base);E=a.emit
    def imm(register,value):E(movw,register,value&65535);E(movt,register,value>>16)
    def call(name):E(bl,labels['c_gr_'+name])
    def tail(target):
        E(ldr_sp,3,28);E(mov_reg,14,3);E(pop_list,[0,1,2,3,4,5,6]);E(add_sp_imm,4);E(b_w,target)
    def saved():E(push_list,[0,1,2,3,4,5,6],lr=True)
    def drop():E(pop_list,[0,1,2,3,4,5,6],pc=True)
    def modifiers():imm(0,T.CTRL+T.HELD);E(ldr_imm,0,0,0);imm(1,T.MODS);E(ands_reg,0,1)
    def shift():
        imm(0,T.CTRL);E(ldr_imm,0,0,0xc);E(movs_imm,1,0);E(bl,C.PARAM_GET);E(ldrb_imm,0,0,0);E(cmp_imm,0,0)
    def commit_result():
        E(push_list,[0,1]);E(mov_reg,0,4);E(bl,'c_gucommit');E(pop_list,[0,1])
    a.label('c_gustate');E(push_list,[4],lr=True);E(bl,native_state);E(cmp_imm,0,0);E(b_cond,'state_x','eq')
    E(mov_reg,4,0);call('runtime_init');E(mov_reg,0,4)
    a.label('state_x');E(pop_list,[4],pc=True)
    a.label('c_gucommit');E(push_list,[4],lr=True);E(mov_reg,4,0);E(bl,int(report['rhrec']['labels']['c_rrt'],16))
    E(cmp_imm,0,0);E(b_cond,'commit_x','eq');E(mov_reg,1,0);E(mov_reg,0,4);call('runtime_store')
    a.label('commit_x');E(pop_list,[4],pc=True)
    for index,target in enumerate(SAVE_CALLS.values()):
        name=f'c_gusave{index}'
        a.label(name);saved();E(bl,state);E(cmp_imm,0,0);E(b_cond,name+'_native','eq')
        E(bl,'c_gucommit')
        a.label(name+'_native');tail(target)
    a.label('c_gureset');saved();E(bl,reset_pages);E(bl,state);E(cmp_imm,0,0);E(b_cond,'reset_done','eq')
    E(mov_reg,4,0);E(ldr_sp,1,0);call('runtime_track_reset');E(mov_reg,0,4);E(bl,'c_gucommit')
    a.label('reset_done');drop()
    a.label('c_gucontext');E(push_list,[4],lr=True);E(bl,state);E(cmp_imm,0,0);E(b_cond,'context_no','eq')
    imm(0,menu+T.O_OPEN);E(ldrb_imm,0,0,0);E(cmp_imm,0,0);E(b_cond,'context_no','eq')
    E(bl,int(report['tmenu']['labels']['c_tmview'],16));E(pop_list,[4],pc=True)
    a.label('context_no');E(movs_imm,0,8);E(pop_list,[4],pc=True)
    a.label('c_guframe');saved();E(bl,previous['frame']);E(bl,state);E(cmp_imm,0,0);E(b_cond,'frame_x','eq');E(mov_reg,4,0)
    E(bl,'c_gucontext');E(mov_reg,5,0);modifiers();E(movs_imm,2,0);E(cmp_imm,0,0);E(b_cond,'frame_tick','ne')
    imm(0,int(bridge['upload'],16));E(ldrb_imm,0,0,0);E(cmp_imm,0,0);E(b_cond,'frame_tick','ne');E(movs_imm,2,1)
    a.label('frame_tick');E(mov_reg,0,4);E(mov_reg,1,5);call('runtime_ui_frame')
    E(mov_reg,0,4);call('runtime_store_pending');E(cmp_imm,0,0);E(b_cond,'frame_x','eq')
    imm(0,int(bridge['upload'],16));E(ldrb_imm,0,0,0);E(cmp_imm,0,0);E(b_cond,'frame_x','ne')
    E(mov_reg,0,4);E(bl,'c_gucommit')
    a.label('frame_x');drop()
    a.label('c_gupad');saved();E(bl,state);E(cmp_imm,0,0);E(b_cond,'pad_pass','eq');E(mov_reg,4,0)
    E(bl,'c_gucontext');E(cmp_imm,0,8);E(b_cond,'pad_pass','hs');E(mov_reg,5,0)
    modifiers();E(cmp_imm,0,0);E(b_cond,'pad_normal','eq')
    E(mov_reg,0,4);E(adds_imm8,0,96);call('ui_release')
    imm(0,T.CTRL+T.HELD);E(ldr_imm,0,0,0);imm(1,1<<23);E(tst_reg,0,1);E(b_cond,'pad_pass','eq')
    E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);call('runtime_clear');commit_result();E(cmp_imm,0,0);E(b_cond,'pad_pass','eq');E(b_w,'pad_drop')
    a.label('pad_normal');E(ldr_sp,6,4);E(cmp_imm,6,29);E(b_cond,'pad_dispatch','ne')
    E(mov_reg,0,4);E(mov_reg,1,5);call('runtime_page');E(cmp_imm,0,0);E(b_cond,'pad_dispatch','ne')
    imm(0,menu+T.O_KNOB);E(movs_imm,1,1);E(strb_imm,1,0,0)
    a.label('pad_dispatch');E(mov_reg,0,4);E(mov_reg,1,5);E(mov_reg,2,6);call('runtime_pad')
    commit_result()
    E(cmp_imm,0,0);E(b_cond,'pad_pass','eq');E(cmp_imm,6,29);E(b_cond,'pad_next','ne')
    imm(0,menu+T.O_PAGE);E(movs_imm,1,0);E(strb_imm,1,0,0)
    E(mov_reg,0,5);E(movs_imm,1,0);E(bl,int(report['tmenu']['labels']['c_tmpgset'],16))
    imm(0,root);E(bl,int(report['tmenu']['labels']['c_tmsp'],16));E(b_w,'pad_drop')
    a.label('pad_next');E(cmp_imm,6,24);E(b_cond,'pad_drop','ne')
    imm(0,menu+T.O_KNOB);E(ldrb_imm,1,0,0);E(adds_imm8,1,1);E(cmp_imm,1,9);E(b_cond,'pad_knob','lo');E(movs_imm,1,1)
    a.label('pad_knob');E(strb_imm,1,0,0)
    a.label('pad_drop');drop()
    a.label('pad_pass');tail(previous['pad'])
    a.label('c_gurelease');saved();E(bl,state);E(cmp_imm,0,0);E(b_cond,'release_pass','eq')
    E(ldr_sp,1,4);call('runtime_release');E(cmp_imm,0,0);E(b_cond,'release_pass','eq');drop()
    a.label('release_pass');tail(previous['release'])
    a.label('c_guknob');saved();E(ldr_sp,0,4);E(cmp_imm,0,8);E(b_cond,'knob_pass','hs')
    E(bl,state);E(cmp_imm,0,0);E(b_cond,'knob_pass','eq');E(mov_reg,4,0)
    E(bl,'c_gucontext');E(cmp_imm,0,8);E(b_cond,'knob_pass','hs');E(mov_reg,5,0)
    E(mov_reg,0,4);E(mov_reg,1,5);call('runtime_page');E(cmp_imm,0,0);E(b_cond,'knob_pass','eq')
    modifiers();E(cmp_imm,0,0);E(b_cond,'knob_modifier','ne')
    shift();E(b_cond,'knob_shift','ne')
    E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);E(ldr_sp,3,8);call('runtime_turn');E(b_w,'knob_commit')
    a.label('knob_modifier');imm(0,T.CTRL+T.HELD);E(ldr_imm,0,0,0);imm(1,1<<23);E(tst_reg,0,1);E(b_cond,'knob_drop','eq')
    imm(0,menu+T.O_KNOB);E(ldr_sp,1,4);E(adds_imm8,1,1);E(strb_imm,1,0,0)
    imm(0,menu+T.O_CLRR);E(ldr_sp,1,4);E(ldr_sp,2,8);call('clear_step');E(cmp_imm,0,0);E(b_cond,'knob_drop','eq')
    shift();E(b_cond,'knob_clear_shift','ne');E(movs_imm,3,0);E(b_w,'knob_clear')
    a.label('knob_clear_shift');E(movs_imm,3,1)
    a.label('knob_clear');E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);call('runtime_clear_knob')
    E(cmp_imm,0,0);E(b_cond,'knob_drop','eq');E(b_w,'knob_commit')
    a.label('knob_shift');E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);E(ldr_sp,3,8);call('runtime_shift_turn')
    E(cmp_imm,0,0);E(b_cond,'knob_drop','eq')
    a.label('knob_commit')
    E(mov_reg,0,4);E(bl,'c_gucommit')
    imm(0,menu+T.O_KNOB);E(ldr_sp,1,4);E(adds_imm8,1,1);E(strb_imm,1,0,0)
    a.label('knob_drop');drop()
    a.label('knob_pass');tail(previous['knob'])
    a.label('c_guout');saved();E(bl,previous['out']);E(bl,state);E(cmp_imm,0,0);E(b_cond,'out_x','eq');E(mov_reg,4,0)
    E(bl,'c_gucontext');E(cmp_imm,0,8);E(b_cond,'out_x','hs');E(mov_reg,5,0)
    shift();imm(3,menu+T.O_KNOB);E(ldrb_imm,3,3,0);E(subs_imm8,3,1)
    E(cmp_imm,0,0);E(b_cond,'out_draw','eq');E(adds_imm8,3,8)
    a.label('out_draw');E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);call('runtime_draw')
    E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);imm(3,menu+T.O_CLRR);call('clear_draw')
    a.label('out_x');drop()
    code,out=a.assemble();img+=b'\xff'*(base-rhbuild.BASE-len(img))+code
    while len(img)%4:img.append(255)
    for key,address in (('pad',T.PP_ENTRY),('release',T.PR_ENTRY),('knob',T.KN_ENTRY)):
        rhbuild.patch(img,address,f'b.w #{previous[key]:#x}',b_w(address,out['c_gu'+key]))
    for address in C.LED_CALLS:rhbuild.patch(img,address,f'bl #{previous["frame"]:#x}',bl(address,out['c_guframe']))
    rhbuild.patch(img,T.OUT_CALL,f'bl #{previous["out"]:#x}',bl(T.OUT_CALL,out['c_guout']))
    rhbuild.patch(img,reset_site,f'bl #{reset_pages:#x}',bl(reset_site,out['c_gureset']))
    for index,(site,target) in enumerate(SAVE_CALLS.items()):
        rhbuild.patch(img,site,f'bl #{target:#x}',bl(site,out[f'c_gusave{index}']))
    report['granular']['ui']=dict(bytes=len(code),menu=hex(menu),page_pad=29,
        labels={key:hex(value) for key,value in out.items()},previous={key:hex(value) for key,value in previous.items()},
        scope='Virtual granular page; native page IDs remain unchanged')
    return out
