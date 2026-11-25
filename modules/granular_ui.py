"""Virtual granular page over native Normal; no legacy page IDs reactivated."""
from thumb import (Asm,bl,b_w,b_cond,bx_lr,mov_reg,movs_imm,movw,movt,
                   push_list,pop_list,ldr_sp,ldr_imm,ldrb_imm,strb_imm,
                   cmp_imm,cmp_reg,add_sp_imm,adds_imm8,subs_imm8,ands_reg,
                   adds_reg,tst_reg,raw,str_imm)
import os

import rhbuild
from flash_placement import emit_code
import countin as C
import tmenu as T

# Both stock session-record writers, as documented in remix/tools/mfsess.py.
SAVE_CALLS = {0x08037fd6: 0x080472e2, 0x08038734: 0x08047270}


def install(img,report,base,persist=True,current=False,pages=False,track_views=False,reverse_cycle=False,editor_settings=False,no_burst=False,page_pad=None,shift_tap=False,*,placement_end=None):
    if page_pad is None:page_pad=31 if current else 29
    labels=report['granular']['arm_kernel']['labels'];bridge=report['granular']['bridge']
    native_state=int(bridge['labels']['c_gstate'],16);state='c_gustate'
    menu=int(report['tmenu']['slot'],16);root=int(report['rhstate']['block'],16)
    previous={key:rhbuild.bw_target(img,address) for key,address in (('pad',T.PP_ENTRY),('release',T.PR_ENTRY),('knob',T.KN_ENTRY))}
    scrub_flag=int(report['gfxmix']['scrub_flag'],16) if os.environ.get('RH_SCRUB_KNOBS')=='1' else 0
    scrub_lights=scrub_flag if os.environ.get('RH_SCRUB_LIGHTS')=='1' else 0
    previous['frame']=rhbuild.bl_target(img,C.LED_CALLS[0]);previous['out']=rhbuild.bl_target(img,T.OUT_CALL)
    if pages:
        previous['button']=rhbuild.bw_target(img,C.BTN_ENTRY)
        previous['button_release']=rhbuild.bw_target(img,C.BTN_RELEASE)
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
        if pages:
            E(mov_reg,0,4);E(mov_reg,1,5);call('runtime_knob_page');E(cmp_imm,0,0)
        else:
            imm(0,T.CTRL);E(ldr_imm,0,0,0xc);E(movs_imm,1,0);E(bl,C.PARAM_GET);E(ldrb_imm,0,0,0);E(cmp_imm,0,0)
    def commit_result():
        E(push_list,[0,1]);E(mov_reg,0,4);E(bl,'c_gucommit');E(pop_list,[0,1])
    a.label('c_gustate');E(push_list,[4],lr=True);E(bl,native_state);E(cmp_imm,0,0);E(b_cond,'state_x','eq')
    E(mov_reg,4,0);call('runtime_init');E(mov_reg,0,4)
    a.label('state_x');E(pop_list,[4],pc=True)
    a.label('c_gucommit')
    if persist:
        E(push_list,[4],lr=True);E(mov_reg,4,0);E(bl,int(report['rhrec']['labels']['c_rrt'],16))
        E(cmp_imm,0,0);E(b_cond,'commit_x','eq');E(mov_reg,1,0);E(mov_reg,0,4);call('runtime_store')
        a.label('commit_x');E(pop_list,[4],pc=True)
    else:E(bx_lr)
    for index,target in enumerate(SAVE_CALLS.values()):
        name=f'c_gusave{index}'
        a.label(name);saved();E(bl,state);E(cmp_imm,0,0);E(b_cond,name+'_native','eq')
        E(bl,'c_gucommit')
        a.label(name+'_native');tail(target)
    a.label('c_gureset');saved();E(bl,state);E(cmp_imm,0,0);E(b_cond,'reset_done','eq')
    E(mov_reg,4,0);E(ldr_sp,1,0);call('runtime_track_reset');E(mov_reg,0,4);E(bl,'c_gucommit')
    a.label('reset_done');E(ldr_sp,0,0);E(ldr_sp,1,4);E(bl,reset_pages);drop()
    a.label('c_gucontext')
    if current and report['storageshadow'].get('granular_settings_bytes'):
        E(push_list,[4],lr=True);E(bl,int(report['storageshadow']['labels']['c_sh_autobank'],16))
        E(cmp_imm,0,0);E(b_cond,'context_available','ne');E(movs_imm,0,8);E(pop_list,[4],pc=True)
        a.label('context_available');E(bl,'c_gunavcontext')
        E(cmp_imm,0,8);E(b_cond,'context_return','hs');E(mov_reg,4,0)
        E(bl,state);E(mov_reg,1,4);call('runtime_shift_layer');E(mov_reg,0,4)
        a.label('context_return');E(pop_list,[4],pc=True)
    else:E(b_w,'c_gunavcontext')
    a.label('c_gunavcontext');E(push_list,[4],lr=True);E(bl,state);E(cmp_imm,0,0);E(b_cond,'context_no','eq')
    imm(0,menu+T.O_OPEN);E(ldrb_imm,0,0,0);E(cmp_imm,0,0);E(b_cond,'context_no','eq')
    E(bl,int(report['tmenu']['labels']['c_tmview'],16))
    if current:
        E(mov_reg,4,0);E(bl,int(report['gfxmix']['labels']['c_gx_autofx'],16));E(cmp_reg,4,0)
        E(b_cond,'context_no','eq')
        E(mov_reg,0,4)
    E(pop_list,[4],pc=True)
    a.label('context_no');E(movs_imm,0,8);E(pop_list,[4],pc=True)
    if pages:
        for kind in ('button','button_release'):
            a.label('c_gu'+kind);saved();E(ldr_sp,6,4)
            if kind=='button_release':
                E(cmp_imm,6,23);E(b_cond,'clear_release_done','ne')
                imm(0,menu+T.O_CLRR);call('clear_end')
                a.label('clear_release_done')
            E(cmp_imm,6,19);E(b_cond,kind+'_arrow','eq')
            E(cmp_imm,6,20);E(b_cond,kind+'_pass','ne')
            a.label(kind+'_arrow');E(bl,state);E(cmp_imm,0,0);E(b_cond,kind+'_pass','eq');E(mov_reg,4,0)
            E(bl,'c_gunavcontext');E(cmp_imm,0,8);E(b_cond,kind+'_pass','hs')
            if kind=='button':
                E(mov_reg,5,0);E(mov_reg,1,5);E(mov_reg,0,4);call('runtime_shift_layer')
                E(mov_reg,1,5);E(mov_reg,0,4);E(mov_reg,2,6);call('runtime_arrow')
            drop()
            a.label(kind+'_pass');tail(previous[kind])
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
    if shift_tap:E(mov_reg,0,4);call('shift_used')
    modifiers();E(cmp_imm,0,0);E(b_cond,'pad_normal','eq')
    E(mov_reg,0,4);E(adds_imm8,0,96);call('ui_release')
    imm(0,T.CTRL+T.HELD);E(ldr_imm,0,0,0);imm(1,1<<23);E(tst_reg,0,1);E(b_cond,'pad_pass','eq')
    E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);call('runtime_clear');commit_result();E(cmp_imm,0,0);E(b_cond,'pad_pass','eq')
    if editor_settings:
        imm(0,int(report['pageclear']['slot'],16));imm(1,C.HAL_TICK);E(ldr_imm,1,1,0);E(str_imm,1,0,0)
        E(ldr_sp,1,4);E(adds_imm8,1,1);E(strb_imm,1,0,4)
    E(b_w,'pad_drop')
    a.label('pad_normal');E(ldr_sp,6,4);E(cmp_imm,6,page_pad);E(b_cond,'pad_dispatch','ne')
    E(mov_reg,0,4);E(mov_reg,1,5);call('runtime_page');E(cmp_imm,0,0);E(b_cond,'pad_dispatch','ne')
    imm(0,menu+T.O_KNOB);E(movs_imm,1,1);E(strb_imm,1,0,0)
    a.label('pad_dispatch');E(mov_reg,0,4);E(mov_reg,1,5);E(mov_reg,2,6);call('runtime_pad')
    commit_result()
    E(cmp_imm,0,0);E(b_cond,'pad_pass','eq')
    if editor_settings:E(cmp_imm,6,25);E(b_cond,'pad_view','eq')
    if 'c_gr_editor_knob_mode' in labels:E(cmp_imm,6,27);E(b_cond,'pad_view','eq')
    if 'pitch_envelope_dsp' in report:E(cmp_imm,6,28);E(b_cond,'pad_view','eq')
    if 'ring_mod_dsp' in report:E(cmp_imm,6,29 if 'scan_dsp' in report else 30);E(b_cond,'pad_view','eq')
    E(cmp_imm,6,page_pad);E(b_cond,'pad_next','ne')
    a.label('pad_view')
    imm(0,menu+T.O_PAGE);E(movs_imm,1,0);E(strb_imm,1,0,0)
    if not current:
        E(mov_reg,0,5);E(movs_imm,1,0);E(bl,int(report['tmenu']['labels']['c_tmpgset'],16))
        imm(0,root);E(bl,int(report['tmenu']['labels']['c_tmsp'],16))
    E(b_w,'pad_drop')
    a.label('pad_next');E(cmp_imm,6,24);E(b_cond,'pad_drop','ne')
    if 'c_gr_editor_knob_mode' in labels:
        E(b_w,'pad_drop')
    elif shift_tap:
        E(mov_reg,0,4);E(mov_reg,1,5);call('cycle_knob')
    elif no_burst:
        # The secondary page has six knobs; K7/K8 are not controls.
        E(mov_reg,0,4);E(mov_reg,1,5);call('runtime_knob_page');E(movs_imm,1,8);E(cmp_imm,0,0);E(b_cond,'pad_count','eq');E(movs_imm,1,6)
        a.label('pad_count');imm(6,menu+T.O_KNOB);E(ldrb_imm,0,6,0);call('cycle_next');E(strb_imm,0,6,0)
    elif reverse_cycle:
        imm(6,menu+T.O_KNOB);E(ldrb_imm,0,6,0);E(movs_imm,1,8);call('cycle_next');E(strb_imm,0,6,0)
    else:
        imm(0,menu+T.O_KNOB);E(ldrb_imm,1,0,0);E(adds_imm8,1,1);E(cmp_imm,1,9);E(b_cond,'pad_knob','lo');E(movs_imm,1,1)
        a.label('pad_knob');E(strb_imm,1,0,0)
    a.label('pad_drop');drop()
    a.label('pad_pass');tail(previous['pad'])
    a.label('c_gurelease');saved();E(bl,state);E(cmp_imm,0,0);E(b_cond,'release_pass','eq')
    E(ldr_sp,1,4);call('runtime_release');E(cmp_imm,0,0);E(b_cond,'release_pass','eq');drop()
    a.label('release_pass');tail(previous['release'])
    a.label('c_guknob');saved()
    if scrub_flag:                                 # a scrub (Shift + Play held) owns the knobs on every page
        imm(0,scrub_flag);E(ldrb_imm,0,0,0);E(cmp_imm,0,0);E(b_cond,'knob_scrub','eq');E(b_w,'knob_pass');a.label('knob_scrub')
    E(ldr_sp,0,4);E(cmp_imm,0,8)
    if 'c_gr_editor_knob_mode' in labels:
        E(b_cond,'knob_index_ok','lo');E(b_w,'knob_pass');a.label('knob_index_ok')
    else:E(b_cond,'knob_pass','hs')
    E(bl,state);E(cmp_imm,0,0)
    if 'c_gr_editor_knob_mode' in labels:E(b_cond,'knob_early_pass','eq')
    else:E(b_cond,'knob_pass','eq')
    E(mov_reg,4,0);E(bl,'c_gucontext');E(cmp_imm,0,8)
    if 'c_gr_editor_knob_mode' in labels:
        E(b_cond,'knob_context_ok','lo')
        a.label('knob_early_pass');E(b_w,'knob_pass');a.label('knob_context_ok')
    else:E(b_cond,'knob_pass','hs')
    E(mov_reg,5,0)
    if shift_tap:E(mov_reg,0,4);call('shift_used')
    if 'c_gr_editor_knob_mode' in labels:
        E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);call('editor_knob_mode')
        E(cmp_imm,0,2);E(b_cond,'knob_assignment','eq')
        E(cmp_imm,0,0);E(b_cond,'knob_ours','ne')
    E(mov_reg,0,4);E(mov_reg,1,5);call('runtime_page');E(cmp_imm,0,0)
    E(b_cond,'knob_native_clear' if 'c_gr_editor_knob_mode' in labels else 'knob_pass','eq')
    a.label('knob_ours')
    modifiers();E(cmp_imm,0,0);E(b_cond,'knob_modifier','ne')
    shift();E(b_cond,'knob_shift','ne')
    E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);E(ldr_sp,3,8);call('lane_turn' if current else 'runtime_turn');E(b_w,'knob_commit')
    a.label('knob_modifier');imm(0,T.CTRL+T.HELD);E(ldr_imm,0,0,0);imm(1,1<<23);E(tst_reg,0,1);E(b_cond,'knob_drop','eq')
    imm(0,menu+T.O_KNOB);E(ldr_sp,1,4);E(adds_imm8,1,1);E(strb_imm,1,0,0)
    imm(0,menu+T.O_CLRR);E(ldr_sp,1,4);E(ldr_sp,2,8);call('clear_step');E(cmp_imm,0,0);E(b_cond,'knob_drop','eq')
    if current:
        E(mov_reg,6,0);E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4)
        E(push_list,[0,1,2,3]);shift();E(mov_reg,3,0);E(pop_list,[0,1,2]);E(add_sp_imm,4)
        call('lane_clear');E(cmp_imm,6,2);E(b_cond,'knob_drop','eq')
    shift();E(b_cond,'knob_clear_shift','ne');E(movs_imm,3,0);E(b_w,'knob_clear')
    a.label('knob_clear_shift');E(movs_imm,3,1)
    a.label('knob_clear');E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);call('runtime_clear_knob')
    E(cmp_imm,0,0);E(b_cond,'knob_drop','eq');E(b_w,'knob_commit')
    a.label('knob_shift');E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);E(ldr_sp,3,8);call('lane_turn' if current else 'runtime_shift_turn')
    E(cmp_imm,0,0);E(b_cond,'knob_drop','eq')
    a.label('knob_commit')
    E(mov_reg,0,4);E(bl,'c_gucommit')
    imm(0,menu+T.O_KNOB);E(ldr_sp,1,4);E(adds_imm8,1,1);E(strb_imm,1,0,0)
    a.label('knob_drop');drop()
    if 'c_gr_editor_knob_mode' in labels:
        a.label('knob_assignment')
        E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);E(ldr_sp,3,8);call('lane_turn');drop()
        a.label('knob_native_clear')
        imm(0,T.CTRL+T.HELD);E(ldr_imm,0,0,0);imm(1,1<<23);E(tst_reg,0,1);E(b_cond,'knob_pass','eq')
        imm(0,menu+T.O_CLRR);E(ldr_sp,1,4);E(ldr_sp,2,8);call('clear_step')
        E(cmp_imm,0,0);E(b_cond,'knob_pass','eq')
        E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);E(movs_imm,3,0);call('lane_clear')
    a.label('knob_pass');tail(previous['knob'])
    a.label('c_guout');saved();E(bl,previous['out'])
    if scrub_lights:                               # a scrub: its lights (K1-K2 green, the track's steps) stay
        imm(0,scrub_flag);E(ldrb_imm,0,0,0);E(cmp_imm,0,0);E(b_cond,'out_live','eq');E(b_w,'out_scrub');a.label('out_live')
    E(bl,state);E(cmp_imm,0,0);E(b_cond,'out_x','eq');E(mov_reg,4,0)
    E(bl,'c_gucontext');E(cmp_imm,0,8);E(b_cond,'out_x','hs');E(mov_reg,5,0)
    shift();imm(3,menu+T.O_KNOB);E(ldrb_imm,3,3,0);E(subs_imm8,3,1)
    E(cmp_imm,0,0);E(b_cond,'out_draw','eq');E(adds_imm8,3,8)
    a.label('out_draw');E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);call('runtime_draw')
    if not current:
        E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);imm(3,menu+T.O_CLRR);call('clear_draw')
    a.label('out_x')
    if current:
        E(bl,'c_gunavcontext');E(cmp_imm,0,8);E(b_cond,'out_done','hs')
        E(mov_reg,5,0)
        E(mov_reg,1,0);E(mov_reg,0,4);E(ldr_sp,2,4);imm(3,menu+T.O_KNOB);E(ldrb_imm,3,3,0);E(subs_imm8,3,1);call('lane_draw')
        E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);imm(3,menu+T.O_CLRR);call('clear_draw')
        if report['tmenu'].get('steady_track'):
            E(mov_reg,0,4);E(bl,'c_gunavcontext');E(mov_reg,1,0);E(mov_reg,0,4);E(ldr_sp,2,4);call('menu_indicator')
        if track_views:
            E(bl,'c_gunavcontext');E(mov_reg,1,0);E(mov_reg,0,4);E(ldr_sp,2,4);call('track_views')
        if editor_settings:
            E(mov_reg,0,4);E(mov_reg,1,5);E(ldr_sp,2,4);imm(3,int(report['pageclear']['slot'],16));call('clear_views')
        a.label('out_done')
    a.label('out_scrub')
    drop()
    if editor_settings:
        # Native step-selection audition only. The held-step stores, pad-down
        # bookkeeping and sequence playback stay on their ordinary paths.
        audition_site=0x0805cc54
        audition_head=bytes(img[audition_site-rhbuild.BASE:audition_site-rhbuild.BASE+6])
        assert audition_head==bytes.fromhex('2f7088f80060') or audition_head==bytes.fromhex('2f70d8f80060'),audition_head.hex()
        a.label('c_gusilent');saved();E(bl,state);E(cmp_imm,0,0);E(b_cond,'silent_native','eq');E(mov_reg,4,0)
        E(bl,'c_gucontext');E(mov_reg,1,0);E(mov_reg,0,4);call('editor_silent');E(cmp_imm,0,0);E(b_cond,'silent_native','eq')
        E(raw,C.popw([0,1,2,3,4,5,6],lr=True));E(movs_imm,0,255);E(strb_imm,0,5,0);E(b_w,0x0805cc66)
        a.label('silent_native');E(raw,C.popw([0,1,2,3,4,5,6],lr=True))
        E(raw,audition_head);E(b_w,audition_site+6)
    code,out=a.assemble();emit_code(img,rhbuild.BASE,base,code,placement_end)
    for key,address in (('pad',T.PP_ENTRY),('release',T.PR_ENTRY),('knob',T.KN_ENTRY)):
        rhbuild.patch(img,address,f'b.w #{previous[key]:#x}',b_w(address,out['c_gu'+key]))
    if pages:
        for key,address in (('button',C.BTN_ENTRY),('button_release',C.BTN_RELEASE)):
            rhbuild.patch(img,address,f'b.w #{previous[key]:#x}',b_w(address,out['c_gu'+key]))
    for address in C.LED_CALLS:rhbuild.patch(img,address,f'bl #{previous["frame"]:#x}',bl(address,out['c_guframe']))
    rhbuild.patch(img,T.OUT_CALL,f'bl #{previous["out"]:#x}',bl(T.OUT_CALL,out['c_guout']))
    rhbuild.patch(img,reset_site,f'bl #{reset_pages:#x}',bl(reset_site,out['c_gureset']))
    for index,(site,target) in enumerate(SAVE_CALLS.items()):
        rhbuild.patch(img,site,f'bl #{target:#x}',bl(site,out[f'c_gusave{index}']))
    if editor_settings:
        rhbuild.patch(img,audition_site,'strb r7, [r5]|ldr.w r6, [r8]',b_w(audition_site,out['c_gusilent'])+b'\x00\xbf')
    report['granular']['ui']=dict(**({'scrub_knobs':True} if scrub_flag else {}),**({'scrub_lights':True} if scrub_lights else {}),bytes=len(code),menu=hex(menu),page_pad=page_pad,arrow_pages=pages,page_dependent_shift=current,settings_owner='active parameter pad view',stock_settings=editor_settings,native_brightness=editor_settings,secondary_knobs=6 if no_burst else 8,shift_tap=shift_tap,per_track_view_colors=track_views,
        labels={key:hex(value) for key,value in out.items()},previous={key:hex(value) for key,value in previous.items()},
        scope='Virtual granular page; native page IDs remain unchanged')
    return out
