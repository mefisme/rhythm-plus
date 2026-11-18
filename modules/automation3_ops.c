/* Mirror existing native Copy/Clear boundaries. No clipboard bank and no SD I/O. */
#include <stdint.h>
#if TASK_GUARD
#include "rp_task_guard.h"
#endif
typedef uint32_t U;typedef uint8_t B;
#define W(a) (*(volatile U *)(a))
typedef U (*F4)(U,U,U,U);
static U item(U s,U i){return W(((U (*)(U,U))0x0803fc59)(s,i))&255;}
static void zero(B *p){for(U i=0;i<32;i++)((volatile B *)p)[i]=0;}
static U fx(void){return ((U (*)(void))(GX_FX|1))();}
static U track(U rec){for(U t=0;t<8;t++)if(W(0x2003d380+4*t)==rec)return t;return 8;}
static U source(U ptr,U *p,U *step){
    U base=W(0x2003c0cc)+0x2e4;
    if(ptr<base || ptr>=base+8*0x5140)return 8;
    U d=ptr-base,t=d/0x5140;d%=0x5140;*p=d/0xa28;d%=0xa28;
    if(d>=256 || (d&7))return 8;*step=d/8;return t;
}
#if NO_A3
#define bulk(op,sp,ss,dp,ds) ((void)0)
#else
static void bulk(U op,U sp,U ss,U dp,U ds){
    U bank=((U (*)(void))(AUTO_READY|1))();if(!bank)return;
    ((U (*)(U,U,U,U,U,U,U))(CORE_BULK|1))(CORE_STATE,bank,op,sp,ss,dp,ds);
}
#endif
static void apply(U t,U op,U sp,U ss,U dp,U ds,B *codes){
    if(t!=fx() || t>=8)return;
#if TASK_GUARD
    U mask=rp_task_lock();
#else
    U mask;__asm__ volatile("mrs %0,primask\n cpsid i":"=r"(mask)::"memory");
#endif
    bulk(op,sp,ss,dp,ds);
    if(codes)((void (*)(U,U,const B *))(GX_WRITE|1))(t,dp,codes);
#if TASK_GUARD
    rp_task_unlock(mask);
#else
    __asm__ volatile("msr primask,%0"::"r"(mask):"memory");
#endif
}
U c_ao_patternpaste(U rec,U ptr,U dst,U d){
    U t=track(rec),sp=8,ss=0,st=source(ptr,&sp,&ss),f=fx();B codes[32];zero(codes);
    if(t==f && dst<8 && st==f && !ss)((U (*)(U,U,B *))(GX_READ|1))(f,sp,codes);
    U result=((F4)(TR_PATTERNPASTE|1))(rec,ptr,dst,d);
    if(t==f && dst<8)apply(t,st==f && !ss?0:1,sp,0,dst,0,codes);
    return result;
}
U c_ao_patternclear(U rec,U p,U c,U d){
    U result=((F4)(TR_PATTERNCLEAR|1))(rec,p,c,d);B codes[32];zero(codes);
    if(p<8)apply(track(rec),1,0,0,p,0,codes);return result;
}
U c_ao_steppaste(U rec,U ptr,U lanes,U d){
    U t=track(rec),sp=8,ss=0,st=source(ptr,&sp,&ss),f=fx();
    U dp=item(W(rec+0x28),0),ds=item(W(rec+0x28),1);B codes[32],src[32];zero(codes);zero(src);
    if(t==f && dp<8 && ds<32){
        ((U (*)(U,U,B *))(GX_READ|1))(f,dp,codes);
        if(st==f){((U (*)(U,U,B *))(GX_READ|1))(f,sp,src);codes[ds]=src[ss];}
        else codes[ds]=0;
    }
    U result=((F4)(TR_STEPPASTE|1))(rec,ptr,lanes,d);
    if(t==f && dp<8 && ds<32)apply(t,st==f?2:3,sp,ss,dp,ds,codes);return result;
}
U c_ao_stepclear(U rec,U b,U c,U d){
    U t=track(rec),p=item(W(rec+0x28),0),s=item(W(rec+0x28),1);B codes[32];zero(codes);
    if(t==fx() && p<8 && s<32){((U (*)(U,U,B *))(GX_READ|1))(t,p,codes);codes[s]=0;}
    U result=((F4)(TR_STEPCLEAR|1))(rec,b,c,d);
    if(p<8 && s<32)apply(t,3,0,0,p,s,codes);return result;
}
U c_ao_trackreset(U t,U b,U c,U d){
    U rec=t<8?W(0x2003d380+4*t):0,p=rec?item(W(rec+0x28),0):8;
    U result=((F4)(TR_TRACKRESET|1))(t,b,c,d);
    if(t==fx() && p<8){
        apply(t,1,0,0,p,0,0);((void (*)(void))(GX_DEFAULTS|1))();
#if !NO_A3
        if(((U (*)(void))(AUTO_READY|1))())for(U k=0;k<3;k++)
            ((void (*)(U,U,U,U))(CORE_MANUAL|1))(CORE_STATE,k,127,0);
#endif
    }
    return result;
}
void c_ao_trackclear(U t){apply(t,4,0,0,0,0,0);}
#ifdef TR_PAGECOPY
U c_ao_pagecopy(U rec,U b,U c,U d){
    U t=track(rec),p=item(W(rec+0x28),0);B codes[32];zero(codes);
    if(t==fx() && p<8)((U (*)(U,U,B *))(GX_READ|1))(t,p,codes);
    U result=((F4)(TR_PAGECOPY|1))(rec,b,c,d);
    if(t==fx() && p<8){
        for(U s=0;s<16;s++)codes[s+16]=codes[s];
        for(U s=0;s<16;s++)apply(t,2,p,s,p,s+16,s==15?codes:0);
    }
    return result;
}
#endif
