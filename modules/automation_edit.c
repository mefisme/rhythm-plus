/* Edit a worker-owned decoded pattern, never the live cache or DSP payload.
 * Request/allow/descriptor/event buffers must not overlap. Caller stages the
 * descriptor and payload; later pool admission/publication is a separate commit.
 * Return0 success,1 capacity,2 damaged source,4 bad request. Errors write nothing.
 */
#include "automation_pool.h"
struct Edit {u32 step,kind,taken[2],count,points[12];};
extern u32 c_ap_validate_stream(const u32 *,u32,u32,u32);
static u32 key(u32 e) {return ((e&255)<<6)|((e>>8)&63);}
static u32 has(const u32 *mask,u32 dest) {return (mask[dest/32]>>(dest%32))&1;}
static void add(u32 *mask,u32 dest) {mask[dest/32]|=1u<<(dest%32);}
static u32 bits(u32 n) {u32 count=0;while(n){n&=n-1;count++;}return count;}
static int removed(u32 event,const struct Edit *edit) {
 return (event&255)/6==edit->step && has(edit->taken,(event>>8)&63);
}
u32 c_ap_edit_step(u32 *events,struct Pattern *p,const struct Edit *edit,const u32 *allow) {
 if(edit->step>=32 || edit->kind>1 || edit->count>(edit->kind?8u:12u) ||
    (edit->taken[0]&~allow[0]) || (edit->taken[1]&~allow[1]))return 4;
 if(c_ap_validate_stream(events,p->count,allow[0],allow[1]))return 2;
 u32 old[4],present[4];for(u32 i=0;i<4;i++){old[i]=0;present[i]=0;}
 for(u32 i=0;i<10;i++) {
  u32 dest=i<2?p->continuous[i]:p->locks[i-2],kind=i<2?0:1;
  if(dest==255)continue;
  if(dest>=64 || !has(allow,dest) || has(old,dest) || has(old+2,dest))return 2;
  add(old+2*kind,dest);
 }
 if((edit->taken[0]&old[2*(1-edit->kind)]) ||
    (edit->taken[1]&old[2*(1-edit->kind)+1]))return 4;
 u32 count=0;
 for(u32 i=0;i<p->count;i++) {
  u32 event=events[i],dest=(event>>8)&63,kind=(event>>28)&1;
  if(!has(old+2*kind,dest))return 2;
  if(!removed(event,edit)){count++;add(present+2*kind,dest);}
 }
 for(u32 i=0;i<edit->count;i++) {
  u32 event=edit->points[i],dest=(event>>8)&63;
  if(c_ap_validate_stream(edit->points+i,1,allow[0],allow[1]) ||
     (event&255)/6!=edit->step || ((event>>28)&1)!=edit->kind ||
     !has(edit->taken,dest) || (i && key(edit->points[i-1])>=key(event)))return 4;
  add(present+2*edit->kind,dest);
 }
 count+=edit->count;
 if(count>384 || bits(present[0])+bits(present[1])>2 ||
    bits(present[2])+bits(present[3])>8)return 1;
 /* Fully preflighted. Compact survivors, then insert at most twelve points. */
 u32 kept=0;
 for(u32 i=0;i<p->count;i++)if(!removed(events[i],edit))events[kept++]=events[i];
 for(u32 i=0;i<edit->count;i++) {
  u32 event=edit->points[i],j=kept;
  while(j && key(events[j-1])>key(event)){events[j]=events[j-1];j--;}
  events[j]=event;kept++;
 }
 p->count=(u16)kept;
 u32 ci=0,li=0;
 for(u32 dest=0;dest<64;dest++) {
  if(has(present,dest))p->continuous[ci++]=(u8)dest;
  if(has(present+2,dest))p->locks[li++]=(u8)dest;
 }
 while(ci<2)p->continuous[ci++]=255;
 while(li<8)p->locks[li++]=255;
 return 0;
}
