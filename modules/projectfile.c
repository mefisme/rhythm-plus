/* Standalone checked file worker. Not installed in production firmware.
 * Each step owns at most one <=512-byte file operation. Adapter must supply a
 * non-waiting shared-filesystem lease and call from a storage/Main task, never
 * sequencer/audio. No native shared file object is reused.
 */
#include <stdint.h>
typedef uint32_t u32;
typedef uint8_t u8;
struct ops {
    u32 (*try_lock)(void); /* 0 acquired; nonzero busy, never wait */
    void (*unlock)(void);
    u32 (*open)(void *,const char *,u32);
    u32 (*read)(void *,u8 *,u32,u32 *);
    u32 (*write)(void *,const u8 *,u32,u32 *);
    u32 (*sync)(void *);
    u32 (*close)(void *);
};
enum {IDLE,OPEN,TRANSFER,SYNC,CLOSE,DONE,FAILED};
struct job {
    const struct ops *ops;
    void *file;
    const char *path;
    u8 *buffer;
    u32 size,offset,write,phase,error,raw_error,opened,cancelled;
};
/* begin returns 1 invalid/busy, 0 accepted. All storage remains caller-owned. */
u32 c_pf_begin(struct job *j,const struct ops *o) {
    if(j->phase!=IDLE && j->phase!=DONE && j->phase!=FAILED)return 1;
    if(j->opened || !o || !o->try_lock || !o->unlock || !o->open || !o->close ||
       !j->file || !j->path || !j->buffer || !j->size || j->size>65536 ||
       j->write>1 || (j->write?(!o->write || !o->sync):!o->read))return 1;
    j->ops=o;j->offset=0;j->error=0;j->raw_error=0;j->cancelled=0;j->phase=OPEN;
    return 0;
}
void c_pf_cancel(struct job *j) {j->cancelled=1;}
/* Returns 0 work progressed, 1 busy, 2 complete, 3 failed. No busy spin. */
u32 c_pf_step(struct job *j) {
    if(j->phase==DONE)return 2;
    if(j->phase==IDLE || j->phase==FAILED)return 3;
    const struct ops *o=j->ops;
    if(o->try_lock())return 1;
    u32 result=0,done=0;
    if(j->cancelled && !j->error)j->error=3;
    if(j->error && j->opened)j->phase=CLOSE;
    if(j->error && !j->opened)j->phase=FAILED;
    if(j->phase==OPEN) {
        /* FatFs 7 = read/write + CREATE_NEW, never overwrite an old companion. */
        result=o->open(j->file,j->path,j->write?7:1);
        if(!result){j->opened=1;j->phase=TRANSFER;}
    } else if(j->phase==TRANSFER) {
        u32 count=j->size-j->offset;
        if(count>512)count=512;
        result=j->write?o->write(j->file,j->buffer+j->offset,count,&done):
                        o->read(j->file,j->buffer+j->offset,count,&done);
        if(!result && done!=count)j->error=2;
        if(!result && !j->error) {
            j->offset+=done;
            if(j->offset==j->size)j->phase=j->write?SYNC:CLOSE;
        }
    } else if(j->phase==SYNC) {
        result=o->sync(j->file);
        if(!result)j->phase=CLOSE;
    } else if(j->phase==CLOSE) {
        result=o->close(j->file);
        /* Failed close means ownership is unresolved: do not silently reuse it. */
        if(!result)j->opened=0;
        j->phase=(result || j->error)?FAILED:DONE;
    }
    if(result) {
        if(!j->error){j->error=1;j->raw_error=result;}
        j->phase=j->opened && j->phase!=FAILED?CLOSE:FAILED;
    } else if(j->error && j->phase!=FAILED)j->phase=j->opened?CLOSE:FAILED;
    o->unlock();
    return j->phase==DONE?2:j->phase==FAILED?3:0;
}

/* Non-waiting submission to stock Content's queue. Main/storage-task context
 * only, never IRQ-masked. Caller constructs all 72 request bytes, retains any
 * referenced buffers until completion, and permits only one private request.
 * Native 0802ACB8 waits/retries when full; this entry instead returns busy.
 * It uses native credit counters and the native queue copier under a short IRQ
 * mask, then wakes Content after restoring interrupts. No filesystem access.
 */
u32 c_pf_submit(u32 service,const u8 *request) {
    if(!service || !request || !*(u32 *)(service+0x14))return 1;
    u32 mask;
    __asm__ volatile("mrs %0, primask":"=r"(mask)::"memory");
    if(mask)return 1;
    __asm__ volatile("cpsid i":::"memory");
    u32 taken=((u32 (*)(u32))0x0802ca6d)(service+0x10);
    u32 queued=0;
    if(taken) {
        u32 message[2]={72,(u32)request};
        queued=((u32 (*)(u32,u32 *))0x08040dc5)(*(u32 *)(service+0x14),message);
        if(!queued)((u32 (*)(u32))0x08023ceb)(service+0x10);
    }
    __asm__ volatile("dmb sy\n msr primask, %0"::"r"(mask):"memory");
    if(queued)((void (*)(u32,u32))0x080240c1)(service,1);
    return queued?0:1;
}

/* Candidate bus bridge: a FIL can occupy CPU-accessible ITCM, but the native
 * SD DMA must receive SRAM. Caller supplies an exclusively owned, DMA-capable
 * 512-byte aligned staging buffer and serialized Media-task calls. Not installed.
 */
struct dma_bridge {
    u32 device;
    u32 (*read)(u32,u32,u8 *,u32);
    u32 (*write)(u32,u32,u8 *,u32);
    u8 *bounce;
};
u32 c_pf_dma(struct dma_bridge *b,u32 write,u32 offset,u8 *buffer,u32 size) {
    u32 ptr=(u32)buffer;
    if(!b || !b->read || !b->write || !b->bounce || write>1)return 1;
    if(ptr>=0x4000) return (write?b->write:b->read)(b->device,offset,buffer,size);
    if(ptr<0x400 || size>0x4000-ptr || !size || (size&511) || (offset&511) ||
       offset>0xffffffffu-size || ((u32)b->bounce&31) ||
       (u32)b->bounce<0x20000000 || (u32)b->bounce>0x2004fe00)return 1;
    for(u32 n=0;n<size;n+=512) {
        if(write)for(u32 i=0;i<512;i++)b->bounce[i]=buffer[n+i];
        u32 result=(write?b->write:b->read)(b->device,offset+n,b->bounce,512);
        if(result)return result;
        if(!write)for(u32 i=0;i<512;i++)buffer[n+i]=b->bounce[i];
    }
    return 0;
}
