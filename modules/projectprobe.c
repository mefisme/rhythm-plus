/* Read-only lifecycle probe. No file opens, extra disk I/O or project writes. */
#include <stdint.h>
typedef uint32_t u32;
typedef u32 (*fn4)(u32,u32,u32,u32);
typedef u32 (*fn5)(u32,u32,u32,u32,u32);
typedef u32 (*fn6)(u32,u32,u32,u32,u32,u32);
struct event { u32 seq, ms, kind, a, b, c, d, e; };
struct state { u32 magic, total, loads, applies, saves, callbacks, pad[2]; struct event events[32]; };
static void log_event(u32 kind,u32 a,u32 b,u32 c,u32 d,u32 e) {
    if (!((u32 (*)(void))(C_RST|1))()) return;
    volatile struct state *s=(volatile struct state *)SLOT;
    u32 mask;
    __asm__ volatile("mrs %0, primask\n cpsid i":"=r"(mask)::"memory");
    u32 n=s->total;
    volatile struct event *v=&s->events[n&31];
    s->magic=0x31505052; /* RPP1 */
    v->seq=n+1;v->ms=*(volatile u32 *)0x20006f3c;v->kind=kind;
    v->a=a;v->b=b;v->c=c;v->d=d;v->e=e;
    if(kind==1)s->loads++;
    if(kind==3)s->applies++;
    if(kind==5)s->saves++;
    if(kind==7)s->callbacks++;
    __asm__ volatile("dmb sy":::"memory");
    s->total=n+1;
    __asm__ volatile("msr primask, %0"::"r"(mask):"memory");
}
static int project(u32 item) {return item && *(u32 *)item==2;}
u32 c_pp_load(u32 session,u32 item,u32 offset,u32 buffer,u32 length) {
    int p=project(item);
    if(p)log_event(1,((u32 *)item)[1],((u32 *)item)[2],offset,length,buffer);
    u32 result=((fn5)(TR_LOAD|1))(session,item,offset,buffer,length);
    if(p)log_event(2,((u32 *)item)[1],((u32 *)item)[2],result,length,buffer);
    return result;
}
u32 c_pp_apply(u32 session,u32 mode,u32 c,u32 d) {
    log_event(3,session,mode,*(u32 *)(session+0x14),0,0);
    u32 result=((fn4)(TR_APPLY|1))(session,mode,c,d);
    log_event(4,session,mode,result,0,0);
    return result;
}
u32 c_pp_save(u32 session,u32 item,u32 offset,u32 buffer,u32 length,u32 observer) {
    if(project(item))log_event(5,((u32 *)item)[1],((u32 *)item)[2],offset,length,buffer);
    u32 result=((fn6)(TR_SAVE|1))(session,item,offset,buffer,length,observer);
    if(project(item))log_event(6,((u32 *)item)[1],((u32 *)item)[2],result,length,buffer);
    return result;
}
u32 c_pp_done(u32 item,u32 kind,u32 result,u32 buffer,u32 count,u32 context) {
    if(project(item))log_event(7,((u32 *)item)[1],((u32 *)item)[2],result,count,buffer);
    return ((fn6)(TR_DONE|1))(item,kind,result,buffer,count,context);
}
