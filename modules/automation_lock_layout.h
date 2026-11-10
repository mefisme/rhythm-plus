#ifndef RHYTHM_PLUS_AUTOMATION_LOCK_LAYOUT_H
#define RHYTHM_PLUS_AUTOMATION_LOCK_LAYOUT_H
#include "automation_runtime.h"
/* Scope alternative only: one14bit lock destination per track-pattern.
 * No globals, installed allocation, format, recorder or playback implementation.
 *65535 marks absence;0..16383 remain exact values.64patterns x32steps.
 * Keep existing128 contextual capture slots and512-byte save-I/O staging even
 * though a held-step-only implementation may not require the entire queue.
 */
struct LockOnlyRuntime {
 u16 values[64][32];             /*4096*/
 u8 destination[64];            /*64*/
 u32 generation[64];            /*256*/
 struct Capture capture[128];    /*1024*/
 struct Player players[8];       /*64*/
 u8 io[512];                    /*512*/
 struct Control control;         /*128*/
};
_Static_assert(sizeof(struct LockOnlyRuntime)==6144,"lock-only alternative6KiB ceiling");
#endif
