/* Grid FX sends and the FX track (Rhythm Plus, MIT): in the Mixer and Grid FX views, a third knob page past the pans, one send a
   track into Grid FX; one track can be the FX track, whose steps turn Grid FX pads on and off (after Circuit Remix's fxseq, by its
   author, MIT). Built by gfxmix.py, which passes the addresses below with -D. */
#include <stdint.h>
#if TASK_GUARD
#include "rp_task_guard.h"
#endif
#ifndef GFX_OVERDUB
#define GFX_OVERDUB 0
#endif

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;

#define R32(a) (*(volatile u32 *)(a))
#define R16(a) (*(volatile u16 *)(a))
#define R8(a) (*(volatile u8 *)(a))
#define FN(a) ((u32)(a) | 1)

typedef u8 *(*get_fn)(u32 store, u32 item);
typedef u32 (*hook_fn)(u32, u32, u32, u32);
typedef void (*wr_fn)(u32 core, u32 value, u32 addr);
typedef u32 (*u32_fn)(void);
typedef void (*set_fn)(u32 obj, u32 group, u32 index, u32 value);
typedef void (*gset_fn)(u32 obj, u32 id, u32 value);
typedef void (*sync_fn)(u32 t, u32 index, u32 value);

#define PARAM_GET ((get_fn)FN(0x0803FC58))
#define WR16 ((wr_fn)FN(0x08031200))        /* (core, word << 8, address): a DSP word; address bit 15 = Y */
#define RRT ((u32_fn)FN(C_RRT))
#define CIOK ((u32_fn)FN(C_CIOK))
#define GETTER ((u32 (*)(u32, u32))FN(0x08046410))   /* (group, index): a parameter's value */
#define SETTER ((set_fn)FN(0x08031A38))
#define SET_OBJ 0x20010E10u
#define GSET ((gset_fn)FN(0x08038A08))
#define GSET_OBJ 0x20011998u
#define PCSYNC ((sync_fn)FN(C_PCSYNC))     /* pageclear's: the views' copy of a track parameter */
#define UNLOCK ((void (*)(u32))FN(0x08030EB8))
#define RELOAD ((void (*)(u32))FN(0x08048932)) /* the stock's pattern load: the edit stores from the pattern */
#define SM_SELTRK ((u32 (*)(u32))FN(0x0805800E)) /* (CONT): Sample mode's track, 8 = none */

#define CTRL 0x200487C8u
#define O_VIEW 0x7C
#define O_HELD 0xA0
#define O_DIMS 0x88
#define CONT 0x20048B9Cu
#define O_SELTRK 0x25C
#define O_MODE 0x264
#define MODE_SAMPLES 0                      /* a track's sample view */
#define MODE_SMP 9                          /* Sample mode */
#define MODE_NOTE 1
#define MODE_GATE 3
#define MODE_VEL 2
#define MODE_NOTE2 7                        /* Note pressed twice */
#define KNOBS (CONT + 0x1C4)                /* [+ 4 t]: track t's knob object; its vtable + KO_TURN = (obj, knob, delta), recording */
#define KO_TURN 0x10
#define GFX_MODE (MIX_VIEW + 0x1CC)         /* [ ]: the store, p0 = 2 the Mixer, 7 Grid FX */
#define MODE_GFX 7
#define MODE_SET ((u32 (*)(u32, u32))FN(0x0804D6B6))       /* (CONT, mode): the view to show, -1 = none */
#define VIEW_SET ((void (*)(u32, u32, u32, u32))FN(0x0803DEBC)) /* (ctrl, view, button, 0): as the stock's view buttons */
#define ENGINE 0x2003D2FCu
#define O_RECS 0x84                         /* [ENGINE + O_RECS + 4 t]: track t's recorder: [+ 4] its patterns, p0 of [+ 0x28] the one shown */
#define MIX_VIEW 0x2004E090u                /* the Mixer and Grid FX */
#define PAGES (MIX_VIEW + 0x13C)            /* the Mixer's knob pages */
#define PAGE_GET ((u32 (*)(u32))FN(0x0805A4CE)) /* (PAGES): 0 the pans, 1 the levels, 2.. Grid FX's effect pages */
#define PANS 0
#define FX_PAGE 2                           /* and up: a held Grid FX effect's settings */
#define ID_SAMPLES 8
#define ID_NOTE 9
#define ID_VEL 10
#define ID_DOWN 19
#define ID_UP 20
#define BIT_CLEAR 23
#define ID_PLAY 17
#define ID_SHIFT 27
#define O_SHIFT 0xC                         /* [ctrl + 0xC] p0 = Shift held */
#define ENG 0x2003C380u                      /* the song engine; [+0xC] its vtable ENG_VT, [+0x90] p0 = the song position in pulses */
#define ENG_VT 0x08066B80u
#define ENG_POS 0x90
#define SONG_STOP 0x08033EAEu                /* (engine + 0xC, force): stock stop, retaining its position */
#define SONG_CONTINUE 0x08033E04u            /* (engine + 0xC, force): stock continue from its position */
#define LOCATE 0x08034082u                   /* (engine, pulses): the stock's locate (scene chain, each track's chain) */
#define PULSES 6                            /* a step */
#define TRANSPORT 0x200122B0u                /* p0 = playing */
#define ENG_CLK 0x14                        /* [eng + 0x14]: the clock's position object; vt[0](obj, 16th % 32), as the stock's
                                               Song Position does when stopped */
#define TAP_MS 300                          /* Shift + Play let go sooner, with no K1 turn: a tap */
#define ENG_TPOS 0x30                       /* [eng + 0x30 + 4t]: track t's position store: p0 its chain slot, p1 its step */
#define ENG_SCENES 0xA0                     /* p0 the scene chain's first, p1 its last */
#define ENG_CHAINS 0x9C                     /* item t: track t's live chain (one scene) */
#define ENG_SCDATA 0x24                     /* the scenes' object */
#define TRK_LEN 0x08034268u                 /* (eng, t, chain start | end << 8) = its chain's length in pulses */
#define SC_START 0x08033242u                /* (scenes, scene, t): its chain's first pattern */
#define SC_END 0x08033262u
#define LED_DOWN 51
#define LED_UP 52
#define LED_KNOB0 60
#define LED_NOTE (LED_TRK0 + ID_NOTE)
#define LED_VEL (LED_TRK0 + ID_VEL)
#define FRAME_PULSE 0x0A                    /* the palette entry the stock pulses */
#define DIM_MUL 141
#define GX_RGB 0xFFAF2Fu                    /* the stock's light for a view button on its second view */
#define LVL_ZERO 24                         /* of 255: a send at 0 */
#define FULL 127
#define READY 0xA0                          /* dspready's byte: the DSP running */
#define WAIT 200                            /* frames after READY before the first write */
#define ROUND 8                             /* one track written again every ROUND frames */

#define MGR 0x200438ACu                     /* Grid FX: [+ 0xC] the slots the project saves, + 0x1D8 the live slots */
#define GFX_TBL (MGR + 0x1D8)               /* 16 slots, 7 B: the type (0-6), the macros */
#define COLT 0x08062B30u                    /* a type's palette code, u16 */
#define COLOURS 0x20003974u
#define HAL_TICK 0x20006F3Cu
#define PLAYERS 0x200470D4u
#define PLAYER_SZ 0x190
#define O_PATS 0x50
#define O_SAMPLE 0x60                       /* [ ]: the store, p0 = the track's sample */
#define PAT_SZ 0xA28
#define STEPOBJ (CONT + 0x74)               /* [+ 4 t]: the step object: [+ 0xC] its step store, p0 of [+ 0x60] the page, p1 of [+ 0x64] the held step */
#define O_ST1 0xC
#define O_SVPAGE 0x60
#define O_SVHELD 0x64
#define WPTR ((u8 *(*)(u32, u32))FN(0x0803FD26))   /* (store, item): the item to write */
#define COMMIT ((void (*)(u32))FN(0x0803FBEC))     /* (store): the writes into the pattern */
#define NTYPES 7
#define NSLOTS 16
#define PAD_FX 7                            /* Sample mode's pad 8 */
#define PAD_SLOT0 16
#define GRP_TRK 0x10
#define K_IDX 6                             /* a track's K1-K8: its group's 6..13 */
#define K1_LO 4                             /* K1 (the pitch) is held in 4..124 */
#define K1_HI 124
#define NONE 0xFF
#define PEND_ON 1
#define STOP_MS 300                         /* no players' tick for this long: the sequencer stopped, the gates end */
#define SPEED_TAB 0x08068D9Cu               /* u32 [8]: a track speed's ticks a step; a note = that * gate / 6 ticks */
#define O_SPEED 0x10                        /* [ ]: the player's store, p1 = its speed */
#define FX_DIM 48                           /* of 255: pad 8 with no FX track */
#define ARROW_DIM 40
#define CLR_CUE 0x54                        /* palette: the stock's dim red (Clear held: what it clears) */
#define CLR_RED 0x55
#define FLASH_MS 384                        /* Clear + pad 8: three red flashes, 64 ms on, 64 ms off */
#define C_BLUE 0x18                         /* palette: the stock's step, and its step with a flip (pink) */
#define C_PINK 0x67

/* the Grid FX view's pads (vtable [0] press (obj, slot, velocity), [1] release (obj, slot)), its held flags (p0 of item s), and
   its settings knobs (0x0805EC26 (obj, knob, delta); 0x08052108 (obj) = their 8 light codes) */
#define GFX_PADS (MIX_VIEW + 0x15C)
#define GFX_HELD (PAGES + 0xC)
#define GFX_SET (MIX_VIEW + 0x94)
#define SET_KNOB ((void (*)(u32, u32, u32))FN(0x0805EC26))
#define SET_LEDS ((volatile u16 *(*)(u32))FN(0x08052108))
#define WHITE 0xFFFFFFu
#define SM_SHOWN(f) (((f) & 17) == 1)       /* stepmut's settings page on the screen */
#define MS_OPEN 1                           /* mutset's flags: its settings page open (the track buttons are its) */
#define LED_TRK0 32
#define LED_MIX 46                          /* the Mixer / Grid FX button (id 14) */
#define MARK_LVL 104                        /* of 255: the FX track's button, and the Mixer button off its view */

/* a step's effects: its slots (bits 0-15) and flags, kept in the project's tail apart from the track's own data. No slots: the
   track's sample's slot (the FX track's sample is the pad selected last) */
#define P_LANES 0x128
#define LANE_SZ 0xC0
#define NLANES 12
#define F_RANDOM (1u << 16)                 /* one of the step's slots (all slots with a type when none) */
#define F_REPEAT (1u << 17)                 /* the slots of the step before */
#define F_LANE 0x3FFFFu
#define F_HIT (1u << 31)                    /* not kept: the step has a hit */
#define NO_HIT 0xFE                         /* flip_at: no hit (a flip is 0..63, or 0xFF none) */
/* the steps' codes at PK_OFF: "GQ", check, the track they are for, then 8 patterns x 32 steps x 6 bits: 0 none, 1-16 one slot,
   17-63 a set; the sets at PS_OFF: "GS", check, 0, then 47 x (slots low, high, flags: 1 random, 2 repeat) */
#define PK_N (NPATS * NSTEPS)
#define PK_LEN (4 + PK_N * 6 / 8)
#define NSETS 47
#define PS_LEN (4 + NSETS * 3)
#define C_SET0 17
#define NO_SET 0xFF
#define VEL_NEW 0x60                        /* the stock's new step */
#define PROB_ALL 7
#define NPATS 8
#define NSTEPS 32
static const u8 STEP_NEW[8] = { 0, 6, 0, 0, PROB_ALL, 0xFF, 0, 0 };  /* a cleared step */

static const u8 BASEID[NTYPES] = { 0xA9, 0xAC, 0xAE, 0xB0, 0xB7, 0xBA, 0xBF };  /* a type's on id; its macros follow */
static const u8 NPAR[NTYPES] = { 3, 2, 2, 7, 3, 5, 5 };

/* the project block: "GX", check, version, 8 sends; v2: the FX track (NONE), its K1-K8 from before */
#define BLK_V1 12
#define BLK_V2 24
#define BLK_LEN 26
#define VERSION 3
#define O_CONTROLS 23                       /* three 7-bit values; bit 7 of the first = audition off */
#define O_SENDS 4
#define O_FXTRK 12
#define O_SAVED 13
#define O_TSMP 21                           /* the FX track's own sample, while it is the FX track */
#define O_FXSMP 22                          /* its pad selected last, while it is not */

#define SHOWN 1                             /* page: the sends shown */
#define JUMP 2                              /* page: Up from the sends went to the held effect's settings; Down comes back */

#define NLOG 32
struct slot {                               /* SLOT, 108 B */
    u8 page, wait, frame, next;
    u8 sent[8];                             /* the send last written + 1; 0 = not yet */
    u32 step_fx;                            /* the step that starts: its slots and flags */
    u16 on, last;                           /* the slots the sequence turned on; the ones before */
    u8 pend, busy, inpad, set;              /* inpad: the stock's pad handling runs (its notes are previews); set: the knobs are settings */
    u8 pstep, pedit, ask, taken;            /* the step pad down: its step + 1; pedit: keep = its effects; pad 8 asks: track + 1 */
    u16 gdown, ask_t0;                      /* the Grid FX pads down (played live) */
    u32 keep;
    u16 dur, tick_at;                       /* the step's gate in the players' ticks; the last tick's time */
    u16 rem[NSLOTS];                        /* a slot's gate: ticks left, 0 = not playing */
    u8 age[NSLOTS];                         /* the clock when its step started */
    u8 play[NTYPES], clock;                 /* a type's engine: the slot it plays + 1, 0 = off */
    u8 cur_step, cur_pat, wpat, pflip;      /* the step playing; the recording window's pattern; the step pad down: its flip before */
    u8 sweep, pkok, wgrace, pcnt;           /* the next code checked for a step deleted; the tail's blocks found ours (bit 0 codes,
                                               1 sets); steps since the window's last pad let go; the Grid FX presses counted */
    u32 snapv, joined;                      /* the window's steps (bit st); the ones it gave pads */
    u16 snap[NSTEPS];                       /* a window step's 8 bytes hashed, at the first press near it */
    u8 sflip[NSTEPS];                       /* its flip then (NO_HIT: no step) */
    u8 prstep[NSLOTS];                      /* a Grid FX pad's step + 1 at its last press while playing, 0 none */
    u8 pord[NSLOTS];                        /* pcnt at a Grid FX pad's last press */
    u8 endst, firstst, lgn, pkver;          /* the last jump back while playing: the step before it + 1 (0 none), the step after;
                                               pkver: counts the tail's effect writes */
    u32 lg[NLOG];                           /* the pads' last events, lgn the next: ms << 16 | velocity << 8 | down << 6 | pad */
    u16 gdur[NSLOTS];                       /* a slot's gate in ticks, as its step started */
    u8 sstep[NSLOTS];                       /* scount as its step started */
    u16 tkstep;                             /* the FX track's ticks a step */
    u8 scount, pad3_;                       /* the FX track's steps counted */
    u8 scr, smoved, spass, shup;            /* Shift + Play held (scrub); K1 turned meanwhile; our own Shift + Play sent;
                                               Shift let go during it */
    u32 sdown;                              /* HAL_TICK ms at its press */
    u32 spos;                               /* a stopped scrub's place in pulses, for the next Shift + Play */
    u8 spend, spg, sedge, sresume;                /* spos waiting; shown page + 1; held boundary; resume when moved inward */
    u8 saoff, samask, sanote[8], sapad[2];   /* stopped audition: default on, active tracks, their notes */
    u32 saat;                              /* last audition time (HAL ms) */
    u16 audown;                            /* sequencer pads actually dispatched to live Grid FX */
    u8 csent[3], cpad[3];                   /* routing controls last sent + 1 */
    u8 cright[4], cleft[4];                 /* native Clear turn counters (40 clicks) */
};
#define S ((volatile struct slot *)SLOT)
_Static_assert(sizeof(struct slot) == 344 + 4 * NLOG, "the slot's size");

static u32 held(void) { return R32(CTRL + O_HELD); }
static int on_mixer(void) { return R32(CTRL + O_VIEW) == MIX_VIEW; }
static u32 stock_page(void) { return PAGE_GET(PAGES); }

static u32 blk_len(const volatile u8 *b) { return b[3] == 1 ? BLK_V1 : b[3] == 2 ? BLK_V2 : BLK_LEN; }
static u8 blk_sum(const volatile u8 *b)
{
    u32 s = 0, n = blk_len(b);
    for (u32 i = 4; i < n; i++)
        s += b[i];
    return (u8)(s ^ 0x5C);
}
static int blk_ok(const volatile u8 *b)
{
    return b[0] == 'G' && b[1] == 'X' && (b[3] >= 1 && b[3] <= VERSION) && b[2] == blk_sum(b);
}
static const volatile u8 *blk(void)
{
    u32 tail = RRT();
    const volatile u8 *b = (const volatile u8 *)(tail + BLK_OFF);
    return tail && blk_ok(b) ? b : 0;
}
static u32 fx_track(void)
{
    const volatile u8 *b = blk();
    return b && b[3] >= 2 && b[O_FXTRK] < 8 ? b[O_FXTRK] : NONE;
}
static void blk_put(u32 i, u32 v)           /* byte i of the block, the block made ours (v2) first */
{
    u32 tail = RRT();
    if (!tail)
        return;
    volatile u8 *b = (volatile u8 *)(tail + BLK_OFF);
#if TASK_GUARD
    u32 guard = rp_task_lock();
#else
    __asm volatile("cpsid i" ::: "memory");
#endif
    if (!blk_ok(b)) {
        for (u32 k = 0; k < 8; k++)
            b[O_SENDS + k] = FULL;
        b[0] = 'G'; b[1] = 'X'; b[3] = 1;
    }
    if (b[3] == 1) {
        for (u32 k = BLK_V1; k < BLK_V2; k++)
            b[k] = 0;
        b[O_FXTRK] = NONE;
        b[3] = 2;
    }
    if (b[3] == 2) {
        for (u32 k = 0; k < 3; k++)
            b[O_CONTROLS + k] = FULL;
        b[3] = VERSION;
    }
    b[i] = (u8)v;
    b[2] = blk_sum(b);
#if TASK_GUARD
    rp_task_unlock(guard);
#else
    __asm volatile("cpsie i" ::: "memory");
#endif
}

static u32 control_base(u32 k)
{
    const volatile u8 *b = blk();
    return b && b[3] == VERSION ? k == 3 ? b[O_CONTROLS] >> 7 : b[O_CONTROLS + k] & 127 : k == 3 ? 0 : FULL;
}
#if AUTOMATION3
__attribute__((naked,noinline)) u32 c_gx_autovalue(u32 k,u32 base)
{ __asm__ volatile("mov r0,r1\n bx lr"); }
#if REC_FEEDBACK
__attribute__((naked,noinline)) u32 c_gx_autodisplay(u32 k,u32 base)
{ __asm__ volatile("mov r0,r1\n bx lr"); }
#endif
#endif
static u32 control_get(u32 k) {
#if AUTOMATION3
    if(k<3)return c_gx_autovalue(k,control_base(k));
#endif
    return control_base(k);
}
static u32 control_edit(u32 k) {
#if REC_FEEDBACK
    if(k<3)return c_gx_autodisplay(k,control_get(k));
#endif
    return control_get(k);
}
static void control_store(u32 k, u32 v)
{
    u32 first = control_base(0) | control_base(3) << 7;
    blk_put(O_CONTROLS + (k == 3 ? 0 : k), k == 3 ? (first & 127) | v << 7 : k == 0 ? (first & 128) | v : v);
}
#if AUTOMATION3
/* Replaced by the independent RAM engine after both modules are linked. */
__attribute__((naked,noinline)) void c_gx_autotouch(u32 k,u32 value,u32 clear)
{ __asm__ volatile("movs r0,#0\n bx lr"); }
u32 c_gx_autofx(void) { return fx_track(); }
#if AUTO_BULK
__attribute__((naked,noinline)) void c_gx_autotrackclear(u32 t)
{ __asm__ volatile("movs r0,#0\n bx lr"); }
void c_gx_autodefaults(void){for(u32 k=0;k<3;k++)control_store(k,FULL);}
#endif
#if REC_FEEDBACK
__attribute__((naked,noinline)) u32 c_gx_autored(u32 k)
{ __asm__ volatile("movs r0,#0\n bx lr"); }
#endif
#endif
/* the FX track's knob k = track k's send */
static u32 knob_get(u32 t, u32 k) { return GETTER(GRP_TRK + t, K_IDX + k) & 0x7F; }
static void knob_put(u32 t, u32 k, u32 v)
{
    SETTER(SET_OBJ, GRP_TRK + t, K_IDX + k, v);
    PCSYNC(t, K_IDX + k, v);
}
static u32 knob_send(u32 k, u32 v)
{
    if (k)
        return v;
    return v <= K1_LO ? 0 : v >= K1_HI ? FULL : ((v - K1_LO) * FULL + 60) / (K1_HI - K1_LO);
}
static u32 send_knob(u32 k, u32 v) { return k ? v : K1_LO + (v * (K1_HI - K1_LO) + 63) / FULL; }

static u32 send_of(u32 t)
{
    u32 fx = fx_track();
    if (fx != NONE)
        return knob_send(t, knob_get(fx, t));
    const volatile u8 *b = blk();
    return b ? b[O_SENDS + t] : FULL;
}

/* a stock store and its two buffers in RAM: 0 while not built yet (a cold start's random words) */
static int in_ram(u32 a) { return a - 0x20000000u < 0x50000u; }
static int built(u32 st) { return in_ram(st) && in_ram(R32(st + 0xC)) && in_ram(R32(st + 0x10)); }

/* ---- the steps' effects in the tail */
static u8 pk_sum(const volatile u8 *b, u32 n)
{
    u32 s = 0;
    for (u32 i = 3; i < n; i++)
        s += b[i];
    return (u8)(s ^ 0x5C);
}
static volatile u8 *pk_blk(u32 off, u32 mark, u32 n)   /* the block, or 0 when not ours */
{
    u32 tail = RRT();
    volatile u8 *b = (volatile u8 *)(tail + off);
    return tail && b[0] == 'G' && b[1] == mark && b[2] == pk_sum(b, n) ? b : 0;
}
static u32 pk_code(const volatile u8 *b, u32 i)
{
    u32 bit = 6 * i, at = 4 + (bit >> 3), w = b[at] | (at + 1 < PK_LEN ? b[at + 1] << 8 : 0);
    return w >> (bit & 7) & 63;
}
static void sum_poke(volatile u8 *b, u32 at, u32 v)   /* byte at of a block whose check byte is right: it stays right */
{
    b[2] = (u8)((((b[2] ^ 0x5Cu) + v - b[at]) & 0xFF) ^ 0x5Cu);
    b[at] = (u8)v;
}
static void pk_setcode(volatile u8 *b, u32 i, u32 c)
{
    u32 bit = 6 * i, at = 4 + (bit >> 3), w = b[at] | (at + 1 < PK_LEN ? b[at + 1] << 8 : 0);
    w = (w & ~(63u << (bit & 7))) | c << (bit & 7);
    sum_poke(b, at, w & 0xFF);
    if (at + 1 < PK_LEN)
        sum_poke(b, at + 1, w >> 8);
}
static void pk_check(void) { S->pkok = (u8)((pk_blk(PK_OFF, 'Q', PK_LEN) ? 1 : 0) | (pk_blk(PS_OFF, 'S', PS_LEN) ? 2 : 0)); }
static const volatile u8 *pk_codes(u32 t)   /* as pk_check found them at the last LED frame, or since our last write */
{
    u32 tail = RRT();
    const volatile u8 *b = (const volatile u8 *)(tail + PK_OFF);
    return tail && S->pkok & 1 && b[0] == 'G' && b[1] == 'Q' && b[3] == t ? b : 0;
}
static const volatile u8 *pk_sets(void)
{
    u32 tail = RRT();
    return tail && S->pkok & 2 ? (const volatile u8 *)(tail + PS_OFF) : 0;
}
static u32 pk_fx(const volatile u8 *sets, u32 c)
{
    if (c < C_SET0)
        return c ? 1u << (c - 1) : 0;
    if (!sets)
        return 0;
    const volatile u8 *e = sets + 4 + 3 * (c - C_SET0);
    return e[0] | e[1] << 8 | (e[2] & 1 ? F_RANDOM : 0) | (e[2] & 2 ? F_REPEAT : 0);
}
static u32 pk_get(u32 t, u32 pat, u32 st)   /* track t's step: its slots and flags */
{
    const volatile u8 *b = pk_codes(t);
    if (!b || pat >= NPATS || st >= NSTEPS)
        return 0;
    return pk_fx(pk_sets(), pk_code(b, pat * NSTEPS + st));
}
static volatile u8 *pk_make(u32 t)          /* the blocks ours, for track t: another track's codes cleared */
{
    u32 tail = RRT();
    if (!tail)
        return 0;
    volatile u8 *b = (volatile u8 *)(tail + PK_OFF), *s = (volatile u8 *)(tail + PS_OFF);
    if (!pk_blk(PS_OFF, 'S', PS_LEN)) {
        for (u32 i = 3; i < PS_LEN; i++)
            s[i] = 0;
        s[0] = 'G'; s[1] = 'S';
        s[2] = pk_sum(s, PS_LEN);
        S->pkver++;
    }
    if (!pk_blk(PK_OFF, 'Q', PK_LEN) || b[3] != t) {
        for (u32 i = 4; i < PK_LEN; i++)
            b[i] = 0;
        b[0] = 'G'; b[1] = 'Q'; b[3] = (u8)t;
        b[2] = pk_sum(b, PK_LEN);
        S->pkver++;
    }
    S->pkok = 3;
    return b;
}
/* fx's code for code i: one slot, an equal set, a free set (*fill = its index, to be written), or NO_SET. Reads only. */
static u32 pk_pick(const volatile u8 *b, const volatile u8 *s, u32 fx, u32 i, u32 *fill)
{
    u32 m = fx & 0xFFFF, fl = (fx & F_RANDOM ? 1u : 0) | (fx & F_REPEAT ? 2u : 0), used[2] = { 0, 0 }, free_ = NO_SET;
    *fill = NO_SET;
    if (!fl && !(m & (m - 1)))
        return m ? 1u + (u32)__builtin_ctz(m) : 0;
    for (u32 k = 0; k < PK_N; k++) {
        u32 c = k == i ? 0 : pk_code(b, k);
        if (c >= C_SET0)
            used[(c - C_SET0) >> 5] |= 1u << ((c - C_SET0) & 31);
    }
    for (u32 k = 0; k < NSETS; k++) {
        const volatile u8 *e = s + 4 + 3 * k;
        if (!(used[k >> 5] >> (k & 31) & 1)) {
            if (free_ == NO_SET)
                free_ = k;
        } else if (e[0] == (m & 0xFF) && e[1] == m >> 8 && e[2] == fl) {
            return C_SET0 + k;
        }
    }
    if (free_ == NO_SET)
        return NO_SET;
    *fill = free_;
    return C_SET0 + free_;
}
/* all 47 sets in use: the step keeps what it had. The search runs with interrupts on (the pads' scan needs them); a write
   between it and the short write below (pkver) starts it again. */
static void pk_put(u32 t, u32 pat, u32 st, u32 fx)
{
    if (pat >= NPATS || st >= NSTEPS)
        return;
    u32 i = pat * NSTEPS + st, m = fx & 0xFFFF, fl = (fx & F_RANDOM ? 1u : 0) | (fx & F_REPEAT ? 2u : 0);
    for (u32 n = 0; n < 4; n++) {
        u32 ver = S->pkver, fill;
        volatile u8 *b = pk_make(t), *sb = (volatile u8 *)(RRT() + PS_OFF);
        if (!b)
            return;
        u32 c = pk_pick(b, sb, fx, i, &fill);
        __asm volatile("cpsid i" ::: "memory");
        if (S->pkver == ver) {
            if (fill != NO_SET) {
                sum_poke(sb, 4 + 3 * fill, m & 0xFF);
                sum_poke(sb, 5 + 3 * fill, m >> 8);
                sum_poke(sb, 6 + 3 * fill, fl);
            }
            if (c != NO_SET)
                pk_setcode(b, i, c);
            S->pkver++;
            __asm volatile("cpsie i" ::: "memory");
            return;
        }
        __asm volatile("cpsie i" ::: "memory");
    }
}
static void pk_clear(u32 t)
{
    if (!pk_codes(t))
        return;
    volatile u8 *b = (volatile u8 *)(RRT() + PK_OFF);
    __asm volatile("cpsid i" ::: "memory");
    b[0] = 0;                               /* read as no effects meanwhile */
    S->pkver++;
    __asm volatile("cpsie i" ::: "memory");
    for (u32 i = 4; i < PK_LEN; i++)
        b[i] = 0;
    __asm volatile("cpsid i" ::: "memory");
    b[2] = pk_sum(b, 4);
    b[0] = 'G';
    S->pkver++;
    __asm volatile("cpsie i" ::: "memory");
}

/* ---- the Grid FX slots */
static volatile u8 *slot_row(u32 s) { return (volatile u8 *)(GFX_TBL + 7 * s); }
static u32 slot_type(u32 s) { return slot_row(s)[0]; }
static void gfx_set(u32 id, u32 v)
{
#ifdef DSP_RETRIGGER
    if(id==0xa9 && !v)WR16(0,0,DSP_RETRIGGER);
#endif
    SETTER(SET_OBJ, 0x20, id - 0x9F, v);
    GSET(GSET_OBJ, id, v);
}
static void slot_macros(u32 s)
{
    u32 ty = slot_type(s);
    const volatile u8 *r = slot_row(s);
    for (u32 k = NPAR[ty] - 1u; k; k--)
        gfx_set(BASEID[ty] + k, r[k]);
}
static void slot_onoff(u32 s, u32 on)       /* the macros first, then the type's on */
{
    u32 ty = slot_type(s);
    if (ty >= NTYPES)
        return;
    if (on)
        slot_macros(s);
    gfx_set(BASEID[ty], on);
}
static u32 typed(void)
{
    u32 m = 0;
    for (u32 s = 0; s < NSLOTS; s++)
        if (slot_type(s) < NTYPES)
            m |= 1u << s;
    return m;
}
static u32 one_type_each(u32 m)             /* two slots of one type share its engine: the higher one plays */
{
    u32 seen = 0, out = 0;
    for (s32 s = NSLOTS - 1; s >= 0; s--)
        if (m >> s & 1) {
            u32 ty = slot_type((u32)s);
            if (ty < NTYPES && !(seen >> ty & 1)) {
                seen |= 1u << ty;
                out |= 1u << s;
            }
        }
    return out;
}
static u32 pick_one(u32 m)
{
    u32 n = 0;
    for (u32 s = 0; s < NSLOTS; s++)
        n += m >> s & 1;
    if (!n)
        return 0;
    u32 k = ((R32(HAL_TICK) * 0x9E3779B1u) >> 24) * n >> 8;
    for (u32 s = 0; s < NSLOTS; s++)
        if (m >> s & 1 && !k--)
            return 1u << s;
    return 0;
}
static u32 gfx_held(void)                   /* the Grid FX pads held or latched (the stock's flags) */
{
    u32 st = R32(GFX_HELD), m = 0;
    if (!built(st))
        return 0;
    for (u32 s = 0; s < NSLOTS; s++)
        if (*PARAM_GET(st, s))
            m |= 1u << s;
    return m;
}
static u32 live_types(void)
{
    u32 m = 0, h = gfx_held();
    for (u32 s = 0; s < NSLOTS; s++)
        if (h >> s & 1 && slot_type(s) < NTYPES)
            m |= 1u << slot_type(s);
    return m;
}
/* each type's engine plays the newest of its slots whose gate runs; the types held on the pads are left to the stock */
static void types_to(u32 retrig)            /* retrig: the types a step starts afresh (off, then on) */
{
    u32 live = live_types(), on = 0;
    for (u32 ty = 0; ty < NTYPES; ty++) {
        u32 newest = 0, best = 0x100;
        for (u32 s = 0; s < NSLOTS; s++)
            if (S->rem[s] && slot_type(s) == ty && (u8)(S->clock - S->age[s]) < best) {
                best = (u8)(S->clock - S->age[s]);
                newest = s + 1;
            }
        u32 cur = S->play[ty];
        S->play[ty] = (u8)newest;
        if (newest)
            on |= 1u << (newest - 1);
        if (live >> ty & 1)
            continue;
        if (!newest) {
            if (cur)
                gfx_set(BASEID[ty], 0);
        } else if (retrig >> ty & 1) {
            if (cur)
                gfx_set(BASEID[ty], 0);
            slot_onoff(newest - 1, 1);
#ifdef DSP_RETRIGGER
            if(ty==0) {
                const volatile u8 *r=slot_row(newest-1);
                if(r[1]<12) {
                    u32 command=((const u8 *)0x08030e74)[r[1]]+1u | ((127u-r[2])&255u)<<8;
                    WR16(0,command<<8,DSP_RETRIGGER);
                }
            }
#endif
        } else if (newest != cur) {
            if (cur)
                slot_macros(newest - 1);    /* a takeover: the engine keeps running */
            else
                slot_onoff(newest - 1, 1);
        }
    }
    S->on = (u16)on;
}
static void step_start(void)                /* a note of the FX track: its slots for its gate */
{
    if (S->scr)
        return;                             /* scrubbing: no effects */
    u32 fx = S->step_fx, m = fx & 0xFFFF, retrig = 0;
    if (fx & F_REPEAT)
        m = S->last;
    else if (fx & F_RANDOM)
        m = pick_one(m ? m & typed() : typed());
    m = one_type_each(m);
    S->last = (u16)m;
    S->clock++;
    for (u32 s = 0; s < NSLOTS; s++) {
        if (!(m >> s & 1))
            continue;
        u32 ty = slot_type(s), going = 0;
        for (u32 o = 0; o < NSLOTS && ty < NTYPES; o++)   /* only a gate past this step's start plays through */
            going |= slot_type(o) == ty && (S->rem[o] || S->play[ty] == o + 1u)
                     && S->gdur[o] > (u32)S->tkstep * (u8)(S->scount - S->sstep[o]);
        if (!going)
            retrig |= 1u << ty;
        S->rem[s] = S->gdur[s] = S->dur;
        S->age[s] = S->clock;
        S->sstep[s] = S->scount;
    }
    types_to(retrig);
}
static u32 sample_raw(u32 t) { u32 st = R32(PLAYERS + PLAYER_SZ * t + O_SAMPLE); return built(st) ? *PARAM_GET(st, 0) : 0; }
static u32 track_sample(u32 t) { return sample_raw(t) & 15; }

static void sample_put(u32 t, u32 v)
{
    u32 st = R32(PLAYERS + PLAYER_SZ * t + O_SAMPLE);
    *WPTR(st, 0) = (u8)v;
    COMMIT(st);
}

/* recording: a live press while playing opens a window on the step playing and the next. The stock writes the recorded step at
   the pad's release (its gate): a window step that changes gets the pads pressed on it or on the step before, in place of its
   pads from before on legacy builds, or merged with them on overdub builds, and its flip goes back to the track's. The window stays while a
   pad is held, and two steps after the last one is let go */
static volatile u8 *track_pats(u32 t);
static volatile u8 *win_pat(u32 t) { volatile u8 *p = track_pats(t); return p ? p + PAT_SZ * (S->wpat & 7) : 0; }
static u32 flip_at(const volatile u8 *p, u32 st) { return p[8 * st + 3] ? p[8 * st + 5] : NO_HIT; }
static u32 step_hash(const volatile u8 *p, u32 st)
{
    u32 h = 0;
    for (u32 i = 0; i < 8; i++)
        h = h * 31 + p[8 * st + i];
    return (u16)(h ^ h >> 16);
}
static int playing(void) { return (u16)((u16)R32(HAL_TICK) - S->tick_at) <= STOP_MS; }
static void rec_end(void)
{
    S->snapv = 0;
    S->joined = 0;
    for (u32 s = 0; s < NSLOTS; s++)
        S->prstep[s] = 0;
}
static void rec_note(const volatile u8 *p, u32 st)   /* a window step: its bytes before the stock's write */
{
    if (st >= NSTEPS || S->snapv >> st & 1)
        return;
    S->snap[st] = (u16)step_hash(p, st);
    S->sflip[st] = (u8)flip_at(p, st);
    S->snapv |= 1u << st;
}
static u32 put_pad(u32 m, u32 s)           /* one pad a type on a step: s in place of its type's other pads */
{
    u32 ty = slot_type(s);
    for (u32 o = 0; o < NSLOTS && ty < NTYPES; o++)
        if (o != s && slot_type(o) == ty)
            m &= ~(1u << o);
    return m | 1u << s;
}
static u32 put_pads(u32 m, u32 pads)        /* in the order pressed: the newest of a type stays */
{
    while (pads & 0xFFFF) {
        u32 first = 0, age = 0;
        for (u32 s = 0; s < NSLOTS; s++)
            if (pads >> s & 1 && (u8)(S->pcnt - S->pord[s]) >= age) {
                age = (u8)(S->pcnt - S->pord[s]);
                first = s;
            }
        m = put_pad(m, first);
        pads &= ~(1u << first);
    }
    return m;
}
static void live_press(u32 t, u32 s)
{
    if (!playing())
        return;
    if (S->snapv && S->wpat != S->cur_pat)
        rec_end();
    S->wpat = S->cur_pat;
    const volatile u8 *p = win_pat(t);
    if (!p)
        return;
    rec_note(p, S->cur_step);
    rec_note(p, S->cur_step + 1u);          /* a late press: the stock records it on the next step, */
    rec_note(p, S->firstst);                /* or the loop's first */
    S->prstep[s] = (u8)(S->cur_step + 1u);
    S->wgrace = 0;
}
static void flip_back(u32 t, u32 pat, u32 st, u32 flip);
static void rec_join(void)
{
    u32 t = fx_track();
    if (!S->snapv || t == NONE)
        return;
    volatile u8 *p = win_pat(t);
    if (!p)
        return;
    for (u32 st = 0; st < NSTEPS; st++) {
        if (!(S->snapv >> st & 1) || step_hash(p, st) == S->snap[st] || flip_at(p, st) == NO_HIT)
            continue;
        u32 pads = 0, before = 0, was = S->sflip[st];
        for (u32 s = 0; s < NSLOTS; s++) {
            pads |= (u32)(S->prstep[s] && S->prstep[s] - 1u == st) << s;
            before |= (u32)(S->prstep[s] && (S->prstep[s] == st || (st == S->firstst && S->prstep[s] == S->endst))) << s;
        }
        if (!pads)
            pads = before;                  /* pressed late on the step before, recorded on this one */
        if (pads) {
            /* Overdubs retain previous effect types and random/repeat flags.
               put_pads replaces only another slot of the same effect type. */
            u32 fx = GFX_OVERDUB || S->joined >> st & 1 ? pk_get(t, S->wpat, st) : 0;
            pk_put(t, S->wpat & 7, st, put_pads(fx, pads));
            flip_back(t, S->wpat & 7, st, was == NO_HIT ? 0xFF : was);
            S->joined |= 1u << st;
        }
        S->snap[st] = (u16)step_hash(p, st);
    }
}
static void rec_step(u32 step)              /* the players' next step: the window ends two steps after its last pad let go */
{
    if (!S->snapv)
        return;
    u32 near = 0;
    for (u32 s = 0; s < NSLOTS; s++)
        near |= S->prstep[s] && (S->gdown >> s & 1 || step == S->prstep[s] - 1u || step == S->prstep[s]
                                 || (step == S->firstst && S->prstep[s] == S->endst));
    S->wgrace = near ? 0 : (u8)(S->wgrace + 1);
    if (S->wgrace >= 2)
        rec_end();
}
static void ends_all(void)
{
    for (u32 s = 0; s < NSLOTS; s++)
        S->rem[s] = 0;
}
static void apply(void)                     /* the note-ons and the gates' ends, after the stock's lock */
{
    __asm volatile("cpsid i" ::: "memory");
    u32 busy = S->busy, p = S->pend;
    if (!busy) {
        S->busy = 1;
        S->pend = 0;
    }
    __asm volatile("cpsie i" ::: "memory");
    if (busy)
        return;
    if (S->on && !playing())
        ends_all();                         /* no ticks: the sequencer stopped */
    if (p == PEND_ON)
        step_start();
    else if (S->on)
        types_to(0);                        /* nothing on: the Grid FX view's objects not read (a cold start) */
    rec_join();
    S->busy = 0;
}

static int is_fx(u32 code) { return code >> 4 == 1 && (code & 15) == fx_track() && CIOK(); }

/* ---- the note-on head (code 0x10 + t, ...): 1 = the FX track's, kept from the DSP */
u32 c_gx_noteon(u32 code)
{
    if (!is_fx(code))
        return 0;
    if (!S->inpad)
        S->pend = PEND_ON;
    return 1;
}
/* ---- the players' tick (player, tick): the FX track's gates count down as the stock's notes do */
void c_gx_tick(u32 pl, u32 tick)
{
    if (!tick || (pl - PLAYERS) / PLAYER_SZ != fx_track())
        return;
    S->tick_at = (u16)R32(HAL_TICK);
    for (u32 s = 0; s < NSLOTS; s++)
        if (S->rem[s])
            S->rem[s]--;
}
/* ---- the note wrappers' release of the stock's lock */
void c_gx_unl(u32 guard)
{
    UNLOCK(guard);
    apply();
}

/* a step's slots and flags as it plays: its own, else the track's sample's (none with random) */
static u32 fx_of(u32 fx, u32 sample)
{
    if (!(fx & 0xFFFF) && !(fx & F_RANDOM))
        fx |= 1u << (sample & 15);
    return fx;
}
/* ---- the players' step start (player, pattern, step): the FX track's step's effects and gate in ticks (as the stock's notes) */
void c_gx_s4(u32 pl, u32 pat, u32 step)
{
    u32 t = (pl - PLAYERS) / PLAYER_SZ;
    if (t >= 8 || t != fx_track() || step >= NSTEPS)
        return;
    const volatile u8 *p = (const volatile u8 *)(R32(pl + O_PATS) + PAT_SZ * pat);
    S->step_fx = fx_of(pk_get(t, pat, step), track_sample(t));
    if (pat != S->cur_pat)
        S->endst = S->firstst = 0;
    else if (step + 1u < S->cur_step)
        S->endst = (u8)(S->cur_step + 1u), S->firstst = (u8)step;
    S->cur_step = (u8)step;
    S->cur_pat = (u8)pat;
    rec_step(step);
    u32 tk = R32(SPEED_TAB + 4 * (*PARAM_GET(R32(pl + O_SPEED), 1) & 7)), d = tk * p[8 * step + 1] / 6;
    S->tkstep = (u16)tk;
    S->scount++;
    S->dur = (u16)(d < 1 ? 1 : d > 0xFFFF ? 0xFFFF : d);
}

static u32 sel_track(void) { u32 st = R32(CONT + O_SELTRK); return built(st) ? *PARAM_GET(st, 0) & 7 : 0; }
static int on_cont(u32 mode) { return R32(CTRL + O_VIEW) == CONT && R8(CONT + O_MODE) == mode && !SM_SHOWN(R8(SM_SLOT)); }
static int fx_view(void)
{
    u32 fx = fx_track();
    return fx != NONE && on_cont(MODE_SAMPLES) && sel_track() == fx && !R8(TM_SLOT + TM_OPEN);
}
static u32 sm_random(u32 n) { return ((u32 (*)(void))FN(0x08047104))() % n; }

/* Step Mutate calls these with interrupts already disabled. Packed codes move
   verbatim, so even a full dictionary preserves combinations and random/repeat. */
u32 c_gx_smread(u32 t, u32 pat, u8 *codes)
{
    if (t != fx_track() || pat >= NPATS)
        return 0;
    pk_check();
    const volatile u8 *b = pk_codes(t);
    for (u32 st = 0; st < NSTEPS; st++) {
        u32 c = b ? pk_code(b, pat * NSTEPS + st) : 0;
        codes[st] = (u8)(c | (pk_fx(pk_sets(), c) & 0xFFFF ? 64 : 0));
    }
    return 1;
}
void c_gx_smwrite(u32 t, u32 pat, const u8 *codes)
{
    if (t != fx_track() || pat >= NPATS)
        return;
    volatile u8 *b = pk_make(t);
    if (!b)
        return;
    for (u32 st = 0; st < NSTEPS; st++)
        pk_setcode(b, pat * NSTEPS + st, codes[st] & 63);
    S->pkver++;
}
void c_gx_smsample(u32 t, u32 pat, u32 st, u32 range)
{
    if (t != fx_track() || pat >= NPATS || st >= NSTEPS)
        return;
    volatile u8 *b = pk_make(t), *sb = (volatile u8 *)(RRT() + PS_OFF);
    if (!b)
        return;
    u32 i = pat * NSTEPS + st, fx = pk_fx(sb, pk_code(b, i)), m = fx & 0xFFFF;
    u32 base = track_sample(t), old = base, n = 0, choices[16], count = 0;
    for (u32 s = 0; s < NSLOTS; s++)
        if (m >> s & 1) {
            n++;
            if (sm_random(n) == 0)
                old = s;
        }
    u32 width = range == 2 ? 8 : range == 3 ? 4 : 0;
    for (u32 s = 0; s < NSLOTS; s++) {
        u32 d = s > base ? s - base : base - s;
        u32 near = (s + NSLOTS - old) % NSLOTS, conflict = 0;
        for (u32 o = 0; o < NSLOTS; o++)
            if (o != old && m >> o & 1 && slot_type(o) == slot_type(s))
                conflict = 1;
        if (slot_type(s) < NTYPES && !conflict && s != old && !(m >> s & 1)
            && (!width || d <= width) && (range != 1 || near == 1 || near == NSLOTS - 1))
            choices[count++] = s;
    }
    if (!count)
        return;   /* no valid replacement: keep the existing effects */
    u32 pad = choices[sm_random(count)];
    u32 next = put_pad(fx & ~(1u << old), pad), fill;
    u32 c = pk_pick(b, sb, next, i, &fill);
    if (c == NO_SET)
        return;   /* dictionary full: preserve the original assignment */
    if (fill != NO_SET) {
        sum_poke(sb, 4 + 3 * fill, next & 0xFF);
        sum_poke(sb, 5 + 3 * fill, next >> 8 & 0xFF);
        sum_poke(sb, 6 + 3 * fill, (next & F_RANDOM ? 1 : 0) | (next & F_REPEAT ? 2 : 0));
    }
    pk_setcode(b, i, c);
    S->pkver++;
}

static u32 rec_of(u32 t) { return R32(ENGINE + O_RECS + 4 * t); }
static u32 shown_idx(u32 t) { u32 r = rec_of(t); return in_ram(r) && built(R32(r + 0x28)) ? *PARAM_GET(R32(r + 0x28), 0) & 7 : NPATS; }
#if REC_FEEDBACK
static u32 send_own(u32 t,u32 k) {
    u32 r=rec_of(t),so=R32(STEPOBJ+4*t);
    if(k>=8 || !in_ram(r) || !in_ram(so) || !built(R32(so+O_SVHELD)))return 255;
    u32 st=((u32 (*)(u32))FN(TM_HELD))(t),p=shown_idx(t);
    if(st>=32 || p>=8 || !in_ram(R32(r+4)))return 255;
    const volatile u8 *v=(const volatile u8 *)(R32(r+4)+p*PAT_SZ+0x128+k*192+st*6);
    for(u32 m=0;m<6;m++)if(v[m]!=255)return v[m];
    return 255;
}
#endif
static u32 step_obj(u32 t) { return R32(STEPOBJ + 4 * t); }
static u32 step_page(u32 t) { u32 o = step_obj(t); return in_ram(o) && built(R32(o + O_SVPAGE)) ? *PARAM_GET(R32(o + O_SVPAGE), 0) & 1 : 0; }
static void all_off(void)
{
    rec_end();
    S->pend = 0;
    ends_all();
    types_to(0);
    S->set = 0;
    S->pstep = 0;
}

static void editor_close(void)              /* as the editor's own close on another button */
{
    R8(TM_SLOT + TM_OPEN) = 0;
    R8(TM_SLOT + TM_STICKY) = 0;
    R8(TM_SLOT + TM_BACK) = 0;
    R8(TM_SLOT + TM_ARM) = TM_ARM_OFF;
    R8(TM_SLOT + TM_PTRK) = 0;
    R8(TM_SLOT + TM_SHOP) = 0;
}
#if EDITOR_GUARD
u32 c_gx_tmallowed(u32 t)
{
    if (t < 8 && CIOK() && t == fx_track()) {
        editor_close();
        return 8;                           /* unavailable to every editor entry/render path */
    }
    return t;
}
#endif

/* ---- a track's 8 patterns */
#define REC_TAIL 0x29110                    /* the session record: its tail, track 0's pattern 0, a track's 8 patterns */
#define REC_PATS 0x2E4
#define REC_TRK 0x5140
static volatile u8 *track_pats(u32 t)       /* from the record, not the recorders (not built yet at a cold start) */
{
    u32 tail = RRT();
    return tail && t < 8 ? (volatile u8 *)(tail - REC_TAIL + REC_PATS + REC_TRK * t) : 0;
}
static void track_clear(u32 t)              /* its steps, automation and effects; the stock's edit stores reloaded after */
{
    volatile u8 *p = track_pats(t);
    if (!p)
        return;
    for (u32 n = 0; n < NPATS; n++, p += PAT_SZ) {
        for (u32 i = 0; i < 8 * NSTEPS; i++)
            p[i] = STEP_NEW[i & 7];
        for (u32 i = 0; i < NLANES * LANE_SZ; i++)
            p[P_LANES + i] = 0xFF;
    }
    pk_clear(t);
#if AUTO_BULK
    c_gx_autotrackclear(t);
#endif
    rec_end();
    RELOAD(rec_of(t));
}

/* the FX track: the sends on its K1-K8 and its pad selected last as its sample; off, its own knobs and sample back */
#if GRANULAR_INTERLOCK
__attribute__((naked,noinline)) u32 c_gx_granular_busy(u32 t)
{ __asm__ volatile("movs r0,#0\n bx lr"); }
#endif
static void fx_toggle(u32 t)
{
#if GRANULAR_INTERLOCK
    if(fx_track()!=t && c_gx_granular_busy(t))return;
#endif
    if (fx_track() == t) {
        all_off();
        u8 saved[8];
        for (u32 k = 0; k < 8; k++) {
            saved[k] = blk()[O_SAVED + k];
            blk_put(O_SENDS + k, knob_send(k, knob_get(t, k)));
        }
        u32 own = blk()[O_TSMP];
        blk_put(O_FXSMP, sample_raw(t));
        blk_put(O_FXTRK, NONE);
        for (u32 k = 0; k < 8; k++)
            knob_put(t, k, saved[k]);
        sample_put(t, own);
        return;
    }
    for (u32 k = 0; k < 8; k++)
        blk_put(O_SAVED + k, knob_get(t, k));
    blk_put(O_TSMP, sample_raw(t));
    const volatile u8 *b = blk();
    for (u32 k = 0; k < 8 && b; k++)
        knob_put(t, k, send_knob(k, b[O_SENDS + k]));
    if (!pk_codes(t))
        blk_put(O_FXSMP, 0);
    pk_make(t);
    blk_put(O_FXTRK, t);
    sample_put(t, blk()[O_FXSMP] & 15);
}
/* Sample mode's pad 8: the FX track on / off (one at a time). Clear + pad 8: the track cleared, pad 8 flashes red */
static u32 since_ask(void) { return (u16)((u16)R32(HAL_TICK) - S->ask_t0); }
static void pad8(u32 t)
{
    u32 fx = fx_track();
    if (held() >> BIT_CLEAR & 1) {
        track_clear(t);
        if (fx == t)
            all_off();
        S->ask = (u8)(t + 1);
        S->ask_t0 = (u16)R32(HAL_TICK);
        return;
    }
    if (fx == NONE || fx == t)
        fx_toggle(t);
}

/* ---- a step through the stock's step store (items: q velocity = on, 8 + q probability, 16 + q microsteps, 24 + q flip; byte
   st & 3); its effects in the tail. The stock's handling sets the flip to the Grid FX pad held: the track's own is put back */
static u32 step_on(u32 t, u32 st) { return PARAM_GET(R32(step_obj(t) + O_ST1), st >> 2)[st & 3]; }
static u32 step_flip(u32 t, u32 st)         /* NO_HIT: no step */
{
    return step_on(t, st) ? PARAM_GET(R32(step_obj(t) + O_ST1), 24 + (st >> 2))[st & 3] : NO_HIT;
}
static u32 step_get(u32 t, u32 st)          /* F_HIT, the slots, the flags */
{
    return step_on(t, st) ? pk_get(t, shown_idx(t), st) | F_HIT : 0;
}
static void step_put(u32 t, u32 st, u32 fx, u32 flip)
{
    u32 hit = fx & F_HIT || fx & 0xFFFF;
    u32 st1 = R32(step_obj(t) + O_ST1), b = st & 3, q = st >> 2;
    u8 *vel = WPTR(st1, q);
    if (hit && !vel[b]) {
        vel[b] = VEL_NEW;
        u8 *micro = WPTR(st1, 16 + q);
        if (!micro[b])
            micro[b] = 1;
        WPTR(st1, 8 + q)[b] = PROB_ALL;
    } else if (!hit) {
        vel[b] = 0;
        WPTR(st1, 16 + q)[b] = 0;
    }
    WPTR(st1, 24 + q)[b] = (u8)(hit && flip != NO_HIT ? flip : 0xFF);
    COMMIT(st1);
    pk_put(t, shown_idx(t), st, hit ? fx & F_LANE : 0);
    const volatile u8 *p = win_pat(t);
    if (p && S->snapv >> st & 1 && shown_idx(t) == S->wpat)
        S->snap[st] = (u16)step_hash(p, st);   /* our own edit: not a recorded step */
}
static void flip_back(u32 t, u32 pat, u32 st, u32 flip)   /* the pattern's byte, and the step store's when it is shown */
{
    volatile u8 *p = track_pats(t);
    if (p)
        p[PAT_SZ * pat + 8 * st + 5] = (u8)flip;
    if (pat == shown_idx(t))
        PARAM_GET(R32(step_obj(t) + O_ST1), 24 + (st >> 2))[st & 3] = (u8)flip;
}

static void with_pad(u32 c, u32 pad, u32 vel, u32 a3, u32 down)  /* the stock's handling; its notes are previews */
{
    S->inpad = 1;
    if (down)
        ((hook_fn)FN(PREV_PAD))(c, pad, vel, a3);
    else
        ((hook_fn)FN(PREV_PADREL))(c, pad, vel, a3);
    S->inpad = 0;
}
static void gfx_pad(u32 s, u32 vel, u32 down) /* as on the Grid FX view */
{
    u32 vt = R32(GFX_PADS);
    if (down)
        ((void (*)(u32, u32, u32))FN(R32(vt)))(GFX_PADS, s, vel);
    else
        ((void (*)(u32, u32))FN(R32(vt + 4)))(GFX_PADS, s);
}
static void edited(u32 t, u32 st, u32 fx)
{
    step_put(t, st, fx, S->pflip);
    S->keep = fx;
    S->pedit = 1;
}

/* ---- the pads (ctrl, pad, velocity). The FX track's sample view: pads 1-16 the stock's steps, 17-32 the Grid FX pads, played as on
   the Grid FX view and handed to the stock as its samples (it selects, records, places); then the step's effects: a step held + a
   pad = that pad on or off the step; pads held + a step = the step has them all, or none when it had them all */
#if !INPUT_TRACE
static void pad_log(u32 pad, u32 vel, u32 down)
{
    S->lg[S->lgn % NLOG] = R32(HAL_TICK) << 16 | (vel & 0xFF) << 8 | down << 6 | (pad & 63);
    S->lgn = (u8)((S->lgn + 1) % NLOG);
}
#endif
#if INPUT_TRACE
static u32 shift_held(void);
static int control_page(void);
/* Reuse the existing diagnostic ring, not project data or more RAM.
   Three words: event/type/index/held-target/Shift, full delta/velocity, caller. */
static void input_trace(u32 kind,u32 index,u32 value,u32 caller)
{
    u32 head=0xd0000000u | kind<<24 | (index&255)<<16 | (S->pstep&255)<<8;
    u32 h=255;
    if(CIOK())h=((u32 (*)(u32))FN(TM_HELD))(sel_track());
    head|=(h<32?h:63)<<2;
    if (shift_held())head|=1;
    if (control_page())head|=2;
    S->lg[S->lgn]=head;S->lgn=(u8)((S->lgn+1)%NLOG);
    S->lg[S->lgn]=value;S->lgn=(u8)((S->lgn+1)%NLOG);
    S->lg[S->lgn]=caller;S->lgn=(u8)((S->lgn+1)%NLOG);
}
#endif
u32 c_gx_pad(u32 c, u32 pad, u32 vel, u32 a3)
{
#if INPUT_TRACE
    input_trace(1,pad,vel,(u32)__builtin_return_address(0));
#else
    pad_log(pad, vel, 1);
#endif
    if (pad >= 32 || !CIOK())
        return ((hook_fn)FN(PREV_PAD))(c, pad, vel, a3);
#if NATIVE_EDGES
    /* The native controller consumes only the first down edge. Pressure /
       repeated down reports must not toggle an FX assignment before that
       controller gets a chance to reject them. */
    if (R32(c + 0x9c) >> pad & 1)
        return ((hook_fn)FN(PREV_PAD))(c, pad, vel, a3);
#endif
    if (pad == PAD_FX && on_cont(MODE_SMP)) {
#if NATIVE_EDGES
        if (S->taken) return 0;
#endif
        u32 t = SM_SELTRK(CONT);
        if (t < 8)
            pad8(t);
        S->taken = 1;
        return 0;
    }
    if (!fx_view())
        return ((hook_fn)FN(PREV_PAD))(c, pad, vel, a3);
    u32 t = sel_track();
    if (pad < PAD_SLOT0) {
        u32 st = pad + 16 * step_page(t), had = step_get(t, st), live = S->gdown;
        S->pflip = (u8)step_flip(t, st);
#if NATIVE_EDGES
        /* Match TPE's select-only press while editing private parameters.
           In particular, selecting an empty step must not arm a note tap. */
        u32 shift = R32(CTRL + O_SHIFT), sf = R32(step_obj(t) + 0x34);
        volatile u8 *select = built(sf) ? PARAM_GET(sf, 0) : 0;
        u32 editing = built(shift) && *PARAM_GET(shift, 0) &&
                      !(held() & ((1u << BIT_CLEAR) | (1u << 24)));
        u8 previous = select ? *select : 0;
        if (editing && select) *select = 1;
        with_pad(c, pad, vel, a3, 1);
        if (editing && select) *select = previous;
#else
        with_pad(c, pad, vel, a3, 1);
#endif
        S->pstep = (u8)(st + 1);
        S->pedit = 0;
        if (live)
            edited(t, st, had && (had & live) == live ? 0 : put_pads(had, live) | F_HIT);
        return 0;
    }
    u32 s = pad - PAD_SLOT0, b = 1u << s;
    if (S->pstep) {
        u32 st = S->pstep - 1u, had = S->pedit ? S->keep : step_get(t, st);
        with_pad(c, pad, vel, a3, 1);
        u32 fx = had & b ? had & ~b : put_pad(had, s);
        edited(t, st, fx & 0xFFFF ? fx | F_HIT : 0);   /* its last pad off: the step deleted */
        return 0;
    }
    if (!control_get(3)) {
        gfx_pad(s, vel, 1);
        S->audown |= (u16)b;
    }
    S->gdown |= (u16)b;
    S->pord[s] = ++S->pcnt;
    live_press(t, s);
    with_pad(c, pad, vel, a3, 1);
    return 0;
}

u32 c_gx_padrel(u32 c, u32 pad, u32 a2, u32 a3)
{
#if INPUT_TRACE
    input_trace(2,pad,0,(u32)__builtin_return_address(0));
#else
    pad_log(pad, 0, 0);
#endif
    if (pad >= 32)
        return ((hook_fn)FN(PREV_PADREL))(c, pad, a2, a3);
    if (pad == PAD_FX && S->taken) {
        S->taken = 0;
        return 0;
    }
#if NATIVE_EDGES
    /* An up report for a pad the native controller has not accepted cannot
       release a live FX gate, change a held target, or erase its FX code. */
    if (!(R32(c + 0x9c) >> pad & 1))
        return ((hook_fn)FN(PREV_PADREL))(c, pad, a2, a3);
#endif
    u32 fx = fx_track();
    if (pad >= PAD_SLOT0 && S->gdown >> (pad - PAD_SLOT0) & 1) {
        u32 s = pad - PAD_SLOT0;
        u32 was_live = S->audown >> s & 1;
        if (was_live) {
            gfx_pad(s, 0, 0);
            S->audown &= (u16)~(1u << s);
        }
        S->gdown &= (u16)~(1u << s);
        u32 ty = slot_type(s);
        if (was_live && ty < NTYPES && S->play[ty] && !(live_types() >> ty & 1))
            slot_onoff(S->play[ty] - 1u, 1); /* the sequence still plays the type */
        with_pad(c, pad, a2, a3, 0);
        rec_join();                         /* the stock records the step at the release */
        return 0;
    }
    if (fx == NONE || sel_track() != fx)
        return ((hook_fn)FN(PREV_PADREL))(c, pad, a2, a3);
    if (pad >= PAD_SLOT0) {
        with_pad(c, pad, a2, a3, 0);
        return 0;
    }
    u32 st = pad + 16 * step_page(fx);
    with_pad(c, pad, a2, a3, 0);
    if (S->pstep == st + 1) {
        if (S->pedit)
            step_put(fx, st, S->keep, S->pflip);   /* the stock's tap would undo it */
        else if (step_on(fx, st))           /* the stock's tap made a step: blue */
            step_put(fx, st, S->pflip == NO_HIT ? F_HIT : step_get(fx, st), S->pflip);
        S->pstep = 0;
    }
    if (!step_on(fx, st))
        pk_put(fx, shown_idx(fx), st, 0);
    return 0;
}

/* ---- buttons (ctrl, id): on the Mixer, the pans' down = the sends; on the sends, up = the stock's page (a held effect's
   settings, or the pans), down nothing; from those settings after that up, down = the sends. The FX track's view: a step held,
   down / up = its random / repeat on or off; a Grid FX pad held, up = its settings on the knobs, down = the sends */
static int fx_track_view(void) { u32 fx = fx_track(); return fx != NONE && R32(CTRL + O_VIEW) == CONT && sel_track() == fx; }
static u32 song_len(void)                   /* in pulses, as the stock's locate counts it: each scene its longest track; 0 unknown */
{
    u32 sc = R32(ENG + ENG_SCENES), ch = R32(ENG + ENG_CHAINS), so = R32(ENG + ENG_SCDATA), total = 0;
    if (!built(sc) || !built(ch) || !in_ram(so))
        return 0;
    const volatile u8 *c = PARAM_GET(sc, 0);
    u32 first = c[0], last = c[1];
    for (u32 n = first; n <= last && n < 16; n++) {
        u32 m = 0;
        for (u32 t = 0; t < 8; t++) {
            u32 info = first == last ? *(volatile u32 *)PARAM_GET(ch, t)
                                     : (((u32 (*)(u32, u32, u32))FN(SC_START))(so, n, t) & 0xFF)
                                       | (((u32 (*)(u32, u32, u32))FN(SC_END))(so, n, t) & 0xFF) << 8;
            u32 l = ((u32 (*)(u32, u32, u32))FN(TRK_LEN))(ENG, t, info);
            m = l > m ? l : m;
        }
        total += m;
    }
    return total;
}
/* Audition through the stock sample selector and the step view's preview dispatcher.
   Transport stays stopped: no sequence ticks, recording, or time stretching. */
static void scrub_audio_end(void)
{
    u32 mask = S->samask;
    S->samask = 0;
    for (u32 t = 0; t < 8; t++)
        if (mask >> t & 1u) {
            u32 so = step_obj(t), obj = in_ram(so) ? R32(so + 0x38) : 0;
            if (in_ram(obj) && R32(obj))
                ((hook_fn)FN(R32(R32(obj) + 4)))(obj, S->sanote[t], 0, 0);
        }
}
static void scrub_audio(void)
{
    scrub_audio_end();
    if (S->saoff)
        return;
    for (u32 t = 0; t < 8; t++) {
        if (t == fx_track())
            continue;                       /* scrubbing never starts the FX sequence */
        u32 ps = R32(ENG + ENG_TPOS + 4 * t), pl = PLAYERS + PLAYER_SZ * t;
        if (!built(ps) || !in_ram(R32(pl + O_PATS)))
            continue;
        u32 pat = *PARAM_GET(ps, 0), step = *PARAM_GET(ps, 1);
        if (pat >= 8 || step >= NSTEPS)
            continue;
        const volatile u8 *p = (const volatile u8 *)(R32(pl + O_PATS) + PAT_SZ * pat + 8 * step);
        if (!(p[2] & 63) || !p[3])
            continue;
        u32 so = step_obj(t), obj = in_ram(so) ? R32(so + 0x38) : 0;
        if (!in_ram(obj))
            continue;
        u32 vt = R32(obj);
        if (!vt)
            continue;
        ((void (*)(u32, u32, u32))FN(R32(0x08068D24u + 16)))(pl, pat, step);
        u32 note = p[0] ? p[0] : 48;
        ((hook_fn)FN(R32(vt)))(obj, note, p[3], 0);
        S->sanote[t] = (u8)note;
        S->samask |= (u8)(1u << t);
    }
    S->saat = R32(HAL_TICK);
}
static void scrub(s32 d)                    /* K1 with Shift + Play held: the song position d steps on, inside the song */
{
    u32 st = R32(ENG + ENG_POS);
    if (R32(ENG + 0xC) != ENG_VT || !built(st))
        return;
    if (!d)
        return;
    u32 len = song_len() / PULSES;
    u32 cur = (S->sedge ? S->spos : *(volatile u32 *)PARAM_GET(st, 0)) / PULSES;
    s32 n = (s32)(len ? cur % len : cur) + d;
    u32 at = n < 0 ? 0u : len && (u32)n >= len ? len - 1u : (u32)n;
    u32 edge = !at || (len && at == len - 1u);
    u32 tr = TRANSPORT, clk = R32(ENG + ENG_CLK);
    u32 running = built(tr) && *PARAM_GET(tr, 0);
    u32 resume = S->sresume;
    if (edge && running) {
        S->sresume = 1;
        ((void (*)(u32, u32))FN(SONG_STOP))(ENG + 0xC, 1);
        running = 0;
    }
    S->sedge = (u8)(edge && (running || S->sresume));
    S->spos = at * PULSES;
    ((void (*)(u32, u32))FN(LOCATE))(ENG, S->spos);
    if (!running && in_ram(clk) && R32(clk)) {
        ((void (*)(u32, u32))FN(R32(R32(clk))))(clk, at % 32);
        S->spend = 1;
    }
    if (!edge && resume) {                  /* only an inward turn releases a boundary stop */
        scrub_audio_end();
        S->sresume = 0;
        ((void (*)(u32, u32))FN(SONG_CONTINUE))(ENG + 0xC, 1);
        S->spend = 0;
    }
    if (!*PARAM_GET(tr, 0))
        scrub_audio();
    else
        scrub_audio_end();
    S->smoved = 1;
}
static u32 shift_held(void) { u32 st = R32(CTRL + O_SHIFT); return built(st) && *PARAM_GET(st, 0); }
static int control_page(void)
{
    return !S->scr && shift_held() &&
        ((fx_track_view() && R8(CONT + O_MODE) != MODE_SMP && !SM_SHOWN(R8(SM_SLOT)) && !R8(TM_SLOT + TM_OPEN))
         || (on_mixer() && (S->page & SHOWN)));
}
static void control_knob(u32 k, s32 d)
{
    if (k >= 4 || !d)
        return;
#if PRIVATE_GESTURE
    /* Native step-view +0xb8 is the pending tap-toggle mask. The native
       hold callback (0805ce48) cancels it for held pads at +0xc0. These
       private knobs bypass the native parameter notification, so explicitly
       consume the gesture without touching notes or native automation. */
    if (fx_track_view()) {
        u32 so = step_obj(sel_track());
        if (in_ram(so))
            *(volatile u32 *)(so + 0xb8) &= ~R32(so + 0xc0);
    }
#endif
    u32 clear = held() >> BIT_CLEAR & 1;
    if (!clear)
        for (u32 i = 0; i < 4; i++)
            S->cright[i] = S->cleft[i] = 0;
    if (clear) {
        volatile u8 *counter = d > 0 ? &S->cright[k] : &S->cleft[k];
        u32 n = *counter, more = d > 0 ? (u32)d : (u32)-d;
        if (n >= 40)
            return;
        *counter = (u8)(more >= 40 - n ? 40 : n + more);
        if (*counter < 40)
            return;
        if (d > 0) S->cleft[k] = 0; else S->cright[k] = 0;
    }
    s32 v = k == 3 ? (d < 0) : clear ? (d > 0 ? FULL : 0) : (s32)control_edit(k) + d;
    v = v < 0 ? 0 : v > FULL ? FULL : v;
    control_store(k, (u32)v);
#if AUTOMATION3
    if(k<3)c_gx_autotouch(k,(u32)v,clear);
#endif
    /* These controls must never address native send/level automation lanes.
       Separate persisted automation is not enabled until its storage is proven. */
    if (k == 3 && v) {
        for (u32 s = 0; s < NSLOTS; s++)
            if (S->audown >> s & 1)
                gfx_pad(s, 0, 0);
        S->audown = 0;
        for (u32 ty = 0; ty < NTYPES; ty++)
            if (S->play[ty] && !(live_types() >> ty & 1))
                slot_onoff(S->play[ty] - 1u, 1);
        types_to(0);                        /* sequenced effects continue */
    }
}

static void shift_put(u32 v)
{
    u32 st = R32(CTRL + O_SHIFT);
    *WPTR(st, 0) = (u8)v;
    COMMIT(st);
}
static void scrub_end(void)                 /* Play let go: no K1 turn = the stock's Shift + Play, Shift held for it */
{
    scrub_audio_end();
    u32 moved = S->smoved, sh = !S->shup;
    S->scr = 0;
    if (moved || R32(HAL_TICK) - S->sdown >= TAP_MS) {
        shift_put(sh);
        return;
    }
    shift_put(1);
    S->spass = 1;
    ((void (*)(u32, u32))FN(BTN_ENTRY_A))(CTRL, ID_PLAY);
    ((hook_fn)FN(PREV_REL))(CTRL, ID_PLAY, 0, 0);
    S->spass = 0;
    shift_put(sh);
    u32 tr = TRANSPORT;
    if (S->spend && built(tr) && *PARAM_GET(tr, 0) && R32(ENG + 0xC) == ENG_VT)
        ((void (*)(u32, u32))FN(LOCATE))(ENG, S->spos);   /* it started: from the scrub's place */
    S->spend = 0;
    S->sedge = S->sresume = 0;
}
u32 c_gx_rel(u32 c, u32 id, u32 a2, u32 a3)
{
    if (id == BIT_CLEAR)
        for (u32 k = 0; k < 4; k++)
            S->cright[k] = S->cleft[k] = 0;
    if (id == ID_SHIFT && S->scr) {
        S->shup = 1;
        return 0;                           /* Shift is already up in the stock */
    }
    if (id == ID_PLAY && S->scr && !S->spass && !R8(CI_PASS)) {
        scrub_end();
        return 0;                           /* its press never reached the stock */
    }
    return ((hook_fn)FN(PREV_REL))(c, id, a2, a3);
}
u32 c_gx_btn(u32 c, u32 id, u32 a2, u32 a3)
{
    if (id == ID_PLAY && !S->spass && !R8(CI_PASS))
        scrub_audio_end();
    if (id == ID_PLAY && !S->spass && !R8(CI_PASS) && !shift_held())
        S->spend = S->sedge = S->sresume = 0; /* a plain Play explicitly leaves the boundary hold */
    if (id == ID_PLAY && !S->spass && !R8(CI_PASS) && CIOK() && shift_held()) {   /* not the count-in's own press */
        S->scr = 1;
        S->smoved = 0;
        S->shup = 0;
        S->spg = 0;
        S->sdown = R32(HAL_TICK);
        ends_all();
        types_to(0);
        shift_put(0);                       /* the views without Shift's pages while it scrubs */
        return 0;
    }
    if ((id == ID_NOTE || id == ID_VEL) && CIOK() && fx_track_view())
        return 0;                           /* no notes and no velocity on the FX track */
    if ((id == ID_DOWN || id == ID_UP) && CIOK() && fx_view()) {
        u32 t = sel_track();
        if (S->pstep) {
            u32 st = S->pstep - 1u, fx = S->pedit ? S->keep : step_get(t, st);
            if (fx & F_HIT)
                edited(t, st, fx ^ (id == ID_DOWN ? F_RANDOM : F_REPEAT));
        } else if (S->gdown) {
            S->set = id == ID_UP;
        }
        return 0;
    }
    if ((id == ID_DOWN || id == ID_UP) && on_mixer()) {
        u32 pg = stock_page();
        if (S->page & SHOWN) {
            if (id == ID_UP)
                S->page = pg >= FX_PAGE ? JUMP : 0;
            return 0;
        }
        if (id == ID_DOWN && (pg == PANS || (S->page & JUMP && pg >= FX_PAGE))) {
            S->page = SHOWN;
            return 0;
        }
        S->page = 0;
    }
    return ((hook_fn)FN(PREV_BTN))(c, id, a2, a3);
}

/* Sends have full as their default, while retaining the native directional
   Clear counters and clear-automation event for the underlying track lane. */
static void send_turn(u32 t, u32 k, s32 d)
{
    u32 ko = R32(KNOBS + 4 * t);
    if (!ko || k >= 8)
        return;
#if NATIVE_EDGES
    if (!d) return;
#endif
    if (!(held() >> BIT_CLEAR & 1)) {
        u32 base=knob_get(t,k);
#if REC_FEEDBACK
        u32 own=send_own(t,k);if(own!=255)base=own;
#endif
        s32 v = (s32)base + d;
        u32 lo = k ? 0 : K1_LO, hi = k ? FULL : K1_HI;
        v = v < (s32)lo ? (s32)lo : v > (s32)hi ? (s32)hi : v;
        knob_put(t, k, (u32)v);
        u32 sink = R32(ko + 0x14), id = R16(ko + 0x44) + k;
        ((void (*)(u32,u32,u32))FN(R32(R32(sink))))(sink, id, (u32)v);
        if (*PARAM_GET(R32(ko + 0x2C), 0))
            ((void (*)(u32,u32,u32))FN(0x08047D82))(rec_of(t), k, (u32)v);
        return;
    }
    if (!d)
        return;
    volatile u8 *counter = (volatile u8 *)(ko + (d > 0 ? 0x59 : 0x51) + k);
    u32 n = *counter, more = d > 0 ? (u32)d : (u32)-d;
    if (n >= 40)
        return;
    *counter = (u8)(more >= 40 - n ? 40 : n + more);
    if (*counter < 40)
        return;
    R8(ko + (d > 0 ? 0x51 : 0x59) + k) = 0;
    knob_put(t, k, send_knob(k, d > 0 ? FULL : 0));
    u32 sink = R32(ko + 0x38);
    ((void (*)(u32,u32,u32,u32))FN(0x08047038))(sink, k, 0, 0);
}

/* ---- the track views' knobs (ctrl, knob, delta): the FX track's view with a Grid FX pad's settings shown, the stock's settings */
u32 c_gx_tknob(u32 c, u32 knob, u32 delta, u32 a3)
{
#if INPUT_TRACE
    input_trace(3,knob,delta,(u32)__builtin_return_address(0));
#endif
    if (S->scr && knob >= 2 && CIOK())
        return 0;                           /* only K1 and K2 exist in scrub mode */
    if (S->scr && knob == 1 && CIOK()) {
        if ((s32)delta) {
            S->smoved = 1;                   /* changing K2 is not a Shift + Play tap */
            S->saoff = (s32)delta < 0;
            if (S->saoff)
                scrub_audio_end();
        }
        return 0;
    }
    if (S->scr && knob == 0 && CIOK()) {
        scrub((s32)delta);
        return 0;
    }
    if (CIOK() && control_page()) {
        control_knob(knob, (s32)delta);
        return 0;
    }
    if (CIOK() && fx_view() && !S->set && knob < 8) {
        send_turn(sel_track(), knob, (s32)delta);
        return 0;
    }
    if (!S->set || knob >= 8 || !CIOK() || !fx_view())
        return ((hook_fn)FN(PREV_TKNOB))(c, knob, delta, a3);
    SET_KNOB(GFX_SET, knob, delta);
    return 0;
}

/* ---- the Mixer's knob slot (view, knob, delta): on the sends, the track's send; Clear + knob = full. With an FX track, the
   send is its knob, which takes one step a turn */
u32 c_gx_knob(u32 view, u32 knob, u32 delta, u32 a3)
{
    if (!(S->page & SHOWN) || knob >= 8)
        return ((hook_fn)FN(PREV_KNOB))(view, knob, delta, a3);
    if (CIOK() && control_page()) {
        control_knob(knob, (s32)delta);
        return 0;
    }
    u32 clr = held() >> BIT_CLEAR & 1, fx = fx_track();
    if (fx != NONE) {
        send_turn(fx, knob, (s32)delta);
        return 0;
    }
    s32 v = clr ? FULL : (s32)send_of(knob) + (s32)delta;
    blk_put(O_SENDS + knob, (u32)(v < 0 ? 0 : v > FULL ? FULL : v));
    return 0;
}

static u32 scl(u32 rgb, u32 lvl)
{
    u32 o = 0;
    for (u32 sh = 0; sh < 24; sh += 8)
        o |= (((rgb >> sh) & 0xFF) * (lvl + 1) >> 8) << sh;
    return o;
}

/* the brightest of the stock's 8 knob lights (a held effect's settings: its colour), at the level full */
static u32 full_colour(const volatile u32 *k, u32 full)
{
    u32 best = 0, top = 0;
    for (u32 i = 0; i < 8; i++) {
        u32 c = k[i], m = 0;
        for (u32 sh = 0; sh < 24; sh += 8)
            if (((c >> sh) & 0xFF) > m)
                m = (c >> sh) & 0xFF;
        if (m > top) {
            top = m;
            best = c;
        }
    }
    if (!top)
        return scl(0xFFFFFFu, full);
    u32 o = 0;
    for (u32 sh = 0; sh < 24; sh += 8)
        o |= (((best >> sh) & 0xFF) * full / top) << sh;
    return o;
}

/* the DSP's share around Grid FX for a send: 0 at FULL, $7FFF at 0 (the word's top 16 bits) */
static void write_send(u32 t, u32 v)
{
    u32 cut = (FULL - v) * 0x7FFF / FULL;
    WR16(0, cut << 16, DSP_CUT + t);
    S->sent[t] = (u8)(v + 1);
}

static void dsp_round(void)
{
    if (R8(READY_AT) != READY) {
        S->wait = 0;
        for (u32 t = 0; t < 8; t++)
            S->sent[t] = 0;
        for (u32 k = 0; k < 3; k++)
            S->csent[k] = 0;
        return;
    }
    if (S->wait < WAIT) {
        S->wait++;
        return;
    }
    for (u32 k = 0; k < 3; k++) {
        u32 v = control_get(k);
        if (S->csent[k] != v + 1) {
            u32 cut = (FULL - v) * 0x7FFF / FULL;
            WR16(0, cut << 16, k < 2 ? DSP_RET + k : DSP_BLEND);
            S->csent[k] = (u8)(v + 1);
        }
    }
    for (u32 t = 0; t < 8; t++) {
        u32 v = send_of(t);
        if (S->sent[t] != v + 1) {
            write_send(t, v);
            return;
        }
    }
    if (++S->frame >= ROUND) {
        S->frame = 0;
        u32 t = S->next++ & 7;
        write_send(t, send_of(t));
    }
}

static void send_lights(volatile u32 *o, u32 full)
{
    u32 fx = fx_track(), ko = fx < 8 ? R32(KNOBS + 4 * fx) : 0;
    for (u32 k = 0; k < 8; k++) {
        u32 color = GX_RGB, level = (LVL_ZERO + send_of(k) * (255 - LVL_ZERO) / FULL) * full >> 8;
#if REC_FEEDBACK
        u32 own=fx<8?send_own(fx,k):255;
        if(own!=255)level=(LVL_ZERO+knob_send(k,own)*(255-LVL_ZERO)/FULL)*full>>8;
        if(ko && (*PARAM_GET(0x200122b0,1)&255) &&
           (R32(PARAM_GET(R32(ko+0x1c),0))>>k&1))color=R32(COLOURS+4*CLR_RED);
        if(own!=255)color=R32(COLOURS+4*CLR_RED);
#endif
        if (ko && (held() >> BIT_CLEAR & 1) && (R8(ko + 0x51 + k) == 40 || R8(ko + 0x59 + k) == 40)) {
            color = R32(COLOURS + 4 * (R8(ko + 0x59 + k) == 40 ? 0x0E : CLR_RED));
            level = full;
        }
        o[LED_KNOB0 + k] = scl(color, level);
    }
}

static u32 pal(u32 code) { return R32(COLOURS + 4 * (code & 0x3FF)); }
static u32 type_code(u32 s) { return R16(COLT + 2 * slot_type(s)); }  /* the dim one; bright = code - 1 */

static void mark_lights(volatile u32 *o, u32 full)    /* the FX track's button amber, the Mixer button dim amber off its view */
{
    u32 fx = fx_track();
    if (fx == NONE)
        return;
    if (!(R8(MS_SLOT) & MS_OPEN))
        o[LED_TRK0 + fx] = scl(GX_RGB, sel_track() == fx ? full : MARK_LVL * full >> 8);
    if (!on_mixer())
        o[LED_MIX] = scl(GX_RGB, sel_track() == fx ? full : MARK_LVL * full >> 8);
    if (fx_track_view())
        o[LED_NOTE] = o[LED_VEL] = 0;
}
static u32 pulse(void) { return 64 + ((255 - (R32(COLOURS + 4 * FRAME_PULSE) & 0xFF)) * 192 >> 8); }
static u32 sequence_lights(void)
{
    u32 lit=S->on;
#if FX_VISUALS
    for(u32 s=0;s<NSLOTS;s++)if(S->rem[s])lit|=1u<<s;
#endif
    return lit;
}

static void control_lights(volatile u32 *o, u32 full)
{
    if (!control_page())
        return;
    const u32 colors[3] = { R32(COLOURS + 4 * 0x141), R32(COLOURS + 4 * 0x139), GX_RGB };
    for (u32 k = 0; k < 8; k++) {
        u32 color=k<3?colors[k]:0;
#if REC_FEEDBACK
        if(k<3 && c_gx_autored(k))color=pal(CLR_RED);
#endif
        o[LED_KNOB0 + k] = k < 3 ? scl(color, (LVL_ZERO + control_edit(k) * (255 - LVL_ZERO) / FULL) * full >> 8)
                             : k == 3 ? scl(control_get(3) ? 0xFF0000 : 0x00FF00, full) : 0;
    }
    if (held() >> BIT_CLEAR & 1)
        for (u32 k = 0; k < 4; k++)
            if (S->cright[k] == 40 || S->cleft[k] == 40)
                o[LED_KNOB0 + k] = scl(pal(S->cright[k] == 40 ? 0x0E : CLR_RED), full);
}

/* The FX assignments replace sample flips in both step views. Keep native
   held/playhead colors and all Gate controls intact. */
static void fx_step_lights(volatile u32 *o, u32 full)
{
    if (!fx_track_view() || !(on_cont(MODE_SAMPLES) || on_cont(MODE_GATE)
#if FX_VISUALS
        || on_cont(4) || on_cont(5) || on_cont(6)
#endif
        ) || R8(TM_SLOT + TM_OPEN))
        return;
    u32 t = sel_track();
    u32 fr = R32(CONT + 4);
    const volatile u16 *codes = in_ram(fr) && in_ram(R32(fr)) ? (const volatile u16 *)R32(fr) : 0;   /* the stock's view: its pads' palette codes */
    const volatile u8 *pk = pk_codes(t), *sets = pk_sets();
    for (u32 p = 0, at = shown_idx(t) * NSTEPS + 16 * step_page(t); codes && p < 16; p++) {
        u32 c = codes[p], want = pk && at < PK_N && pk_fx(sets, pk_code(pk, at + p)) & 0xFFFF ? C_PINK : C_BLUE;
        if (c == 0x1A || c == 0x69)
            want = want == C_PINK ? 0x69 : 0x1A;   /* native selected-hit colors include the white pulse */
        if ((c == C_BLUE || c == C_PINK || c == 0x1A || c == 0x69) && c != want)
            o[p] = scl(pal(want), full);   /* pink: the step has its own pads */
    }
}

static void fx_lights(volatile u32 *o, u32 full)
{
    fx_step_lights(o, full);
    if (on_cont(MODE_SMP) && SM_SELTRK(CONT) < 8) {
        u32 fx = fx_track(), t = SM_SELTRK(CONT), since = since_ask();
        if (S->ask == t + 1 && since < FLASH_MS)
            o[PAD_FX] = since >> 6 & 1 ? 0 : scl(pal(CLR_RED), full);
        else if (held() >> BIT_CLEAR & 1)
            o[PAD_FX] = scl(pal(CLR_CUE), full);
        else
            o[PAD_FX] = fx == t ? scl(GX_RGB, full) : fx == NONE ? scl(GX_RGB, FX_DIM * full >> 8) : 0;
        return;
    }
    if (!fx_view() || !S->gdown)
        S->set = 0;
    if (!fx_view())
        return;
    u32 t = sel_track(), sfx = 0, lit = sequence_lights(), sel = 1u << track_sample(t), down = S->gdown | gfx_held();   /* latched pads too */
    if (S->pstep) {
        sfx = S->pedit ? S->keep : step_get(t, S->pstep - 1u);
        lit = sfx & F_HIT ? fx_of(sfx & F_LANE, track_sample(t)) & 0xFFFF : 0;
    }
    for (u32 s = 0; s < NSLOTS; s++) {
        u32 b = 1u << s, code = type_code(s);
        if (down & b)
            o[PAD_SLOT0 + s] = scl(WHITE, full);
        else if (sel & b && !S->pstep)
            o[PAD_SLOT0 + s] = scl(WHITE, pulse() * full >> 8);   /* the selected pad: a blue step's */
        else if (slot_type(s) < NTYPES)
            o[PAD_SLOT0 + s] = scl(pal(lit & b ? code - 1u : code), full);
        else
            o[PAD_SLOT0 + s] = lit & b ? scl(WHITE, FX_DIM * full >> 8) : 0;
    }
    if (S->pstep) {
        o[LED_DOWN] = scl(WHITE, sfx & F_RANDOM ? full : ARROW_DIM * full >> 8);
        o[LED_UP] = scl(WHITE, sfx & F_REPEAT ? full : ARROW_DIM * full >> 8);
    } else if (S->gdown) {
        u32 s = 31u - (u32)__builtin_clz(S->gdown);
        o[LED_UP] = S->set ? 0 : slot_type(s) < NTYPES ? scl(pal(type_code(s) - 1u), full) : scl(WHITE, full);
        o[LED_DOWN] = S->set ? scl(GX_RGB, full) : 0;
    } else {
        o[LED_UP] = o[LED_DOWN] = 0;
    }
    if (S->set) {
        volatile u16 *lc = SET_LEDS(GFX_SET);
        for (u32 k = 0; k < 8; k++)
            o[LED_KNOB0 + k] = scl(pal(lc[k]), full);
    } else {
        send_lights(o, full);
    }
}

static void pk_sweep(void)                  /* 32 codes a frame: a step deleted anywhere loses its effects */
{
    u32 tail = RRT();
    volatile u8 *b = tail && S->pkok & 1 ? (volatile u8 *)(tail + PK_OFF) : 0;
    const volatile u8 *p = b && b[3] < 8 ? track_pats(b[3]) : 0;
    if (!p)
        return;
    u32 i0 = S->sweep & ~31u;
    S->sweep = (u8)(i0 + 32);
    for (u32 i = i0; i < i0 + 32; i++)
        if (pk_code(b, i) && !p[PAT_SZ * (i / NSTEPS) + 8 * (i % NSTEPS) + 3]) {
            __asm volatile("cpsid i" ::: "memory");
            pk_setcode(b, i, 0);
            S->pkver++;
            __asm volatile("cpsie i" ::: "memory");
        }
}

/* ---- the output stage (ctrl, out RGB words, frame) */
#define SCRUB_RGB 0x00FF00u
static void scrub_page(u32 frame)           /* reconcile the actual page, then draw that page in this frame */
{
    if (!S->scr || R32(CTRL + O_VIEW) != CONT)
        return;
    u32 t = sel_track(), ps = R32(ENG + ENG_TPOS + 4 * t), so = step_obj(t);
    if (!built(ps) || !in_ram(so) || !built(R32(so + O_SVPAGE)))
        return;
    u32 pg = (PARAM_GET(ps, 1)[0] & 31) >> 4;
    if (step_page(t) != pg) {
        *WPTR(R32(so + O_SVPAGE), 0) = (u8)pg;
        COMMIT(R32(so + O_SVPAGE));
    }
    S->spg = (u8)(pg + 1u);
    /* The stock frame was assembled before this output hook. Its step object
       already holds both pages: use its own page getter to refresh pads 1-16.
       A cached requested page cannot tell whether a native update restored it. */
    u32 vt = R32(so);
    u32 pads = ((u32 (*)(u32))FN(R32(vt + 28)))(so);
    if (in_ram(pads) && in_ram(frame))
        for (u32 i = 0; i < 16; i++)
            ((volatile u16 *)frame)[i] = ((volatile u16 *)pads)[i];
}
static void scrub_light(volatile u32 *o, u32 full)
{
    if (!S->scr)
        return;
    o[LED_KNOB0] = scl(SCRUB_RGB, full);
    o[LED_KNOB0 + 1] = scl(S->saoff ? 0xFF0000u : SCRUB_RGB, full);
    for (u32 k = 2; k < 8; k++)
        o[LED_KNOB0 + k] = 0;
    u32 t = sel_track(), ps = R32(ENG + ENG_TPOS + 4 * t);
    if (R32(CTRL + O_VIEW) != CONT || !built(ps))
        return;
    u32 st = PARAM_GET(ps, 1)[0] & 31;
    if (step_page(t) == st >> 4)
        o[st & 15] = scl(WHITE, full);
}
u32 c_gx_out(u32 c, u32 out, u32 frame, u32 a3)
{
    if (CIOK() && R8(TM_SLOT + TM_OPEN) && fx_track() == sel_track())
        editor_close();                     /* no Track Parameter Editor on the FX track */
    if (CIOK() && S->samask && (!S->scr || R32(HAL_TICK) - S->saat >= 120))
        scrub_audio_end();
    if (CIOK())
        scrub_page(frame);
    u32 ret = ((hook_fn)FN(PREV_OUT))(c, out, frame, a3);
    if (!CIOK())
        return ret;
    u32 md = R8(CONT + O_MODE);
    if (fx_track_view() && (md == MODE_NOTE || md == MODE_VEL || md == MODE_NOTE2)) {
        u32 v = MODE_SET(CONT, MODE_SAMPLES);
        if (v != 0xFFFFFFFFu)
            VIEW_SET(CTRL, v, ID_SAMPLES, 0);
    }
    apply();
    pk_check();
    pk_sweep();
    dsp_round();
    volatile u32 *o = (volatile u32 *)out;
    u32 dimmed = (*(volatile u32 *)PARAM_GET(R32(CTRL + O_DIMS), 2) >> 10) & 1;
    u32 full = dimmed ? DIM_MUL : 255;
    mark_lights(o, full);
    if (on_mixer() && *PARAM_GET(R32(GFX_MODE), 0) == MODE_GFX) {
        u32 h = gfx_held();
        for (u32 s = 0; s < NSLOTS; s++)
            if (sequence_lights() >> s & 1 && !(h >> s & 1) && slot_type(s) < NTYPES)
                o[PAD_SLOT0 + s] = scl(pal(type_code(s) - 1u), full);   /* the FX track plays it */
    }
    if (!on_mixer()) {
        S->page = 0;
        fx_lights(o, full);
        control_lights(o, full);
        return scrub_light(o, full), ret;
    }
    u32 pg = stock_page();
    if (!(S->page & SHOWN)) {
        if (pg < FX_PAGE)
            S->page = 0;                    /* the effect let go: the stock's page is back */
        if (pg == PANS)
            o[LED_DOWN] = o[LED_UP];        /* down leads on to the sends */
        else if (S->page & JUMP)
            o[LED_DOWN] = scl(GX_RGB, full);
        control_lights(o, full);
        return scrub_light(o, full), ret;
    }
    if (pg >= FX_PAGE)
        o[LED_UP] = full_colour(o + LED_KNOB0, full);
    send_lights(o, full);
    o[LED_DOWN] = 0;
    control_lights(o, full);
    scrub_light(o, full);
    return ret;
}
