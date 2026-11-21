/* Step Mutate offload. projectfile.c is concatenated before this source.
 * Native storage task owns every filesystem operation and private FIL.
 */
typedef uint64_t u64;
#if TASK_GUARD
#include "rp_task_guard.h"
#endif
typedef u32 (*fn4)(u32,u32,u32,u32);
typedef u32 (*fn7)(u32,u32,u32,u32,u32,u32,u32);
enum {MAGIC,ACTIVE,PENDING,MODE,STAGE,NSAVE,NLOAD,WRITES,READS,VERIFIED,MISSING,
      FAILS,SKIPPED,RAW,ELAPSED,START,ITCM,VTOR,MPU,CCR,GUARD,PROJECT,PACK,OPER,QBUSY};
#define TAG 0x31464f53u
#define FIL 0x400u
#define FIL_END (FIL+4136u)
#define TAIL 0x29110u
#define META 276u
#define OLD_SM 404u
#define BANK ((u8 *)0x1500u)
#define SNAP ((u8 *)0x3de0u)
#define AST ((u32 *)0x3d40u)
#ifdef GR_STORE
#ifndef GR_SETTINGS_BYTES
#define GR_SETTINGS_BYTES 224u
#endif
#define PAYLOAD (4784u+GR_SETTINGS_BYTES)
#define GR_LIVE ((u8 *)GR_STORE)
#ifdef GR_SINGLE_BUFFER
/* The native Content worker serializes full project backends. The snapshot
 * is built in this buffer only inside writebackend, consumed before return;
 * loading fills it only inside backend, before native project apply. No UI
 * frame mutates it. ACTIVE guards reject reentrant project backends. */
#define GR_FROZEN GR_LIVE
#else
#define GR_FROZEN ((u8 *)(GR_STORE+224u))
#endif
#else
#define PAYLOAD 4784u
#endif
#define AMAGIC 0x31533341u
#if NO_A3
/* No K1-K3 automation engine: a save holds no lanes; a load reads an old file's lanes and drops them. */
static u32 a3_file(u32 offset,u8 *out,u32 n,const u8 *settings){
    static const u32 head[7]={0x33304152,4608,3,8,32,6,0};
    for(u32 i=0;i<n;i++){u32 o=offset+i;out[i]=o<28?((const u8 *)head)[o]:o<128?settings[o-28]:0;}
    return 0;
}
#define BANKFILESIZE() 176u
#define BANKFILE(o,d,n,s) a3_file(o,d,n,s)
#define BANKSNAPSHOT() 0u
#define BANKRELEASE() ((void)0)
#define BANKIMPORT(l,d,n,k) 0u
#else
#define BANKFILESIZE() ((u32 (*)(void))(A3_BANKFILESIZE|1))()
#define BANKFILE(o,d,n,s) ((u32 (*)(u32,void *,u32,const void *))(A3_BANKFILE|1))(o,d,n,s)
#define BANKSNAPSHOT() ((u32 (*)(void))(A3_BANKSNAPSHOT|1))()
#define BANKRELEASE() ((void (*)(void))(A3_BANKRELEASE|1))()
#define BANKIMPORT(l,d,n,k) ((u32 (*)(u32,const void *,u32,u32))(A3_BANKIMPORT|1))(l,d,n,k)
#endif
#if PACK_FILES
/* path holds a whole pack path; the lane descriptors share it, read only after the file is open. */
struct shadow {u32 m[32];struct job job;u8 data[100],readback[100];char path[104];u8 pad[32],bounce[512];};
#define REQUEST ((u8 *)S->path)
#else
struct shadow {u32 m[32];struct job job;u8 data[100],readback[100];char path[32];u8 request[72],pad[32],bounce[512];};
#define REQUEST S->request
#endif
struct runtime {u32 magic,record,key,state,generation,error;u8 block[100];u32 guard;};
_Static_assert(sizeof(struct shadow)==1024,"private SRAM budget");
_Static_assert(sizeof(struct runtime)==128,"private ITCM settings budget");
#define S ((struct shadow *)SLOT)
#define R ((volatile struct runtime *)0x1440u)
enum {UNSET,LOADING,READY,BROKEN,LOADED};
static u32 now(void){return *(volatile u32 *)0x20006f3c;}
static int record_ok(u32 p){return p>=0x20000000 && p<=0x20050000-0x29484;}
static u32 crc_more(u32 c,const volatile u8 *b,u32 n){
    static const u32 tab[16]={0,0x1db71064,0x3b6e20c8,0x26d930ac,0x76dc4190,0x6b6b51f4,0x4db26158,0x5005713c,
        0xedb88320,0xf00f9344,0xd6d6a3e8,0xcb61b38c,0x9b64c2b0,0x86d3d2d4,0xa00ae278,0xbdbdf21c};
    for(u32 i=0;i<n;i++){c^=b[i];c=(c>>4)^tab[c&15];c=(c>>4)^tab[c&15];}return c;
}
static u32 crc(const volatile u8 *b,u32 n){return ~crc_more(0xffffffffu,b,n);}
static void auto_reset(void){
#ifdef GR_STORE
    for(u32 i=0;i<GR_SETTINGS_BYTES;i++)GR_LIVE[i]=0;
#endif
#if !NO_A3
((void (*)(void *,void *))(A3_INIT|1))(AST,BANK);
#endif
}
static void auto_guards(void){
    *(u32 *)0x14fc=AMAGIC;*(u32 *)0x3ae0=AMAGIC;*(u32 *)0x3fe0=AMAGIC;
}
#if NO_A3
static int auto_ok(void){return *(u32 *)0x14fc==AMAGIC && *(u32 *)0x3ae0==AMAGIC && *(u32 *)0x3fe0==AMAGIC;}
#else
static int auto_ok(void){return AST[0]==AMAGIC && *(u32 *)0x3dbc==AMAGIC && *(u32 *)0x14fc==AMAGIC &&
    *(u32 *)0x3ae0==AMAGIC && *(u32 *)0x3fe0==AMAGIC && *(u32 *)0x1500==0x37575043u && *(u32 *)0x16c4==0x37575043u;}
#endif
static u32 frozen_size(void){return BANKFILESIZE()
#ifdef GR_STORE
    +GR_SETTINGS_BYTES
#endif
; }
static int empty_bank(void){
#ifdef GR_STORE
    return 0; /* Settings are an explicit part of every card save. */
#else
    return frozen_size()==176;
#endif
}
static u32 frozen_chunk(u32 offset,u32 n){
#if TASK_GUARD
    u32 mask=rp_task_lock();
#else
    u32 mask;__asm__ volatile("mrs %0,primask\n cpsid i":"=r"(mask)::"memory");
#endif
#ifdef GR_STORE
    u32 base=BANKFILESIZE(), first=offset<base?base-offset:0;
    if(first>n)first=n;
    u32 e=first?BANKFILE(offset,SNAP,first,S->data):0;
    if(!e && offset==0 && first>=4)SNAP[0]='R',SNAP[1]='A',SNAP[2]='0',SNAP[3]='4';
    for(u32 i=first;!e && i<n;i++)SNAP[i]=GR_FROZEN[offset+i-base];
#else
    u32 e=BANKFILE(offset,SNAP,n,S->data);
#endif
#if TASK_GUARD
    rp_task_unlock(mask);
#else
    __asm__ volatile("msr primask,%0"::"r"(mask):"memory");
#endif
    return e;
}
static u32 bundle(void){
#if TASK_GUARD
    u32 mask=rp_task_lock();
#else
    u32 mask;__asm__ volatile("mrs %0,primask\n cpsid i":"=r"(mask)::"memory");
#endif
    for(u32 i=0;i<25;i++)((u32 *)S->data)[i]=((volatile u32 *)R->block)[i];
    u32 e=0;
#ifdef GR_STORE
    if(!((u32 (*)(void *,void *))(GR_SETTINGS_STORE|1))((void *)GR_STATE,GR_FROZEN))e=0x115;
#endif
    if(!e)e=BANKSNAPSHOT();
#if TASK_GUARD
    rp_task_unlock(mask);
#else
    __asm__ volatile("msr primask,%0"::"r"(mask):"memory");
#endif
    return e;
}
static void release(void){
#if TASK_GUARD
    u32 mask=rp_task_lock();
#else
    u32 mask;__asm__ volatile("mrs %0,primask\n cpsid i":"=r"(mask)::"memory");
#endif
    BANKRELEASE();
#if TASK_GUARD
    rp_task_unlock(mask);
#else
    __asm__ volatile("msr primask,%0"::"r"(mask):"memory");
#endif
}
static int valid(const volatile u8 *b){u32 n=0;for(u32 i=4;i<100;i++)n+=b[i];return b[0]=='S' && b[1]=='M' && b[3]==2 && b[2]==(u8)(n^0x5c);}
static const u8 defaults[12]={0x2e,0x0a,0,0x2a,0x2a,0x1e,2,2,7,0x0a,4,0};
static void default_block(volatile u8 *b){b[0]='S';b[1]='M';b[3]=2;u32 n=0;for(u32 i=4;i<100;i++){b[i]=defaults[(i-4)%12];n+=b[i];}b[2]=(u8)(n^0x5c);}
static int is_default(const u8 *b){for(u32 i=4;i<100;i++)if(b[i]!=defaults[(i-4)%12])return 0;return 1;}
static int claimed(const u8 *b){return b[0]=='S' && b[1]=='O';}
static int meta_valid(const u8 *b){u32 n=*(const u32 *)(b+8);return claimed(b) && (b[2]>=1 && b[2]<=
#ifdef GR_STORE
    4
#else
    3
#endif
    ) && b[3]<=1 &&
    *(const u32 *)(b+12)==0 && *(const u32 *)(b+16)==crc(b,16) &&
    (b[3]?(b[2]==1?n==100:b[2]==2?n==4736:n>=176 && n<=PAYLOAD):!*(const u32 *)(b+4) && !n);}
static int guards(void){return *(volatile u32 *)(FIL-4)==TAG && *(volatile u32 *)FIL_END==TAG && R->magic==TAG && R->guard==TAG && auto_ok();}
static int ready(void){
    if(!((u32 (*)(void))(C_RST|1))())return 0;
    S->m[MAGIC]=TAG;S->m[ITCM]=*(volatile u32 *)0xe000ef90;S->m[VTOR]=*(volatile u32 *)0xe000ed08;
    S->m[MPU]=*(volatile u32 *)0xe000ed94;S->m[CCR]=*(volatile u32 *)0xe000ed14;
    if(S->m[ITCM]!=0x73 || S->m[VTOR]<0x08010000 || S->m[VTOR]>=0x08080000 ||
       (S->m[MPU]&1) || (S->m[CCR]&0x10000))return 0;
    if(!S->m[30]){
        *(volatile u32 *)(FIL-4)=TAG;*(volatile u32 *)FIL_END=TAG;
        R->magic=TAG;R->record=0;R->state=UNSET;R->generation=0;R->error=0;R->guard=TAG;S->m[30]=1;
        auto_reset();auto_guards();
    }
    if(!guards()){S->m[GUARD]++;S->m[RAW]=0x102;return 0;}
    return !S->m[GUARD];
}
static void error(u32 code){S->m[FAILS]++;S->m[RAW]=code;R->state=BROKEN;R->error=code;S->m[31]=BROKEN;}
static void publish(u32 record,u32 key,const u8 *b){
    for(u32 i=0;i<100;i++)R->block[i]=b[i];
    R->record=record;R->key=key;R->error=0;R->generation++;
    u32 state=S->m[ACTIVE] && !S->m[MODE]?LOADED:READY;
    __asm__ volatile("dmb sy":::"memory");R->state=state;S->m[31]=state;S->m[RAW]=0;
}
static void path(u32 key){
    const char prefix[]="1:/RP_AUTO/",hex[]="0123456789ABCDEF";
    for(u32 i=0;i<11;i++)S->path[i]=prefix[i];
    for(u32 i=0;i<8;i++)S->path[11+i]=hex[(key>>(28-i*4))&15];
    S->path[19]='.';S->path[20]='R';S->path[21]='P';S->path[22]='S';S->path[23]=0;
}
#if PACK_FILES==1
/* A Plus file sits next to its project: <pack>/Sessions/RP_<slot>_<key>.rps. The stock reads a slot only from a
   leading "NN_", so it skips these. The key in the name means a save never overwrites the file in use. */
#define PLUS_NAME 18u
#define ANY_SLOT 64u
#define F_OPENDIR 0x08022529u
#define F_READDIR 0x080225b7u
#define F_CLOSEDIR 0x08022589u
#define F_UNLINK 0x080226edu
#define F_MKDIR 0x08022789u
static const char hexd[]="0123456789ABCDEF";
static int in_sram(u32 p){return p>=0x20000000 && p<0x20050000;}
/* S->path = <folder>/; returns its length, 0 if the folder is unknown. */
static u32 put_folder(const char *p){
    const char s[]="/Sessions/";u32 n=0;
    if(!p)return 0;
    while(n<64 && p[n]){S->path[n]=p[n];n++;}
    if(n<4 || n>=64)return 0;
    for(u32 i=0;s[i];i++)S->path[n++]=s[i];
    return n;
}
static u32 pack_sessions(u32 pack){
    u32 store=*(volatile u32 *)0x20006e20;
    if(!pack || pack>31 || !in_sram(store) || !((u32 (*)(u32,u32))0x0802e25b)(store,pack))return 0;
    return put_folder(((const char *(*)(u32,u32))0x0802e44d)(store,pack));
}
static u32 store_sessions(u32 store){
    if(!in_sram(store))return 0;
    const char *p=((const char *(*)(u32,u32))0x0802e7ef)(store,0);
    if(!p)return 0;
    u32 n=0;while(n<72 && p[n]){S->path[n]=p[n];n++;}
    if(n<4 || n>=72)return 0;
    S->path[n++]='/';return n;
}
static u32 put_name(u32 n,u32 slot,u32 key){
    char *d=S->path+n;
    d[0]='R';d[1]='P';d[2]='_';d[3]=(char)('0'+slot/10);d[4]=(char)('0'+slot%10);d[5]='_';
    for(u32 i=0;i<8;i++)d[6+i]=hexd[(key>>(28-i*4))&15];
    d[14]='.';d[15]='r';d[16]='p';d[17]='s';d[18]=0;
    return n+PLUS_NAME;
}
static u32 plus_path(u32 pack,u32 slot,u32 key){u32 n=slot<ANY_SLOT?pack_sessions(pack):0;return n?put_name(n,slot,key):0;}
static int hex_digit(char c){return (c>='0' && c<='9') || (c>='A' && c<='F') || (c>='a' && c<='f');}
static int lower(char c){return c>='A' && c<='Z'?c+32:c;}
/* A name is ours when it is exactly RP_<2 digits>_<8 hex>.rps. */
static int plus_file(const char *n,u32 slot,u32 key,int any_key){
    for(u32 i=0;i<PLUS_NAME;i++)if(!n[i])return 0;
    if(n[PLUS_NAME] || lower(n[0])!='r' || lower(n[1])!='p' || n[2]!='_' || n[5]!='_' || n[14]!='.' ||
       lower(n[15])!='r' || lower(n[16])!='p' || lower(n[17])!='s')return 0;
    if(n[3]<'0' || n[3]>'9' || n[4]<'0' || n[4]>'9')return 0;
    if(slot!=ANY_SLOT && (u32)((n[3]-'0')*10+n[4]-'0')!=slot)return 0;
    for(u32 i=0;i<8;i++){
        if(!hex_digit(n[6+i]))return 0;
        if(!any_key && lower(n[6+i])!=lower(hexd[(key>>(28-i*4))&15]))return 0;
    }
    return 1;
}
/* Finds the first Plus file in the folder S->path[0..n) that matches; leaves its whole path in S->path.
   DIR (52 B) and FILINFO (long name at +0x16, 128 B) use SNAP, which no save step needs at that time. */
static u32 find_plus(u32 n,u32 slot,u32 key,int any_key,const char *skip){
    u8 *dir=SNAP,*info=SNAP+64;const char *name=(const char *)(info+0x16);
    S->path[n-1]=0;
    u32 found=0,result=((u32 (*)(void *,const char *))F_OPENDIR)(dir,S->path);
    S->path[n-1]='/';
    if(result)return 0;
    while(!found && !((u32 (*)(void *,void *))F_READDIR)(dir,info) && name[0]){
        if(info[8]&0x10 || !plus_file(name,slot,key,any_key))continue;
        u32 same=skip!=0;
        for(u32 i=0;same && i<=PLUS_NAME;i++)same=name[i]==skip[i];
        if(same)continue;
        for(u32 i=0;i<=PLUS_NAME;i++)S->path[n+i]=name[i];
        found=1;
    }
    ((u32 (*)(void *))F_CLOSEDIR)(dir);
    return found;
}
/* Deletes a slot's Plus files (every slot's for ANY_SLOT) in the folder S->path[0..n), except skip. */
static void sweep(u32 n,u32 slot,const char *skip){
    for(u32 round=0;round<16 && find_plus(n,slot,0,1,skip);round++)
        if(((u32 (*)(const char *))F_UNLINK)(S->path))return;
}
#elif PACK_FILES>=2
/* A Plus file sits next to its project: <pack>/Sessions/RP_<slot>_<project name>_<key>.rps (A0234: no name part). The
   stock reads a slot only from a leading "NN_", so it skips these. The key in the name means a save never overwrites the
   file in use. */
#define PATH_MAX 104u
#define ANY_SLOT 64u
#define F_OPENDIR 0x08022529u
#define F_READDIR 0x080225b7u
#define F_CLOSEDIR 0x08022589u
#define F_UNLINK 0x080226edu
#define F_MKDIR 0x08022789u
#define F_RENAME 0x080228c3u
#define SHIFT_HELD() ((*(volatile u32 *)(0x200487c8u+0xa0u)>>27)&1u)
static const char hexd[]="0123456789ABCDEF";
static int in_sram(u32 p){return p>=0x20000000 && p<0x20050000;}
static int digit(char c){return c>='0' && c<='9';}
static int hexval(char c){return digit(c)?c-'0':c>='A' && c<='F'?c-'A'+10:-1;}
static void put_key(char *d,u32 key){for(u32 i=0;i<8;i++)d[i]=hexd[(key>>(28-i*4))&15];}
/* S->path = <folder>/; returns its length, 0 if the folder is unknown. */
static u32 put_folder(const char *p){
    const char s[]="/Sessions/";u32 n=0;
    if(!p)return 0;
    while(n<64 && p[n]){S->path[n]=p[n];n++;}
    if(n<4 || n>=64)return 0;
    for(u32 i=0;s[i];i++)S->path[n++]=s[i];
    return n;
}
static u32 pack_sessions(u32 pack){
    u32 store=*(volatile u32 *)0x20006e20;
    if(!pack || pack>31 || !in_sram(store) || !((u32 (*)(u32,u32))0x0802e25b)(store,pack))return 0;
    return put_folder(((const char *(*)(u32,u32))0x0802e44d)(store,pack));
}
static u32 store_sessions(u32 store){
    if(!in_sram(store))return 0;
    const char *p=((const char *(*)(u32,u32))0x0802e7ef)(store,0);
    if(!p)return 0;
    u32 n=0;while(n<72 && p[n]){S->path[n]=p[n];n++;}
    if(n<4 || n>=72)return 0;
    S->path[n++]='/';return n;
}
/* The project file's name without "NN_" and ".ncs", from the loaded pack (its store's byte 0 = the pack). */
static const char *project_name(u32 pack,u32 slot,u32 *len){
    u32 cs=*(volatile u32 *)0x20006e24;
    *len=0;
    if(!in_sram(cs) || *(volatile u8 *)cs!=pack)return 0;
    const char *p=((const char *(*)(u32,u32,u32))0x0802e83d)(cs,0,slot),*b=p;
    if(!p)return 0;
    for(u32 i=0;i<160 && p[i];i++)if(p[i]=='/')b=p+i+1;
    while(*b && *b!='_')b++;
    if(!*b++)return 0;
    u32 n=0;while(n<64 && b[n])n++;
    *len=n>4?n-4:0;return b;
}
/* Appends RP_<slot>_[<name>_]<key>.rps at S->path+n; returns the whole length. The name part is cut to fit. */
static u32 put_name(u32 n,u32 slot,u32 key,const char *name,u32 len){
    char *d=S->path;
    if(len>PATH_MAX-20-n)len=PATH_MAX-20-n;
    d[n++]='R';d[n++]='P';d[n++]='_';d[n++]=(char)('0'+slot/10);d[n++]=(char)('0'+slot%10);d[n++]='_';
    if(len){for(u32 i=0;i<len;i++)d[n++]=name[i];d[n++]='_';}
    put_key(d+n,key);n+=8;
    d[n++]='.';d[n++]='r';d[n++]='p';d[n++]='s';d[n]=0;
    return n;
}
/* Builds the Plus file path; *folder = the length of <folder>/. 0 if the pack folder is unknown. */
static u32 plus_path(u32 pack,u32 slot,u32 key,u32 *folder){
    u32 n=slot<ANY_SLOT?pack_sessions(pack):0,len;
    *folder=n;
    if(!n)return 0;
    const char *name=project_name(pack,slot,&len);
    return put_name(n,slot,key,name,len);
}
/* A Plus file name: RP_<2 digits>_[<any>_]<8 hex>.rps, as the unit writes it. */
static int plus_parse(const char *n,u32 *slot,u32 *key){
    u32 L=0;while(L<128 && n[L])L++;
    if(L<18 || L>=128 || n[0]!='R' || n[1]!='P' || n[2]!='_' || !digit(n[3]) || !digit(n[4]) || n[5]!='_' ||
       n[L-4]!='.' || n[L-3]!='r' || n[L-2]!='p' || n[L-1]!='s' || (L>18 && (L<20 || n[L-13]!='_')))return 0;
    u32 k=0;
    for(u32 i=0;i<8;i++){int v=hexval(n[L-12+i]);if(v<0)return 0;k=k<<4|(u32)v;}
    *slot=(u32)(n[3]-'0')*10+(u32)(n[4]-'0');*key=k;return 1;
}
/* Finds the first matching Plus file in the folder S->path[0..n) and leaves its whole path in S->path.
   DIR (52 B) and FILINFO (long name at +0x16, 128 B) use SNAP, which no save step needs at that time. */
static u32 find_plus(u32 n,u32 slot,u32 key,int any_key,const char *skip){
    u8 *dir=SNAP,*info=SNAP+64;const char *name=(const char *)(info+0x16);
    S->path[n-1]=0;
    u32 found=0,result=((u32 (*)(void *,const char *))F_OPENDIR)(dir,S->path);
    S->path[n-1]='/';
    if(result)return 0;
    while(!found && !((u32 (*)(void *,void *))F_READDIR)(dir,info) && name[0]){
        u32 s,k,L=0;
        if(info[8]&0x10 || !plus_parse(name,&s,&k) || (slot!=ANY_SLOT && s!=slot) || (!any_key && k!=key))continue;
        while(name[L])L++;
        u32 same=skip!=0;
        for(u32 i=0;same && i<=L;i++)same=name[i]==skip[i];
        if(same || n+L+1>PATH_MAX)continue;
        for(u32 i=0;i<=L;i++)S->path[n+i]=name[i];
        found=1;
    }
    ((u32 (*)(void *))F_CLOSEDIR)(dir);
    return found;
}
/* Deletes a slot's Plus files (ANY_SLOT: every slot's) in the folder S->path[0..n), except skip; or moves them to
   RP_AUTO/<key>.RPS, where a load looks when the file next to its project is missing. */
static void drop(u32 n,u32 slot,const char *skip,u32 move){
    char *d=(char *)S->pad;
    for(u32 round=0;round<80 && find_plus(n,slot,0,1,skip);round++){
        u32 s,k,r=8;
        if(move){
            plus_parse(S->path+n,&s,&k);
            for(u32 i=0;i<11;i++)d[i]="1:/RP_AUTO/"[i];
            put_key(d+11,k);
            d[19]='.';d[20]='R';d[21]='P';d[22]='S';d[23]=0;
            r=((u32 (*)(const char *))F_MKDIR)("1:/RP_AUTO");
            if(r && r!=8)return;
            r=((u32 (*)(const char *,const char *))F_RENAME)(S->path,d);
        }
        if(r==8)r=((u32 (*)(const char *))F_UNLINK)(S->path);
        if(r)return;
    }
}
#endif
static u32 no_lock(void){return 0;}static void no_unlock(void){}
static const struct ops file_ops={no_lock,no_unlock,(void *)0x08021d91,(void *)0x08021f73,
    (void *)0x080220fd,(void *)0x080222bd,(void *)0x08022347};
/* Called only by a native Content backend, not Main/interrupt context. */
/* Compare in small private SRAM chunks, retaining the complete frozen snapshot.
 * This executes on Content, under its existing filesystem serialization. */
static u32 verify_file(u32 size){
    if(S->job.opened)return 0x105;
    u32 result=file_ops.open((void *)FIL,S->path,1);
    if(result)return result;
    if(*(volatile u32 *)(FIL+12)!=size)result=0x103;
    for(u32 off=0;!result && off<size;){
        u32 n=size-off;if(n>100)n=100;u32 done=0;
        result=file_ops.read((void *)FIL,S->readback,n,&done);
        if(!result && done!=n)result=0x104;
        if(!result && frozen_chunk(off,n))result=0x103;
        if(!result)for(u32 i=0;i<n;i++)if(S->readback[i]!=SNAP[i]){result=0x103;break;}
        off+=n;
        if(!guards()){S->m[GUARD]++;result=0x102;}
    }
    u32 close=file_ops.close((void *)FIL);
    if(close){S->job.opened=1;S->job.phase=FAILED;return close;}
    return result;
}
static u32 close_file(u32 result){
    u32 e=file_ops.close((void *)FIL);
    if(e){S->job.opened=1;S->job.phase=FAILED;return e;}return result;
}
static u32 write_frozen(u32 size){
    if(S->job.opened)return 0x105;
    u32 result=file_ops.open((void *)FIL,S->path,7);if(result)return result;
    for(u32 off=0;!result && off<size;){
        u32 n=size-off;if(n>512)n=512;
        result=frozen_chunk(off,n);u32 done=0;
        if(!result)result=file_ops.write((void *)FIL,SNAP,n,&done);
        if(!result && done!=n)result=0x104;
        if(!guards())result=0x102;off+=n;
    }
    if(!result)result=file_ops.sync((void *)FIL);
    return close_file(result);
}
static u32 read_part(u8 *out,u32 n,u32 *checksum){
    u32 done=0,result=file_ops.read((void *)FIL,out,n,&done);
    if(!result && done!=n)result=0x104;
    if(!result)*checksum=crc_more(*checksum,out,n);
    if(!guards())result=0x102;return result;
}
static u32 load_file(u32 version,u32 size,u32 key){
    if(S->job.opened)return 0x105;
    u32 result=file_ops.open((void *)FIL,S->path,1);if(result)return result;
    u32 checksum=0xffffffffu;
    if(*(volatile u32 *)(FIL+12)!=size)result=0x103;
    if(!result && version==1){
        result=read_part(S->readback,100,&checksum);
    }else if(!result){
        result=read_part(SNAP,128,&checksum);
        const u32 expected[7]={0x32304152,4608,3,8,32,6,0};
        if(!result)for(u32 i=0;i<7;i++){
            u32 v=i==0 && version>=3?(version==4?0x34304152:0x33304152):expected[i];
            if(((u32 *)SNAP)[i]!=v){result=0x103;break;}
        }
        if(!result)for(u32 i=0;i<100;i++)S->readback[i]=SNAP[28+i];
        if(!result && version>=3)result=read_part(REQUEST,48,&checksum);
        u32 total=version>=3?176:128;
        for(u32 lane=0;!result && lane<24;lane++){
            u32 descriptor=version>=3?((uint16_t *)REQUEST)[lane]:0x80c0;
            u32 n=descriptor&0x7fff,kind=descriptor>>15;
            if(n>192 || (kind && n!=192) || n>size-total){result=0x103;break;}
            if(n)result=read_part(SNAP,n,&checksum);
            if(!result)result=BANKIMPORT(lane,SNAP,n,kind);
            total+=n;
        }
#ifdef GR_STORE
        if(!result && version==4) {
#if GR_SETTINGS_BYTES==224
            if(size-total!=224)result=0x103;
            else result=read_part(GR_LIVE,224,&checksum);
            if(!result && !((u32 (*)(const void *))(GR_SETTINGS_VALID|1))(GR_LIVE))result=0x103;
            total+=224;
#else
            /* Older saves hold 224 settings bytes; the GS version inside says which. */
            u32 settings_size=size-total;
            if(settings_size!=224 && settings_size!=GR_SETTINGS_BYTES)result=0x103;
            else result=read_part(GR_LIVE,settings_size,&checksum);
            if(!result && !((u32 (*)(const void *))(GR_SETTINGS_VALID|1))(GR_LIVE))result=0x103;
            total+=settings_size;
#endif
        }
#endif
        if(!result && total!=size)result=0x103;
    }
    if(!result && (~checksum!=key || !valid(S->readback)))result=0x103;
    return close_file(result);
}
static u32 restore(u32 record){
    const u8 *meta=(const u8 *)(record+TAIL+META),*old=(const u8 *)(record+TAIL+OLD_SM);
    auto_reset();
    /* SO v2 automation must be restored even if a downgraded build edited SM. */
    if(valid(old) && !(claimed(meta) && meta[2]>=2)){S->path[0]=0;publish(record,crc(old,100),old);return 0;}
    if(!claimed(meta)){S->path[0]=0;default_block(S->readback);publish(record,0,S->readback);return 0;}
    if(!meta_valid(meta)){error(0x110);return 0x110;}
    if(!meta[3]){S->path[0]=0;default_block(S->readback);publish(record,0,valid(old)?old:S->readback);return 0;}
    u32 key=*(const u32 *)(meta+4),size=*(const u32 *)(meta+8),result=4;
#if PACK_FILES>=2
    /* Next to the project, then RP_AUTO, then any file with this key in the same folder. */
    u32 folder;
    if(plus_path(S->m[PACK],S->m[PROJECT],key,&folder))result=load_file(meta[2],size,key);
    if(result==4 || result==5){path(key);result=load_file(meta[2],size,key);}
    if(result==4 || result==5){
        u32 n=pack_sessions(S->m[PACK]);
        if(n && find_plus(n,ANY_SLOT,key,0,0))result=load_file(meta[2],size,key);
    }
#elif PACK_FILES
    /* Next to the project, then RP_AUTO, then any slot's file with this key in the same folder. */
    if(plus_path(S->m[PACK],S->m[PROJECT],key))result=load_file(meta[2],size,key);
    if(result==4 || result==5){path(key);result=load_file(meta[2],size,key);}
    if(result==4 || result==5){
        u32 n=pack_sessions(S->m[PACK]);
        if(n && find_plus(n,ANY_SLOT,key,0,0))result=load_file(meta[2],size,key);
    }
#else
    path(key);result=load_file(meta[2],size,key);
#endif
    if(result){if(result==4 || result==5)S->m[MISSING]++;error(result);return result;}
    S->m[READS]++;
    publish(record,key,valid(old)?old:S->readback);S->m[VERIFIED]++;return 0;
}
#ifdef GR_STORE
u32 c_sh_grsettings(void) {
    return R->record==*(volatile u32 *)0x2003c0cc && (R->state==LOADED || R->state==READY) &&
        ((u32 (*)(const void *))(GR_SETTINGS_VALID|1))(GR_LIVE)?(u32)GR_LIVE:0;
}
#endif
#if PLUS_USB
/* Plus files over USB SysEx (commands 0x20-0x27 of rdiag's frame). c_sh_pxmidi runs in the MIDI task: it hands the request
   to Content through the stock synchronous read (op 6) with a private item, and c_sh_backend runs it there, under Content's
   filesystem serialization, writing the reply over the request. Only Plus file names are accepted. */
#define PX_KIND 0x58555052u
#if PX_PROJHEAD
#define PX_VERSION 3u                                            /* 3: 0x28 adds the project's first 48 bytes: header, colour, name */
#define PROJ_HEAD 48u
#elif PX_COLOUR
#define PX_VERSION 2u                                            /* 2: 0x28 adds the project's colour */
#define PROJ_COLOUR 12u
#else
#define PX_VERSION 1u
#endif
#define PX_NMAX 64u
#define PX_NAME 64u
#define F_LSEEK 0x080223d9u
#define CONTENT_READ 0x08046055u
#define PX_DATA 256u                                         /* SNAP: [0, 256) data, +256 a second path, +400 a name */
#define PX_PATH2 ((char *)SNAP+256)
#define PX_TMP ((char *)SNAP+400)
enum {PX_BAD=0x100,PX_NOPACK=0x101,PX_BUSY=0x102,PX_SHORT=0x103,PX_END=0x110};
typedef u32 (*px_f1)(u32);typedef u32 (*px_f2)(u32,u32);typedef u32 (*px_f3)(u32,u32,u32);typedef u32 (*px_f4)(u32,u32,u32,u32);
static u32 px_g32(const u8 *p){u32 v=0;for(u32 i=0;i<8;i++)v=v<<4|(p[i]&15);return v;}
static u8 *px_p32(u8 *d,u32 v){for(u32 i=0;i<8;i++){*d++=(u8)(v>>28);v<<=4;}return d;}
/* RP_AUTO: <8 hex>.RPS; a pack: plus_parse's form. Printable ASCII, no path separators. */
static int px_name_ok(u32 dir,const char *n,u32 L){
    if(!L || L>PX_NAME)return 0;
    for(u32 i=0;i<L;i++)if(n[i]<' ' || n[i]>'~' || n[i]=='/' || n[i]=='\\' || n[i]==':')return 0;
    if(dir){u32 s,k;return plus_parse(n,&s,&k);}
    if(L!=12 || n[8]!='.' || (n[9]|32)!='r' || (n[10]|32)!='p' || (n[11]|32)!='s')return 0;
    for(u32 i=0;i<8;i++)if(hexval(n[i])<0)return 0;
    return 1;
}
/* S->path = the folder with its slash; returns its length. 0 = no such pack. */
static u32 px_folder(u32 dir){
    if(!dir){const char a[]="1:/RP_AUTO/";for(u32 i=0;i<sizeof a;i++)S->path[i]=a[i];return sizeof a-1;}
    return dir<=31?pack_sessions(dir):0;
}
/* S->path = the folder and the name; *e = the refusal. Returns the folder's length. */
static u32 px_path(u32 dir,const u8 *name,u32 L,u32 *e){
    char *tmp=PX_TMP;
    *e=PX_BAD;
    if(L>PX_NAME)return 0;
    for(u32 i=0;i<L;i++)tmp[i]=(char)name[i];tmp[L]=0;
    if(!px_name_ok(dir,tmp,L))return 0;
    *e=PX_NOPACK;
    u32 n=px_folder(dir);
    if(!n)return 0;
    *e=PX_BAD;
    if(n+L+1>PATH_MAX)return 0;
    for(u32 i=0;i<=L;i++)S->path[n+i]=tmp[i];
    *e=0;return n;
}
static u32 px_mkdir(u32 n){
    S->path[n-1]=0;u32 r=((px_f1)(F_MKDIR|1))((u32)S->path);S->path[n-1]='/';
    return r==8?0:r;
}
static u32 px_close(u32 r){u32 c=file_ops.close((void *)FIL);return r?r:c;}
static u32 px_open(u32 mode){return file_ops.open((void *)FIL,S->path,mode);}
static u32 px_fsize(void){return *(volatile u32 *)(FIL+12);}
/* n bytes at off into d; *size = the file's size */
static u32 px_read(u32 off,u8 *d,u32 n,u32 *done,u32 *size){
    u32 r=px_open(1);*done=0;
    if(r)return r;
    *size=px_fsize();
    r=((px_f2)F_LSEEK)(FIL,off);
    if(!r)r=file_ops.read((void *)FIL,d,n,done);
    return px_close(r);
}
/* n bytes at off; off 0 makes the file anew (fresh: only if it does not exist), else off must be the file's end */
static u32 px_write(u32 off,const u8 *d,u32 n,u32 fresh){
    u32 r=px_open(off?2:fresh?7:0x0a),done=0;
    if(r)return r;
    if(px_fsize()!=off)r=PX_SHORT;
    if(!r && off)r=((px_f2)F_LSEEK)(FIL,off);
    if(!r)r=file_ops.write((void *)FIL,d,n,&done);
    if(!r && done!=n)r=PX_SHORT;
    if(!r)r=file_ops.sync((void *)FIL);
    return px_close(r);
}
static u32 px_crc(u32 *size,u32 *c){
    u32 r=px_open(1),done=0,sum=0xffffffffu;
    if(r)return r;
    *size=px_fsize();
    for(u32 off=0;!r && off<*size;off+=done){
        r=file_ops.read((void *)FIL,SNAP,PX_DATA,&done);
        if(!r && !done)r=PX_SHORT;
        if(!r)sum=crc_more(sum,SNAP,done);
    }
    *c=~sum;return px_close(r);
}
static u32 px_list(u32 dir,u32 index,u8 **o){
    u32 n=px_folder(dir);
    if(!n)return PX_NOPACK;
    u8 *d=SNAP,*info=SNAP+64;const char *name=(const char *)(info+0x16);
    S->path[n-1]=0;
    u32 r=((px_f2)F_OPENDIR)((u32)d,(u32)S->path);
    if(r)return r;
    r=PX_END;
    while(!((px_f2)F_READDIR)((u32)d,(u32)info) && name[0]){
        u32 L=0;while(L<=PX_NAME && name[L])L++;
        if(info[8]&0x10 || !px_name_ok(dir,name,L) || index--)continue;
        *o=px_p32(*o,*(u32 *)info);*(*o)++=(u8)L;for(u32 i=0;i<L;i++)*(*o)++=(u8)name[i];
        r=0;break;
    }
    ((px_f1)F_CLOSEDIR)((u32)d);
    return r;
}
/* the whole file to another name or pack; the target must not exist; a failed copy removes it */
static u32 px_copy(u32 dir,const u8 *name,u32 L,u32 dir2,const u8 *name2,u32 L2){
    u32 e,size=0,r=0,done=0,n;
    if(!px_path(dir,name,L,&e))return e;
    if(!(n=px_path(dir2,name2,L2,&e)))return e;
    if((e=px_mkdir(n)))return e;
    for(u32 off=0;!r && (!off || off<size);off+=done){
        px_path(dir,name,L,&e);r=px_read(off,SNAP,PX_DATA,&done,&size);
        px_path(dir2,name2,L2,&e);
        if(!r)r=px_write(off,SNAP,done,1);
        if(!r && !done)break;
        if(!r && !guards())r=PX_BUSY;
    }
    if(r && r!=8)((px_f1)F_UNLINK)((u32)S->path);
    return r;
}
#if FILE_TOOLS
static int px_lc(char c){return c>='A' && c<='Z'?c+32:c;}
/* S->path = the pack's project file for slot (NN_*.ncs); 4 = none */
static u32 px_project(u32 dir,u32 slot){
    u32 n=dir?px_folder(dir):0,r,found=4;
    if(!n)return PX_NOPACK;
    u8 *d=SNAP,*info=SNAP+64;const char *name=(const char *)(info+0x16);
    S->path[n-1]=0;r=((px_f2)F_OPENDIR)((u32)d,(u32)S->path);S->path[n-1]='/';
    if(r)return r;
    while(found && !((px_f2)F_READDIR)((u32)d,(u32)info) && name[0]){
        u32 L=0;while(L<128 && name[L])L++;
        if(info[8]&0x10 || L<8 || n+L+1>PATH_MAX || !digit(name[0]) || !digit(name[1]) || name[2]!='_' ||
           (u32)(name[0]-'0')*10+(u32)(name[1]-'0')!=slot || name[L-4]!='.' || px_lc(name[L-3])!='n' ||
           px_lc(name[L-2])!='c' || px_lc(name[L-1])!='s')continue;
        for(u32 i=0;i<=L;i++)S->path[n+i]=name[i];
        found=0;
    }
    ((px_f1)F_CLOSEDIR)((u32)d);
    return found;
}
/* The project's size and its 20 Plus bytes at TAIL+META (m: 'S' 'O' version claimed, key, size, -, crc) */
static u32 px_meta(u32 dir,u32 slot,u32 *size,u8 *m){
    u32 r=px_project(dir,slot),done=0;
    if(!r)r=px_read(TAIL+META,m,20,&done,size);
    if(!r && done!=20)r=PX_SHORT;
    return r;
}
static u32 px_claimed(const u8 *m){return m[0]=='S' && m[1]=='O' && m[3] && *(const u32 *)(m+4)?*(const u32 *)(m+4):0;}
/* A project copy's Plus file. Phase 0: A's file to B's pack as RP_<B>_<key>.rps (*copied 0: A has none).
   Phase 1, after the project: B's other Plus files deleted, as after a save. */
static u32 px_slotcopy(u32 pa,u32 sa,u32 pb,u32 sb,u32 phase,u32 *copied){
    u8 *m=SNAP+256;u32 size,r,n,key;
    char *src=PX_PATH2,*dst=PX_TMP;
    *copied=0;
    if(sa>=ANY_SLOT || sb>=ANY_SLOT || !pb)return PX_BAD;
    if(phase){
        r=px_meta(pb,sb,&size,m);
        if(r)return r;
        key=px_claimed(m);
        if(!(n=px_folder(pb)))return PX_NOPACK;
        if(!key){drop(n,sb,0,0);return 0;}
        u32 e=put_name(n,sb,key,0,0);
        for(u32 i=n;i<=e;i++)dst[i-n]=S->path[i];
        drop(n,sb,dst,0);
        return 0;
    }
    if(!pa)return 0;                                           /* the internal pack keeps its settings in the project */
    r=px_meta(pa,sa,&size,m);
    if(r)return r;
    if(!(key=px_claimed(m)))return 0;
    if(!(n=px_folder(pa)))return PX_NOPACK;
    if(!find_plus(n,sa,key,0,0)){
        path(key);
        if(px_open(1)){if(!(n=px_folder(pa)) || !find_plus(n,ANY_SLOT,key,0,0))return 4;}
        else file_ops.close((void *)FIL);
    }
    for(u32 i=0;i<PATH_MAX;i++)src[i]=S->path[i];
    if(!(n=px_folder(pb)))return PX_NOPACK;
    put_name(n,sb,key,0,0);
    for(u32 i=0;i<PATH_MAX;i++)dst[i]=S->path[i];
    if((r=px_mkdir(n)))return r;
    u32 done=0;r=0;size=0;
    for(u32 off=0;!r && (!off || off<size);off+=done){
        for(u32 i=0;i<PATH_MAX;i++)S->path[i]=src[i];
        r=px_read(off,SNAP,PX_DATA,&done,&size);
        for(u32 i=0;i<PATH_MAX;i++)S->path[i]=dst[i];
        if(!r)r=px_write(off,SNAP,done,0);
        if(!r && !done)break;
        if(!r && !guards())r=PX_BUSY;
    }
    if(r){((px_f1)F_UNLINK)((u32)S->path);return r;}
    *copied=1;return 0;
}
/* S->path = the idx-th Plus file of the folder S->path[0..n); 0 = none */
static u32 nth_plus(u32 n,u32 idx){
    u8 *d=SNAP,*info=SNAP+64;const char *name=(const char *)(info+0x16);
    S->path[n-1]=0;u32 r=((px_f2)F_OPENDIR)((u32)d,(u32)S->path),found=0;S->path[n-1]='/';
    if(r)return 0;
    while(!found && !((px_f2)F_READDIR)((u32)d,(u32)info) && name[0]){
        u32 sl,k,L=0;while(L<128 && name[L])L++;
        if(info[8]&0x10 || !plus_parse(name,&sl,&k) || n+L+1>PATH_MAX || idx--)continue;
        for(u32 i=0;i<=L;i++)S->path[n+i]=name[i];
        found=1;
    }
    ((px_f1)F_CLOSEDIR)((u32)d);
    return found;
}
/* Every Plus file of pack a to pack b, same names. */
static void plus_follow(u32 a,u32 b){
    char *src=PX_PATH2,*dst=PX_TMP;
    for(u32 idx=0;idx<256;idx++){
        u32 n=pack_sessions(a),m,L,size=0,done=0,r=0;
        if(!n || !nth_plus(n,idx))return;
        for(u32 i=0;i<PATH_MAX;i++)src[i]=S->path[i];
        L=0;while(src[n+L])L++;
        if(!(m=pack_sessions(b)) || m+L+1>PATH_MAX)return;
        for(u32 i=0;i<=L;i++)S->path[m+i]=src[n+i];
        for(u32 i=0;i<PATH_MAX;i++)dst[i]=S->path[i];
        if(px_mkdir(m))return;
        for(u32 off=0;!r && (!off || off<size);off+=done){
            for(u32 i=0;i<PATH_MAX;i++)S->path[i]=src[i];
            r=px_read(off,SNAP,PX_DATA,&done,&size);
            for(u32 i=0;i<PATH_MAX;i++)S->path[i]=dst[i];
            if(!r)r=px_write(off,SNAP,done,0);
            if(!r && !done)break;
        }
        if(r){((px_f1)F_UNLINK)((u32)S->path);return;}
        if(!guards())return;
    }
}
/* The stock pack copy (Duplicate + an empty pack slot) takes only the files it knows: the Plus files follow it. */
u32 c_sh_packcopy(u32 *src,u32 *dst,u32 p3,u32 cb,u32 p5){
    u32 r=((u32 (*)(u32 *,u32 *,u32,u32,u32))0x0804143fu)(src,dst,p3,cb,p5);
    if(!r && src[0]==1 && (src[2]&255) && (dst[2]&255) && ready() && !S->job.opened && !S->m[ACTIVE] && guards())
        plus_follow(src[2]&255,dst[2]&255);
    return r;
}
#endif
/* request: [6] dir (0 = RP_AUTO, 1-31 = a pack), [7] name length, the name, then the command's fields */
static u32 px_run(u8 *q,u32 len){
    u32 cmd=q[4]&0x3f,dir=q[6],L=q[7],e=PX_BAD,n,size=0,done=0;
    u8 *a=q+8+L,*st=q+6,*o=q+14;
    if(8+L+20>len)goto out;
    e=PX_BUSY;
    if(!ready() || S->job.opened || S->m[ACTIVE] || !guards())goto out;
    if(cmd==0x20){                                               /* info: the version, the folder */
        e=0;o=px_p32(o,PX_VERSION);
        n=px_folder(dir);*o++=(u8)n;for(u32 i=0;i<n;i++)*o++=(u8)S->path[i];
        goto out;
    }
    if(cmd==0x21){e=px_list(dir,px_g32(a),&o);goto out;}       /* list: the index-th Plus file: size, name */
#if FILE_TOOLS
    if(cmd==0x28){                                               /* project [a] slot: size, its 20 Plus bytes */
        u8 *m=SNAP+256;
        e=px_meta(dir,a[0],&size,m);
#if PX_PROJHEAD
        if(!e)e=px_read(0,m+20,PROJ_HEAD,&done,&size);
        if(!e && done!=PROJ_HEAD)e=PX_SHORT;
        if(!e){o=px_p32(o,size);for(u32 i=0;i<20+PROJ_HEAD;i++){*o++=m[i]>>4;*o++=m[i]&15;}}
#elif PX_COLOUR
        if(!e)e=px_read(PROJ_COLOUR,m+20,1,&done,&size);
        if(!e && done!=1)e=PX_SHORT;
        if(!e){o=px_p32(o,size);for(u32 i=0;i<21;i++){*o++=m[i]>>4;*o++=m[i]&15;}}
#else
        if(!e){o=px_p32(o,size);for(u32 i=0;i<20;i++){*o++=m[i]>>4;*o++=m[i]&15;}}
#endif
        goto out;
    }
    if(cmd==0x29){                                               /* a project copy's Plus file: [a] slot A, pack B, slot B, phase */
        e=px_slotcopy(dir,a[0],a[1],a[2],a[3],&done);
        if(!e)o=px_p32(o,done);
        goto out;
    }
#endif
    if(!(n=px_path(dir,q+8,L,&e)))goto out;
    if(cmd==0x22){                                               /* read: size, count, the bytes as nibbles */
        u32 c=a[8]>PX_NMAX?PX_NMAX:a[8];
        e=px_read(px_g32(a),SNAP,c,&done,&size);
        if(!e){o=px_p32(o,size);o=px_p32(o,done);for(u32 i=0;i<done;i++){*o++=SNAP[i]>>4;*o++=SNAP[i]&15;}}
    }else if(cmd==0x23){                                         /* write: off, count, the bytes as nibbles */
        u32 c=a[8];
        if(c>PX_NMAX || 8+L+9+2*c>len)e=PX_BAD;
        else{
            for(u32 i=0;i<c;i++)SNAP[i]=(u8)(a[9+2*i]<<4|(a[10+2*i]&15));
            u32 off=px_g32(a);
            e=off?0:px_mkdir(n);
            if(!e)e=px_write(off,SNAP,c,0);
        }
    }else if(cmd==0x24)e=((px_f1)F_UNLINK)((u32)S->path);       /* delete */
    else if(cmd==0x25){e=px_crc(&size,&done);if(!e){o=px_p32(o,size);o=px_p32(o,done);}}   /* size and CRC-32 */
    else if(cmd==0x26){                                          /* rename in the same folder: [a] length, the new name */
        char *to=PX_PATH2;u32 L2=a[0];
        for(u32 i=0;i<PATH_MAX;i++)to[i]=S->path[i];
        if(8+L+1+L2>len || !px_path(dir,a+1,L2,&e))goto out;
        e=((px_f2)F_RENAME)((u32)to,(u32)S->path);
    }else if(cmd==0x27){                                         /* copy: [a] the target dir, [a+1] length, its name */
        u32 L2=a[1];
        e=8+L+2+L2>len?PX_BAD:px_copy(dir,q+8,L,a[0],a+2,L2);
    }
out:
    px_p32(st,e);
    return (u32)(o-q);
}
/* rdiag's c_rdcmd, commands 0x20-0x2F (buf[4] already has 0x40); returns the reply's end */
u8 *c_sh_pxmidi(u8 *buf,u32 len,u32 port){
    (void)port;
    u32 item[3]={PX_KIND,0,0},done=0,r;
    if(S->m[MAGIC]!=TAG || !S->m[30] || S->m[GUARD] || len<24)r=PX_BUSY;
    else if((r=((u32 (*)(u32 *,u32,u32,u32,u32,u32,u32 *))CONTENT_READ)(item,0,(u32)buf,len,0,0,&done)))r|=0x200;
    else if(done<14 || done>=len)r=PX_SHORT;
    else return buf+done;
    return px_p32(buf+6,r);
}
#endif
u32 c_sh_autobank(void){
    return S->m[MAGIC]==TAG && S->m[PACK] && R->state==READY &&
        R->record==*(volatile u32 *)0x2003c0cc && !S->m[GUARD] && guards()?(u32)BANK:0;
}
u32 c_sh_block(void){
    u32 record=*(volatile u32 *)0x2003c0cc;
    if(!record_ok(record))return 0;
    if(!ready())return claimed((const u8 *)(record+TAIL+META))?0:record+TAIL+OLD_SM;
    if(R->state==UNSET){
        const u8 *old=(const u8 *)(record+TAIL+OLD_SM);
        if(valid(old))publish(record,crc(old,100),old);
        else if(!claimed((const u8 *)(record+TAIL+META))){default_block(S->readback);publish(record,0,S->readback);}
    }
    return R->state==READY && R->record==record?(u32)R->block:0;
}
u32 c_sh_backend(u32 item,u32 offset,u32 buffer,u32 length,u32 actual,u32 a,u32 b){
#if PLUS_USB
    if(*(u32 *)item==PX_KIND){
        u32 n=buffer>=0x20000000u && buffer<0x20050000u && length>=24 && length<=512?px_run((u8 *)buffer,length):0;
        if(actual)*(u32 *)actual=n;
        return 0;
    }
#endif
    if(*(u32 *)item!=2 || offset || length!=0x29484 || !record_ok(buffer) || buffer!=*(volatile u32 *)0x2003c0cc)
        return ((fn7)(TR_BACKEND|1))(item,offset,buffer,length,actual,a,b);
    int enabled=ready();
#ifdef GR_SINGLE_BUFFER
    if(enabled && S->m[ACTIVE])return 5;
#endif
    if(enabled){R->state=LOADING;S->m[31]=LOADING;S->m[ACTIVE]=1;S->m[MODE]=0;S->m[START]=now();S->m[NLOAD]++;
        S->m[PACK]=((u32 *)item)[2]&255;S->m[PROJECT]=((u32 *)item)[1];}
    u32 result=((fn7)(TR_BACKEND|1))(item,offset,buffer,length,actual,a,b);
    if(enabled){
        if(!result && actual && *(u32 *)actual==length)restore(buffer);
        else error(result?result:0x104);
        S->m[ACTIVE]=0;S->m[ELAPSED]=now()-S->m[START];
    }
    return result;
}
u32 c_sh_writebackend(u32 item,u32 offset,u32 buffer,u32 length,u32 actual,u32 a,u32 b){
    if(*(u32 *)item!=2 || offset || length!=0x29484 || !record_ok(buffer) || buffer!=*(volatile u32 *)0x2003c0cc)
        return ((fn7)(TR_WRITEBACKEND|1))(item,offset,buffer,length,actual,a,b);
    if(!ready()){
        if(claimed((const u8 *)(buffer+TAIL+META))){if(actual)*(u32 *)actual=0;return 5;}
        return ((fn7)(TR_WRITEBACKEND|1))(item,offset,buffer,length,actual,a,b);
    }
#ifdef GR_SINGLE_BUFFER
    if(S->m[ACTIVE]){if(actual)*(u32 *)actual=0;return 5;}
#endif
    S->m[NSAVE]++;S->m[START]=now();S->m[ACTIVE]=1;S->m[MODE]=1;S->m[PROJECT]=((u32 *)item)[1];S->m[PACK]=((u32 *)item)[2]&255;
#if PACK_FILES>=2
    /* Shift + Save on a project whose Plus file is missing: save it with the default settings. */
    if(R->state==BROKEN && (((u32 *)item)[2]&255) && SHIFT_HELD()){
        auto_reset();default_block(S->readback);publish(buffer,0,S->readback);
    }
#endif
    if(R->state!=READY || R->record!=buffer || !valid(R->block)){
        error(0x111);S->m[ACTIVE]=0;if(actual)*(u32 *)actual=0;return 5;
    }
    u32 result=bundle();
    if(result){S->m[FAILS]++;S->m[RAW]=0x114;S->m[ACTIVE]=0;if(actual)*(u32 *)actual=0;return 5;}
    u32 size=frozen_size(),sum=0xffffffffu;
    for(u32 off=0;off<size;){u32 n=size-off;if(n>512)n=512;
        if(frozen_chunk(off,n)){result=0x114;break;}sum=crc_more(sum,SNAP,n);off+=n;}
    u32 key=~sum,def=is_default(S->data) && empty_bank(),card=((u32 *)item)[2]&255;
    /* Internal projects cannot acquire independent automation or drop it silently. */
    if(!card && BANKFILESIZE()!=176){release();S->m[FAILS]++;S->m[RAW]=0x113;S->m[ACTIVE]=0;if(actual)*(u32 *)actual=0;return 5;}
    if(!card || def)S->path[0]=0;
#if PACK_FILES>=2
    u32 slot=((u32 *)item)[1],plus=0,folder=0;char keep[PATH_MAX];
#elif PACK_FILES
    u32 slot=((u32 *)item)[1],plus=0;char keep[PLUS_NAME+1];
#endif
    if(!result && card && !def){
#if PACK_FILES>=2
        plus=plus_path(card,slot,key,&folder);
        if(plus){
            S->path[folder-1]=0;result=((u32 (*)(const char *))F_MKDIR)(S->path);S->path[folder-1]='/';
            if(result && result!=8)plus=0;
        }
        if(plus)for(u32 i=folder;i<=plus;i++)keep[i-folder]=S->path[i];
        else{path(key);result=((u32 (*)(const char *))0x08022789)("1:/RP_AUTO");}
#elif PACK_FILES
        plus=plus_path(card,slot,key);
        if(plus){
            S->path[plus-PLUS_NAME-1]=0;result=((u32 (*)(const char *))F_MKDIR)(S->path);S->path[plus-PLUS_NAME-1]='/';
            if(result && result!=8)plus=0;
        }
        if(plus)for(u32 i=0;i<=PLUS_NAME;i++)keep[i]=S->path[plus-PLUS_NAME+i];
        else{path(key);result=((u32 (*)(const char *))0x08022789)("1:/RP_AUTO");}
#else
        path(key);result=((u32 (*)(const char *))0x08022789)("1:/RP_AUTO");
#endif
        if(!result || result==8){
            result=write_frozen(size);if(!result)S->m[WRITES]++;
            if(!result || result==8){result=verify_file(size);if(!result){S->m[READS]++;
                if(!result)S->m[VERIFIED]++;
            }}
        }
    }
    release();
    if(result){S->m[FAILS]++;S->m[RAW]=result;S->m[ACTIVE]=0;S->m[ELAPSED]=now()-S->m[START];if(actual)*(u32 *)actual=0;return 5;}
    /* Companion is durable/read-back verified before native data is submitted.
     * Live settings stay in owned ITCM. Only the extension's 120 bytes change. */
    u8 *meta=(u8 *)(buffer+TAIL+META),*old=(u8 *)(buffer+TAIL+OLD_SM);
    /* Clear only a recognized legacy SM block. Other bytes may already belong
     * to a future feature, including before its first converted save. */
    u32 clear_old=card && valid(old);
    for(u32 i=0;i<20;i++){S->pad[i]=meta[i];meta[i]=0;}
    for(u32 i=0;i<100;i++){
        S->readback[i]=old[i];
        if(!card)old[i]=S->data[i];else if(clear_old)old[i]=0;
    }
    if(card){
        meta[0]='S';meta[1]='O';meta[2]=
#ifdef GR_STORE
        4
#else
        3
#endif
        ;meta[3]=(u8)!def;
        *(u32 *)(meta+4)=def?0:key;*(u32 *)(meta+8)=def?0:size;*(u32 *)(meta+16)=crc(meta,16);
    }
    result=((fn7)(TR_WRITEBACKEND|1))(item,offset,buffer,length,actual,a,b);
    if(result || !actual || *(u32 *)actual!=length){
        for(u32 i=0;i<20;i++)meta[i]=S->pad[i];
        for(u32 i=0;i<100;i++)old[i]=S->readback[i];
        /* Keep the current settings usable; the old saved project is not claimed
         * recovered if native writing itself was partial. */
        S->m[FAILS]++;S->m[RAW]=result?result:0x104;
        if(!result)result=3;
    } else {
        R->key=def?0:key;S->m[RAW]=0;
#if PACK_FILES>=2
        /* The saved project no longer needs this slot's older Plus files. */
        if(plus)drop(folder,slot,keep,0);
#elif PACK_FILES
        /* The saved project no longer needs this slot's older Plus files. */
        if(plus)sweep(plus-PLUS_NAME,slot,keep);
        else if(card && def && slot<ANY_SLOT){u32 n=pack_sessions(card);if(n)sweep(n,slot,0);}
#endif
    }
    S->m[ACTIVE]=0;S->m[ELAPSED]=now()-S->m[START];return result;
}
#if PACK_FILES>=2
/* The stock pack delete removes only the files it knows, then the folders: move ours out first. */
u32 c_sh_packdelete(u32 store,u32 fs){
    if(ready() && !S->m[ACTIVE]){u32 n=store_sessions(store);if(n)drop(n,ANY_SLOT,0,1);}
    return ((u32 (*)(u32,u32))0x0802e939)(store,fs);
}
/* After the stock deletes a project (type 0 = Sessions), its Plus files move to RP_AUTO. 0 = deleted. */
u32 c_sh_itemdelete(u32 store,u32 fs,u32 type,u32 slot){
    u32 result=((u32 (*)(u32,u32,u32,u32))0x0802e8e5)(store,fs,type,slot);
    if(!result && !(type&255) && (slot&255)<ANY_SLOT && ready() && !S->m[ACTIVE]){u32 n=store_sessions(store);if(n)drop(n,slot&255,0,1);}
    return result;
}
#elif PACK_FILES
/* The stock pack delete removes only the files it knows, then the folders: remove ours first. */
u32 c_sh_packdelete(u32 store,u32 fs){
    if(ready() && !S->m[ACTIVE]){u32 n=store_sessions(store);if(n)sweep(n,ANY_SLOT,0);}
    return ((u32 (*)(u32,u32))0x0802e939)(store,fs);
}
/* After the stock deletes a project (type 0 = Sessions), its Plus files go too. 0 = deleted. */
u32 c_sh_itemdelete(u32 store,u32 fs,u32 type,u32 slot){
    u32 result=((u32 (*)(u32,u32,u32,u32))0x0802e8e5)(store,fs,type,slot);
    if(!result && !(type&255) && (slot&255)<ANY_SLOT && ready() && !S->m[ACTIVE]){u32 n=store_sessions(store);if(n)sweep(n,slot&255,0);}
    return result;
}
#endif
u32 c_sh_apply(u32 a,u32 b,u32 c,u32 d){
    u32 record=*(u32 *)(a+0x14);
    int enabled=ready();
    if(enabled && record_ok(record)){
        /* Session's native pack store is the source used by stock Save. */
        u32 packstore=*(u32 *)(a+0x44);
        if(packstore>=0x20000000 && packstore<0x20050000)
            S->m[PACK]=*(u8 *)((u32 (*)(u32,u32))0x0803fc59)(packstore,0);
        const u8 *meta=(const u8 *)(record+TAIL+META),*old=(const u8 *)(record+TAIL+OLD_SM);
        /* New/cleared and legacy projects need no additional disk operation. */
        if(valid(old) && !(claimed(meta) && meta[2]>=2)){auto_reset();S->path[0]=0;publish(record,crc(old,100),old);}
        else if(!claimed(meta)){auto_reset();S->path[0]=0;default_block(S->readback);publish(record,0,S->readback);}
        else if(!meta_valid(meta)){error(0x110);}
        else if(!meta[3]){auto_reset();S->path[0]=0;default_block(S->readback);publish(record,0,valid(old)?old:S->readback);}
        else if(R->state!=BROKEN && ((R->state!=READY && R->state!=LOADED) || R->record!=record || R->key!=*(const u32 *)(meta+4)))error(0x112);
    }
    if(enabled && R->state==READY){R->state=LOADED;S->m[31]=LOADED;}
    u32 result=((fn4)(TR_APPLY|1))(a,b,c,d);
    if(enabled && guards() && R->state==LOADED){R->state=READY;S->m[31]=READY;}
    return result;
}
u32 c_sh_out(u32 a,u32 out,u32 c,u32 d){
    u32 result=((fn4)(PREV_OUT|1))(a,out,c,d);
    if(ready()){
        S->m[31]=R->state;
        if(!S->m[ACTIVE] && R->state==READY)for(u32 i=0;i<100;i++)S->data[i]=R->block[i];
        /* Encode one lane outside the publication lock, at most every 20ms.
         * No SD access; generation checks discard stale prepared encodings. */
#if !NO_A3
        if(!S->m[ACTIVE] && R->state==READY && S->m[PACK] && now()-AST[24]>=20){
            AST[24]=now();u32 lane=AST[25]%24;AST[25]=(lane+1)%24;
            ((u32 (*)(u32))(A3_BANKMAINTAIN|1))(lane);
        }
#endif
        if((R->state==BROKEN || S->m[RAW]) && (now()&256))
            ((u32 *)out)[57]=*(u32 *)(0x20003974+4*0x55);
    }
    return result;
}
static u64 media(u32 write,u32 a,u32 offset,u32 buffer,u32 length){
    int owned=(buffer>=FIL && buffer<FIL_END) || (buffer>=0x3de0 && buffer<0x3fe0);
    if(!owned)return ((u64 (*)(u32,u32,u32,u32))((write?TR_WRITE:TR_READ)|1))(a,offset,buffer,length);
    u32 end=buffer<FIL_END?FIL_END:0x3fe0;
    if(length>end-buffer || S->m[MAGIC]!=TAG)return ((u64)length<<32)|1;
    struct dma_bridge bridge={a,(void *)(TR_READ|1),(void *)(TR_WRITE|1),S->bounce};
    return ((u64)length<<32)|c_pf_dma(&bridge,write,offset,(u8 *)buffer,length);
}
u64 c_sh_read(u32 a,u32 b,u32 c,u32 d){return media(0,a,b,c,d);}
u64 c_sh_write(u32 a,u32 b,u32 c,u32 d){return media(1,a,b,c,d);}
