#ifndef RP_AUTOMATION3_H
#define RP_AUTOMATION3_H
#include <stdint.h>
typedef uint32_t a3_u32;
typedef uint16_t a3_u16;
typedef uint8_t a3_u8;
#define A3_CELLS 4608u
#define A3_BANK 0x1500u
#if COW7
#define A3_BANK_BYTES 456u
#define A3_STATE 0x3d40u
#elif PACK129
#define A3_BANK_BYTES 4176u
#define A3_SNAPSHOT 0x2580u
#define A3_PAYLOAD 4304u
#define A3_STATE 0x3680u
#else
#define A3_BANK_BYTES 4608u
#define A3_SNAPSHOT 0x2720u
#define A3_PAYLOAD 4736u
#define A3_STATE 0x3a00u
#endif
#define A3_NONE 65535u
struct a3_state {
    a3_u32 magic,generation,writes,applies,touched,epoch;
    a3_u16 held[3],last[3],output[3],pending[3],previous[3];
    a3_u8 prev_step[3],prev_micro[3],prev_rate[3],prev_pattern[3],prev_valid[3];
    a3_u8 playing,recording,fx,reserved;
    a3_u32 padding[12],guard;
};
_Static_assert(sizeof(struct a3_state)==128,"automation control state and guard offset");
#if !COW7
_Static_assert(A3_BANK+A3_BANK_BYTES<A3_SNAPSHOT,"active bank bounds");
_Static_assert(A3_SNAPSHOT+A3_PAYLOAD<A3_STATE,"snapshot bounds");
#endif
_Static_assert(A3_STATE+sizeof(struct a3_state)<0x4000,"physical ITCM envelope");
void c_a3_init(struct a3_state *,a3_u8 *);
void c_a3_reset(struct a3_state *);
void c_a3_disarm(struct a3_state *);
void c_a3_manual(struct a3_state *,a3_u32,a3_u32,a3_u32);
/* op: 0 pattern copy, 1 pattern clear, 2 step copy, 3 step clear, 4 bank clear. */
a3_u32 c_a3_bulk(struct a3_state *,a3_u8 *,a3_u32,a3_u32,a3_u32,a3_u32,a3_u32);
a3_u32 c_a3_clear(struct a3_state *,a3_u8 *,a3_u32,a3_u32,a3_u32);
a3_u32 c_a3_lock(struct a3_state *,a3_u8 *,a3_u32,a3_u32,a3_u32,a3_u32);
void c_a3_record(struct a3_state *,a3_u8 *,a3_u32,a3_u32,a3_u32,a3_u32);
a3_u32 c_a3_value(struct a3_state *,const a3_u8 *,a3_u32,a3_u32,a3_u32,a3_u32,a3_u32,a3_u32);
#endif
