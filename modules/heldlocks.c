/* Common track recording boundary: live movement and held-step locks are
 * separate operations. Never move the actual transport/playhead position. */
#include <stdint.h>
typedef uint32_t u32;
#define W(a) (*(volatile u32 *)(a))
typedef u32 (*F4)(u32,u32,u32,u32);
static u32 item(u32 store,u32 index){return W(((u32 (*)(u32,u32))0x0803fc59)(store,index));}
static u32 held(u32 t){return ((u32 (*)(u32))(TM_HELD|1))(t);}
static u32 track(u32 base){
    if(W(base)!=0x08067864)return 8;
    for(u32 t=0;t<8;t++)if(W(base+0xc)==W(0x200470dc+0x190*t))return t;
    return 8;
}
static int hold_record(u32 t){return t<8 && (item(0x200122b0,1)&255) && held(t)<32;}
u32 c_hl_lock(u32 rec,u32 lane,u32 v,u32 d){
    u32 t=8;
    for(u32 n=0;n<8;n++)if(W(0x2003d380+4*n)==rec){t=n;break;}
    if(lane<12 && hold_record(t)){
        uint8_t *pos=(void *)((u32 (*)(u32,u32))0x0803fc59)(W(rec+0x28),1);
        uint8_t old=*pos;*pos=(uint8_t)held(t);
        u32 result=((F4)(TR_LOCK|1))(rec,lane,v,d);*pos=old;return result;
    }
    return ((F4)(TR_LOCK|1))(rec,lane,v,d);
}
static int suppress(u32 base,u32 lane){
    u32 t=track(base);
    if(lane>=12 || !hold_record(t) || !(item(0x200122b0,0)&255))return 0;
    /* Prevent the first released tick from interpolating from a pre-hold
     * position. This is recorder runtime state, never saved automation. */
    W(W(base+0x38))&=~(1u<<lane);
    return 1;
}
u32 c_hl_bridge(u32 base,u32 lane,u32 v,u32 d){
    return suppress(base,lane)?d:((F4)(TR_BRIDGE|1))(base,lane,v,d);
}
u32 c_hl_tick(u32 base,u32 lane,u32 pulse,u32 v){
    return suppress(base,lane)?v:((F4)(TR_TICK|1))(base,lane,pulse,v);
}
