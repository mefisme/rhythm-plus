/* Controlled SD mirror test. Native Step Mutate remains authoritative/embedded.
 * projectfile.c is concatenated ahead of this file by the builder.
 */
typedef uint64_t u64;
typedef u32 (*fn4)(u32,u32,u32,u32);
typedef u32 (*fn6)(u32,u32,u32,u32,u32,u32);
enum {MAGIC,ACTIVE,PENDING,MODE,STAGE,NSAVE,NLOAD,WRITES,READS,VERIFIED,MISSING,
      FAILS,SKIPPED,RAW,ELAPSED,START,ITCM,VTOR,MPU,CCR,GUARD,PROJECT,PACK,OPER,QBUSY};
#define TAG 0x31534852u
#define PRIVATE_KIND 0x52505348u
#define FIL 0x400u
#define FIL_END (FIL+4136u)
struct shadow {
    u32 m[32]; struct job job;
    u8 data[100],readback[100];char path[32];u8 request[72],pad[32],bounce[512];
};
_Static_assert(sizeof(struct shadow)==1024,"shadow RAM budget");
#define S ((struct shadow *)SLOT)
static u32 now(void){return *(volatile u32 *)0x20006f3c;}
static u32 no_lock(void){return 0;}
static void no_unlock(void){}
static const struct ops file_ops={no_lock,no_unlock,
    (void *)0x08021d91,(void *)0x08021f73,(void *)0x080220fd,
    (void *)0x080222bd,(void *)0x08022347};
static int ready(void) {
    if(!((u32 (*)(void))(C_RST|1))())return 0;
    S->m[MAGIC]=TAG;
    S->m[ITCM]=*(volatile u32 *)0xe000ef90;
    S->m[VTOR]=*(volatile u32 *)0xe000ed08;
    S->m[MPU]=*(volatile u32 *)0xe000ed94;
    S->m[CCR]=*(volatile u32 *)0xe000ed14;
    /* Configuration previously tested by the unit's AD001/AD002 probes. No
     * register reconfiguration or execution from ITCM in this build. */
    return S->m[ITCM]==0x73 && S->m[VTOR]>=0x08010000 && S->m[VTOR]<0x08080000 &&
           !(S->m[MPU]&1) && !(S->m[CCR]&0x10000);
}
static u32 crc(const u8 *p,u32 n) {
    u32 c=0xffffffff;
    for(u32 i=0;i<n;i++){c^=p[i];for(u32 j=0;j<8;j++)c=(c>>1)^(0xedb88320u&-(c&1));}
    return ~c;
}
static int valid(const u8 *b) {
    u32 sum=0;for(u32 i=4;i<100;i++)sum+=b[i];
    return b[0]=='S' && b[1]=='M' && b[3]==2 && b[2]==(u8)(sum^0x5c);
}
static int guards(void) {
    return *(volatile u32 *)(FIL-4)==TAG && *(volatile u32 *)FIL_END==TAG;
}
static void finish(u32 fail,u32 raw) {
    S->m[ELAPSED]=now()-S->m[START];S->m[RAW]=raw;
    if(fail)S->m[FAILS]++;
    S->m[ACTIVE]=0;
}
static int begin_job(u32 write) {
    struct job *j=&S->job;
    j->file=(void *)FIL;j->path=S->path;j->buffer=write?S->data:S->readback;
    j->size=100;j->write=write;
    if(c_pf_begin(j,&file_ops)){finish(1,0x101);return 0;}
    return 1;
}
static void start(u32 buffer,u32 mode,u32 slot,u32 pack) {
    if(S->m[ACTIVE] || S->job.opened || S->m[GUARD]){S->m[SKIPPED]++;return;}
    if(buffer<0x20000000 || buffer>0x20050000-0x29484)return;
    const u8 *b=(const u8 *)(buffer+0x29110+404);
    if(!valid(b)){S->m[SKIPPED]++;return;}
    for(u32 i=0;i<100;i++)S->data[i]=b[i];
    const char prefix[]="1:/RP_AUTO/";
    for(u32 i=0;i<sizeof(prefix)-1;i++)S->path[i]=prefix[i];
    u32 key=crc(S->data,100);
    const char hex[]="0123456789ABCDEF";
    for(u32 i=0;i<8;i++)S->path[11+i]=hex[(key>>(28-i*4))&15];
    S->path[19]='.';S->path[20]='R';S->path[21]='P';S->path[22]='S';S->path[23]=0;
    S->m[MODE]=mode;S->m[STAGE]=0;S->m[PROJECT]=slot;S->m[PACK]=pack&255;
    S->m[START]=now();S->m[RAW]=0;S->m[ACTIVE]=mode?1:2;
    if(!S->m[30]) {
        *(volatile u32 *)(FIL-4)=TAG;*(volatile u32 *)FIL_END=TAG;S->m[30]=1;
    } else if(!guards()) {S->m[GUARD]++;finish(1,0x102);return;}
    if(!mode){S->m[STAGE]=2;begin_job(0);}
}
void c_sh_complete(u32 item,u32 kind,u32 result,u32 buffer,u32 count,u32 context) {
    (void)item;(void)kind;(void)buffer;(void)count;
    if(context!=SLOT)return;
    S->m[PENDING]=0;
    if(result)finish(1,result);
}
/* Private requests run inside Content, serialized with all stock filesystem jobs.
 * No raw file operation runs in the Main/LED hook or application callback. */
u32 c_sh_backend(u32 item,u32 offset,u32 buffer,u32 length,u32 actual,u32 a,u32 b) {
    if(*(u32 *)item!=PRIVATE_KIND)
        return ((u32 (*)(u32,u32,u32,u32,u32,u32,u32))(TR_BACKEND|1))(item,offset,buffer,length,actual,a,b);
    if(buffer!=SLOT || length || !actual || S->m[ACTIVE]!=2)return 5;
    *(u32 *)actual=0;
    if(!guards()){S->m[GUARD]++;finish(1,0x102);return 0;}
    if(S->m[STAGE]==0) {
        u32 result=((u32 (*)(const char *))0x08022789)("1:/RP_AUTO");
        if(result && result!=8){finish(1,result);return 0;}
        S->m[STAGE]=1;begin_job(1);
    } else {
        S->m[OPER]++;c_pf_step(&S->job);
        if(S->m[STAGE]==2 && S->job.phase==TRANSFER && !S->job.offset &&
           *(volatile u32 *)(FIL+12)!=100)S->job.error=2;
        if(!guards()){S->m[GUARD]++;finish(1,0x102);}
    }
    return 0;
}
static void pump(void) {
    if(!ready() || S->m[ACTIVE]!=2 || S->m[PENDING])return;
    struct job *j=&S->job;
    if(S->m[STAGE]) {
        if(j->phase==FAILED) {
            if(S->m[STAGE]==1 && j->raw_error==8 && !j->opened) {
                S->m[STAGE]=2;if(!begin_job(0))return;
            } else if(!S->m[MODE] && (j->raw_error==4 || j->raw_error==5) && !j->opened) {
                S->m[MISSING]++;finish(0,j->raw_error);return;
            } else {finish(1,j->raw_error?j->raw_error:0x100+j->error);return;}
        } else if(j->phase==DONE) {
            if(S->m[STAGE]==1) {
                S->m[WRITES]++;S->m[STAGE]=2;if(!begin_job(0))return;
            } else {
                S->m[READS]++;
                for(u32 i=0;i<100;i++)if(S->data[i]!=S->readback[i]){finish(1,0x103);return;}
                S->m[VERIFIED]++;finish(0,0);return;
            }
        }
    }
    u8 *r=S->request;for(u32 i=0;i<72;i++)r[i]=0;
    r[0]=6;*(u32 *)(r+4)=PRIVATE_KIND;*(u32 *)(r+20)=SLOT;
    *(u32 *)(r+60)=(u32)c_sh_complete;*(u32 *)(r+64)=SLOT;
    u32 service=*(volatile u32 *)0x20006ca8;
    S->m[PENDING]=1;
    if(c_pf_submit(service,r)){S->m[PENDING]=0;S->m[QBUSY]++;}
}
u32 c_sh_out(u32 a,u32 b,u32 c,u32 d) {
    u32 result=((fn4)(PREV_OUT|1))(a,b,c,d);pump();return result;
}
u32 c_sh_apply(u32 a,u32 b,u32 c,u32 d) {
    if(ready()){S->m[NLOAD]++;start(*(u32 *)(a+0x14),0,0xffffffff,0xffffffff);}
    return ((fn4)(TR_APPLY|1))(a,b,c,d);
}
u32 c_sh_save(u32 a,u32 item,u32 offset,u32 buffer,u32 length,u32 observer) {
    if(ready() && *(u32 *)item==2 && length==0x29484 && (((u32 *)item)[2]&255)) {
        S->m[NSAVE]++;start(buffer,1,((u32 *)item)[1],((u32 *)item)[2]);
    }
    return ((fn6)(TR_SAVE|1))(a,item,offset,buffer,length,observer);
}
u32 c_sh_done(u32 item,u32 kind,u32 result,u32 buffer,u32 count,u32 context) {
    if(ready() && *(u32 *)item==2 && S->m[ACTIVE]==1 &&
       ((u32 *)item)[1]==S->m[PROJECT] && (((u32 *)item)[2]&255)==S->m[PACK]) {
        if(result || count!=0x29484)finish(1,result?result:0x104);
        else S->m[ACTIVE]=2;
    }
    return ((fn6)(TR_DONE|1))(item,kind,result,buffer,count,context);
}
static u64 media(u32 write,u32 a,u32 offset,u32 buffer,u32 length) {
    if(buffer<FIL || buffer>=FIL_END)
        return ((u64 (*)(u32,u32,u32,u32))((write?TR_WRITE:TR_READ)|1))(a,offset,buffer,length);
    if(buffer+length>FIL_END || S->m[MAGIC]!=TAG)return ((u64)length<<32)|1;
    struct dma_bridge bridge={a,(void *)(TR_READ|1),(void *)(TR_WRITE|1),S->bounce};
    return ((u64)length<<32)|c_pf_dma(&bridge,write,offset,(u8 *)buffer,length);
}
u64 c_sh_read(u32 a,u32 b,u32 c,u32 d){return media(0,a,b,c,d);}
u64 c_sh_write(u32 a,u32 b,u32 c,u32 d){return media(1,a,b,c,d);}
