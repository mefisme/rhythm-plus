/* Step Mutate offload. projectfile.c is concatenated before this source.
 * Native storage task owns every filesystem operation and private FIL.
 */
typedef uint64_t u64;
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
struct shadow {u32 m[32];struct job job;u8 data[100],readback[100];char path[32];u8 request[72],pad[32],bounce[512];};
struct runtime {u32 magic,record,key,state,generation,error;u8 block[100];u32 guard;};
_Static_assert(sizeof(struct shadow)==1024,"private SRAM budget");
_Static_assert(sizeof(struct runtime)==128,"private ITCM settings budget");
#define S ((struct shadow *)SLOT)
#define R ((volatile struct runtime *)0x1440u)
enum {UNSET,LOADING,READY,BROKEN,LOADED};
static u32 now(void){return *(volatile u32 *)0x20006f3c;}
static int record_ok(u32 p){return p>=0x20000000 && p<=0x20050000-0x29484;}
static u32 crc(const volatile u8 *b,u32 n){u32 c=0xffffffff;for(u32 i=0;i<n;i++){c^=b[i];for(u32 j=0;j<8;j++)c=(c>>1)^(0xedb88320u&-(c&1));}return ~c;}
static int valid(const volatile u8 *b){u32 n=0;for(u32 i=4;i<100;i++)n+=b[i];return b[0]=='S' && b[1]=='M' && b[3]==2 && b[2]==(u8)(n^0x5c);}
static const u8 defaults[12]={0x2e,0x0a,0,0x2a,0x2a,0x1e,2,2,7,0x0a,4,0};
static void default_block(volatile u8 *b){b[0]='S';b[1]='M';b[3]=2;u32 n=0;for(u32 i=4;i<100;i++){b[i]=defaults[(i-4)%12];n+=b[i];}b[2]=(u8)(n^0x5c);}
static int is_default(const u8 *b){for(u32 i=4;i<100;i++)if(b[i]!=defaults[(i-4)%12])return 0;return 1;}
static int claimed(const u8 *b){return b[0]=='S' && b[1]=='O';}
static int meta_valid(const u8 *b){return claimed(b) && b[2]==1 && b[3]<=1 &&
    *(const u32 *)(b+12)==0 && *(const u32 *)(b+16)==crc(b,16) &&
    (b[3]?*(const u32 *)(b+8)==100:!*(const u32 *)(b+4) && !*(const u32 *)(b+8));}
static int guards(void){return *(volatile u32 *)(FIL-4)==TAG && *(volatile u32 *)FIL_END==TAG && R->magic==TAG && R->guard==TAG;}
static int ready(void){
    if(!((u32 (*)(void))(C_RST|1))())return 0;
    S->m[MAGIC]=TAG;S->m[ITCM]=*(volatile u32 *)0xe000ef90;S->m[VTOR]=*(volatile u32 *)0xe000ed08;
    S->m[MPU]=*(volatile u32 *)0xe000ed94;S->m[CCR]=*(volatile u32 *)0xe000ed14;
    if(S->m[ITCM]!=0x73 || S->m[VTOR]<0x08010000 || S->m[VTOR]>=0x08080000 ||
       (S->m[MPU]&1) || (S->m[CCR]&0x10000))return 0;
    if(!S->m[30]){
        *(volatile u32 *)(FIL-4)=TAG;*(volatile u32 *)FIL_END=TAG;
        R->magic=TAG;R->record=0;R->state=UNSET;R->generation=0;R->error=0;R->guard=TAG;S->m[30]=1;
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
static u32 file_job(u32 write){
    struct job *j=&S->job;j->file=(void *)FIL;j->path=S->path;
    j->buffer=write?S->data:S->readback;j->size=100;j->write=write;
    if(c_pf_begin(j,&file_ops))return 0x101;
    for(u32 n=0;n<8;n++){
        S->m[OPER]++;u32 result=c_pf_step(j);
        if(!guards()){S->m[GUARD]++;return 0x102;}
        if(!write && j->phase==TRANSFER && !j->offset && *(volatile u32 *)(FIL+12)!=100)j->error=2;
        if(result==2)return 0;
        if(result==3)return j->raw_error?j->raw_error:0x100+j->error;
        if(result==1)return 0x105;
    }
    return 0x106;
}
static u32 restore(u32 record){
    const u8 *meta=(const u8 *)(record+TAIL+META),*old=(const u8 *)(record+TAIL+OLD_SM);
    /* A valid legacy block also permits recovery of edits made after downgrade. */
    if(valid(old)){S->path[0]=0;publish(record,crc(old,100),old);return 0;}
    if(!claimed(meta)){S->path[0]=0;default_block(S->readback);publish(record,0,S->readback);return 0;}
    if(!meta_valid(meta)){error(0x110);return 0x110;}
    if(!meta[3]){S->path[0]=0;default_block(S->readback);publish(record,0,S->readback);return 0;}
    u32 key=*(const u32 *)(meta+4);path(key);u32 result=file_job(0);
    if(result){if(result==4 || result==5)S->m[MISSING]++;error(result);return result;}
    S->m[READS]++;
    if(!valid(S->readback) || crc(S->readback,100)!=key){error(0x103);return 0x103;}
    publish(record,key,S->readback);S->m[VERIFIED]++;return 0;
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
    if(enabled){R->state=LOADING;S->m[31]=LOADING;S->m[ACTIVE]=1;S->m[MODE]=0;S->m[START]=now();S->m[NLOAD]++;}
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
    /* Only this small settings snapshot is frozen; normal automation continues. */
    u32 mask;__asm__ volatile("mrs %0,primask\n cpsid i":"=r"(mask)::"memory");
    for(u32 i=0;i<100;i++)S->data[i]=R->block[i];
    __asm__ volatile("msr primask,%0"::"r"(mask):"memory");
    u32 key=crc(S->data,100),result=0,def=is_default(S->data),card=((u32 *)item)[2]&255;
    if(!card || def)S->path[0]=0;
    if(card && !def){
        path(key);result=((u32 (*)(const char *))0x08022789)("1:/RP_AUTO");
        if(!result || result==8){
            result=file_job(1);if(!result)S->m[WRITES]++;
            if(!result || result==8){result=file_job(0);if(!result){S->m[READS]++;
                for(u32 i=0;i<100;i++)if(S->data[i]!=S->readback[i]){result=0x103;break;}
                if(!result)S->m[VERIFIED]++;
            }}
        }
    }
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
        meta[0]='S';meta[1]='O';meta[2]=1;meta[3]=(u8)!def;
        *(u32 *)(meta+4)=def?0:key;*(u32 *)(meta+8)=def?0:100;*(u32 *)(meta+16)=crc(meta,16);
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
        const u8 *meta=(const u8 *)(record+TAIL+META),*old=(const u8 *)(record+TAIL+OLD_SM);
        /* New/cleared and legacy projects need no additional disk operation. */
        if(valid(old)){S->path[0]=0;publish(record,crc(old,100),old);}
        else if(!claimed(meta)){S->path[0]=0;default_block(S->readback);publish(record,0,S->readback);}
        else if(!meta_valid(meta)){error(0x110);}
        else if(!meta[3]){S->path[0]=0;default_block(S->readback);publish(record,0,S->readback);}
        else if(R->state!=BROKEN && ((R->state!=READY && R->state!=LOADED) || R->record!=record || R->key!=*(const u32 *)(meta+4)))error(0x112);
    }
    u32 result=((fn4)(TR_APPLY|1))(a,b,c,d);
    if(enabled && guards() && R->state==LOADED){R->state=READY;S->m[31]=READY;}
    return result;
}
u32 c_sh_out(u32 a,u32 out,u32 c,u32 d){
    u32 result=((fn4)(PREV_OUT|1))(a,out,c,d);
    if(ready()){
        S->m[31]=R->state;
        if(!S->m[ACTIVE] && R->state==READY)for(u32 i=0;i<100;i++)S->data[i]=R->block[i];
        if((R->state==BROKEN || S->m[RAW]) && (now()&256))
            ((u32 *)out)[57]=*(u32 *)(0x20003974+4*0x55);
    }
    return result;
}
static u64 media(u32 write,u32 a,u32 offset,u32 buffer,u32 length){
    if(buffer<FIL || buffer>=FIL_END)return ((u64 (*)(u32,u32,u32,u32))((write?TR_WRITE:TR_READ)|1))(a,offset,buffer,length);
    if(buffer+length>FIL_END || S->m[MAGIC]!=TAG)return ((u64)length<<32)|1;
    struct dma_bridge bridge={a,(void *)(TR_READ|1),(void *)(TR_WRITE|1),S->bounce};
    return ((u64)length<<32)|c_pf_dma(&bridge,write,offset,(u8 *)buffer,length);
}
u64 c_sh_read(u32 a,u32 b,u32 c,u32 d){return media(0,a,b,c,d);}
u64 c_sh_write(u32 a,u32 b,u32 c,u32 d){return media(1,a,b,c,d);}
