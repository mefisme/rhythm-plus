/* Compile-time layout proof; no global allocation or hardware access. */
#include "automation_runtime.h"
#include "automation_lock_layout.h"
u32 c_ap_runtime_bytes(void) {return sizeof(struct AutomationRuntime);}
u32 c_ap_capture_capacity(void) {return sizeof(((struct AutomationRuntime *)0)->capture)/sizeof(struct Capture);}
u32 c_ap_lock_runtime_bytes(void) {return sizeof(struct LockOnlyRuntime);}

/* Bounded SPSC transport only. Integrator must assign exactly one producer and
 * one consumer; project epoch changes/reset require both to be quiescent.
 * Context: low6 pattern, high26 nonzero epoch. Full queues never overwrite.
 * Results:0 success,1 empty,2 full,3 invalid/corrupt,4 discarded stale command.
 * DMB publishes complete payload before head and consumes it before tail.
 * No IRQ masking, allocations, file calls or DSP transfers occur here.
 */
static void barrier(void) {__asm__ volatile("dmb sy" ::: "memory");}
static int event_valid(u32 e) {
 u32 position=e&255,kind=(e>>28)&3;
 return !(e>>30) && position<192 && kind<2 && (!kind || !(position%6));
}
u32 c_ap_capture_push(volatile struct AutomationRuntime *r,u32 event,u32 context) {
 u32 epoch=r->control.epoch;
 if(!epoch || epoch>0x3ffffff || (context>>6)!=epoch || !event_valid(event))return 3;
 u32 head=r->control.queue_head,tail=r->control.queue_tail,used=head-tail;
 if(used>128)return 3;
 if(used==128)return 2;
 barrier();
 r->capture[head&127].event=event;r->capture[head&127].context=context;
 barrier();r->control.queue_head=head+1;
 return 0;
}
u32 c_ap_capture_pop(volatile struct AutomationRuntime *r,struct Capture *out) {
 u32 head=r->control.queue_head,tail=r->control.queue_tail,used=head-tail;
 if(used>128 || !r->control.epoch || r->control.epoch>0x3ffffff)return 3;
 if(!used)return 1;
 barrier();
 u32 event=r->capture[tail&127].event,context=r->capture[tail&127].context;
 u32 result=(context>>6)!=r->control.epoch?4:!event_valid(event)?3:0;
 if(!result) {out->event=event;out->context=context;}
 barrier();r->control.queue_tail=tail+1;
 return result;
}
