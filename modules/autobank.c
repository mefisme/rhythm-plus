/* AD007: fixed-bank proof only. No SD, sample-memory or DSP-program writes. */
#include "autobank_config.h"
#include "automation_core.c"
#define U32(a) (*(volatile u32 *)(a))
#define U8(a) (*(volatile u8 *)(a))
#define FN(a,t) ((t)((a)|1u))
typedef u32 (*F1)(u32);
typedef u32 (*F2)(u32,u32);
typedef u32 (*F3)(u32,u32,u32);
#define MAGIC 0x41424b31u
#define BASE 0x2400u
#define WORDS 8192u
#define CHUNK 32u
#define PATTERN 0x5a7000u
struct BankState {
 u32 magic,fills,checks,clears,errors,first,expected,actual;
 u32 maxread,maxwrite,maxcodec,maxhold,maxwait;
 u32 filled[8],io[32],verify[32],events[24],decoded[24];
};
_Static_assert(sizeof(struct BankState)==532,"bank state layout");
#define S ((struct BankState *)0x300u)
static u32 running(void) {
 u32 p=FN(0x0803fc58,F2)(0x200122b0,0);return U32(p)&255;
}
static int ready(void) {
 return U32(PRIVATE_MAGIC_ADDR)==PRIVATE_MAGIC && U8(READY_ADDR)==READY_VALUE &&
  U8(WAIT_ADDR)>=200 && !U8(UPLOAD_ADDR);
}
static int usable(void) {
 u32 cr=U32(0xe000ef90);
 return (cr&1) && ((cr>>3)&15)>=5 && U32(0xe000ed08)>=0x4000 && !U32(0xe000ed94);
}
static int active(void) {
 return U32(PRIVATE_MAGIC_ADDR)==PRIVATE_MAGIC && U32(FLAG_ADDR)==MAGIC && usable() && S->magic==MAGIC;
}
static int excluded(u32 chunk) {return chunk>=224 && chunk<230;}
static u32 pattern(u32 address) {return PATTERN^address;}
static u32 readword(u32 address) {
 u32 v=FN(0x08031268,F2)(0,address)>>8;U32(0x20003684)=65535;return v;
}
static void writeword(u32 address,u32 value) {FN(0x080311da,F3)(0,value<<8,address);}
static u32 now(void) {return U32(0xe0001004);}
static void high(u32 *target,u32 value) {if(value>*target)*target=value;}
static u32 bad(u32 address,u32 expected,u32 actual) {
 S->errors++;S->first=address;S->expected=expected;S->actual=actual;return 8;
}
static void readblock(u32 address,u32 *out) {
 /* AD003's proved consecutive protocol, under the caller's DSP mutex. */
 FN(0x08046414,F1)(0);FN(0x08046534,F1)(0);
 FN(0x08031020,F1)(0);FN(0x08031048,F1)(0);
 FN(0x08046510,F3)(0x80,address>>8,address&255);
 for(u32 i=0;i<32;i++)out[i]=FN(0x08046510,F3)(0x40,0,0)>>8;
 FN(0x08046414,F1)(0);
 FN(0x0803107a,F1)(0);FN(0x08031032,F1)(0);U32(0x20003684)=65535;
}
static u32 chunkop(u32 op,u32 chunk) {
 u32 mask=1u<<(chunk&31),address=BASE+chunk*CHUNK;
 int owned=(S->filled[chunk>>5]&mask)!=0;
 if(op!=42 && !owned)return 10;
 /* Preflight the entire chunk before any write, never repair interference. */
 u32 readstart=now();
 for(u32 i=0;i<CHUNK;i++) {
  u32 v=readword(address+i),expected=pattern(address+i);
  if((owned || op!=42)?v!=expected:(v!=0 && v!=expected))return bad(address+i,expected,v);
 }
 high(&S->maxread,now()-readstart);
 if(op==43){S->checks++;return 0;}
 u32 start=now();
 for(u32 i=0;i<CHUNK;i++)writeword(address+i,op==44?0:pattern(address+i));
 high(&S->maxwrite,now()-start);
 if(op==42){S->filled[chunk>>5]|=mask;S->fills++;}
 else {S->filled[chunk>>5]&=~mask;S->clears++;}
 return 0;
}
static u32 benchmark(void) {
 if(!(S->filled[0]&1))return 10;
 for(u32 i=0;i<32;i++) {
  u32 v=readword(BASE+i);if(v!=pattern(BASE+i))return bad(BASE+i,pattern(BASE+i),v);
 }
 for(u32 i=0;i<24;i++)S->events[i]=i*6|((8193+i*17)<<14)|(1u<<28);
 u32 start=now();
 if(c_ap_pack(S->io,S->events,1,0))return 11;
 high(&S->maxcodec,now()-start);start=now();
 for(u32 i=0;i<32;i++)writeword(BASE+i,S->io[i]);
 high(&S->maxwrite,now()-start);start=now();
 readblock(BASE,S->verify);high(&S->maxread,now()-start);
 for(u32 i=0;i<32;i++)if(S->verify[i]!=S->io[i])return bad(BASE+i,S->io[i],S->verify[i]);
 /* Only restore after an exact fixture roundtrip; preserve mismatches as evidence. */
 for(u32 i=0;i<32;i++)writeword(BASE+i,pattern(BASE+i));
 return 0;
}
static u32 readbenchmark(void) {
 if(!(S->filled[0]&1))return 10;
 u32 start=now();readblock(BASE,S->verify);high(&S->maxread,now()-start);
 for(u32 i=0;i<32;i++)if(S->verify[i]!=pattern(BASE+i))return bad(BASE+i,pattern(BASE+i),S->verify[i]);
 return 0;
}
u32 c_apbkcommand(u32 command,u32 buf) {
 if(command<40 || command>47)return FN(PREV_COMMAND,F2)(command,buf);
 u32 status=0,chunk=0,ptr=buf;
 if(command!=40) {
  if(FN(GET32,F1)(buf)!=MAGIC)status=1;
  else if(!ready())status=3;
  else if(!usable())status=4;
  else if(command!=43 && command!=46 && running())status=2;
  else if(command==47)
   status=FN(AP_IMPORT,F3)(FN(GET32,F1)(buf+8),FN(GET32,F1)(buf+16),buf+24);
  else if(command==41) {
   /* Refuse accidental reinitialization that would erase test history. */
   if(active())status=12;
   else {
    for(u32 i=0;i<sizeof(*S)/4;i++)((u32 *)S)[i]=0;
    S->magic=MAGIC;U32(FLAG_ADDR)=MAGIC;
   }
  } else if(!active())status=7;
  else {
   if(command!=45 && command!=46) {
    chunk=FN(GET32,F1)(buf+8);
    if(chunk>=WORDS/CHUNK)status=5;
    else if(excluded(chunk))status=9;
   }
   if(!status) {
    u32 demcr=U32(0xe000edfc),ctrl=U32(0xe0001000),lsr=U32(0xe0001fb4);
    U32(0xe000edfc)=demcr|(1u<<24);U32(0xe0001fb0)=0xc5acce55;U32(0xe0001000)=ctrl|1;
    u32 lock=0x20003688,start=now();FN(0x08029c8c,F1)(lock);
    high(&S->maxwait,now()-start);start=now();
    /* Upload may start while waiting for the mutex. Recheck all guards. */
    if(!ready() || !usable())status=3;
    else if(command!=43 && command!=46 && running())status=2;
    else if(command==45)status=benchmark();
    else if(command==46)status=readbenchmark();
    else status=chunkop(command,chunk);
    U32(0x20003684)=65535;FN(0x08030eb8,F1)((u32)&lock);
    high(&S->maxhold,now()-start);
    if(!status && (command==45 || command==46)) {
     /* Decode outside the mutex. Playing command 46 reads only canaries and
        benchmarks the codec on a local fixture, not DSP event writes. */
     if(command==46) {
      for(u32 i=0;i<24;i++)S->events[i]=i*6|((8193+i*17)<<14)|(1u<<28);
      status=c_ap_pack(S->verify,S->events,1,0)?11:0;
     }
     u32 codecstart=now();
     if(!status && c_ap_unpack(S->decoded,S->verify,1,0))status=11;
     for(u32 i=0;!status && i<24;i++)if(S->decoded[i]!=S->events[i])status=11;
     high(&S->maxcodec,now()-codecstart);
    }
    U32(0xe0001000)=ctrl;if(lsr&2)U32(0xe0001fb0)=0;
    U32(0xe000edfc)=demcr;
   }
  }
 }
 ptr=FN(PUT32,F2)(ptr,status);
 if(command==40) {
  int have=active();ptr=FN(PUT32,F2)(ptr,0xad000007);ptr=FN(PUT32,F2)(ptr,have);
  for(u32 i=1;i<13;i++)ptr=FN(PUT32,F2)(ptr,have?((u32 *)S)[i]:0);
  u32 filled=0;if(have)for(u32 i=0;i<256;i++)filled+=(S->filled[i>>5]>>(i&31))&1;
  ptr=FN(PUT32,F2)(ptr,filled);ptr=FN(PUT32,F2)(ptr,sizeof(*S));
 }
 return ptr;
}
