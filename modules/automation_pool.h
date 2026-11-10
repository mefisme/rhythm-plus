#ifndef RHYTHM_PLUS_AUTOMATION_POOL_H
#define RHYTHM_PLUS_AUTOMATION_POOL_H
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
struct Pattern {
 u16 head,tail,count;
 u8 blocks,flags,continuous[2],locks[8];
 u16 reserved;
 u32 generation;
};
struct Pool {
 struct Pattern patterns[64];
 u16 next[224];
 u32 used[7],dirty[7],generation,config;
};
_Static_assert(sizeof(struct Pattern)==24,"pattern directory size");
_Static_assert(sizeof(struct Pool)==2048,"allocator metadata ceiling");
#endif
