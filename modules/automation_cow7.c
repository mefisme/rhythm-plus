/* Adaptive RAM pool / shared immutable save view. Selected by COW7 builds.
 * Single serialized owner; callers must serialize publication and copy payloads
 * before allowing a pool mutation. No payload pointer may survive a yield.
 * The pool uses four-byte aligned variable blocks. Snapshot and Copy initially
 * share records; editing clones only the lane that actually changes.
 * At capacity 9216, all 24 live + 24 saved lanes fit even incompressible input.
 * Smaller capacities report an unchanged failed edit; they are NOT selected as
 * a firmware recording-capacity limit. No SD writes, allocation or globals. */
#include <stdint.h>
typedef uint32_t C_U;typedef uint16_t C_H;typedef uint8_t C_B;
#define CP_LANES 24u
#define CP_SLOTS 48u
#define CP_NONE 255u
#define CP_MAGIC 0x37575043u
struct cp_record {C_H offset,size,refs,kind;};
struct cp_pool {
    C_U magic,generation,used,capacity,snapshot;
    C_B live[CP_LANES],saved[CP_LANES];
    struct cp_record records[CP_SLOTS];
    C_U guard;
};
_Static_assert(sizeof(struct cp_pool)==456,"pool metadata budget");
static C_U padded(C_U n){return (n+3)&~3u;}
static void compact(struct cp_pool *p,C_B *data){
    C_U from=0,to=0;
    /* Records remain contiguous, including dead blocks until this pass. */
    while(from<p->used){
        C_U id=CP_NONE;
        for(C_U i=0;i<CP_SLOTS;i++)if(p->records[i].size && p->records[i].offset==from){id=i;break;}
        if(id==CP_NONE)return; /* invariant checker reports any damaged layout */
        struct cp_record *r=&p->records[id];C_U n=padded(r->size);
        if(r->refs){
            if(from!=to)for(C_U i=0;i<n;i+=4)((C_U *)(data+to))[i/4]=((C_U *)(data+from))[i/4];
            r->offset=(C_H)to;to+=n;
        }else r->size=0;
        from+=n;
    }
    p->used=to;
}
void c_cp_init(struct cp_pool *p,C_U capacity){
    for(C_U i=0;i<sizeof(*p);i++)((C_B *)p)[i]=0;
    for(C_U i=0;i<CP_LANES;i++)p->live[i]=p->saved[i]=CP_NONE;
    p->magic=p->guard=CP_MAGIC;p->capacity=capacity>9216?9216:capacity&~3u;
}
C_U c_cp_read(const struct cp_pool *p,const C_B *data,C_U saved,C_U lane,C_B *out){
    if(lane>=CP_LANES || saved>1 || (saved && !p->snapshot))return 1;
    C_U id=(saved?p->saved:p->live)[lane];
    if(id==CP_NONE){for(C_U i=0;i<192;i++)out[i]=255;return 0;}
    if(id>=CP_SLOTS)return 1;const struct cp_record *r=&p->records[id];
    if(!r->refs || !r->size || r->size>192 || r->offset+r->size>p->used)return 1;
    if(r->kind){
        if(r->kind!=1 || r->size!=192)return 1;
        for(C_U i=0;i<192;i++)if(data[r->offset+i]>127 && data[r->offset+i]!=255)return 1;
        for(C_U i=0;i<192;i++)out[i]=data[r->offset+i];return 0;
    }
    return c_lc_decode(out,data+r->offset,r->size);
}
static C_U set_payload(struct cp_pool *p,C_B *data,C_U lane,const C_B *bytes,C_U n,C_U kind){
    if(lane>=CP_LANES)return 1;
    C_U old=p->live[lane],old_bytes=0;
    if(old!=CP_NONE){
        struct cp_record *r=&p->records[old];
        if(n==r->size && kind==r->kind){
            C_U equal=1;for(C_U i=0;i<n;i++)if(data[r->offset+i]!=bytes[i]){equal=0;break;}
            if(equal)return 0;
        }
        if(r->refs==1)old_bytes=padded(r->size);
        /* Replacing an exclusively owned block of the same aligned size
         * needs no compaction. This is the dense-recording fast path. */
        if(n && old_bytes==padded(n)){
            for(C_U i=0;i<padded(n);i++)data[r->offset+i]=i<n?bytes[i]:0;
            r->size=(C_H)n;r->kind=(C_H)kind;p->generation++;return 0;
        }
    }else if(!n)return 0;
    if(p->used-old_bytes+padded(n)>p->capacity)return 2;
    C_U slot=CP_NONE;
    if(n){
        for(C_U i=0;i<CP_SLOTS;i++)if(!p->records[i].size){slot=i;break;}
        if(slot==CP_NONE){if(old_bytes)slot=old;else return 2;}
    }
    if(old!=CP_NONE)p->records[old].refs--;
    p->live[lane]=CP_NONE;compact(p,data);
    if(n){
        struct cp_record *r=&p->records[slot];r->offset=(C_H)p->used;r->size=(C_H)n;r->refs=1;r->kind=(C_H)kind;
        for(C_U i=0;i<padded(n);i++)data[p->used+i]=i<n?bytes[i]:0;
        p->used+=padded(n);p->live[lane]=(C_B)slot;
    }
    p->generation++;return 0;
}
C_U c_cp_set(struct cp_pool *p,C_B *data,C_U lane,const C_B *raw){
    if(lane>=CP_LANES)return 1;
    C_B encoded[193];C_U n=c_lc_encode(encoded,193,raw);
    if(n==0xffffffffu)return 1;
    return set_payload(p,data,lane,n>=192?raw:encoded,n>=192?192:n,n>=192);
}
/* File import and the short live-cache flush path. Raw input avoids running
 * an encoder while recording/Save takes its consistent state boundary. */
C_U c_cp_encoded(struct cp_pool *p,C_B *data,C_U lane,const C_B *bytes,C_U n,C_U kind){
    if(lane>=CP_LANES || n>192 || kind>1 || (kind && n!=192))return 1;
    if(kind){
        C_U empty=1;for(C_U i=0;i<192;i++){
            if(bytes[i]>127 && bytes[i]!=255)return 1;
            if(bytes[i]!=255)empty=0;
        }
        if(empty)n=kind=0;
    }else if(n){C_B decoded[192];if(c_lc_decode(decoded,bytes,n))return 1;}
    return set_payload(p,data,lane,bytes,n,kind);
}
C_U c_cp_snapshot(struct cp_pool *p){
    if(p->snapshot)return 1;
    for(C_U i=0;i<CP_LANES;i++){C_U id=p->live[i];p->saved[i]=(C_B)id;if(id!=CP_NONE)p->records[id].refs++;}
    p->snapshot=1;return 0;
}
void c_cp_release(struct cp_pool *p,C_B *data){
    if(!p->snapshot)return;
    for(C_U i=0;i<CP_LANES;i++){C_U id=p->saved[i];if(id!=CP_NONE)p->records[id].refs--;p->saved[i]=CP_NONE;}
    p->snapshot=0;compact(p,data);
}
C_U c_cp_copy(struct cp_pool *p,C_B *data,C_U src,C_U dst,C_U count){
    if(count>CP_LANES || src>CP_LANES-count || dst>CP_LANES-count)return 1;
    C_B ids[CP_LANES];
    for(C_U i=0;i<count;i++){ids[i]=p->live[src+i];if(ids[i]!=CP_NONE)p->records[ids[i]].refs++;}
    for(C_U i=0;i<count;i++){C_U old=p->live[dst+i];if(old!=CP_NONE)p->records[old].refs--;p->live[dst+i]=ids[i];}
    compact(p,data);p->generation++;return 0;
}
C_U c_cp_clear(struct cp_pool *p,C_B *data,C_U first,C_U count){
    if(count>CP_LANES || first>CP_LANES-count)return 1;
    for(C_U i=0;i<count;i++){C_U id=p->live[first+i];if(id!=CP_NONE)p->records[id].refs--;p->live[first+i]=CP_NONE;}
    compact(p,data);p->generation++;return 0;
}
C_U c_cp_valid(const struct cp_pool *p){
    if(p->magic!=CP_MAGIC || p->guard!=CP_MAGIC || p->capacity>9216 || p->used>p->capacity || (p->used&3))return 0;
    C_U bytes=0;
    for(C_U i=0;i<CP_SLOTS;i++){
        const struct cp_record *r=&p->records[i];C_U refs=0;
        for(C_U j=0;j<CP_LANES;j++){refs+=p->live[j]==i;refs+=p->snapshot && p->saved[j]==i;}
        if(refs!=r->refs || (!!refs)!=!!r->size)return 0;
        if(refs){
            if(r->size>192 || (r->offset&3) || r->offset+padded(r->size)>p->used || r->kind>1 || (r->kind && r->size!=192))return 0;
            bytes+=padded(r->size);
            for(C_U j=0;j<i;j++)if(p->records[j].refs && r->offset<p->records[j].offset+padded(p->records[j].size) &&
                p->records[j].offset<r->offset+padded(r->size))return 0;
        }
    }
    for(C_U i=0;i<CP_LANES;i++)if((p->live[i]!=CP_NONE && p->live[i]>=CP_SLOTS) ||
        (p->saved[i]!=CP_NONE && p->saved[i]>=CP_SLOTS))return 0;
    return bytes==p->used;
}
