/* Sends a packed DSP program as the stock sender sends a block. */
#include <stdint.h>
typedef uint32_t u32; typedef uint16_t u16; typedef uint8_t u8;

struct dir { u32 magic, tab, doff, bits0, size0, bits1, size1; };
#define D ((const struct dir *)DIR)
#define WIN 240u
#define MINL 3u

static void wait_(void) { ((void (*)(void))(WAIT | 1))(); }

#ifndef RC
#define RC 0
#endif
#if !RC
typedef struct { const u8 *p; u32 pos; } bits_t;

/* canonical Huffman: count[1..15] codes of each length; -> the index into the sorted symbols */
static u32 decode(bits_t *b, const u16 *count) {
    u32 code = 0, first = 0, index = 0;
    for (u32 len = 1; len < 16; len++) {
        code |= (b->p[b->pos >> 3] >> (b->pos & 7)) & 1;
        b->pos++;
        u32 c = count[len];
        if (code - first < c) return index + code - first;
        index += c; first = (first + c) << 1; code <<= 1;
    }
    for (;;) {}                                    /* a broken stream: never send it as program words */
}

static void send(u32 bits, u32 size, u32 core) {
    const u8 *tab = (const u8 *)D->tab;
    const u16 *llcount = (const u16 *)tab, *llsym = llcount + 16;
    const u16 *dcount = (const u16 *)(tab + D->doff);
    const u8 *dsym = (const u8 *)(dcount + 16);
    u8 *ring = (u8 *)RING;
    bits_t b = { (const u8 *)bits, 0 };
    u32 sent = 0, wi = 0, left = 0, mi = 0;
    wait_();
    ((void (*)(u32))(SELECT | 1))(core);
    while (sent < size) {
        u32 n = size - sent;
        if (n > WIN) n = WIN;                      /* every chunk but the last fills the ring from 0 */
        for (u32 k = 0; k < n; k++) {
            if (!left) {
                u32 s = llsym[decode(&b, llcount)];
                if (s < 256) {
                    ring[wi] = (u8)s;
                    if (++wi == WIN) wi = 0;
                    continue;
                }
                left = s - 256 + MINL;
                u32 off = dsym[decode(&b, dcount)] + 1u;
                mi = wi >= off ? wi - off : wi + WIN - off;
            }
            ring[wi] = ring[mi];
            if (++mi == WIN) mi = 0;
            if (++wi == WIN) wi = 0;
            left--;
        }
        ((void (*)(u32, u32))(SPI | 1))((u32)ring, n);
        wait_();
        sent += n;
    }
    wait_();
    ((void (*)(u32))(END | 1))(core);
}

#else
/* LZ + adaptive binary range coding (dsprc.py's model): probabilities and the last 4 KB sent in the ITCM, only while a block is sent */
#define PBITS 11u
#define PMOVE 5u
#define PONE (1u << PBITS)
#define PTOP (1u << 24)
#define LIT 0u
#define ISM 0x300u
#define ISR 0x30Cu
#define ISR0L 0x318u
#define MLEN 0x324u
#define RLEN (MLEN + 274u)
#define SLOT (RLEN + 274u)
#define SPEC (SLOT + 256u)
#define ALIGN (SPEC + 114u)
#define NPROB (ALIGN + 16u)
#define WMASK 0xFFFu
#define P ((u16 *)PROBS)
#define W ((u8 *)WINDOW)

typedef struct { const u8 *p; u32 code, rng; } rc_t;
static const u8 NEXT_LIT[12] = { 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 4, 5 };

#define HOT static inline __attribute__((always_inline))   /* the per-bit path: -Oz would make each a call */

HOT void norm(rc_t *r) { if (r->rng < PTOP) { r->rng <<= 8; r->code = r->code << 8 | *r->p++; } }

HOT u32 bit(rc_t *r, u32 i) {
    u32 p = P[i], bound = (r->rng >> PBITS) * p, b;
    if (r->code < bound) { r->rng = bound; P[i] = (u16)(p + ((PONE - p) >> PMOVE)); b = 0; }
    else { r->code -= bound; r->rng -= bound; P[i] = (u16)(p - (p >> PMOVE)); b = 1; }
    norm(r);
    return b;
}

static u32 direct(rc_t *r, u32 n) {
    u32 v = 0;
    while (n--) {
        r->rng >>= 1; v <<= 1;
        if (r->code >= r->rng) { r->code -= r->rng; v |= 1; }
        norm(r);
    }
    return v;
}

/* n bits through the tree at base: -> highest bit first; *low = the same bits lowest first */
static u32 tree(rc_t *r, u32 base, u32 n, u32 *low) {
    u32 m = 1, v = 0;
    for (u32 j = 0; j < n; j++) { u32 b = bit(r, base + m); m = m << 1 | b; v |= b << j; }
    if (low) *low = v;
    return m - (1u << n);
}

static u32 dlen(rc_t *r, u32 o) {
    if (!bit(r, o)) return 2 + tree(r, o + 2, 3, 0);
    if (!bit(r, o + 1)) return 10 + tree(r, o + 10, 3, 0);
    return 18 + tree(r, o + 18, 8, 0);
}

static void send(u32 stream, u32 size, u32 core) {
    const u8 *s = (const u8 *)stream;
    rc_t r = { s + 4, (u32)s[0] << 24 | (u32)s[1] << 16 | (u32)s[2] << 8 | s[3], 0xFFFFFFFFu };
    u8 *ring = (u8 *)RING;
    u32 sent = 0, w = 0, left = 0, st = 0, r0 = 0;
    for (u32 i = 0; i < NPROB; i++) P[i] = PONE / 2;
    wait_();
    ((void (*)(u32))(SELECT | 1))(core);
    while (sent < size) {
        u32 n = size - sent;
        if (n > WIN) n = WIN;
        for (u32 k = 0; k < n; k++) {
            u32 byte;
            if (left) {
                byte = W[(w - r0 - 1) & WMASK];
                left--;
            } else if (!bit(&r, ISM + st)) {
                u32 offs = 0, m = 0, sym = 1;
                if (st >= 7) { offs = 0x100; m = W[(w - r0 - 1) & WMASK]; }
                while (sym < 0x100) {
                    m <<= 1;
                    u32 b0 = m & offs, b = bit(&r, LIT + offs + b0 + sym);
                    sym = sym << 1 | b;
                    offs = b ? offs & b0 : offs & ~b0;
                }
                byte = sym & 0xFF;
                st = NEXT_LIT[st];
            } else {
                u32 l;
                if (bit(&r, ISR + st)) {
                    if (!bit(&r, ISR0L + st)) { l = 1; st = st < 7 ? 9 : 11; }
                    else { l = dlen(&r, RLEN); st = st < 7 ? 8 : 11; }
                } else {
                    l = dlen(&r, MLEN); st = st < 7 ? 7 : 10;
                    u32 sl = tree(&r, SLOT + 64 * (l - 2 < 3 ? l - 2 : 3), 6, 0);
                    if (sl < 4) r0 = sl;
                    else {
                        u32 nd = (sl >> 1) - 1, d = (2 | (sl & 1)) << nd, v;
                        if (sl < 14) { tree(&r, SPEC + d - sl - 1, nd, &v); d += v; }
                        else { d += direct(&r, nd - 4) << 4; tree(&r, ALIGN, 4, &v); d += v; }
                        r0 = d;
                    }
                }
                byte = W[(w - r0 - 1) & WMASK];
                left = l - 1;
            }
            W[w] = (u8)byte;
            w = (w + 1) & WMASK;
            ring[k] = (u8)byte;
        }
        ((void (*)(u32, u32))(SPI | 1))((u32)ring, n);
        wait_();
        sent += n;
    }
    wait_();
    ((void (*)(u32))(END | 1))(core);
}
#endif

/* core 0, mode 0: dspzip's stream (after its loader block) */
void c_hz_core0(u32 block, u32 core) { (void)block; send(D->bits0, D->size0, core); }

/* core 1: its mode 0 block packed, any other block the stock's */
void c_hz_core1(u32 block, u32 core) {
    if (block != BLK1) { ((void (*)(u32, u32))(SEND | 1))(block, core); return; }
    if (!((u32 (*)(void))(C_RST | 1))()) for (;;) {}   /* no ring: never send packed bytes */
    send(D->bits1, D->size1, core);
}
