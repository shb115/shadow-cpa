/*
    This file is part of the ChipWhisperer Example Targets
    Copyright (C) 2012-2017 NewAE Technology Inc.

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#include "aes-independant.h"
#include "hal.h"
#include "simpleserial.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

// ---------------------------------------------------------------------------
// Shadow-32 with two-share masking by table recomputation (v3, the table-recomputation
// implementation of Section 4.7 of the paper).
// (The source file is revision v3; the build target and the trace files keep the name
// masking_ISWLUT_v2.)
//
// [Principle]  When the two shares (s0, s1) of one value pass through the same register or
//   the same bus transfer in succession, the Hamming distance of that transition is
//   HW(s0 ^ s1) = HW(value), a first-order leak. Therefore every operation that touches a
//   share is written in inline assembly: between the access to share 0 and the access to
//   share 1 the working registers (r2, r3) are overwritten with the overwriting value w, and
//   before share 1 is stored, w is first stored to the same location, so that the store bus
//   is overwritten as well. The compiled C code never handles both shares together: the round
//   function and masked_F pass pointers only, and the table-build loop of tableG handles only
//   share 0 (t0) of the refreshed input. The two shares live in different 32-bit words (the
//   padding of MaskedByte), so that no single byte access puts both on the bus, and no
//   structure is copied by value. The key is also passed as the two shares (RK ^ q, q).
//   (In v1/v2 the XOR and the rotation were plain C, and the compiled code moved the two
//    shares through the same register in succession. v3 removes that.)
//
// [Operations]  masked_xor_w(out, a, b, w)      out = a ^ b
//               masked_rol2_w(out, a, w)        out = ROL(a, 2)
//               masked_copy_w(out, a, w)        out = a
//               mask_refreshing(out, a, r, w)   out = a ^ (r, r)
//               masked_xor_key(a, kq, w)        a ^= kq, kq = (RK ^ q, q): the key is added masked
//               tableG(out, in, y0, w)          table recomputation of the AND part g(x) = ROL(x,1) & ROL(x,7):
//                                               rebuilds the table under the input share and the output mask, then looks it up
//   In every operation out must be an object other than the inputs (the overwriting store
//   would overwrite share 1 of the input).
//
// [Randomness]  pt[0..3] = plaintext, pt[4..7] = m (y0, the output masks), pt[8..11] = r_in,
//   pt[12..15] = r_key, pt[16..19] = f (refresh bytes, also the overwriting values).
// Built at -O0. The operand constraint of the assembly is "l" (r0-r7); r2 and r3 are the
// working registers.
// ---------------------------------------------------------------------------

static inline uint8_t ROL8(uint8_t val, int rot) {
    return ((val << rot) | (val >> (8 - rot))) & 0xFF;
}

// A masked byte: the two shares in different words (offsets 0 and 4).
typedef struct {
    uint8_t s0;
    uint8_t pad0[3];
    uint8_t s1;
    uint8_t pad1[3];
} MaskedByte;

static inline void mask_byte(uint8_t v, MaskedByte *m, uint8_t r) {
    m->s0 = r;
    m->s1 = v ^ r;
}

static inline uint8_t unmask_byte(const MaskedByte *m) {
    return m->s0 ^ m->s1;
}

// out = a ^ b, share by share. r3: the share of a, r2: the share of b.
static void masked_xor_w(MaskedByte *out, const MaskedByte *a, const MaskedByte *b, uint8_t w) {
    __asm__ __volatile__(
        ".syntax unified\n\t"
        "movs r3,%[w]\n\t"
        "movs r2,%[w]\n\t"
        "ldrb r3,[%[a],#0]\n\t"
        "ldrb r2,[%[b],#0]\n\t"
        "eors r3,r3,r2\n\t"
        "strb r3,[%[o],#0]\n\t"
        "movs r3,%[w]\n\t"
        "movs r2,%[w]\n\t"
        "strb r3,[%[o],#4]\n\t"      // overwrite the store bus
        "ldrb r3,[%[a],#4]\n\t"
        "ldrb r2,[%[b],#4]\n\t"
        "eors r3,r3,r2\n\t"
        "strb r3,[%[o],#4]\n\t"
        "movs r3,%[w]\n\t"
        "movs r2,%[w]\n\t"
        ".syntax divided\n\t"
        : : [o]"l"(out), [a]"l"(a), [b]"l"(b), [w]"l"(w) : "r2", "r3", "cc", "memory");
}

// out = ROL8(a, 2), share by share. r3: the share, r2: the shift temporary.
static void masked_rol2_w(MaskedByte *out, const MaskedByte *a, uint8_t w) {
    __asm__ __volatile__(
        ".syntax unified\n\t"
        "movs r3,%[w]\n\t"
        "movs r2,%[w]\n\t"
        "ldrb r3,[%[a],#0]\n\t"
        "lsls r2,r3,#2\n\t"
        "lsrs r3,r3,#6\n\t"
        "orrs r3,r3,r2\n\t"
        "uxtb r3,r3\n\t"
        "strb r3,[%[o],#0]\n\t"
        "movs r3,%[w]\n\t"
        "movs r2,%[w]\n\t"
        "strb r3,[%[o],#4]\n\t"      // overwrite the store bus
        "ldrb r3,[%[a],#4]\n\t"
        "lsls r2,r3,#2\n\t"
        "lsrs r3,r3,#6\n\t"
        "orrs r3,r3,r2\n\t"
        "uxtb r3,r3\n\t"
        "strb r3,[%[o],#4]\n\t"
        "movs r3,%[w]\n\t"
        "movs r2,%[w]\n\t"
        ".syntax divided\n\t"
        : : [o]"l"(out), [a]"l"(a), [w]"l"(w) : "r2", "r3", "cc", "memory");
}

// out = a, copied byte by byte (instead of a structure copy).
static void masked_copy_w(MaskedByte *out, const MaskedByte *a, uint8_t w) {
    __asm__ __volatile__(
        ".syntax unified\n\t"
        "movs r3,%[w]\n\t"
        "ldrb r3,[%[a],#0]\n\t"
        "strb r3,[%[o],#0]\n\t"
        "movs r3,%[w]\n\t"
        "strb r3,[%[o],#4]\n\t"      // overwrite the store bus
        "ldrb r3,[%[a],#4]\n\t"
        "strb r3,[%[o],#4]\n\t"
        "movs r3,%[w]\n\t"
        ".syntax divided\n\t"
        : : [o]"l"(out), [a]"l"(a), [w]"l"(w) : "r3", "cc", "memory");
}

// Key addition (in place): a.s0 ^= kq.s0 (= RK ^ q), a.s1 ^= kq.s1 (= q). The key byte is handled masked only.
// r3: a.s0 -> w -> q,  r2: kq.s0 -> w -> a.s1 ;  store bus: a.s0^k, w, a.s1^q.
static void masked_xor_key(MaskedByte *a, const MaskedByte *kq, uint8_t w) {
    __asm__ __volatile__(
        ".syntax unified\n\t"
        "movs r3,%[w]\n\t"
        "movs r2,%[w]\n\t"
        "ldrb r3,[%[a],#0]\n\t"
        "ldrb r2,[%[k],#0]\n\t"
        "eors r3,r3,r2\n\t"
        "strb r3,[%[a],#0]\n\t"
        "movs r3,%[w]\n\t"
        "movs r2,%[w]\n\t"
        "ldrb r2,[%[a],#4]\n\t"      // r2 = a.s1 (read before the overwriting store)
        "strb r3,[%[a],#4]\n\t"      // overwrite the store bus
        "ldrb r3,[%[k],#4]\n\t"      // r3 = q
        "eors r2,r2,r3\n\t"
        "strb r2,[%[a],#4]\n\t"
        "movs r3,%[w]\n\t"
        "movs r2,%[w]\n\t"
        ".syntax divided\n\t"
        : : [a]"l"(a), [k]"l"(kq), [w]"l"(w) : "r2", "r3", "cc", "memory");
}

// mask_refreshing with overwriting: out.s0 = a.s0 ^ r, out.s1 = a.s1 ^ r.
static void mask_refreshing(MaskedByte *out, const MaskedByte *a, uint8_t r, uint8_t w) {
    __asm__ __volatile__(
        ".syntax unified\n\t"
        "movs r3,%[w]\n\t"
        "ldrb r3,[%[a],#0]\n\t"     // r3 = a.s0
        "eors r3,r3,%[r]\n\t"       // r3 = a.s0 ^ r
        "strb r3,[%[o],#0]\n\t"     // out.s0 = r3
        "movs r3,%[w]\n\t"          // overwrite r3
        "strb r3,[%[o],#4]\n\t"     // out.s1 = w (overwrite the store bus)
        "ldrb r3,[%[a],#4]\n\t"     // r3 = a.s1
        "eors r3,r3,%[r]\n\t"       // r3 = a.s1 ^ r
        "strb r3,[%[o],#4]\n\t"     // out.s1 = r3
        "movs r3,%[w]\n\t"          // overwrite r3
        ".syntax divided\n\t"
        : : [o]"l"(out), [a]"l"(a), [r]"l"(r), [w]"l"(w) : "r3", "cc", "memory");
}

// The table of the AND part g(x) = ROL(x,1) & ROL(x,7).
static uint8_t g_plain[256];
static uint8_t g_tab[256];

static void g_plain_init(void) {
    int v;
    for (v = 0; v < 256; v++)
        g_plain[v] = (uint8_t)(ROL8((uint8_t)v, 1) & ROL8((uint8_t)v, 7));
}

// Masked AND by table recomputation, with overwriting. in = (x0, x1), y0 = the output mask,
// w = the overwriting value. T[a] = g(a ^ x0) ^ y0 (only x0 enters the build), out = (y0, T[x1]).
static void tableG(MaskedByte *out, const MaskedByte *in, uint8_t y0, uint8_t w) {
    int a;
    uint8_t x0 = in->s0;                     // reads share 0 only
    for (a = 0; a < 256; a++)
        g_tab[a] = (uint8_t)(g_plain[(uint8_t)(a ^ x0)] ^ y0);
    x0 = w;                                  // overwrite the variable that held share 0

    // out.s0 = y0; overwrite the registers; out.s1 = T[x1] (reads share 1 only)
    __asm__ __volatile__(
        ".syntax unified\n\t"
        "strb %[y],[%[o],#0]\n\t"
        "movs r2,%[w]\n\t"
        "movs r3,%[w]\n\t"
        "strb r3,[%[o],#4]\n\t"      // overwrite the store bus
        "ldrb r3,[%[i],#4]\n\t"      // r3 = x1
        "ldrb r3,[%[gt],r3]\n\t"     // r3 = T[x1]
        "strb r3,[%[o],#4]\n\t"
        "movs r3,%[w]\n\t"
        "movs r2,%[w]\n\t"
        ".syntax divided\n\t"
        : : [o]"l"(out), [i]"l"(in), [y]"l"(y0), [w]"l"(w), [gt]"l"(g_tab) : "r2", "r3", "cc", "memory");
}

// Masked F:  out = g(x) ^ ROL(x,2)  (the masked evaluation of F(x)): refresh, then the table lookup.
static void masked_F(MaskedByte *out, const MaskedByte *x, uint8_t y0, uint8_t f) {
    MaskedByte t, gv, rl2;
    mask_refreshing(&t, x, f, f);
    tableG(&gv, &t, y0, f);
    masked_rol2_w(&rl2, x, f);
    masked_xor_w(out, &gv, &rl2, f);
}

// The round:  s0 = F(l0) ^ l1 ^ RK0,  s1 = F(r0) ^ r1 ^ RK1,
//             lo1 = F(s0) ^ l0 ^ RK2, ro1 = F(s1) ^ r0 ^ RK3,
//             then the swap: l0 = s1, l1 = lo1, r0 = s0, r1 = ro1.
//   kq[j] = (RK_j ^ q_j, q_j) the masked key, m_j = the output masks, f_j = the refresh bytes,
//   which also serve as the overwriting values.
void shadow32_round_masked(MaskedByte* l0, MaskedByte* l1,
                           MaskedByte* r0, MaskedByte* r1,
                           uint8_t m0, uint8_t m1, uint8_t m2, uint8_t m3,
                           const MaskedByte *kq,
                           uint8_t f0, uint8_t f1, uint8_t f2, uint8_t f3)
{
    MaskedByte fv, s0, s1, lo1, ro1;

    masked_F(&fv, l0, m0, f0);
    masked_xor_w(&s0, &fv, l1, f0);
    masked_xor_key(&s0, &kq[0], f0);

    masked_F(&fv, r0, m1, f1);
    masked_xor_w(&s1, &fv, r1, f1);
    masked_xor_key(&s1, &kq[1], f1);

    masked_F(&fv, &s0, m2, f2);
    masked_xor_w(&lo1, &fv, l0, f2);
    masked_xor_key(&lo1, &kq[2], f2);

    masked_F(&fv, &s1, m3, f3);
    masked_xor_w(&ro1, &fv, r0, f3);
    masked_xor_key(&ro1, &kq[3], f3);

    masked_copy_w(l0, &s1, f0);
    masked_copy_w(l1, &lo1, f1);
    masked_copy_w(r0, &s0, f2);
    masked_copy_w(r1, &ro1, f3);
}

static const uint8_t RK_TABLE[64] = {
    0x0D, 0x3B, 0x60, 0x33, 0x43, 0x60, 0x25, 0x3C,
    0x13, 0x25, 0x89, 0xC5, 0x3C, 0x89, 0x0D, 0x5D,
    0x25, 0x0D, 0x40, 0xD1, 0x8D, 0x40, 0x14, 0x15,
    0x11, 0x14, 0x91, 0x56, 0xC5, 0x91, 0x03, 0x6D,
    0x16, 0x03, 0x02, 0xD6, 0x1D, 0x02, 0x08, 0x63,
    0x06, 0x08, 0x31, 0x39, 0x43, 0x31, 0x2C, 0x90,
    0x69, 0x2C, 0x01, 0x0A, 0x20, 0x01, 0x11, 0xAB,
    0x9A, 0x11, 0x00, 0xBC, 0x0B, 0x00, 0x04, 0xCE
};

#ifdef SHADOW32_FULL
// ---------------------------------------------------------------------------
// Full-encryption variant (make ... EXTRA_OPTS=SHADOW32_FULL): all 16 rounds run masked.
// Because of the 64-byte command limit of SimpleSerial v1 the random bytes are uploaded in
// pieces with the 'q' command:
//   'q' (49 bytes): [piece number c = 0..3][48 bytes]  -> rnd[48c .. 48c+47]
//   rnd[12i .. 12i+11] = m0..m3, f0..f3, q0..q3 of round i  (i = 0..15, 192 bytes in all)
//   'p' (8 bytes):  pt[0..3] = plaintext, pt[4..7] = r_in (input masks)  -> runs the encryption
// Response 'r', 16 bytes: the first 4 bytes are the ciphertext [r0, l1, l0, r1] (the order of
// capture_exp.enc32).
// ---------------------------------------------------------------------------
static uint8_t rnd[192];

uint8_t get_rnd(uint8_t* d, uint8_t len)
{
    (void)len;
    uint8_t c = d[0];
    if (c < 4)
        memcpy(rnd + 48 * c, d + 1, 48);
    return 0x00;
}

uint8_t get_pt(uint8_t* pt, uint8_t len)
{
    (void)len;
    aes_indep_enc_pretrigger(pt);

    volatile uint8_t l0 = pt[0];
    volatile uint8_t l1 = pt[1];
    volatile uint8_t r0 = pt[2];
    volatile uint8_t r1 = pt[3];

    MaskedByte kq[64];
    int i, j;

    g_plain_init();

    // Key masking (outside the trigger): kq = (RK ^ q, q)
    for (i = 0; i < 16; i++)
        for (j = 0; j < 4; j++) {
            uint8_t q = rnd[12*i + 8 + j];
            kq[4*i + j].s0 = RK_TABLE[4*i + j] ^ q;
            kq[4*i + j].s1 = q;
        }

    MaskedByte ml0, ml1, mr0, mr1;
    mask_byte(l0, &ml0, pt[4]);
    mask_byte(l1, &ml1, pt[5]);
    mask_byte(r0, &mr0, pt[6]);
    mask_byte(r1, &mr1, pt[7]);

    trigger_high();

    for (i = 0; i < 16; i++) {
        const uint8_t *rr = rnd + 12*i;
        shadow32_round_masked(&ml0, &ml1, &mr0, &mr1,
                              rr[0], rr[1], rr[2], rr[3],
                              &kq[4*i],
                              rr[4], rr[5], rr[6], rr[7]);
    }

    trigger_low();

    // Ciphertext (unmasked), in the output order of enc32 [r0, l1, l0, r1]
    pt[0] = unmask_byte(&mr0);
    pt[1] = unmask_byte(&ml1);
    pt[2] = unmask_byte(&ml0);
    pt[3] = unmask_byte(&mr1);

    aes_indep_enc_posttrigger(pt);

    simpleserial_put('r', 16, pt);
    return 0x00;
}

int main(void)
{
    uint8_t tmp[KEY_LENGTH] = {DEFAULT_KEY};
    (void)tmp;

    platform_init();
    init_uart();
    trigger_setup();

    simpleserial_init();
    simpleserial_addcmd('q', 49, get_rnd);  // random bytes in pieces (4 x 48 bytes)
    simpleserial_addcmd('p', 8, get_pt);    // plaintext 4 + input masks 4
    while(1)
        simpleserial_get();
}

#else  /* one round (the measurement firmware of Section 4.7 of the paper) */

uint8_t get_pt(uint8_t* pt, uint8_t len)
{
    (void)len;
    aes_indep_enc_pretrigger(pt);

    volatile uint8_t l0 = pt[0];
    volatile uint8_t l1 = pt[1];
    volatile uint8_t r0 = pt[2];
    volatile uint8_t r1 = pt[3];

    uint8_t m0 = pt[4];
    uint8_t m1 = pt[5];
    uint8_t m2 = pt[6];
    uint8_t m3 = pt[7];

    uint8_t r_in0 = pt[8];
    uint8_t r_in1 = pt[9];
    uint8_t r_in2 = pt[10];
    uint8_t r_in3 = pt[11];

    uint8_t f0 = pt[16];
    uint8_t f1 = pt[17];
    uint8_t f2 = pt[18];
    uint8_t f3 = pt[19];

    g_plain_init();

    // Key masking (outside the trigger): kq[j] = (RK_j ^ r_key_j, r_key_j), r_key = pt[12..15]
    MaskedByte kq[4];
    int j;
    for (j = 0; j < 4; j++) {
        kq[j].s0 = RK_TABLE[j] ^ pt[12 + j];
        kq[j].s1 = pt[12 + j];
    }

    MaskedByte ml0, ml1, mr0, mr1;
    mask_byte(l0, &ml0, r_in0);
    mask_byte(l1, &ml1, r_in1);
    mask_byte(r0, &mr0, r_in2);
    mask_byte(r1, &mr1, r_in3);

    trigger_high();

    shadow32_round_masked(&ml0, &ml1, &mr0, &mr1, m0, m1, m2, m3, kq, f0, f1, f2, f3);

    for (volatile uint32_t pad = 0; pad < 10000u; pad++) {
        asm("NOP");
    }

    trigger_low();

    // Known-answer test (KAT), enabled only by make ... EXTRA_OPTS=SHADOW32_KAT:
    // returns the state after the round [l0, l1, r0, r1] with the masking removed.
#ifdef SHADOW32_KAT
    pt[0] = unmask_byte(&ml0);
    pt[1] = unmask_byte(&ml1);
    pt[2] = unmask_byte(&mr0);
    pt[3] = unmask_byte(&mr1);
#endif

    aes_indep_enc_posttrigger(pt);

    simpleserial_put('r', 16, pt);
    return 0x00;
}

int main(void)
{
    uint8_t tmp[KEY_LENGTH] = {DEFAULT_KEY};
    (void)tmp;

    platform_init();
    init_uart();
    trigger_setup();

    simpleserial_init();
    simpleserial_addcmd('p', 20, get_pt);
    while(1)
        simpleserial_get();
}

#endif /* SHADOW32_FULL */
