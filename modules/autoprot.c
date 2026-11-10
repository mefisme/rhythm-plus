/* One-lane volatile automation proof. Stock timing tables and record interpolation,
 * widened to 14 bits. All stock lanes remain owned by stock. */
#include "autoprot_config.h"
#ifndef FIX_RECORD_TOUCH
#define FIX_RECORD_TOUCH 0
#endif
#ifndef AUDIT_BATCH
#define AUDIT_BATCH 0
#endif
#ifndef IMPORT_LOCKS
#define IMPORT_LOCKS 0
#endif
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
#define NONE 65535u
#define MAGIC 0x41505431u
#define OWNED 0x41505430u
#define U32(a) (*(volatile u32 *)(a))
#define U8(a) (*(volatile u8 *)(a))
#define FN(a,t) ((t)((a)|1u))
typedef u32 (*F0)(void);
typedef u32 (*F1)(u32);
typedef u32 (*F2)(u32,u32);
typedef u32 (*F3)(u32,u32,u32);
typedef u32 (*F4)(u32,u32,u32,u32);
struct State {
 u32 magic,record,error,writes,applies,reads;
 u16 held,last,output,pending,previous;
 u8 prev_valid,prev_step,prev_micro,prev_rate,prev_pattern,touch;
 u16 lane[192];
 u32 demcr,dwtctrl,larlocked,maxplay,maxrecord,trace;
#if AUDIT_BATCH
 u32 reason;
#endif
};
#define S ((volatile struct State *)0x100u)
static u32 get(u32 store,u32 item) {return FN(0x0803fc58,F2)(store,item);}
static u32 item(u32 store,u32 index) {return U32(get(store,index));}
static u32 transport(u32 index) {return item(0x200122b0,index)&255;}
static int ready(void) {
 return U32(PRIVATE_MAGIC_ADDR)==PRIVATE_MAGIC && U8(READY_ADDR)==READY_VALUE &&
 U8(WAIT_ADDR)>=200 && !U8(UPLOAD_ADDR);
}
void c_apdisable(void);
static int active(void) {
 if(U32(FLAG_ADDR)!=MAGIC) return 0;
 if(S->magic!=MAGIC || S->record!=U32(0x2003c0cc) || !ready()) {
#if AUDIT_BATCH
  if(S->magic==MAGIC)S->reason=S->record!=U32(0x2003c0cc)?3:4;
#endif
  c_apdisable();return 0;
 }
 return 1;
}
void c_apdisable(void) {
 if(U32(FLAG_ADDR)==MAGIC) {
#if AUDIT_BATCH
  if(S->magic==MAGIC && !S->reason)S->reason=1;
#endif
  if(S->magic==MAGIC && S->trace) {
   U32(0xe0001000)=S->dwtctrl;
   if(S->larlocked&2)U32(0xe0001fb0)=0;
   U32(0xe000edfc)=S->demcr;S->trace=0;
  }
  U32(FLAG_ADDR)=OWNED;
 }
}
#if AUDIT_BATCH
void c_apload_disable(void) {
 if(U32(FLAG_ADDR)==MAGIC && S->magic==MAGIC)S->reason=2;
 c_apdisable();
}
#endif
static void lock(u32 *p) {*p=0x20003688;FN(0x08029c8c,F1)(*p);}
static void unlock(u32 *p) {U32(0x20003684)=65535;FN(0x08030eb8,F1)((u32)p);}
static u32 readword(u32 index) {
 u32 v=FN(0x08031268,F2)(0,0x4000+index)>>8;
 U32(0x20003684)=65535;return v;
}
static void writeword(u32 index,u32 value) {
 FN(0x080311da,F3)(0,value<<8,0x4000+index);
}
static int cell(u32 index,u32 value) {
 if(index>=192 || (value>16383 && value!=NONE)) {S->error=5;return 0;}
 if(S->lane[index]==value) return 1;
 u32 p;lock(&p);
 if(!active()) {unlock(&p);return 0;}
 writeword(index,value);S->lane[index]=(u16)value;S->writes++;
 unlock(&p);return 1;
}
u32 c_aparm(void) {
 if(transport(0))return 2;
 if(!ready())return 3;
 u32 cr=U32(0xe000ef90);
 if(!(cr&1) || ((cr>>3)&15)<5 || U32(0xe000ed08)<0x4000 || U32(0xe000ed94))return 4;
 int owned=U32(FLAG_ADDR)==MAGIC || U32(FLAG_ADDR)==OWNED;
 c_apdisable();
 u32 p;lock(&p);
 if(!ready()){unlock(&p);return 3;}
 for(u32 i=0;i<192;i++) {
  u32 v=readword(i);
  if(!owned && v!=0 && v!=NONE){unlock(&p);return 6;}
 }
 U32(FLAG_ADDR)=OWNED;
 for(u32 i=0;i<sizeof(*S)/4;i++) ((volatile u32 *)S)[i]=0;
 S->magic=MAGIC;S->record=U32(0x2003c0cc);
 S->held=S->last=S->output=S->pending=S->previous=NONE;
 for(u32 i=0;i<192;i++){writeword(i,NONE);S->lane[i]=NONE;}
 unlock(&p);
 S->demcr=U32(0xe000edfc);S->dwtctrl=U32(0xe0001000);S->larlocked=U32(0xe0001fb4);
 U32(0xe000edfc)=S->demcr|(1u<<24);U32(0xe0001fb0)=0xc5acce55;
 U32(0xe0001000)=S->dwtctrl|1;S->trace=1;
 U32(FLAG_ADDR)=MAGIC;return 0;
}
u32 c_aprefill(void) {
 if(transport(0))return 2;
 if(!active())return 7;
 u32 p;lock(&p);
 if(!active()){unlock(&p);return 3;}
 for(u32 i=0;i<192;i++) {
  u32 v=readword(i);
  if(v>16383 && v!=NONE){
   S->error=8;
#if AUDIT_BATCH
   S->reason=5;
#endif
   c_apdisable();unlock(&p);return 8;
  }
  S->lane[i]=(u16)v;S->reads++;
 }
 unlock(&p);S->held=S->last=NONE;return 0;
}
#if IMPORT_LOCKS
/* Bounded restore of an archived prototype lane. No host-selected DSP address.
 * The host verifies pattern identity before arming/restoring. Record must be off.
 */
u32 c_apimport(u32 offset,u32 count,u32 data) {
 if(transport(0) || transport(1))return 2;
 if(!active())return 7;
 if(!count || count>24 || offset>=192 || count>192-offset)return 5;
 u16 values[24];
 for(u32 i=0;i<count;i++) {
  u32 value=FN(GET32,F1)(data+i*8);
  if(value>16383 && value!=NONE)return 5;
  values[i]=(u16)value;
 }
 u32 p;lock(&p);
 if(!active()){unlock(&p);return 3;}
 if(transport(0) || transport(1)){unlock(&p);return 2;}
 for(u32 i=0;i<count;i++)if(readword(offset+i)!=S->lane[offset+i]) {
  S->error=8;
#if AUDIT_BATCH
  S->reason=5;
#endif
  c_apdisable();unlock(&p);return 8;
 }
 for(u32 i=0;i<count;i++) {
  writeword(offset+i,values[i]);S->lane[offset+i]=values[i];S->writes++;
 }
 unlock(&p);S->held=S->last=S->pending=S->previous=NONE;
 S->prev_valid=0;S->touch=0;return 0;
}
#endif
static u32 rec_object(void) {return U32(0x2003d2fc+0x84);}
static int shown_pattern(void) {return (item(U32(rec_object()+0x28),0)&255)==0;}
static u32 heldstep(void) {return FN(TM_HELD,F1)(0);}
void c_apclear(u32 track,u32 parameter) {
 if(track || parameter || !active() || !shown_pattern())return;
 u32 step=heldstep(),first=step<32?step*6:0,count=step<32?6:192;
 for(u32 i=0;i<count;i++) if(!cell(first+i,NONE))break;
 S->pending=S->held=S->last=NONE;S->prev_valid=0;S->touch=0;
}
/* Knob handler calls this wrapper, not playback. Keep all other targets untouched. */
void c_apmanual(u32 track,u32 parameter,u32 value) {
 FN(UI_PUT,F3)(track,parameter,value);
 if(track || parameter || value>16383 || !active())return;
 S->output=(u16)value;
#if AUDIT_BATCH
 /* Stock compares the next automation value against last-applied, not the
    current manual value. Do not invent a separate persistent suspension latch. */
 if(!transport(1))S->touch=0; /* In this variant the byte tracks Record ownership only. */
#elif FIX_RECORD_TOUCH
 /* Recording is not a manual playback suspension. In particular a held lock
    entered while already stopped must play on the FIRST subsequent start. */
 S->touch=!transport(1);
#else
 S->touch=1;
#endif
#if !AUDIT_BATCH
 S->held=NONE;
#endif
 if(!transport(1) || !shown_pattern())return;
 u32 h=heldstep();
 if(h<32) {
  if(cell(h*6,value))for(u32 n=1;n<6;n++)if(!cell(h*6+n,NONE))break;
  S->pending=NONE;S->prev_valid=0;
 } else if(transport(0) && !transport(2)) {
#if AUDIT_BATCH
  S->touch=1;
#endif
  S->pending=(u16)value;
 }
}
u32 c_apget(u32 track,u32 parameter) {
 if(!track && !parameter && active() && S->output!=NONE)return S->output;
 return FN(GET_TRAMP,F2)(track,parameter);
}
/* Stock 0x08049706 + 0x080497EC behavior, widened. Exposed for differential tests. */
void c_aprecord(u32 rate,u32 step,u32 pulse,u32 value) {
 if(!active() || rate>7 || step>31 || pulse>=((const u32 *)0x08068d9c)[rate] || (value>16383 && value!=NONE))return;
 if(S->prev_valid) {
  u32 n=S->prev_rate==0?2:S->prev_rate==1?1:
   (S->prev_rate==2 && (S->prev_micro==0 || S->prev_micro==3)?1:0);
  for(u32 j=1;j<=n;j++) {
   u32 v=NONE;
   if(S->previous!=NONE && value!=NONE)
    v=n==1?(S->previous+value)/2:
      (j==1?(S->previous*2+value)/3:(S->previous+value*2)/3);
   if(!cell((S->prev_step*6+S->prev_micro+j)&255,v))return;
  }
 }
#if !AUDIT_BATCH
 if(value==NONE){S->prev_valid=0;return;}
#endif
 u32 micro=FN(0x0804ab24,F2)(pulse,rate);
 if(micro>5 || !cell(step*6+micro,value))return;
 S->prev_valid=rate<3;S->previous=(u16)value;
 S->prev_step=step;S->prev_micro=micro;S->prev_rate=rate;S->prev_pattern=0;
}
/* Runs after stock recorder listener on the same time event, before note output. */
void c_aprec_listener(u32 object,u32 event,u32 changed,u32 unused) {
 FN(0x0804946c,F4)(object,event,changed,unused);
 if(!active())return;
 u32 base=object-8;
 if(U32(base)!=0x08067864 || U32(base+0xc)!=U32(0x200470d4+8))return;
#if !AUDIT_BATCH
 if(event!=U32(base+0x30))return;
#endif
 if(!transport(0) || !transport(1) || transport(2)) {
  S->pending=NONE;S->prev_valid=0;
#if AUDIT_BATCH
  S->touch=0;
#endif
  return;
 }
#if AUDIT_BATCH
 if(event!=U32(base+0x30) || !S->touch)return;
#endif
 u32 pos=U32(base+0xc),pattern=item(pos,0)&255;
 if(pattern){S->pending=NONE;S->prev_valid=0;return;}
 u32 rate=FN(0x08048cca,F1)(base),value=S->pending;
 S->pending=NONE;u32 start=U32(0xe0001004);
 c_aprecord(rate,item(pos,1)&255,item(pos,2),value);
 u32 elapsed=U32(0xe0001004)-start;if(elapsed>S->maxrecord)S->maxrecord=elapsed;
}
/* Match stock value/held/last logic using stock ROM rate and interpolation tables. */
u32 c_apvalue(u32 rate,u32 step,u32 pulse,u32 next) {
 if(rate>7 || step>31 || pulse>=((const u32 *)0x08068d9c)[rate])return NONE;
 u32 v=NONE,offset=step*6;
 if(rate<4) {
  u32 m=((const u8 *)0x0806651c)[rate*24+pulse];
  v=S->lane[(offset+m)&255];
 } else {
  u32 length=((const u32 *)0x08068d9c)[rate],m=pulse*6/length;
  u32 a=S->lane[offset+m],b=m<5?S->lane[offset+m+1]:next;
  if(a!=NONE) {
   if(b!=NONE) {
    const u8 *w=(const u8 *)0x0806645c+(rate-4)*48+pulse*2;
    v=(a*w[0]+b*w[1])>>3;
   } else if(!pulse || (pulse-1)*6/length!=m)v=a;
  }
 }
 if(v==NONE)v=S->held;
 S->held=NONE;
 if(rate<3) {
  u32 m=rate==0?pulse*3+2:rate==1?pulse*2+1:pulse==0?1:pulse==2?4:192;
  if(m<6)S->held=S->lane[offset+m];
  if(rate==0 && S->held==NONE)S->held=S->lane[offset+pulse*3+1];
 }
 return v;
}
void c_applay(u32 player,u32 pattern,u32 step,u32 pulse) {
 FN(0x08055324,F4)(player,pattern,step,pulse);
 if(player!=0x200470d4 || !active())return;
 if(pattern || step>31) {S->held=S->last=NONE;return;}
 u32 start=U32(0xe0001004);
 u32 rate=item(U32(player+0x10),1)&255;
 /* A manual move suspends this extra lane until transport reset in this prototype.
    Independent stock touch masks are never borrowed. Full touch lifecycle pending. */
#if !AUDIT_BATCH
 if(S->touch && !transport(1)){S->last=NONE;return;}
#endif
 u32 pos=U32(player+0xc),next=NONE;
 if(!(item(pos,0)&255)) {u32 ns=item(pos,1)&255;if(ns<32)next=S->lane[ns*6];}
 u32 v=c_apvalue(rate,step,pulse,next);
 if(v!=NONE && v!=S->last) {
  S->output=(u16)v;
  FN(SP_WRITE,F2)((v-8192)*192,PITCH_AMOUNT_Y);
  S->applies++;
 }
 S->last=(u16)v;
 u32 elapsed=U32(0xe0001004)-start;if(elapsed>S->maxplay)S->maxplay=elapsed;
}
void c_apreset(u32 player) {
 FN(RESET_TRAMP,F1)(player);
 if(player==0x200470d4 && active()) {S->held=S->last=S->pending=NONE;S->prev_valid=0;S->touch=0;}
}
#if AUDIT_BATCH
/* Extend the stock step-audition/microstep callback, rather than invent a
   separate pad gesture or a separate preview timer. */
u32 c_appreview(u32 object,u32 micro) {
 u32 result=FN(PREVIEW_TRAMP,F2)(object,micro);
 if(!active() || object!=U32(TM_STEP_PTR) || micro>=6 || !shown_pattern())return result;
 u32 step=item(U32(object+0x18),1)&255;
 if(step<32) {
  u32 v=S->lane[step*6+micro];
  if(v!=NONE){S->output=(u16)v;FN(SP_WRITE,F2)((v-8192)*192,PITCH_AMOUNT_Y);}
 }
 return result;
}
#endif
#if AUDIT_BATCH
/* Feedback only; holding a lock does not change sound or saved parameter blocks. */
u32 c_appedled(u32 controller,u32 frame) {
 u32 result=FN(PREV_LED,F2)(controller,frame);
 if(!active() || !U8(TM_SLOT) || U8(TM_SLOT+10)!=1 || FN(TM_VIEW,F0)()!=0 || !shown_pattern())return result;
 u32 step=heldstep();if(step>=32)return result;
 for(u32 n=0;n<6;n++)if(S->lane[step*6+n]!=NONE){((volatile u16 *)frame)[60]=0x55;break;}
 return result;
}
#endif
/* Keyed diagnostic entry: fixed targets only. */
u32 c_apcommand(u32 command,u32 buf) {
 u32 ptr=buf,status=0;
 if(command<52 || command>55) {
  return FN(PUT32,F2)(ptr,0xffffffff);
 }
 if(command!=53) {
  if(FN(GET32,F1)(buf)!=MAGIC)status=1;
  else if(command==52)status=c_aparm();
  else if(command==54)c_apdisable();
  else status=c_aprefill();
 }
 ptr=FN(PUT32,F2)(ptr,status);
 if(command==53) {
#if AUDIT_BATCH
  ptr=FN(PUT32,F2)(ptr,0xad000006);
#else
  ptr=FN(PUT32,F2)(ptr,0xad000004);
#endif
  int on=active();ptr=FN(PUT32,F2)(ptr,on);
#if AUDIT_BATCH
  u32 flag=U32(FLAG_ADDR);
  int have=(flag==MAGIC || flag==OWNED) && S->magic==MAGIC;
#else
  int have=on;
#endif
  for(u32 i=0;i<6;i++)ptr=FN(PUT32,F2)(ptr,have?((volatile u32 *)S)[i]:0);
  ptr=FN(PUT32,F2)(ptr,have?S->output:NONE);
  ptr=FN(PUT32,F2)(ptr,have?S->maxplay:0);
  ptr=FN(PUT32,F2)(ptr,have?S->maxrecord:0);
#if AUDIT_BATCH
  ptr=FN(PUT32,F2)(ptr,have?S->reason:0);
#endif
 }
 return ptr;
}
