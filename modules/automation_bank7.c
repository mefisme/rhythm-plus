/* RAM-only adapter for the three-control engine. Callers serialize access.
 * One raw current-pattern cache per control keeps ordinary recording writes
 * constant-time. Dirty eviction publishes a raw immutable lane; compression
 * is separate from the consistency boundary. No filesystem calls here. */
#define B7_POOL ((struct cp_pool *)0x1500u)
#define B7_DATA ((C_B *)0x16e0u)
#define B7_CACHE ((C_B *)0x3b00u)
#define B7_STATE ((struct a3_state *)0x3d40u)
/* padding[0] belongs to recording feedback. */
#define B7_KEYS (B7_STATE->padding+1)
#define B7_DIRTY (B7_STATE->padding[4])
#if TASK_GUARD
#include "rp_task_guard.h"
static C_U b7_lock(void){return rp_task_lock();}
static void b7_unlock(C_U mask){rp_task_unlock(mask);}
#else
static C_U b7_lock(void){C_U mask;__asm__ volatile("mrs %0,primask\n cpsid i":"=r"(mask)::"memory");return mask;}
static void b7_unlock(C_U mask){__asm__ volatile("msr primask,%0"::"r"(mask):"memory");}
#endif
static C_U b7_flush(C_U k){
    if(!(B7_DIRTY&(1u<<k)))return 0;
    C_U e=c_cp_encoded(B7_POOL,B7_DATA,B7_KEYS[k],B7_CACHE+k*192,192,1);
    if(!e)B7_DIRTY&=~(1u<<k);
    return e;
}
C_U c_a3_bankflush(void){
    for(C_U k=0;k<3;k++){C_U e=b7_flush(k);if(e)return e;}return 0;
}
C_U c_a3_bankread(C_U lane,C_B *out){
    if(lane>=24)return 1;C_U e=c_a3_bankflush();
    return e?e:c_cp_read(B7_POOL,B7_DATA,0,lane,out);
}
static C_U b7_select(C_U lane){
    C_U k=lane/8;
    if(B7_KEYS[k]==lane)return 0;
    C_U e=b7_flush(k);if(e)return e;
    e=c_cp_read(B7_POOL,B7_DATA,0,lane,B7_CACHE+k*192);
    if(!e)B7_KEYS[k]=lane;
    return e;
}
static void b7_invalidate(void){for(C_U k=0;k<3;k++)B7_KEYS[k]=255;B7_DIRTY=0;}
void c_a3_bankinit(void){c_cp_init(B7_POOL,9216);b7_invalidate();}
C_U c_a3_bankget(const C_B *unused,C_U index){
    (void)unused;if(index>=4608)return 255;
    C_U mask=b7_lock(),v=255;
    if(!b7_select(index/192))v=B7_CACHE[(index/1536)*192+index%192];
    b7_unlock(mask);return v;
}
void c_a3_bankset(C_B *unused,C_U index,C_U value){
    (void)unused;if(index>=4608 || (value>127 && value!=255))return;
    C_U mask=b7_lock();
    if(!b7_select(index/192)){
        C_U k=index/1536;B7_CACHE[k*192+index%192]=(C_B)value;B7_DIRTY|=1u<<k;
    }
    b7_unlock(mask);
}
/* The playback callback asks for the next step before reading the current
 * one. Across a pattern boundary this must not evict the current raw cache
 * twice per pulse. Cache one exact lookahead value per control instead. */
C_U c_a3_bankpeek(C_U index){
    if(index>=4608)return 255;
    C_U mask=b7_lock(),k=index/1536,lane=index/192,v=255;
    if(B7_KEYS[k]==lane)v=B7_CACHE[k*192+index%192];
    else {
        if(B7_STATE->padding[10]!=B7_STATE->generation || B7_STATE->padding[11]!=B7_POOL->generation){
            for(C_U j=7;j<10;j++)B7_STATE->padding[j]=0;
            B7_STATE->padding[10]=B7_STATE->generation;B7_STATE->padding[11]=B7_POOL->generation;
        }
        C_U cached=B7_STATE->padding[7+k];
        if((cached&0x8000ffffu)==(0x80000000u|index))v=(cached>>16)&255;
        else {
            C_B raw[192];
            if(!c_cp_read(B7_POOL,B7_DATA,0,lane,raw)){
                v=raw[index%192];B7_STATE->padding[7+k]=0x80000000u|(v<<16)|index;
            }
        }
    }
    b7_unlock(mask);return v;
}
C_U c_a3_banksnapshot(void){C_U e=c_a3_bankflush();return e?e:c_cp_snapshot(B7_POOL);}
void c_a3_bankrelease(void){c_cp_release(B7_POOL,B7_DATA);}
/* Compression is explicit; firmware must schedule this outside the short
 * publication boundary or use a generation-checked prepared lane. */
C_U c_a3_bankcompress(C_U lane){
    if(lane>=24)return 1;C_U e=c_a3_bankflush();if(e)return e;
    C_B raw[192];e=c_cp_read(B7_POOL,B7_DATA,0,lane,raw);
    return e?e:c_cp_set(B7_POOL,B7_DATA,lane,raw);
}
C_U c_a3_bankbulk(C_U op,C_U sp,C_U ss,C_U dp,C_U ds){
    C_U e=c_a3_bankflush();if(e)return e;
    if(op==4){e=c_cp_clear(B7_POOL,B7_DATA,0,24);b7_invalidate();return e;}
    for(C_U k=0;k<3;k++){
        C_U src=k*8+sp,dst=k*8+dp;
        if(op==0)e=c_cp_copy(B7_POOL,B7_DATA,src,dst,1);
        else if(op==1)e=c_cp_clear(B7_POOL,B7_DATA,dst,1);
        else {
            C_B raw[192],from[192];
            e=c_cp_read(B7_POOL,B7_DATA,0,dst,raw);if(e)return e;
            if(op==2){e=c_cp_read(B7_POOL,B7_DATA,0,src,from);if(e)return e;}
            for(C_U m=0;m<6;m++)raw[ds*6+m]=op==2?from[ss*6+m]:255;
            e=c_cp_encoded(B7_POOL,B7_DATA,dst,raw,192,1);
        }
        if(e)return e;
    }
    b7_invalidate();return 0;
}
/* RA03 virtual file: 28-byte header, frozen StepMutate settings (100),
 * 24 two-byte lane descriptors, then immutable lane payloads. The caller
 * copies each chunk under its publication lock and performs I/O afterwards;
 * no pointer into the movable pool survives a scheduler yield. */
static C_U b7_descriptor(C_U lane){
    C_U id=B7_POOL->saved[lane];if(id==CP_NONE)return 0;
    const struct cp_record *r=&B7_POOL->records[id];
    return r->size|(r->kind?0x8000u:0);
}
C_U c_a3_bankfilesize(void){
    if(!B7_POOL->snapshot)return 0;
    C_U n=176;for(C_U lane=0;lane<24;lane++)n+=b7_descriptor(lane)&0x7fffu;return n;
}
C_U c_a3_bankfile(C_U offset,C_B *out,C_U count,const C_B *settings){
    C_U size=c_a3_bankfilesize();
    if(!size || offset>size || count>size-offset)return 1;
    /* Header values are calculated directly, avoiding a temporary raw bank. */
    C_U i=0;
    for(;i<count && offset+i<176;i++){
        C_U pos=offset+i,v=0;
        if(pos<28){
            C_U word=pos/4;
            C_U field=word==0?0x33304152u:word==1?4608:word==2?3:word==3?8:word==4?32:word==5?6:0;
            v=(field>>((pos&3)*8))&255;
        }else if(pos<128)v=settings[pos-28];
        else if(pos<176)v=(b7_descriptor((pos-128)/2)>>((pos&1)*8))&255;
        out[i]=(C_B)v;
    }
    C_U skip=offset+i>=176?offset+i-176:0;
    for(C_U lane=0;i<count && lane<24;lane++){
        C_U id=B7_POOL->saved[lane];if(id==CP_NONE)continue;
        const struct cp_record *r=&B7_POOL->records[id];
        if(skip>=r->size){skip-=r->size;continue;}
        C_U n=r->size-skip;if(n>count-i)n=count-i;
        for(C_U j=0;j<n;j++)out[i+j]=B7_DATA[r->offset+skip+j];
        i+=n;skip=0;
    }
    return 0;
}
/* Called only while the project is unavailable during a validated-file load.
 * READY is published by storage only after every lane and file CRC succeed. */
C_U c_a3_bankimport(C_U lane,const C_B *bytes,C_U n,C_U kind){
    if(B7_POOL->snapshot || lane>=24)return 1;
    C_U e=c_cp_encoded(B7_POOL,B7_DATA,lane,bytes,n,kind);
    if(!e)b7_invalidate();return e;
}
/* Main-task maintenance: encode with interrupts enabled, then publish only if
 * neither recording nor a pool operation changed the captured lane version. */
C_U c_a3_bankmaintain(C_U lane){
    if(lane>=24)return 1;
    C_B raw[192],encoded[193];C_U mask=b7_lock();
    if(mask){b7_unlock(mask);return 1;}
    C_U e=c_a3_bankflush(),g=B7_STATE->generation,pg=B7_POOL->generation,epoch=B7_STATE->epoch;
    if(!e)e=c_cp_read(B7_POOL,B7_DATA,0,lane,raw);
    b7_unlock(mask);if(e)return e;
    C_U n=c_lc_encode(encoded,193,raw);if(n==0xffffffffu)return 1;
    mask=b7_lock();
    if(g!=B7_STATE->generation || pg!=B7_POOL->generation || epoch!=B7_STATE->epoch)e=3;
    else e=set_payload(B7_POOL,B7_DATA,lane,n>=192?raw:encoded,n>=192?192:n,n>=192);
    b7_unlock(mask);return e;
}
