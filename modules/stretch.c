/* Time stretch (Rhythm Plus, MIT): Sample mode pads 9-17 and the words of core 0's stretch engine (stretch_dsp.py).
   Built by stretch_arm.py, which passes the addresses below with -D. */
#include <stdint.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

#define R32(a) (*(volatile u32 *)(a))
#define R8(a) (*(volatile u8 *)(a))
#define FN(a) ((u32)(a) | 1)

typedef u8 *(*get_fn)(u32 store, u32 item);
typedef u32 (*hook_fn)(u32, u32, u32, u32);
typedef u32 (*u32_fn)(void);
typedef u32 (*u32_1)(u32);
typedef void (*wr_fn)(u32, u32);
typedef u32 (*scan_fn)(u32, u32, u32);
typedef u32 (*route_fn)(u32, u32);
typedef u32 (*read_fn)(u32);

#define PARAM_GET ((get_fn)FN(0x0803FC58))
#define TEMPO_GET ((get_fn)FN(0x0803FC6C))
#define RRT ((u32_fn)FN(C_RRT))
#define RST ((u32_fn)FN(C_RST))
#define READY ((u32_fn)FN(C_READY))
#define BUSY ((u32_1)FN(C_BUSY))           /* the track is Granular's (or turning into it) */
#define DSP_WRITE ((wr_fn)FN(C_WRITE))     /* Granular's write of a route word or a host parameter word */
#define SCAN ((scan_fn)FN(C_SCAN))
#define GSWITCH ((scan_fn)FN(C_GSWITCH))    /* (state, t, 0 off / 1 on / ~0 read): Granular's on / off */
#define ROUTE ((route_fn)FN(C_ROUTE))        /* Granular's own route word 3 for a track */
#define SHARED_READ ((read_fn)FN(C_SREAD))   /* Granular's read of a snapshot word */

#define CTRL 0x200487C8u
#define O_VIEW 0x7C
#define O_DIMS 0x88
#define KSTORES 0x1F4                       /* [+ 4 t]: the track's knob store: K1-K8 items 0-7, K2 / K3's fine 14 / 15 */
#define CONT 0x20048B9Cu
#define O_SELTRK 0x25C
#define O_MODE 0x264
#define MODE_SMP 9
#define TEMPO 0x20012788u
#define PLAYERS 0x200470D4u
#define PLAYER_SZ 0x190
#define O_SAMPLE 0x60                       /* [ ]: the store, item 0 the track's sample */
#define SMPMGR 0x20006F24u                  /* [ ]: the stock's samples, read by SMP_LEN */
#define SMP_LEN ((u32_1)FN(0x0804A4E4))     /* a sample's length in samples, as the stock's half / double read it */
#define COLOURS 0x20003974u
#define CLR_CUE 0x54                        /* the stock's dim red: a length the sample cannot reach */
#define CLR_RED 0x55
#define DIM 48                              /* of 255 */
#define HALF 128
#define DIM_MUL 141                         /* the stock's dimmed LEDs */

#define CONTROL 0x37400u                    /* route words, 4 a track */
#define SNAPSHOT 0x37420u                   /* core 1's voice snapshot, 8 words a track: word 7 the note's serial */
#define POOL 0x2400u                        /* host parameter words, 256 a track (16 used) */
#define ROUTE_KEY 0x674E31u
#define NATIVE_IN_LOOP 2                    /* route word 3: core 1's own reader runs on in Loop play mode, so off is in time */
#define FADING_OUT 3                        /* route word 3: core 1 crossfades back to its own reader (8 blocks, 5.3 ms) */
#define DRAINING 4                          /* route word 3: the engine plays on, core 1's own reader runs unheard */
#define FADE_MS 10                          /* then the words go off */
#define SPEED_ONE (1u << 20)
#define HAL_TICK 0x20006F3Cu                /* ms */
#define GR_KEY 0x6A7A4Bu                    /* Granular's word 15 */
#define W_SPD 0                             /* Q20 speed, or 0 */
#define W_TGT 2                             /* a length in samples, or 0; with TGT_PART the part fits it */
#define BEAT_SAMPLES 2880000u               /* 60 s x 48 kHz: a beat's samples x the tempo */
#define SPD_MIN (1u << 18)                  /* 0.25 and 4 in Q20 */
#define SPD_MAX (4u << 20)
#define SCAN_STILL 1024                     /* Granular's Scan in sixteenths of a knob step */
#define SCAN_DEFAULT (72 * 16)              /* Granular's default Scan */

#define PAD_ON 8                            /* pad 9: on (the kept length, or Follow) / off */
#define PAD_FIT 9                           /* pad 10: the whole sample (white) or the part K2 / K3 play (amber) fits the length */
#define PAD_LEN 10                          /* pads 11-16: the lengths; the lit one again is Follow */
#define NLEN 6
#define PAD_GRAN 16                         /* pad 17: Granular on / off, as in its editor */
static const u8 QUARTERS[NLEN] = { 1, 2, 4, 8, 16, 32 };      /* 1/4, 1/2, 1, 2, 4 and 8 bars, in beats */
static const u32 RGB[NLEN] = { 0xE6D166, 0xCCDA66, 0xB3E466, 0x99ED66, 0x80F666, 0x66FF66 };  /* the probability gradient */
#define GREEN 0x66FF66
#define WHITE 0xFFFFFF
#define AMBER 0xFFA020
#define GR_ON_RGB 0x35DF74                  /* Granular's editor: its on / off pad */
#define GR_OFF_RGB 0xFF3040

/* the project block: "ST", check, version, then 3 B a track: bit 7 on, bit 3 the part fits, bits 0-2 the choice (0 Follow, 1-6 a length);
   Follow's tempo x 10 (u16): the tempo at which the sample plays at its own speed. No good block: every track off. */
#define BLK_LEN (4 + 8 * 3)
#define VERSION 1
#define ON 0x80
#define PART 0x08

#define SENT_TGT 0x80000000u                /* sent[t]: the length sent, with this bit, or the speed */
typedef struct {
    u8 on;                                  /* tracks with the stretch words sent; first: Granular reads it (G_STRETCH_ON) */
    u32 sent[8];
    u16 gscan[8];                           /* the Scan a length pad last set on a Granular track */
    u16 gprev[8];                           /* the Scan before it, 0 unknown */
    u16 mark[8];                            /* draining: the note's serial (low 16 bits); fading: HAL_TICK when it began */
    u8 fading;                              /* tracks fading out (route word 3 = FADING_OUT) */
    u8 draining;                            /* tracks off that play the note on at speed 1 until the next note */
    u8 round;
} State;
_Static_assert(sizeof(State) <= SLOT_LEN, "stretch: the RAM slot");
_Static_assert(__builtin_offsetof(State, on) == 0, "stretch: Granular reads the on byte at the slot");
#define S ((volatile State *)SLOT)

static u32 sel_track(void) { return *PARAM_GET(R32(CONT + O_SELTRK), 0) & 7; }
static int page_shown(void) { return R32(CTRL + O_VIEW) == CONT && R8(CONT + O_MODE) == MODE_SMP; }
static u32 tempo(void)
{
    u32 b = *TEMPO_GET(TEMPO, 0);
    return b < 30 ? 120 : b;
}
static int dsp_ok(void) { return READY() && !R8(UPLOAD); }
static int in_ram(u32 a) { return a - 0x20000000u < 0x50000u; }
static int built(u32 st) { return in_ram(st) && in_ram(R32(st + 0xC)) && in_ram(R32(st + 0x10)); }

/* ---- the block */
static u8 blk_sum(const volatile u8 *b)
{
    u32 s = 0;
    for (u32 i = 4; i < BLK_LEN; i++)
        s += b[i];
    return (u8)(s ^ 0x5A);
}
static int blk_ok(const volatile u8 *b) { return b[0] == 'S' && b[1] == 'T' && b[3] == VERSION && b[2] == blk_sum(b); }
static u32 rec(u32 t)                       /* byte 0 | Follow's tempo x 10 << 8 */
{
    u32 tail = RRT();
    const volatile u8 *b = (const volatile u8 *)(tail + BLK_OFF);
    if (!tail || !blk_ok(b))
        return 0;
    b += 4 + 3 * t;
    return b[0] | (u32)b[1] << 8 | (u32)b[2] << 16;
}
static void rec_put(u32 t, u32 v)
{
    u32 tail = RRT();
    if (!tail)
        return;
    volatile u8 *b = (volatile u8 *)(tail + BLK_OFF);
    if (!blk_ok(b)) {                       /* readers see a bad block (all off) until the check byte */
        for (u32 i = 4; i < BLK_LEN; i++)
            b[i] = 0;
        b[0] = 'S'; b[1] = 'T'; b[3] = VERSION;
        b[2] = blk_sum(b);
    }
    u32 s = b[2] ^ 0x5A, o = 4 + 3 * t;
    s = s - b[o] - b[o + 1] - b[o + 2] + (v & 0xFF) + (v >> 8 & 0xFF) + (v >> 16 & 0xFF);
    __asm volatile("cpsid i" ::: "memory");
    b[o] = (u8)v; b[o + 1] = (u8)(v >> 8); b[o + 2] = (u8)(v >> 16);
    b[2] = (u8)(s ^ 0x5A);
    __asm volatile("cpsie i" ::: "memory");
}

/* ---- the track's sample, before any note: the stock's length, and the part from K2 / K3 as core 1 sets it */
static u32 scale(u32 p, u32 n) { return p * (n >> 14) + (p * (n & 0x3FFF) >> 14); }    /* p / 16384 of n */
static u32 knob(u32 st, u32 k) { return *PARAM_GET(st, k) * 128u + *PARAM_GET(st, k + 13); }
static u32 src_len(u32 t, u32 part)         /* 0: unknown */
{
    u32 ps = R32(PLAYERS + PLAYER_SZ * t + O_SAMPLE), ks = R32(CTRL + KSTORES + 4 * t);
    if (!built(ps) || !in_ram(R32(SMPMGR)))
        return 0;
    u32 smp = *PARAM_GET(ps, 0), n = smp < 128 ? SMP_LEN(smp) : 0;
    if (!part || !n || !built(ks))
        return n;
    u32 a = scale(knob(ks, 1), n), b = a + scale(knob(ks, 2) + 1, n);
    return (b > n ? n : b) - a;
}

/* ---- the words */
static u32 length_of(u32 k, u32 bpm) { return QUARTERS[k] * BEAT_SAMPLES / bpm; }
static int reachable(u32 n, u32 len) { return !n || (4 * n >= len && n <= 4 * len); }
static u32 isqrt(u32 x)
{
    u32 r = 0;
    for (u32 b = 1u << 30; b; b >>= 2)
        if (x >= r + b) { x -= r + b; r = (r >> 1) + b; } else r >>= 1;
    return r;
}
/* Granular's Scan for a length: the playhead moves s^2 / 64 samples a block (s in knob steps from still), so the region
   n lasts len when (16 s)^2 = 2^19 n / len. ~0: unknown or out of reach. */
static u32 scan_for(u32 n, u32 len)
{
    if (!n || !len)
        return ~0u;
    u32 q = n / len, r = n % len;
    if (q >= 2)
        return ~0u;
    u32 s16 = isqrt((q << 19) + (((r << 10) / len) << 9));
    return s16 >= 1 && s16 < SCAN_STILL ? SCAN_STILL + s16 : ~0u;
}
static void want(u32 t, u32 bpm, u32 *spd, u32 *tgt)    /* both 0: off */
{
    u32 r = rec(t), ch = r & 7;
    *spd = *tgt = 0;
    if (!(r & ON) || ch > NLEN)
        return;
    if (ch) {
        *tgt = length_of(ch - 1, bpm) | (r & PART ? TGT_PART : 0);
        return;
    }
    u32 t10 = r >> 8 ? r >> 8 : bpm * 10, v = (bpm * 10 << 20) / t10;
    *spd = v < SPD_MIN ? SPD_MIN : v > SPD_MAX ? SPD_MAX : v;
}
static void words_on(u32 t, u32 spd, u32 tgt, int all)  /* the key before the route: the engine never sees Granular's words */
{
    DSP_WRITE(POOL + 256 * t + W_SPD, spd);
    DSP_WRITE(POOL + 256 * t + W_TGT, tgt);
    if (all) {
        DSP_WRITE(POOL + 256 * t + 15, HOST_KEY);
        DSP_WRITE(CONTROL + 4 * t + 3, NATIVE_IN_LOOP);
        DSP_WRITE(CONTROL + 4 * t, ROUTE_KEY);
    }
    S->sent[t] = tgt ? tgt | SENT_TGT : spd;
    S->on |= 1u << t;
}
static void words_granular(u32 t)           /* Granular's own values for words 0, 2 and 15 */
{
    DSP_WRITE(POOL + 256 * t, t + 1);
    DSP_WRITE(POOL + 256 * t + 2, 0);
    DSP_WRITE(POOL + 256 * t + 15, GR_KEY);
    S->on &= ~(1u << t);
    S->fading &= ~(1u << t);
    S->draining &= ~(1u << t);
}
static void granular_follow(u32 t, u32 bpm)  /* a length pad's Scan follows the tempo and the sample until Scan is turned */
{
    u32 r = rec(t), ch = r & 7;
    if (!(r & ON) || !ch || ch > NLEN || !S->gscan[t])
        return;
    u32 now = SCAN(GSTATE, t, ~0u), v = scan_for(src_len(t, 1), length_of(ch - 1, bpm));
    if (now == S->gscan[t] && v != ~0u && v != now) {
        SCAN(GSTATE, t, v);
        S->gscan[t] = (u16)v;
    }
}
static void dsp_frame(u32 bpm)
{
    u32 rt = S->round & 7;
    S->round = (u8)(rt + 1);
    for (u32 t = 0; t < 8; t++) {
        u32 bit = 1u << t;
        if (BUSY(t)) {
            if (S->on & bit) {                  /* stretch's word 3 can land after Granular's: hand back Granular's value */
                words_granular(t);
                DSP_WRITE(CONTROL + 4 * t + 3, ROUTE(GSTATE, t));
            }
            granular_follow(t, bpm);
            continue;
        }
        u32 spd, tgt;
        want(t, bpm, &spd, &tgt);
        if (spd | tgt) {
            if (!(S->on & bit) || ((S->fading | S->draining) & bit) || t == rt) {
                S->fading &= ~bit;
                S->draining &= ~bit;
                words_on(t, spd, tgt, 1);
            } else if (S->sent[t] != (tgt ? tgt | SENT_TGT : spd))
                words_on(t, spd, tgt, 0);
        } else if (S->on & bit) {
            /* core 1's own reader stopped where the engine took the note: the engine ends the note at speed 1, and at
               the next note, with both readers at its start, core 1 fades back to its own */
            u16 now = (u16)R32(HAL_TICK), serial = (u16)SHARED_READ(SNAPSHOT + 8 * t + 7);
            if (!((S->fading | S->draining) & bit)) {
                DSP_WRITE(POOL + 256 * t + W_SPD, SPEED_ONE);
                DSP_WRITE(POOL + 256 * t + W_TGT, 0);
                DSP_WRITE(CONTROL + 4 * t + 3, DRAINING);
                S->sent[t] = SPEED_ONE;
                S->draining |= bit;
                S->mark[t] = serial;
            } else if (S->draining & bit) {
                if (serial != S->mark[t]) {
                    DSP_WRITE(CONTROL + 4 * t + 3, FADING_OUT);
                    S->draining &= ~bit;
                    S->fading |= bit;
                    S->mark[t] = now;
                }
            } else if ((u16)(now - S->mark[t]) >= FADE_MS) {
                DSP_WRITE(CONTROL + 4 * t, 0);
                DSP_WRITE(CONTROL + 4 * t + 3, 1);
                words_granular(t);
            }
        }
    }
}

/* ---- the lights */
static u32 scl(u32 rgb, u32 lvl)
{
    u32 o = 0;
    for (u32 sh = 0; sh < 24; sh += 8)
        o |= (((rgb >> sh) & 0xFF) * (lvl + 1) >> 8) << sh;
    return o;
}
static void draw(volatile u32 *out, u32 t, u32 bpm)
{
    u32 dimmed = (*(volatile u32 *)PARAM_GET(R32(CTRL + O_DIMS), 2) >> 10) & 1;
    u32 full = dimmed ? DIM_MUL : 255, lo = DIM * full >> 8, half = HALF * full >> 8;
    u32 r = rec(t), on = r & ON, ch = r & 7, n = src_len(t, BUSY(t) || (r & PART)), cue = scl(R32(COLOURS + 4 * CLR_CUE), full);
    u32 lit = on ? full : half, red = scl(R32(COLOURS + 4 * CLR_RED), lo);
    out[PAD_GRAN] = scl(GSWITCH(GSTATE, t, ~0u) ? GR_ON_RGB : GR_OFF_RGB, full);
    if (BUSY(t)) {
        u32 now = SCAN(GSTATE, t, ~0u);
        out[PAD_ON] = red;
        out[PAD_FIT] = 0;
        for (u32 k = 0; k < NLEN; k++) {
            u32 ok = now != ~0u && scan_for(n, length_of(k, bpm)) != ~0u;
            u32 chosen = on && ch == k + 1 && now == S->gscan[t];
            out[PAD_LEN + k] = ok ? scl(RGB[k], chosen ? full : lo) : cue;
        }
        return;
    }
    out[PAD_ON] = on ? scl(GREEN, full) : red;
    out[PAD_FIT] = scl(r & PART ? AMBER : WHITE, lit);
    for (u32 k = 0; k < NLEN; k++)
        out[PAD_LEN + k] = reachable(n, length_of(k, bpm)) ? scl(RGB[k], ch == k + 1 ? lit : lo) : cue;
}

u32 c_st_out(u32 c, u32 out, u32 frame, u32 a3)
{
    u32 ret = ((hook_fn)FN(PREV_OUT))(c, out, frame, a3);
    if (!RST())
        return ret;
    u32 bpm = tempo(), shown = page_shown(), t = sel_track();
    if (dsp_ok())
        dsp_frame(bpm);
    if (shown)
        draw((volatile u32 *)out, t, bpm);
    return ret;
}

#ifdef PREV_WIPE
/* Clear + track's wipe (trackreset's page reset call, r0 = the track): stretch off, its choices back to their defaults */
u32 c_st_wipe(u32 t, u32 a1, u32 a2, u32 a3)
{
    if (t < 8 && RST()) {
        rec_put(t, 0);
        S->gscan[t] = 0;
        S->gprev[t] = 0;
    }
    return ((hook_fn)FN(PREV_WIPE))(t, a1, a2, a3);
}
#endif

/* Sample mode's pads (slot 0 of its subview, presses only): 9-17 ours, the rest the stock's */
u32 c_st_pad(u32 sub, u32 pad, u32 vel, u32 a3)
{
    if (pad < PAD_ON || pad > PAD_GRAN || !RST())
        return ((hook_fn)FN(PREV_PAD))(sub, pad, vel, a3);
    u32 t = sel_track(), bpm = tempo(), r = rec(t), ch = r & 7, t10 = r >> 8, part = r & PART;
    u32 off = (r & ~ON & 0xFF) | t10 << 8, follow = ON | part | (bpm * 10) << 8;    /* Follow takes the tempo each time it starts */
    u32 back = ch ? ON | (r & 0xFF) | t10 << 8 : follow;                            /* on again: the kept length */
    if (pad == PAD_GRAN) {                  /* Granular and stretch turn each other off */
        GSWITCH(GSTATE, t, !GSWITCH(GSTATE, t, ~0u));
        rec_put(t, off);
        return 0;
    }
    if (pad == PAD_ON && BUSY(t)) {
        GSWITCH(GSTATE, t, 0);
        rec_put(t, back);
        return 0;
    }
    if (BUSY(t)) {
        if (pad < PAD_LEN)
            return 0;
        u32 k = pad - PAD_LEN, now = SCAN(GSTATE, t, ~0u), ours = S->gscan[t] && now == S->gscan[t];
        if (ours && (r & ON) && ch == k + 1) {  /* the chosen pad again: Scan back to before, the choice kept */
            SCAN(GSTATE, t, S->gprev[t] ? S->gprev[t] : SCAN_DEFAULT);
            S->gscan[t] = 0;
            rec_put(t, (r & ~ON & 0xFF) | t10 << 8);
            return 0;
        }
        u32 v = now == ~0u ? ~0u : scan_for(src_len(t, 1), length_of(k, bpm));
        if (v != ~0u) {
            if (!ours)
                S->gprev[t] = (u16)now;
            SCAN(GSTATE, t, v);
            S->gscan[t] = (u16)v;
            rec_put(t, ON | part | (k + 1) | t10 << 8);
        }
        return 0;
    }
    if (pad == PAD_ON) {                    /* off keeps the length for the next on */
        rec_put(t, r & ON ? off : back);
    } else if (pad == PAD_FIT) {
        rec_put(t, ((r & 0xFF) ^ PART) | t10 << 8);
    } else if ((r & ON) && ch == pad - PAD_LEN + 1) {
        rec_put(t, follow);
    } else if (reachable(src_len(t, part), length_of(pad - PAD_LEN, bpm))) {
        rec_put(t, ON | part | (pad - PAD_LEN + 1) | t10 << 8);
    }
    return 0;
}
