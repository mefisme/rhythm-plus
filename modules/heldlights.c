/* Post-render counterpart of Track Parameter Editor's c_tmrpad.
 * Only RGB output changes; no recording, playback or project state is written. */
#include <stdint.h>
typedef uint32_t u32;
#define W(a) (*(volatile u32 *)(a))
#define B(a) (*(volatile uint8_t *)(a))
static int ram(u32 p){return p>=0x20000000 && p<0x2004ff00;}
static int built(u32 p){return ram(p) && ram(W(p+12)) && ram(W(p+16));}
static u32 item(u32 st,u32 i){return W(((u32 (*)(u32,u32))0x0803fc59)(st,i));}
static u32 scale(u32 rgb,u32 full){
    return (((rgb&255)*(full+1)>>8)&255) |
        ((((rgb>>8&255)*(full+1)>>8)&255)<<8) |
        ((((rgb>>16&255)*(full+1)>>8)&255)<<16);
}
u32 c_hp_out(u32 controller,u32 output,u32 frame,u32 d){
    u32 result=((u32 (*)(u32,u32,u32,u32))(PREV_OUT|1))(controller,output,frame,d);
    if(W(0x200487c8+0x7c)!=0x20048b9c || B(0x20048b9c+0x264)>4 ||
       B(TM_SLOT) || (B(MS_SLOT)&1) || (B(SM_SLOT)&17)==1)return result;
    if(!built(0x200122b0) || !(item(0x200122b0,1)&255))return result;
    u32 selected=W(0x20048b9c+0x25c);
    if(!built(selected))return result;
    u32 t=item(selected,0)&255;if(t>=8)return result;
    u32 so=W(0x20048b9c+0x74+4*t);
    if(!ram(so) || !built(W(so+0x64)) || !built(W(so+0x60)))return result;
    u32 h=((u32 (*)(u32))(TM_HELD|1))(t);if(h>=32)return result;
    u32 page=item(W(so+0x60),0)&255;if(page>1)return result;
    u32 dimstore=W(0x200487c8+0x88);
    if(!built(dimstore))return result;
    u32 full=item(dimstore,2)&(1u<<10)?141:255;
    u32 *out=(u32 *)output;
    if(item(0x200122b0,0)&255){
        u32 rec=W(0x2003d380+4*t);
        if(ram(rec) && built(W(rec+0xc))){
            u32 play=item(W(rec+0xc),1)&255;
            if(play<32 && play/16==page)out[play&15]=scale(0xffffff,full);
        }
    }
    /* A held step wins when the playhead crosses that same pad. */
    if(h/16==page)out[h&15]=scale(W(0x20003974+4*0x55),full);
    return result;
}
