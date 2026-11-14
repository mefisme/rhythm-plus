/* Linked with automation3.h/core. Native callbacks always run first. */
#define AS ((struct a3_state *)A3_STATE)
#define AB ((a3_u8 *)A3_BANK)
#define AW(a) (*(volatile a3_u32 *)(a))
typedef a3_u32 (*a3_f4)(a3_u32,a3_u32,a3_u32,a3_u32);
static a3_u32 item(a3_u32 st,a3_u32 index){
    return *(a3_u32 *)((a3_u32 (*)(a3_u32,a3_u32))0x0803fc59)(st,index);
}
/* Patched to storage's availability gate, including current project and pack. */
__attribute__((naked,noinline)) a3_u32 c_a3_available(void)
{__asm__ volatile("movs r0,#0\n bx lr");}
static a3_u32 fx(void){return ((a3_u32 (*)(void))(GX_FX|1))();}
static a3_u32 held_value(a3_u32 k){
    if(k>=3 || !c_a3_available())return A3_NONE;
    a3_u32 t=fx();if(t>=8)return A3_NONE;
    a3_u32 st=((a3_u32 (*)(a3_u32))(TM_HELD|1))(t);
    a3_u32 r=AW(0x2003d380+4*t),p=item(AW(r+0x28),0)&255;
    if(st>=32 || p>=8)return A3_NONE;
    for(a3_u32 m=0;m<6;m++){a3_u32 v=value(bank_get(AB,at(k,p,st,m)));if(v!=A3_NONE)return v;}
    return A3_NONE;
}
a3_u32 c_a3_display(a3_u32 k,a3_u32 base){a3_u32 v=held_value(k);return v==A3_NONE?base:v;}
/* Playback never rewrites the native project buffer during a native Save.
 * Sound and LEDs consume this same volatile output through control_get. */
a3_u32 c_a3_controlvalue(a3_u32 k,a3_u32 base){
    return k<3 && c_a3_available() && AS->output[k]!=A3_NONE?AS->output[k]:base;
}
static int recording(void){return (item(0x200122b0,0)&255) && (item(0x200122b0,1)&255) && !(item(0x200122b0,2)&255);}
a3_u32 c_a3_red(a3_u32 k){
    if(!c_a3_available() || k>=3)return 0;
    if(fx()>=8){AS->padding[0]=0;return 0;}
    if(held_value(k)!=A3_NONE)return 1;
    if(!(item(0x200122b0,1)&255)){AS->padding[0]=0;return 0;}
    return AS->padding[0]>>k&1;
}
static void sync_state(a3_u32 t){
    a3_u32 playing=item(0x200122b0,0)&255,rec=recording();
    if(AS->fx!=t || (!AS->playing && playing))c_a3_reset(AS);
    if(!rec && AS->recording)c_a3_disarm(AS);
    AS->playing=playing;AS->recording=rec;AS->fx=t;
    if(!(item(0x200122b0,1)&255))AS->padding[0]=0;
}
void c_a3_touch(a3_u32 k,a3_u32 v,a3_u32 clear){
    if(k>=3 || !c_a3_available())return;
    a3_u32 t=fx();if(t>=8){c_a3_manual(AS,k,v,0);return;}sync_state(t);
    if(!clear && (item(0x200122b0,1)&255))AS->padding[0]|=1u<<k;
    else if(clear)AS->padding[0]&=~(1u<<k);
    a3_u32 r=AW(0x2003d380+4*t),p=item(AW(r+0x28),0)&255;
    a3_u32 step=((a3_u32 (*)(a3_u32))(TM_HELD|1))(t);
    if(clear){c_a3_clear(AS,AB,k,p,step);c_a3_manual(AS,k,v,0);}
    else if(step<32 && (item(0x200122b0,1)&255))c_a3_lock(AS,AB,k,p,step,v);
    else c_a3_manual(AS,k,v,recording());
}
void c_a3_play(a3_u32 player,a3_u32 pattern,a3_u32 step,a3_u32 pulse){
    ((a3_f4)0x08055325)(player,pattern,step,pulse);
    if(!c_a3_available())return;
    a3_u32 t=fx();if(t>=8 || player!=0x200470d4+0x190*t)return;
    sync_state(t);
    a3_u32 pos=AW(player+0xc),np=item(pos,0)&255,ns=item(pos,1)&255;
    a3_u32 rate=item(AW(player+0x10),1)&255;
    for(a3_u32 k=0;k<3;k++){
        a3_u32 next=A3_NONE;
        if(np<8 && ns<32){
#if COW7
            next=value(c_a3_bankpeek(at(k,np,ns,0)));
#else
            next=value(bank_get(AB,at(k,np,ns,0)));
#endif
        }
        c_a3_value(AS,AB,k,pattern,step,pulse,rate,next);
    }
}
void c_a3_listener(a3_u32 object,a3_u32 event,a3_u32 changed,a3_u32 unused){
    ((a3_f4)0x0804946d)(object,event,changed,unused);
    if(!c_a3_available())return;
    a3_u32 t=fx(),base=object-8;
    if(t>=8 || AW(base)!=0x08067864 || AW(base+0xc)!=AW(0x200470dc+0x190*t))return;
    sync_state(t);if(!recording() || event!=AW(base+0x30))return;
    if(((a3_u32 (*)(a3_u32))(TM_HELD|1))(t)<32){c_a3_disarm(AS);return;}
    a3_u32 pos=AW(base+0xc);
    c_a3_record(AS,AB,item(pos,0)&255,item(pos,1)&255,item(pos,2),((a3_u32 (*)(a3_u32))0x08048ccb)(base));
}
void c_a3_playerreset(a3_u32 player){
    ((void (*)(a3_u32))(RESET_TRAMP|1))(player);
    if(c_a3_available() && fx()<8 && player==0x200470d4+0x190*fx())c_a3_reset(AS);
}
