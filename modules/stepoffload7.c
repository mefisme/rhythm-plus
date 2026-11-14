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
#define PAYLOAD 5008u
#define GR_LIVE ((u8 *)GR_STORE)
#define GR_FROZEN ((u8 *)(GR_STORE+224u))
#else
#define PAYLOAD 4784u
#endif
#define AMAGIC 0x31533341u
struct shadow {u32 m[32];struct job job;u8 data[100],readback[100];char path[32];u8 request[72],pad[32],bounce[512];};
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
    for(u32 i=0;i<224;i++)GR_LIVE[i]=0;
#endif
((void (*)(void *,void *))(A3_INIT|1))(AST,BANK);}
static void auto_guards(void){
    *(u32 *)0x14fc=AMAGIC;*(u32 *)0x3ae0=AMAGIC;*(u32 *)0x3fe0=AMAGIC;
}
static int auto_ok(void){return AST[0]==AMAGIC && *(u32 *)0x3dbc==AMAGIC && *(u32 *)0x14fc==AMAGIC &&
    *(u32 *)0x3ae0==AMAGIC && *(u32 *)0x3fe0==AMAGIC && *(u32 *)0x1500==0x37575043u && *(u32 *)0x16c4==0x37575043u;}
static u32 frozen_size(void){return ((u32 (*)(void))(A3_BANKFILESIZE|1))()
#ifdef GR_STORE
    +224u
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
    u32 base=((u32 (*)(void))(A3_BANKFILESIZE|1))(), first=offset<base?base-offset:0;
    if(first>n)first=n;
    u32 e=first?((u32 (*)(u32,void *,u32,const void *))(A3_BANKFILE|1))(offset,SNAP,first,S->data):0;
    if(!e && offset==0 && first>=4)SNAP[0]='R',SNAP[1]='A',SNAP[2]='0',SNAP[3]='4';
    for(u32 i=first;!e && i<n;i++)SNAP[i]=GR_FROZEN[offset+i-base];
#else
    u32 e=((u32 (*)(u32,void *,u32,const void *))(A3_BANKFILE|1))(offset,SNAP,n,S->data);
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
    if(!e)e=((u32 (*)(void))(A3_BANKSNAPSHOT|1))();
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
    ((void (*)(void))(A3_BANKRELEASE|1))();
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
        if(!result && version>=3)result=read_part(S->request,48,&checksum);
        u32 total=version>=3?176:128;
        for(u32 lane=0;!result && lane<24;lane++){
            u32 descriptor=version>=3?((uint16_t *)S->request)[lane]:0x80c0;
            u32 n=descriptor&0x7fff,kind=descriptor>>15;
            if(n>192 || (kind && n!=192) || n>size-total){result=0x103;break;}
            if(n)result=read_part(SNAP,n,&checksum);
            if(!result)result=((u32 (*)(u32,const void *,u32,u32))(A3_BANKIMPORT|1))(lane,SNAP,n,kind);
            total+=n;
        }
#ifdef GR_STORE
        if(!result && version==4) {
            if(size-total!=224)result=0x103;
            else result=read_part(GR_LIVE,224,&checksum);
            if(!result && !((u32 (*)(const void *))(GR_SETTINGS_VALID|1))(GR_LIVE))result=0x103;
            total+=224;
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
    u32 key=*(const u32 *)(meta+4),size=*(const u32 *)(meta+8);path(key);u32 result=load_file(meta[2],size,key);
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
    if(*(u32 *)item!=2 || offset || length!=0x29484 || !record_ok(buffer) || buffer!=*(volatile u32 *)0x2003c0cc)
        return ((fn7)(TR_BACKEND|1))(item,offset,buffer,length,actual,a,b);
    int enabled=ready();
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
    S->m[NSAVE]++;S->m[START]=now();S->m[ACTIVE]=1;S->m[MODE]=1;S->m[PROJECT]=((u32 *)item)[1];S->m[PACK]=((u32 *)item)[2]&255;
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
    if(!card && ((u32 (*)(void))(A3_BANKFILESIZE|1))()!=176){release();S->m[FAILS]++;S->m[RAW]=0x113;S->m[ACTIVE]=0;if(actual)*(u32 *)actual=0;return 5;}
    if(!card || def)S->path[0]=0;
    if(!result && card && !def){
        path(key);result=((u32 (*)(const char *))0x08022789)("1:/RP_AUTO");
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
    } else {R->key=def?0:key;S->m[RAW]=0;}
    S->m[ACTIVE]=0;S->m[ELAPSED]=now()-S->m[START];return result;
}
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
        if(!S->m[ACTIVE] && R->state==READY && S->m[PACK] && now()-AST[24]>=20){
            AST[24]=now();u32 lane=AST[25]%24;AST[25]=(lane+1)%24;
            ((u32 (*)(u32))(A3_BANKMAINTAIN|1))(lane);
        }
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
