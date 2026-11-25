/* On-unit file tools (Rhythm Plus, MIT): Duplicate copies a project (Projects view) or a sample (Sample Rec view) to
   another slot, of this pack or of a pack loaded later; Clear deletes a pack (Packs view). Only the card's packs are
   written; the internal pack (0) is read only. Built by filetools.py, which passes the addresses below with -D. */
#include <stdint.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

#define R32(a) (*(volatile u32 *)(a))
#define R8(a) (*(volatile u8 *)(a))
#define FN(a) ((u32)(a) | 1)

typedef u32 (*hook_fn)(u32, u32, u32, u32);
typedef u32 (*pad_fn)(u32, u32, u32, u32);
typedef u8 *(*get_fn)(u32 store, u32 item);
typedef u32 (*item_fn)(u32 *item);
typedef u32 (*io_fn)(u32 *item, u32 off, u32 buf, u32 n, u32 cb, u32 ctx, u32 *done);
typedef u32 (*del_fn)(u32 *item, u32, u32);

#define PARAM_NEW ((get_fn)FN(0x0803FC6C))
#define WPTR ((get_fn)FN(0x0803FD26))
#define COMMIT ((u32 (*)(u32, u32))FN(0x0803FBEC))
#define EXISTS ((item_fn)FN(0x08045FB4))
#define SIZE ((item_fn)FN(0x08045FCE))
#define READ ((io_fn)FN(0x08046054))
#define WRITE ((io_fn)FN(0x0804607A))
#define DELETE ((del_fn)FN(0x08046098))
#define BUF_LOCK ((void (*)(u32))FN(0x0802EF6A))
#define BUF_UNLOCK ((void (*)(void))FN(0x0802EF98))
#define DSP_READ ((u32 (*)(u32, u32))FN(0x080314D6))
#define SM_REFRESH ((void (*)(u32, u32))FN(0x08039FB4))
#define SM_RELOAD ((void (*)(u32, u32))FN(0x0803A0D8))
#define FEED ((void (*)(void))FN(0x08026DD6))          /* the watchdog, as the stock's own long loops feed it */
#define RST ((u32 (*)(void))FN(C_RST))
#define PX ((u8 *(*)(u8 *, u32, u32))FN(C_PX))

#define CTRL 0x200487C8u
#define CTRL_VT 0x080672E4u
#define O_VIEW 0x7C
#define O_HELD 0xA0
#define O_SHIFT 0x0C
#define BIT_CLEAR 23
#define BIT_DUP 24
#define TRANSPORT 0x200122B0u
#define HAL_TICK 0x20006F3Cu
#define COLOURS 0x20003974u
#define FRAME_PULSE 0x0A
#define CLR_CUE 0x54                                   /* the stock's dim red */
#define CLR_RED 0x55
#define CLR_GREEN 0x1E
#define CLR_WHITE 0x01
#ifndef HOLD_SOURCE
#define HOLD_SOURCE 0
#endif
#ifndef BUTTONS
#define BUTTONS 0
#endif
#if HOLD_SOURCE                                        /* the source pulses green while Duplicate is held; one copy, then it is forgotten */
#define SOURCE(c) scl(rgb(CLR_GREEN), pulse())
#else
#define SOURCE(c) scl(rgb(CLR_WHITE), pulse())
#endif

#define PROJ_VT 0x080679CCu
#define P_PAGE 0x36
#define P_STORE 0x20
#define P_LOADED 11
#define P_USED 12
#define P_COL 16
#define SR_VIEW 0x2004DC90u
#define SR_VT 0x08067A08u
#define S_PAGE 0x0C
#define SM 0x20043DC0u
#define SM_STATE 0x20
#define DSP_FREE 0x371D2u
#define DSP_LIMIT 0xE00000u
#define DSP_MARGIN 0x400u
#define PACKS_VIEW 0x2004D7FCu
#define PACKS_VT 0x08067954u
#define K_CARD 0x0C
#define K_LOADED 0x10
#define K_LIST 0x14
#define CUR_PACK_PTR 0x20006E24u

#define KIND_PACK 1
#define KIND_SESS 2
#define KIND_PCM 4
#define SESS_SIZE 0x29484u
#define BUF 0x20003F94u
#define CHUNK 4096u
#define LOCK_OWNER 5

#define PULSES_MS 900u                                 /* three pulses of 300 ms */
#define FAIL_MS 1500u
#define TAG 0xF7

enum { W_NONE, W_PROJ, W_SMP, W_PACK };
enum { R_OK = 1, R_BAD = 2 };

struct st {
    u8 tag, src_ok, src_pack, src_slot;                /* the project source */
    u8 src_col, smp_ok, smp_pack, smp_slot;           /* its colour; the sample source */
    u8 arm, arm_pack, arm_slot, res;                  /* the pad asked about (W_*); the last result (R_*) */
    u8 res_kind, res_pack, res_slot, pad0;
    u32 res_t;
    u8 req[32];                                        /* a Plus command: request, then reply */
};

static struct st *state(void)
{
    if (!RST())
        return 0;
    struct st *s = (struct st *)SLOT;
    if (s->tag != TAG) {
        u8 *p = (u8 *)s;
        for (u32 i = 0; i < sizeof *s; i++)
            p[i] = 0;
        s->tag = TAG;
    }
    return s;
}
static int ctrl_ok(void) { return R32(CTRL) == CTRL_VT; }
static u32 held(void) { return R32(CTRL + O_HELD); }
static u32 now(void) { return R32(HAL_TICK); }
static u32 newest(u32 store, u32 p) { return *(volatile u32 *)PARAM_NEW(store, p); }
static int playing(void) { return (newest(TRANSPORT, 0) & 0xFF) != 0; }
static u32 view(void) { return R32(CTRL + O_VIEW); }
static int on(u32 v, u32 vt) { return v && R32(v) == vt; }

/* The loaded pack: the packs view's, or the storage task's current pack. */
static u32 loaded_pack(void)
{
    if (R32(PACKS_VIEW) == PACKS_VT)
        return newest(R32(PACKS_VIEW + K_LOADED), 0) & 0xFF;
    return R8(R32(CUR_PACK_PTR));
}
static void item(u32 *it, u32 kind, u32 slot, u32 pack) { it[0] = kind; it[1] = slot; it[2] = pack; }
static u32 size_of(u32 kind, u32 slot, u32 pack) { u32 it[3]; item(it, kind, slot, pack); return SIZE(it); }
/* The storage task back on the loaded pack: any operation on it, by its own number. */
static void reselect(void) { u32 it[3]; item(it, KIND_SESS, 0, loaded_pack()); EXISTS(it); }

/* A's file to B in 4 KB pieces through the stock's shared buffer. 0 = copied. */
static u32 copy_file(u32 kind, u32 sa, u32 pa, u32 sb, u32 pb, u32 size)
{
    u32 a[3], b[3], r = 0, done;
    item(a, kind, sa, pa);
    item(b, kind, sb, pb);
    BUF_LOCK(LOCK_OWNER);
    for (u32 off = 0; !r && off < size; off += CHUNK) {
        u32 n = size - off < CHUNK ? size - off : CHUNK;
        done = 0;
        r = READ(a, off, BUF, n, 0, 0, &done);
        if (!r && done != n)
            r = 8;
        if (!r)
            r = WRITE(b, off, BUF, n, 0, 0, &done);
        FEED();
    }
    BUF_UNLOCK();
    return r;
}

/* A Plus command through the storage shadow's handler (it runs in the storage task). 0 = done. */
static u32 plus(struct st *s, u32 cmd, u32 dir, u32 f0, u32 f1, u32 f2, u32 f3, u32 *value)
{
    u8 *q = s->req;
    for (u32 i = 0; i < sizeof s->req; i++)
        q[i] = 0;
    q[4] = (u8)(cmd | 0x40);
    q[6] = (u8)dir;
    q[8] = (u8)f0; q[9] = (u8)f1; q[10] = (u8)f2; q[11] = (u8)f3;
    PX(q, sizeof s->req, 0);
    u32 st = 0, v = 0;
    for (u32 i = 0; i < 8; i++) {
        st = st << 4 | (q[6 + i] & 15);
        v = v << 4 | (q[14 + i] & 15);
    }
    if (value)
        *value = v;
    return st;
}

static void result(struct st *s, u32 kind, u32 pack, u32 slot, u32 ok)
{
    s->res_kind = (u8)kind; s->res_pack = (u8)pack; s->res_slot = (u8)slot;
    s->res = ok ? R_OK : R_BAD;
    s->res_t = now();
}

/* ---- Projects view */
static u32 proj_copy(struct st *s, u32 store, u32 sb, u32 pb)
{
    u32 sa = s->src_slot, pa = s->src_pack, copied;
    if (size_of(KIND_SESS, sa, pa) != SESS_SIZE)
        return 1;
    if (plus(s, 0x29, pa, sa, pb, sb, 0, &copied))
        return 1;
    u32 r = copy_file(KIND_SESS, sa, pa, sb, pb, SESS_SIZE);
    reselect();
    if (r)
        return r;
    plus(s, 0x29, pa, sa, pb, sb, 1, 0);
    reselect();
    u32 *used = (u32 *)WPTR(store, P_USED + (sb >> 5));
    *used |= 1u << (sb & 31);
    u8 *col = (u8 *)WPTR(store, P_COL + (sb >> 2));
    col[sb & 3] = s->src_col;
    COMMIT(store, 0);
    return 0;
}

u32 c_ft_projpad(u32 v, u32 pad, u32 vel, u32 a3)
{
    struct st *s;
    if (pad >= 32 || !ctrl_ok() || !(held() >> BIT_DUP & 1) || !(s = state()))
        return ((pad_fn)FN(PREV_PROJ))(v, pad, vel, a3);
    if (playing())
        return 0;
    u32 slot = pad + 32u * R8(v + P_PAGE), pack = loaded_pack(), store = R32(v + P_STORE);
    if (slot >= 64)
        return 0;
    if (!s->src_ok) {
        if (size_of(KIND_SESS, slot, pack)) {
            s->src_ok = 1; s->src_pack = (u8)pack; s->src_slot = (u8)slot;
            s->src_col = ((const u8 *)PARAM_NEW(store, P_COL + (slot >> 2)))[slot & 3];
            s->arm = W_NONE;
        }
        return 0;
    }
    if (s->src_pack == pack && s->src_slot == slot) {
        s->src_ok = 0; s->arm = W_NONE;
        return 0;
    }
    if (!pack || slot == (newest(store, P_LOADED) & 0xFF)) {
        result(s, W_PROJ, pack, slot, 0);
        return 0;
    }
    if (size_of(KIND_SESS, slot, pack) && !(s->arm == W_PROJ && s->arm_pack == pack && s->arm_slot == slot)) {
        s->arm = W_PROJ; s->arm_pack = (u8)pack; s->arm_slot = (u8)slot;
        return 0;
    }
    s->arm = W_NONE;
    result(s, W_PROJ, pack, slot, proj_copy(s, store, slot, pack) == 0);
#if HOLD_SOURCE
    s->src_ok = 0;
#endif
    return 0;
}

/* ---- Sample Rec view */
static u32 smp_copy(struct st *s, u32 sb, u32 pb)
{
    u32 sa = s->smp_slot, pa = s->smp_pack, size = size_of(KIND_PCM, sa, pa), r = 0, b[3];
    if (!size) { reselect(); return 1; }
    if ((DSP_READ(0, DSP_FREE) >> 8) + (size >> 1) + DSP_MARGIN >= DSP_LIMIT) { reselect(); return 1; }
    item(b, KIND_PCM, sb, pb);
    if (SIZE(b))
        r = DELETE(b, 0, 0);
    if (!r) {
        r = copy_file(KIND_PCM, sa, pa, sb, pb, size);
        if (r)
            DELETE(b, 0, 0);
    }
    reselect();
    SM_REFRESH(SM, sb);
    SM_RELOAD(SM, sb);
    return r;
}

u32 c_ft_smppad(u32 v, u32 pad, u32 vel, u32 a3)
{
    struct st *s;
    if (pad >= 16 || !ctrl_ok() || !(held() >> BIT_DUP & 1) || !(s = state()))
        return ((pad_fn)FN(PREV_SMP))(v, pad, vel, a3);
    if (playing())
        return 0;
    u32 slot = pad + 16u * R8(v + S_PAGE), pack = loaded_pack();
    if (slot >= 128)
        return 0;
    if (!s->smp_ok) {
        if (size_of(KIND_PCM, slot, pack)) {
            s->smp_ok = 1; s->smp_pack = (u8)pack; s->smp_slot = (u8)slot;
            s->arm = W_NONE;
        }
        return 0;
    }
    if (s->smp_pack == pack && s->smp_slot == slot) {
        s->smp_ok = 0; s->arm = W_NONE;
        return 0;
    }
    if (!pack || (newest(R32(SM + SM_STATE), 1) & 0xFF)) {
        result(s, W_SMP, pack, slot, 0);
        return 0;
    }
    if (size_of(KIND_PCM, slot, pack) && !(s->arm == W_SMP && s->arm_pack == pack && s->arm_slot == slot)) {
        s->arm = W_SMP; s->arm_pack = (u8)pack; s->arm_slot = (u8)slot;
        return 0;
    }
    s->arm = W_NONE;
    result(s, W_SMP, pack, slot, smp_copy(s, slot, pack) == 0);
#if HOLD_SOURCE
    s->smp_ok = 0;
#endif
    return 0;
}

/* ---- Packs view */
static int card(u32 v) { return newest(R32(v + K_CARD), 0) & 1; }
static int deletable(u32 v, u32 p)
{
    return p && p < 32 && p != (newest(R32(v + K_LOADED), 0) & 0xFF) &&
           ((const u8 *)PARAM_NEW(R32(v + K_LIST), p))[0] != 0xFF;
}
static int clear_mode(u32 v)
{
    return (held() >> BIT_CLEAR & 1) && !(newest(R32(CTRL + O_SHIFT), 0) & 1) && card(v) && !playing();
}

u32 c_ft_packpad(u32 v, u32 pad, u32 vel, u32 a3)
{
    struct st *s;
    if (pad >= 32 || !ctrl_ok() || !(held() >> BIT_CLEAR & 1) || (newest(R32(CTRL + O_SHIFT), 0) & 1) || !card(v) ||
        !(s = state()))
        return ((pad_fn)FN(PREV_PACK))(v, pad, vel, a3);
    if (playing() || !deletable(v, pad))
        return 0;
    if (!(s->arm == W_PACK && s->arm_slot == pad)) {
        s->arm = W_PACK; s->arm_slot = (u8)pad;
        return 0;
    }
    s->arm = W_NONE;
    u32 it[3];
    item(it, KIND_PACK, 0, pad);
    u32 r = DELETE(it, 0, 0);
    reselect();
    if (!r) {
        u32 list = R32(v + K_LIST);
        *WPTR(list, pad) = 0xFF;
        COMMIT(list, 0);
    }
    result(s, W_PACK, 0, pad, r == 0);
    return 0;
}

/* ---- the lights: the last RGB stage */
static u32 rgb(u32 code) { return R32(COLOURS + 4 * code); }
static u32 scl(u32 c, u32 lvl)
{
    u32 o = 0;
    for (u32 sh = 0; sh < 24; sh += 8)
        o |= (((c >> sh) & 0xFF) * (lvl + 1) >> 8) << sh;
    return o;
}
static u32 pulse(void) { return 64 + ((255 - (rgb(FRAME_PULSE) & 0xFF)) * 192 >> 8); }
/* the result on its pad: three pulses (green done, red delete done), or steady red for a refusal; 0 = over */
static int shown(struct st *s, u32 *c)
{
    u32 t = now() - s->res_t;
    if (s->res == R_BAD) {
        if (t >= FAIL_MS) return 0;
        *c = rgb(CLR_RED);
        return 1;
    }
    if (t >= PULSES_MS) return 0;
    u32 ph = t % 300, lvl = ph < 150 ? ph * 255 / 150 : (300 - ph) * 255 / 150;
    *c = scl(rgb(s->res_kind == W_PACK ? CLR_RED : CLR_GREEN), lvl);
    return 1;
}

#if BUTTONS
/* A view's slot 8: the buttons it uses, bit 0 Clear, bit 1 Duplicate. The stock lights them dim, and bright while held. */
#define USES_CLEAR 1u
#define USES_DUP 2u
typedef u32 (*uses_fn)(u32);
u32 c_ft_projuse(u32 v) { return (((uses_fn)FN(USE_PROJ))(v) & 0xFF) | USES_DUP; }
u32 c_ft_smpuse(u32 v) { return (((uses_fn)FN(USE_SMP))(v) & 0xFF) | USES_DUP; }
u32 c_ft_packuse(u32 v) { return (((uses_fn)FN(USE_PACK))(v) & 0xFF) | USES_CLEAR; }
#endif

u32 c_ft_out(u32 c, u32 out, u32 frame, u32 a3)
{
    u32 ret = ((hook_fn)FN(PREV_OUT))(c, out, frame, a3);
    struct st *s;
    if (!ctrl_ok() || !(s = state()))
        return ret;
    volatile u32 *o = (volatile u32 *)out;
    u32 v = view(), h = held(), col;
    if (s->res && !shown(s, &col))
        s->res = 0;
#if HOLD_SOURCE
    if (!(h >> BIT_DUP & 1)) {
        if (s->arm == W_PROJ || s->arm == W_SMP)
            s->arm = W_NONE;
        s->src_ok = s->smp_ok = 0;
    }
#else
    if ((s->arm == W_PROJ || s->arm == W_SMP) && !(h >> BIT_DUP & 1))
        s->arm = W_NONE;
#endif
    if (on(v, PROJ_VT)) {
        u32 page = R8(v + P_PAGE), pack = loaded_pack();
        if (s->src_ok && s->src_pack == pack && s->src_slot >> 5 == page)
            o[s->src_slot & 31] = SOURCE(0);
        if (s->arm == W_PROJ && s->arm_pack == pack && s->arm_slot >> 5 == page)
            o[s->arm_slot & 31] = scl(rgb(CLR_RED), pulse());
        if (s->res && s->res_kind == W_PROJ && s->res_pack == pack && s->res_slot >> 5 == page)
            o[s->res_slot & 31] = col;
    } else if (v == SR_VIEW && on(v, SR_VT)) {
        u32 page = R8(v + S_PAGE), pack = loaded_pack();
        if (s->smp_ok && s->smp_pack == pack && s->smp_slot >> 4 == page)
            o[s->smp_slot & 15] = SOURCE(0);
        if (s->arm == W_SMP && s->arm_pack == pack && s->arm_slot >> 4 == page)
            o[s->arm_slot & 15] = scl(rgb(CLR_RED), pulse());
        if (s->res && s->res_kind == W_SMP && s->res_pack == pack && s->res_slot >> 4 == page)
            o[s->res_slot & 15] = col;
    } else if (v == PACKS_VIEW && on(v, PACKS_VT)) {
        if (!clear_mode(v)) {
            if (s->arm == W_PACK)
                s->arm = W_NONE;
        } else {
            u32 loaded = newest(R32(v + K_LOADED), 0) & 0xFF;
            for (u32 p = 0; p < 32; p++) {
                if (p == loaded)
                    continue;
                if (!deletable(v, p))
                    o[p] = 0;
                else if (s->arm == W_PACK && s->arm_slot == p)
                    o[p] = scl(rgb(CLR_RED), pulse());
                else
                    o[p] = rgb(CLR_CUE);
            }
        }
        if (s->res && s->res_kind == W_PACK)
            o[s->res_slot & 31] = col;
    }
    return ret;
}
