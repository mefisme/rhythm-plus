/* Step Mutate (Rhythm Plus, MIT): Shift + tap Duplicate on a track view mutates the selected track's pattern with that track's
   settings; Shift + hold Duplicate opens the settings page. Built by stepmut.py, which passes the addresses below with -D. */
#include <stdint.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#ifndef OFFLOAD
#define OFFLOAD 0
#endif
#if OFFLOAD
/* Patched to the owned storage accessor after both modules are linked. */
__attribute__((naked,noinline)) u32 c_sm_store(void) { __asm volatile("movs r0,#0\n bx lr"); }
#endif

#define R32(a) (*(volatile u32 *)(a))
#define R8(a) (*(volatile u8 *)(a))
#define FN(a) ((u32)(a) | 1)

typedef u8 *(*get_fn)(u32 store, u32 item);
typedef u32 (*hook_fn)(u32, u32, u32, u32);
typedef void (*obj_fn)(u32 obj);
typedef u32 (*u32_fn)(void);

#define PARAM_GET ((get_fn)FN(0x0803FC58))
#define RELOAD ((obj_fn)FN(0x08048932))     /* the stock's pattern load: the edit stores from the pattern, notified */
#define RAND ((u32_fn)FN(0x08047104))       /* the stock's random (the stock Mutate's): 0 .. 2^30 - 1 */
#define RRT ((u32_fn)FN(C_RRT))
#define CIOK ((u32_fn)FN(C_CIOK))

#define CTRL 0x200487C8u
#define O_VIEW 0x7C
#define O_HELD 0xA0
#define O_DIMS 0x88
#define O_VIEWWORD 0x14                     /* the view word: bits 16-23 = the view button's group */
#define CONT 0x20048B9Cu
#define O_SELTRK 0x25C
#define O_MAINMODE 0x260                    /* item t: track t's main view (its Note or Sample view), the mode a track press gives */
#define O_MODE 0x264
#define ENGINE 0x2003D2FCu
#define O_RECS 0x84
#define HAL_TICK 0x20006F3Cu
#define COLOURS 0x20003974u
#define GRAD0 0x76
#define FRAME_PULSE 0x0A
#define CLR_CUE 0x54                        /* the stock's dim red (pad 26's cue), palette code */
#define CLR_RED 0x55
#define FLASH_MS 384                        /* three red flashes, 64 ms on, 64 ms off */
#define PLAYERS 0x200470D4u
#define PLAYER_SZ 0x190
#define O_SAMPLE 0x60

#define ID_VIEW0 8                          /* the five two-view buttons, 8-12 */
#define ID_VIEW4 12
#define ID_REC 16
#define ID_PLAY 17
#define ID_CLEAR 23
#define ID_DUP 24
#define BIT_CLEAR 23
#define ID_SHIFT 27
#define LED_DUP 56

#define PAT_SZ 0xA28
#define P_END 0x100
#define P_START 0x101
#define P_SPEED 0x102
#define P_MODE 0x103
#define P_LANES 0x128
#define LANES 12
#define LANE_SZ 0xC0

#define HOLD_MS 333                         /* Duplicate, and a view button held to look at its view */
#define PAD_HOLD_MS 400
#define DIM 48                              /* of 255: a value or target not chosen */
#define DUP_DIM 80
#define DIM_MUL 141                         /* the stock's dimmed LEDs */
#define COL0 5                              /* the settings: pad columns 6-8 */

#define FL_OPEN 1
#define FL_PEND 2                           /* Shift + Duplicate down: the stock's mutate waits for the release */
#define FL_DUPDN 4
#define FL_PADHELD 8                        /* the held target pad already showed its settings */
#define FL_HIDE 16                          /* a view button held over the page: its view shows */
#define FL_BACK 32                          /* that button let go after a hold: the page again, on a track view */
#define FL_EDIT 64                          /* the editor was open under the page: a Duplicate tap gives it back */
struct slot {                               /* SLOT, 32 B */
    u8 flags, shown, pend_trk, held_pad;    /* shown: target + 1 (0 = Step movement); held_pad: pad + 1, 0 = none */
    u32 dup_t0, pad_t0, back_t0, pend_obj, taken, trk_taken;
    u8 back_id, flash_pad;                  /* flash_pad: the cleared target's pad + 1 */
    u16 flash_t0;
};
#define S ((volatile struct slot *)SLOT)

/* the project block: "SM", check, version, then 8 tracks x 12 B: 10 target bytes (setting k in bits 2k, 2k + 1; Play mode: a
   mode a bit), the targets on (bit i, u16) */
#define VERSION 2
#define BLK_LEN (4 + 8 * 12)
#define TRK_LEN 12
#define O_ON 10

enum { T_NOTE, T_SAMPLE, T_MOVE, T_VEL, T_GATE, T_MICRO, T_LEN, T_SPEED, T_MODE, T_PROB, NT };
static const u8 T_PAD[NT] = { 0, 1, 2, 8, 16, 17, 24, 25, 26, 27 };
static const u8 DEFAULTS[TRK_LEN] = { 0x2E, 0x0A, 0x00, 0x2A, 0x2A, 0x1E, 0x02, 0x02, 0x07, 0x0A, 1 << T_MOVE, 0 };
/* each setting: kind << 4 | values; kind 0 meter, 1 choice, 2 toggles; 0 = none */
#define M(n) (0x00 | (n))
#define C(n) (0x10 | (n))
#define TG(n) (0x20 | (n))
static const u8 COLS[NT][3] = {
    { M(4), M(4), C(3) }, { M(4), M(4), C(2) }, { M(4), M(4), 0 }, { M(4), M(4), C(3) }, { M(4), M(4), C(3) },
    { M(4), M(4), C(2) }, { M(4), C(3), 0 }, { M(3), 0, 0 }, { TG(4), 0, 0 }, { M(4), M(4), 0 },
};
static const u32 T_RGB[NT] = {              /* the probability gradient in 10 steps, yellow (ffc866) to green (66ff66) */
    0xFFC866, 0xEECE66, 0xDDD466, 0xCCDA66, 0xBBE066, 0xAAE766, 0x99ED66, 0x88F366, 0x77F966, 0x66FF66,
};
static const u8 METER_CODE[4] = { 7, 5, 3, 1 };

static const u8 NOTE_R[4] = { 0, 12, 7, 3 };       /* 0 = any */
static const u8 FLIP_W[4] = { 0, 0, 8, 4 };        /* the window around the track's sample; 0 = all 64 */
#define FLIP_GROW 1                                 /* Range choice: +-1 from the step's own flip */
static const u8 VEL_R[4] = { 0, 48, 24, 8 };
static const u8 GATE_R[4] = { 0, 12, 6, 3 };
static const u8 HITS[4] = { 6, 4, 3, 2 };
static const u8 HIT_MASK[7] = { 0, 1, 0x09, 0x15, 0x1B, 0x1F, 0x3F };
static const u8 MOVE_R[4] = { 0, 8, 4, 2 };
static const u8 LEN_R[4] = { 0, 8, 4, 2 };
static const u8 SPEED_R[3] = { 0, 2, 1 };
static const u8 PROB_FLOOR[4] = { 0, 1, 3, 5 };
#define NOTE_LO 25                          /* the note view's keyboard: 25 .. 108; 0x30 = the sample's pitch */
#define NOTE_HI 108
#define GATE_MAX 96
#define NSAMPLES 64

static u32 now(void) { return R32(HAL_TICK); }
static u32 held(void) { return R32(CTRL + O_HELD); }
static int on_track_view(void) { return R32(CTRL + O_VIEW) == CONT; }
static u32 sel_track(void) { return *PARAM_GET(R32(CONT + O_SELTRK), 0) & 7; }
static int editor_open(void) { return R8(TM_SLOT + TM_OPEN) != 0; }
static void editor_forget(void) { R8(TM_SLOT + TM_PTRK) = 0; R8(TM_SLOT + TM_SHOP) = 0; }   /* its track tap / hold / Shift + track */
static void editor_close(void)                  /* as the editor's own close on another button */
{
    R8(TM_SLOT + TM_OPEN) = 0;
    R8(TM_SLOT + TM_STICKY) = 0;
    R8(TM_SLOT + TM_BACK) = 0;
    R8(TM_SLOT + TM_ARM) = TM_ARM_OFF;
    editor_forget();
}
static u32 shown(void) { return S->shown ? S->shown - 1u : T_MOVE; }
static u32 rnd(u32 n) { return n ? RAND() % n : 0; }

/* ---- the block */
static u8 blk_sum(const volatile u8 *b)
{
    u32 s = 0;
    for (u32 i = 4; i < BLK_LEN; i++)
        s += b[i];
    return (u8)(s ^ 0x5C);
}
static int blk_ok(const volatile u8 *b) { return b[0] == 'S' && b[1] == 'M' && b[3] == VERSION && b[2] == blk_sum(b); }
static const volatile u8 *trk_rec(u32 t)
{
#if OFFLOAD
    const volatile u8 *b = (const volatile u8 *)c_sm_store();
    return b && blk_ok(b) ? b + 4 + TRK_LEN * t : (const volatile u8 *)DEFAULTS;
#else
    u32 tail = RRT();
    const volatile u8 *b = (const volatile u8 *)(tail + BLK_OFF);
    return tail && blk_ok(b) ? b + 4 + TRK_LEN * t : (const volatile u8 *)DEFAULTS;
#endif
}
static void blk_set(u32 t, u32 i, u8 v)     /* byte i of track t's record, the block made ours first */
{
#if OFFLOAD
    volatile u8 *b = (volatile u8 *)c_sm_store();
    if (!b) return;
#else
    u32 tail = RRT();
    if (!tail)
        return;
    volatile u8 *b = (volatile u8 *)(tail + BLK_OFF);
#endif
    __asm volatile("cpsid i" ::: "memory");
    if (!blk_ok(b)) {
        for (u32 k = 0; k < 8 * TRK_LEN; k++)
            b[4 + k] = DEFAULTS[k % TRK_LEN];
        b[0] = 'S'; b[1] = 'M'; b[3] = VERSION;
    }
    b[4 + TRK_LEN * t + i] = v;
    b[2] = blk_sum(b);
    __asm volatile("cpsie i" ::: "memory");
}
static u32 col(const volatile u8 *r, u32 tg, u32 k) { return (r[tg] >> (2 * k)) & 3; }
static u32 ons(const volatile u8 *r) { return r[O_ON] | r[O_ON + 1] << 8; }
static u32 is_on(const volatile u8 *r, u32 tg) { return (ons(r) >> tg) & 1; }

/* ---- the mutate */
static u32 obj_of(u32 t) { return R32(ENGINE + O_RECS + 4 * t); }

/* a new value 1 .. r away from v (r = 0: any distance), up (dir 0), down (1) or either (2), in lo .. hi, each one as likely */
static u32 pick(u32 v, u32 r, u32 dir, u32 lo, u32 hi)
{
    if (v < lo) v = lo;
    if (v > hi) v = hi;
    u32 a = dir == 0 ? v : (!r || v - lo < r) ? lo : v - r;
    u32 b = dir == 1 ? v : (!r || hi - v < r) ? hi : v + r;
    if (b == a)
        return v;
    u32 x = a + rnd(b - a);
    return x >= v ? x + 1 : x;
}

/* Optional Grid FX adapter. gfxmix installs these four-byte stubs after us.
   Naked assembly keeps calls opaque to the compiler when the feature is absent. */
__attribute__((naked, noinline)) u32 c_sm_fxread(u32 t, u32 pat, u8 *codes)
{ __asm volatile("movs r0, #0\n bx lr"); }
__attribute__((naked, noinline)) void c_sm_fxwrite(u32 t, u32 pat, const u8 *codes)
{ __asm volatile("bx lr\n nop"); }
__attribute__((naked, noinline)) void c_sm_fxsample(u32 t, u32 pat, u32 st, u32 cfg)
{ __asm volatile("bx lr\n nop"); }

static void swap_steps(u8 *pat, u32 a, u32 b, u8 *fx)
{
    if (a == b)
        return;
    if (fx) { u8 x = fx[a]; fx[a] = fx[b]; fx[b] = x; }
    for (u32 i = 0; i < 8; i++) {
        u8 x = pat[8 * a + i]; pat[8 * a + i] = pat[8 * b + i]; pat[8 * b + i] = x;
    }
    for (u32 l = 0; l < LANES; l++) {
        u8 *ln = pat + P_LANES + LANE_SZ * l;
        for (u32 m = 0; m < 6; m++) {
            u8 x = ln[6 * a + m]; ln[6 * a + m] = ln[6 * b + m]; ln[6 * b + m] = x;
        }
    }
}

static int counts(const u8 *st, u32 flipped) { return st[2] != 0 && (!flipped || st[5] != 0xFF); }

/* steps idx[0 .. len - 1] (start .. end); fills sel[] with the chosen note steps' positions in idx (flipped: only steps with a
   sample flip), returns their count */
static u32 choose(const u8 *pat, const u8 *idx, u32 len, u32 amount, u8 *sel, u32 flipped, const u8 *fx)
{
    u32 cnt = 0, n, k = 0;
    for (u32 i = 0; i < len; i++)
        cnt += (fx && flipped ? pat[8 * idx[i] + 2] != 0 && (fx[idx[i]] & 64) != 0 : counts(pat + 8 * idx[i], flipped));
    if (!cnt)
        return 0;
    n = (cnt * (4 - amount) + 2) / 4;
    if (!n)
        n = 1;
    for (u32 i = 0; i < len && n; i++) {
        if (!(fx && flipped ? pat[8 * idx[i] + 2] != 0 && (fx[idx[i]] & 64) != 0 : counts(pat + 8 * idx[i], flipped)))
            continue;
        if (rnd(cnt) < n) {
            sel[k++] = (u8)i;
            n--;
        }
        cnt--;
    }
    return k;
}

static void mutate(u32 t, u32 obj)
{
#if OFFLOAD
    if (!c_sm_store()) return;
#endif
    const volatile u8 *r = trk_rec(t);
    u8 rec[TRK_LEN], idx[32], sel[32], codes[32];
    for (u32 i = 0; i < TRK_LEN; i++)
        rec[i] = r[i];
    if (!(ons(rec) & ((1u << NT) - 1)) || !obj)
        return;
    u32 pn = *PARAM_GET(R32(obj + 0x28), 0) & 7;
    u8 *pat = (u8 *)(R32(obj + 4) + PAT_SZ * pn);
    u32 start = pat[P_START] & 31, len = ((pat[P_END] - start) & 31) + 1;
    for (u32 i = 0; i < len; i++)
        idx[i] = (u8)((start + i) & 31);
    u32 tsample = *PARAM_GET(R32(PLAYERS + PLAYER_SZ * t + O_SAMPLE), 0) & (NSAMPLES - 1);
    RAND();                                  /* its first call seeds it, outside the critical section */

    __asm volatile("cpsid i" ::: "memory");
    u8 *fx = c_sm_fxread(t, pn, codes) ? codes : 0;
    for (u32 tg = 0; tg <= T_MICRO; tg++) {
        if (!is_on(rec, tg) || tg == T_MOVE)
            continue;
        u32 c1 = col(rec, tg, 1), c2 = col(rec, tg, 2);
        u32 n = choose(pat, idx, len, col(rec, tg, 0), sel, tg == T_SAMPLE && c2 == 0, fx);
        for (u32 j = 0; j < n; j++) {
            u8 *st = pat + 8 * idx[sel[j]];
            switch (tg) {
            case T_NOTE:
                st[0] = (u8)pick(st[0] ? st[0] : 0x30, NOTE_R[c1], c2, NOTE_LO, NOTE_HI);
                break;
            case T_SAMPLE: {
                if (fx) {
                    c_sm_fxsample(t, pn, idx[sel[j]], c1);
                    break;
                }
                u32 w = FLIP_W[c1], lo = 0, hi = NSAMPLES - 1, cur = st[5];
                if (c1 == FLIP_GROW) {
                    st[5] = (u8)(((cur != 0xFF ? cur : tsample) + (rnd(2) ? 1 : NSAMPLES - 1)) % NSAMPLES);
                    break;
                }
                if (w) {
                    lo = tsample > w ? tsample - w : 0;
                    hi = tsample + w < NSAMPLES ? tsample + w : NSAMPLES - 1;
                }
                u32 skip = cur >= lo && cur <= hi && hi > lo, x = lo + rnd(hi - lo + 1 - skip);
                st[5] = (u8)(skip && x >= cur ? x + 1 : x);
                break;
            }
            case T_VEL:
                st[3] = (u8)pick(st[3], VEL_R[c1], c2, 1, 127);
                break;
            case T_GATE:
                st[1] = (u8)pick(st[1], GATE_R[c1], c2, 1, GATE_MAX);
                break;
            case T_MICRO: {                     /* 1 .. HITS hits; c2 0: on random microsteps, 1: the even roll from the first */
                u32 k = 1 + rnd(HITS[c1]), m = 0;
                if (c2 == 0) {
                    for (u32 bit = 0; bit < 6; bit++)
                        if (rnd(6 - bit) < k) {
                            m |= 1u << bit;
                            k--;
                        }
                } else {
                    m = HIT_MASK[k];
                }
                st[2] = (u8)m;
                break;
            }
            }
        }
    }
    if (is_on(rec, T_PROB)) {
        u32 n = choose(pat, idx, len, col(rec, T_PROB, 0), sel, 0, fx), f = PROB_FLOOR[col(rec, T_PROB, 1)];
        for (u32 j = 0; j < n; j++)
            pat[8 * idx[sel[j]] + 4] = (u8)(f + rnd(8 - f));
    }
    if (fx)
        c_sm_fxread(t, pn, codes);   /* sample mutations may have changed the packed codes */
    if (is_on(rec, T_MOVE) && len > 1) {
        u32 amount = col(rec, T_MOVE, 0), rg = MOVE_R[col(rec, T_MOVE, 1)];
        if (!amount && !rg) {                /* All, Anywhere: the stock Mutate's shuffle, empty steps too */
            for (u32 i = 0; i + 1 < len; i++)
                swap_steps(pat, idx[i], idx[i + rnd(len - i)], fx);
        } else {
            u32 n = choose(pat, idx, len, amount, sel, 0, fx);
            if (!rg || rg > len - 1)
                rg = len - 1;
            for (u32 j = 0; j < n; j++) {
                u32 d = 1 + rnd(rg), p = sel[j];
                swap_steps(pat, idx[p], idx[rnd(2) ? (p + d) % len : (p + len - d) % len], fx);
            }
        }
    }
    if (is_on(rec, T_SPEED))
        pat[P_SPEED] = (u8)pick(pat[P_SPEED] & 7, SPEED_R[col(rec, T_SPEED, 0)], 2, 0, 7);
    if (is_on(rec, T_MODE)) {
        u32 m = rec[T_MODE] & 15, cur = pat[P_MODE] & 3, cand = m & ~(1u << cur), k = 0;
        u8 list[4];
        if (!cand)
            cand = m;
        for (u32 i = 0; i < 4; i++)
            if (cand >> i & 1)
                list[k++] = (u8)i;
        if (k)
            pat[P_MODE] = list[rnd(k)];
    }
    if (is_on(rec, T_LEN) && start <= (pat[P_END] & 31)) {
        u32 rg = LEN_R[col(rec, T_LEN, 0)], which = col(rec, T_LEN, 1), s = start, e = pat[P_END] & 31;
        if (which != 1)
            e = pick(e, rg, 2, s, 31);
        if (which != 0)
            s = pick(s, rg, 2, 0, e);
        pat[P_START] = (u8)s;
        pat[P_END] = (u8)e;
    }
    if (fx)
        c_sm_fxwrite(t, pn, codes);
    __asm volatile("cpsie i" ::: "memory");
    RELOAD(obj);
}

/* ---- Clear + a target pad: that target back to the stock's default, from the start to the end (Step movement: nothing) */
static void clear_target(u32 t, u32 tg)
{
    u32 obj = obj_of(t);
    u8 *pat = (u8 *)(R32(obj + 4) + PAT_SZ * (*PARAM_GET(R32(obj + 0x28), 0) & 7));
    u32 start = pat[P_START] & 31, len = ((pat[P_END] - start) & 31) + 1;
    __asm volatile("cpsid i" ::: "memory");
    for (u32 i = 0; i < len; i++) {
        u8 *st = pat + 8 * ((start + i) & 31);
        if (!st[2])
            continue;
        switch (tg) {
        case T_NOTE: st[0] = 0; break;
        case T_SAMPLE: st[5] = 0xFF; break;
        case T_VEL: st[3] = 0x60; break;
        case T_GATE: st[1] = 6; break;
        case T_MICRO: st[2] &= (u8)-st[2]; break;      /* the first hit only */
        case T_PROB: st[4] = 7; break;
        }
    }
    if (tg == T_LEN) {
        pat[P_START] = 0;
        pat[P_END] = 15;
    } else if (tg == T_SPEED) {
        pat[P_SPEED] = 3;
    } else if (tg == T_MODE) {
        pat[P_MODE] = 0;
    }
    __asm volatile("cpsie i" ::: "memory");
    RELOAD(obj);
}

/* ---- the stock's Mutate call (0x0803656C): r0 = the track's step object */
void c_sm_mut(u32 obj)
{
    u32 t = 0;
    while (t < 8 && obj_of(t) != obj)
        t++;
    if (t == 8)
        return;
    if (S->flags & FL_DUPDN) {
        S->flags |= FL_PEND;
        S->pend_trk = (u8)t;
        S->pend_obj = obj;
        return;
    }
    mutate(t, obj);
}

static void close_page(void) { S->flags &= ~(FL_OPEN | FL_PADHELD | FL_HIDE | FL_BACK | FL_EDIT); S->held_pad = 0; }
static int page_shown(void) { return (S->flags & (FL_OPEN | FL_HIDE)) == FL_OPEN; }

/* the stock gives a view button's second view when bits 16-23 of the view word match its group (0x0803D79C); with no group
   there, a press gives the first view, Shift + a press the second */
static u32 first_view(u32 c, u32 id, u32 a2, u32 a3)
{
    volatile u32 *vw = (volatile u32 *)PARAM_GET(R32(CTRL + O_VIEWWORD), 0);
    u32 w = *vw, nogrp = w | 0xFF0000u;
    *vw = nogrp;
    u32 ret = ((hook_fn)FN(PREV_BTN))(c, id, a2, a3);
    if (*vw == nogrp)
        *vw = w;
    return ret;
}

/* ---- buttons (ctrl, id) */
u32 c_sm_btn(u32 c, u32 id, u32 a2, u32 a3)
{
    if (id == ID_DUP) {
        if ((S->flags & FL_OPEN) && !(held() >> ID_SHIFT & 1)) {
            u32 back = S->flags & FL_EDIT;
            close_page();
            if (back) {
                R8(TM_SLOT + TM_OPEN) = 1;
                R8(TM_SLOT + TM_STICKY) = 1;
            }
        }
        S->flags = (S->flags & ~FL_PEND) | FL_DUPDN;
        S->dup_t0 = now();
    } else if (page_shown()) {
        if (id < 8) {
            if (id == sel_track()) {         /* the track's steps show; on its main view the stock never sees the button */
                S->flags |= FL_HIDE;
                S->back_id = (u8)id;
                S->back_t0 = now();
                if (R8(CONT + O_MODE) == *PARAM_GET(R32(CONT + O_MAINMODE), id)) {
                    S->trk_taken |= 1u << id;
                    return 0;
                }
                u32 ret = ((hook_fn)FN(PREV_BTN))(c, id, a2, a3);
                editor_forget();
                return ret;
            }
        } else if (id != ID_REC && id != ID_PLAY && id != ID_CLEAR && id != ID_SHIFT) {
            S->flags |= FL_HIDE;             /* its view shows; a tap closes the page, a hold brings it back */
            S->back_id = (u8)id;
            S->back_t0 = now();
            if (id >= ID_VIEW0 && id <= ID_VIEW4)
                return first_view(c, id, a2, a3);
        }
    }
    return ((hook_fn)FN(PREV_BTN))(c, id, a2, a3);
}

u32 c_sm_rel(u32 c, u32 id, u32 a2, u32 a3)
{
    u32 taken = id < 8 && (S->trk_taken >> id & 1);
    S->trk_taken &= ~(1u << id);
    if (id == ID_DUP) {
        u32 f = S->flags;
        S->flags = f & ~(FL_DUPDN | FL_PEND);
        if (f & FL_PEND)
            mutate(S->pend_trk, S->pend_obj);
    } else if ((S->flags & FL_HIDE) && !(S->flags & FL_BACK) && id == S->back_id) {
        if (now() - S->back_t0 >= HOLD_MS)
            S->flags |= FL_BACK;
        else
            close_page();
    }
    return taken ? 0 : ((hook_fn)FN(PREV_REL))(c, id, a2, a3);
}

/* ---- pads (ctrl, pad 0-31, velocity) */
static void press_setting(u32 t, u32 pad)
{
    u32 tg = shown(), k = (pad & 7) - COL0, row = pad >> 3, spec = COLS[tg][k];
    const volatile u8 *r = trk_rec(t);
    if (!spec || row >= (spec & 15))
        return;
    u8 v = r[tg];
    if ((spec >> 4) == 2)
        v ^= (u8)(1 << row);
    else
        v = (u8)((v & ~(3 << (2 * k))) | row << (2 * k));
    blk_set(t, tg, v);
}

static int target_of(u32 pad)
{
    for (u32 tg = 0; tg < NT; tg++)
        if (T_PAD[tg] == pad)
            return (int)tg;
    return -1;
}

u32 c_sm_pad(u32 c, u32 pad, u32 vel, u32 a3)
{
    if (!page_shown() || pad > 31)
        return ((hook_fn)FN(PREV_PAD))(c, pad, vel, a3);
    S->taken |= 1u << pad;
    int ct = target_of(pad);
    if (ct >= 0 && (held() >> BIT_CLEAR & 1)) {
        if (ct != T_MOVE) {
            clear_target(sel_track(), (u32)ct);
            S->flash_pad = (u8)(pad + 1);
            S->flash_t0 = (u16)now();
        }
        S->held_pad = 0;
    } else if (ct >= 0) {
        S->held_pad = (u8)(pad + 1);
        S->pad_t0 = now();
        S->flags &= ~FL_PADHELD;
    } else if ((pad & 7) >= COL0 && !(held() >> BIT_CLEAR & 1)) {
        press_setting(sel_track(), pad);
    }
    return 0;
}

u32 c_sm_padrel(u32 c, u32 pad, u32 a2, u32 a3)
{
    if (pad > 31 || !(S->taken >> pad & 1))
        return ((hook_fn)FN(PREV_PADREL))(c, pad, a2, a3);
    S->taken &= ~(1u << pad);
    if (S->held_pad == pad + 1) {
        int tg = target_of(pad);
        if (!(S->flags & FL_PADHELD) && tg >= 0 && page_shown()) {
            u32 t = sel_track(), on = ons(trk_rec(t)) ^ (1u << tg);
            blk_set(t, O_ON, (u8)on);
            blk_set(t, O_ON + 1, (u8)(on >> 8));
        }
        S->held_pad = 0;
        S->flags &= ~FL_PADHELD;
    }
    return 0;
}

/* ---- the lights, after the output stage (ctrl, out words, frame) */
static u32 scl(u32 rgb, u32 lvl)
{
    u32 o = 0;
    for (u32 sh = 0; sh < 24; sh += 8)
        o |= (((rgb >> sh) & 0xFF) * (lvl + 1) >> 8) << sh;
    return o;
}
static u32 pulse(void) { return 64 + ((255 - (R32(COLOURS + 4 * FRAME_PULSE) & 0xFF)) * 192 >> 8); }

static void draw_page(volatile u32 *out, u32 dimmed)
{
    u32 sh = shown();
    const volatile u8 *r = trk_rec(sel_track());
    u32 full = dimmed ? DIM_MUL : 255, lo = DIM * full >> 8;
    for (u32 p = 0; p < 32; p++)
        out[p] = 0;
    u32 clr = held() >> BIT_CLEAR & 1;
    for (u32 tg = 0; tg < NT; tg++) {
        u32 l = is_on(r, tg) ? full : lo;
        if (tg == sh)
            l = l * pulse() >> 8;
        out[T_PAD[tg]] = !clr ? scl(T_RGB[tg], l) : tg == T_MOVE ? 0 : scl(R32(COLOURS + 4 * CLR_CUE), full);
    }
    if (S->flash_pad) {
        u32 e = (u16)((u16)now() - S->flash_t0);
        if (e >= FLASH_MS)
            S->flash_pad = 0;
        else
            out[S->flash_pad - 1] = (e >> 6) & 1 ? 0 : scl(R32(COLOURS + 4 * CLR_RED), full);
    }
    for (u32 k = 0; k < 3; k++) {
        u32 spec = COLS[sh][k], kind = spec >> 4, n = spec & 15, v = col(r, sh, k);
        for (u32 row = 0; row < n; row++) {
            u32 rgb, lit;
            if (kind == 0) {
                rgb = R32(COLOURS + 4 * (GRAD0 + METER_CODE[row]));
                lit = row >= v;
            } else {
                rgb = T_RGB[sh];
                lit = kind == 1 ? row == v : (r[sh] >> row) & 1;
            }
            out[8 * row + COL0 + k] = scl(rgb, lit ? full : lo);
        }
    }
    u32 g = R32(COLOURS + 4 * (GRAD0 + 7));
    out[LED_DUP] = (held() >> ID_DUP & 1) ? g : scl(g, pulse());
}

u32 c_sm_out(u32 c, u32 out, u32 frame, u32 a3)
{
    u32 ret = ((hook_fn)FN(PREV_OUT))(c, out, frame, a3);
    if (!CIOK())
        return ret;
#if OFFLOAD
    if (!c_sm_store()) { S->flags = 0; return ret; }
#endif
    volatile u32 *o = (volatile u32 *)out;
    u32 f = S->flags, h = held(), tnow = now();
    if (f & FL_BACK) {                       /* the held view button let go: the page again on a track view */
        if (on_track_view())
            S->flags = f & ~(FL_HIDE | FL_BACK);
        else
            close_page();
        f = S->flags;
    }
    if (f & FL_HIDE)
        return ret;
    if (!on_track_view()) {
        S->flags = f & ~(FL_OPEN | FL_PEND | FL_PADHELD | FL_EDIT);
        return ret;
    }
    if ((f & FL_PEND) && (h >> ID_DUP & 1) && tnow - S->dup_t0 >= HOLD_MS) {
        u32 ed = editor_open() ? FL_EDIT : 0;
        if (ed)
            editor_close();
        S->flags = (f & ~FL_PEND) | FL_OPEN | ed;
        S->held_pad = 0;
    }
    f = S->flags;
    if ((f & FL_OPEN) && S->held_pad && !(f & FL_PADHELD) && tnow - S->pad_t0 >= PAD_HOLD_MS) {
        int tg = target_of(S->held_pad - 1u);
        if (tg >= 0)
            S->shown = (u8)(tg + 1);
        S->flags |= FL_PADHELD;
    }
    u32 dimmed = (*(volatile u32 *)PARAM_GET(R32(CTRL + O_DIMS), 2) >> 10) & 1;
    if (S->flags & FL_OPEN) {
        draw_page(o, dimmed);
    } else if (h >> ID_SHIFT & 1) {
        if (ons(trk_rec(sel_track())) & ((1u << NT) - 1)) {
            u32 g = R32(COLOURS + 4 * (GRAD0 + 7));
            o[LED_DUP] = (h >> ID_DUP & 1) ? g : scl(g, DUP_DIM);
        }
    }
    return ret;
}

#ifdef QUANTIZE
/* ---- Pattern Settings pad 25: the view's pattern quantized to its steps. A single hit on microsteps 2-3 goes to microstep 1;
   on 4-6 to microstep 1 of the next step (the end step's to the start step). A hit that moves takes its whole step into an
   empty next step, else it adds microstep 1 there. Rolls stay. */
#define PS0 0x2004C4B8u
#define PS_SZ 0x60u
#define Q_PAD 24
#define Q_MAGIC 0x5154u
#define Q_MS 384
#define CLR_GREEN 0x1E
struct qflash { u16 magic; u8 ok, pad; u32 t0; };
#define QF ((volatile struct qflash *)Q_RAM)

static int single(const u8 *st) { return st[2] && !(st[2] & (st[2] - 1)); }
static int late(const u8 *st) { return single(st) && st[2] >= 8; }

static u32 quantize(u32 t)
{
    u32 obj = obj_of(t);
    if (!obj || !CIOK())
        return 0;
    u32 pn = *PARAM_GET(R32(obj + 0x28), 0) & 7;
    u8 *pat = (u8 *)(R32(obj + 4) + PAT_SZ * pn), was[32 * 8], fx[32], fxn[32];
    u32 start = pat[P_START] & 31, len = ((pat[P_END] - start) & 31) + 1;
    for (u32 i = 0; i < 32 * 8; i++)
        was[i] = pat[i];
    __asm volatile("cpsid i" ::: "memory");
    u32 hasfx = c_sm_fxread(t, pn, fx);
    for (u32 i = 0; i < 32; i++)
        fxn[i] = fx[i];
    for (u32 k = 0; k < len; k++) {
        u32 i = (start + k) & 31;
        u8 *st = pat + 8 * i;
        if (late(was + 8 * i)) {
            static const u8 empty[8] = {0, 6, 0, 0, 7, 0xFF, 0, 0};
            for (u32 b = 0; b < 8; b++)
                st[b] = empty[b];
            fxn[i] = 0;
        } else if (single(was + 8 * i)) {
            st[2] = 1;
        }
    }
    for (u32 k = 0; k < len; k++) {
        u32 i = (start + k) & 31, j = (start + (k + 1) % len) & 31;
        const u8 *from = was + 8 * i, *to = was + 8 * j;
        if (!late(from))
            continue;
        if (!to[2] || late(to)) {
            for (u32 b = 0; b < 8; b++)
                pat[8 * j + b] = from[b];
            pat[8 * j + 2] = 1;
            fxn[j] = fx[i];
        } else {
            pat[8 * j + 2] |= 1;
        }
    }
    if (hasfx)
        c_sm_fxwrite(t, pn, fxn);
    __asm volatile("cpsie i" ::: "memory");
    RELOAD(obj);
    return 1;
}

u32 c_sm_qpad(u32 view, u32 pad, u32 vel)
{
    u32 t = (view - PS0) / PS_SZ;
    if (pad != Q_PAD || view < PS0 || t >= 8)
        return ((hook_fn)FN(PREV_QPAD))(view, pad, vel, 0);
    if (vel) {
        QF->ok = (u8)quantize(t);
        QF->t0 = now();
        QF->magic = Q_MAGIC;
    }
    return view;
}

u32 c_sm_qled(u32 view)
{
    u32 r = ((u32 (*)(u32))FN(PREV_QLED))(view);
    volatile u16 *buf = (volatile u16 *)R32(R32(view + 4));
    u32 e = now() - QF->t0, c = Q_IDLE;
    if (QF->magic == Q_MAGIC && e < Q_MS)
#ifdef Q_FLASH
        c = (e >> 6) & 1 ? 0 : QF->ok ? Q_IDLE : CLR_RED;    /* done: the ready colour flashes */
#else
        c = QF->ok ? CLR_GREEN : ((e >> 6) & 1 ? 0 : CLR_RED);
#endif
    buf[Q_PAD] = (u16)c;
    return r;
}
#endif
