/* Bounded metadata allocator; payload I/O/publication are separate worker duties.
 * No DSP/file access, heap or globals. Caller owns and serializes Pool[2048].
 */
#include "automation_pool.h"
#define END 65535u
static u32 marked(const u32 *map,u32 block) {return (map[block/32]>>(block%32))&1;}
static void mark(u32 *map,u32 block,u32 value) {
 u32 mask=1u<<(block%32);
 if(value)map[block/32]|=mask;else map[block/32]&=~mask;
}
u32 c_ap_pool_init(struct Pool *pool,u32 limit,u32 minimum) {
 if((minimum!=1 && minimum!=2) || limit<64*minimum || limit>224)return 4;
 /* Volatile stores keep this freestanding loop from becoming a CRT memset. */
 for(u32 i=0;i<sizeof(*pool)/4;i++)((volatile u32 *)pool)[i]=0;
 pool->config=limit|(minimum<<16);
 for(u32 i=0;i<64;i++) {
  pool->patterns[i].head=pool->patterns[i].tail=END;
  for(u32 j=0;j<2;j++)pool->patterns[i].continuous[j]=255;
  for(u32 j=0;j<8;j++)pool->patterns[i].locks[j]=255;
 }
 for(u32 i=0;i<224;i++)pool->next[i]=END;
 return 0;
}
u32 c_ap_pool_validate(const struct Pool *pool) {
 u32 limit=pool->config&511,minimum=(pool->config>>16)&3;
 volatile u32 seen[7];for(u32 i=0;i<7;i++)seen[i]=0;
 if((pool->config&~0x301ffu) || (minimum!=1 && minimum!=2) || limit<64*minimum || limit>224)return 2;
 u32 charge=64*minimum;
 for(u32 i=0;i<64;i++) {
  const struct Pattern *p=pool->patterns+i;
  if(p->count>384 || p->blocks!=(p->count+23)/24)return 2;
  if(p->blocks>minimum)charge+=p->blocks-minimum;
  u32 block=p->head;
  if(!p->blocks && (block!=END || p->tail!=END))return 2;
  for(u32 j=0;j<p->blocks;j++) {
   if(block>=limit || ((seen[block/32]>>(block%32))&1) || !marked(pool->used,block))return 2;
   seen[block/32]|=1u<<(block%32);
   if(j+1==p->blocks && p->tail!=block)return 2;
   block=pool->next[block];
  }
  if(block!=END)return 2;
 }
 if(charge>limit)return 2;
 for(u32 i=0;i<7;i++)if(seen[i]!=pool->used[i] || (pool->dirty[i]&~seen[i]))return 2;
 for(u32 i=0;i<224;i++)if(!((seen[i/32]>>(i%32))&1) && pool->next[i]!=END)return 2;
 return 0;
}
/* Resize an already-staged pattern; emits at most16 block IDs to caller.
 * Error1: quota/capacity;2: damaged metadata;4: invalid caller parameters.
 * On error metadata and output stay unchanged. This does NOT commit payload.
 */
u32 c_ap_pool_resize(struct Pool *pool,u32 pattern,u32 events,u16 *out) {
 if(pattern>=64 || events>384)return 4;
 if(c_ap_pool_validate(pool))return 2;
 u32 limit=pool->config&511,minimum=(pool->config>>16)&3;
 struct Pattern *p=pool->patterns+pattern;
 u32 need=(events+23)/24,charge=0;
 for(u32 i=0;i<64;i++) {
  u32 blocks=i==pattern?need:pool->patterns[i].blocks;
  charge+=blocks>minimum?blocks:minimum;
 }
 if(charge>limit)return 1;
 volatile u16 old[16],ids[16];u32 block=p->head;
 for(u32 i=0;i<p->blocks;i++){old[i]=(u16)block;block=pool->next[block];}
 u32 keep=need<p->blocks?need:p->blocks,found=keep;
 for(u32 i=0;i<keep;i++)ids[i]=old[i];
 for(u32 i=0;found<need && i<limit;i++)if(!marked(pool->used,i))ids[found++]=(u16)i;
 if(found!=need)return 1;
 /* All checks complete; metadata mutation starts here. */
 for(u32 i=need;i<p->blocks;i++) {
  mark(pool->used,old[i],0);mark(pool->dirty,old[i],0);pool->next[old[i]]=END;
 }
 for(u32 i=0;i<need;i++) {
  mark(pool->used,ids[i],1);mark(pool->dirty,ids[i],1);
  pool->next[ids[i]]=i+1<need?ids[i+1]:END;
 }
 p->head=need?ids[0]:END;p->tail=need?ids[need-1]:END;
 p->blocks=(u8)need;p->count=(u16)events;
 p->generation=++pool->generation;
 for(u32 i=0;i<16;i++)out[i]=i<need?ids[i]:END;
 return 0;
}
