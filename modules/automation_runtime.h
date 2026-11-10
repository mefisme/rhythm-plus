#ifndef RHYTHM_PLUS_AUTOMATION_RUNTIME_H
#define RHYTHM_PLUS_AUTOMATION_RUNTIME_H
#include "automation_pool.h"
/* Layout budget only; no installed firmware owns or enables this object yet. */
struct Capture {u32 event,context;}; /* Context includes pattern and project epoch. */
struct Player {u16 held,last,output;u8 destination,flags;};
struct Control {
 u32 magic,epoch,record,flags,queue_head,queue_tail,published_generation;
 u8 active_pattern[8];
 u16 cache_count[8],cache_start[8];
 u32 captured_target[3],save_record,save_observer,save_service;
 u32 snapshot_generation,write_offset,crc;
 u8 token[12],save_phase,error;
 u16 reserved;
 u32 counters[2];
};
struct AutomationRuntime {
 struct Pool pool;               /* 2048 */
 u32 lookahead[8][80];           /* 2560: four steps x max20 events */
 u32 edit[384];                  /* 1536: one bounded pattern */
 struct Capture capture[128];    /* 1024:128 contextual commands, NOT256 */
 u32 io[64];                    /* 256: two32-DSP-word ARM staging halves */
 struct Player players[8][10];  /* 640: held/last/output for assigned controls */
 struct Control control;         /* 128 */
};
_Static_assert(sizeof(struct Capture)==8,"capture context must be budgeted");
_Static_assert(sizeof(struct Player)==8,"player state budget");
_Static_assert(sizeof(struct Control)==128,"control/save context budget");
_Static_assert(sizeof(struct AutomationRuntime)==8192,"hard8KiB runtime ceiling");
#endif
