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

// ---------------------------------------------------------------------------
// Shadow-32 with two-share ISW masking (v2, the ISW implementation of Section 4.7 of the
// paper). The ISW AND gadget and the mask refresh follow the structure of the PIPO reference
// code (simpleserial-aes_PIPO_SHARES3): ISW_AND_HO, the ISW multiplication, and
// mask_refreshing, the refresh before each AND, specialized to two shares and applied to our
// cipher. Plain C, no on-device random number generator (every random byte comes with the
// command input), built at -O0, the refresh fixed before each AND.
//
// [Randomness]  pt[0..3] = plaintext, pt[4..7] = m (the fresh random byte of each ISW AND),
//   pt[8..11] = r_in (input masks), pt[12..15] = r_key (key masks), pt[16..19] = f (the
//   refresh byte before each AND).
//
// [ISW_AND]  PIPO ISW_AND_HO with SHARES = 2:
//   r10 = r ^ (a0&b1) ^ (a1&b0)
//   c0  = a0&b0 ^ r
//   c1  = a1&b1 ^ r10
//
// [mask_refreshing]  PIPO mask_refreshing with SHARES = 2: the shared value is unchanged,
//   both shares ^= r. The operand a of each AND is refreshed before it (the pattern of the
//   PIPO S-box).
//
// [Key masking]  rk[j] ^= r_key_j, outside the trigger. Inside the round the masked key byte
//   rk[j] is XORed into share 0 and its mask r_key_j into share 1 (masked_xor_key). The XOR
//   of the two shares is then value ^ RK_j, so the round computes correctly, and the key byte
//   never appears unmasked.
//   (The v1 firmware added rk[j] to share 0 only and r_key_j to neither share, so the XOR of
//    the two shares was value ^ RK_j ^ r_key_j: every encryption ran under a different key.
//    This file is v2, which corrects that one line.)
//   The trigger rises after the input and key masking and covers the round only.
// ---------------------------------------------------------------------------

static inline uint8_t ROL8(uint8_t val, int rot) {
    return ((val << rot) | (val >> (8 - rot))) & 0xFF;
}

// A masked byte: two shares (s0, s1)
typedef struct {
    uint8_t s0;
    uint8_t s1;
} MaskedByte;

static inline void mask_byte(uint8_t v, MaskedByte *m, uint8_t r) {
    m->s0 = r;
    m->s1 = v ^ r;
}

static inline uint8_t unmask_byte(const MaskedByte *m) {
    return m->s0 ^ m->s1;
}

static inline MaskedByte masked_ROL8(const MaskedByte *a, int rot) {
    MaskedByte out;
    out.s0 = ROL8(a->s0, rot);
    out.s1 = ROL8(a->s1, rot);
    return out;
}

static inline MaskedByte masked_xor(const MaskedByte *a, const MaskedByte *b) {
    MaskedByte out;
    out.s0 = a->s0 ^ b->s0;
    out.s1 = a->s1 ^ b->s1;
    return out;
}

// Key addition (v2): the masked key byte k = RK ^ q into share 0, its mask q into share 1.
static inline void masked_xor_key(MaskedByte *a, uint8_t k, uint8_t q) {
    a->s0 ^= k;
    a->s1 ^= q;
}

// mask_refreshing (PIPO, SHARES = 2): the value s0 ^ s1 is unchanged, both shares are remasked with r.
static inline MaskedByte mask_refreshing(const MaskedByte *a, uint8_t r) {
    MaskedByte out;
    out.s0 = a->s0 ^ r;
    out.s1 = a->s1 ^ r;
    return out;
}

// ISW_AND (PIPO ISW_AND_HO, SHARES = 2). a = a0 ^ a1, b = b0 ^ b1. The random byte r comes from the input (pt).
static inline MaskedByte ISW_AND(const MaskedByte *a, const MaskedByte *b, uint8_t r) {
    uint8_t r10 = (r ^ (a->s0 & b->s1)) ^ (a->s1 & b->s0);
    MaskedByte c;
    c.s0 = (a->s0 & b->s0) ^ r;
    c.s1 = (a->s1 & b->s1) ^ r10;
    return c;
}

// The round (the operation order of the original masking.c), with mask_refreshing of the operand a before each AND.
//   s0  = (((ROL8(l0,1) & ROL8(l0,7)) ^ l1) ^ ROL8(l0,2)) ^ k0
//   s1  = (((ROL8(r0,1) & ROL8(r0,7)) ^ r1) ^ ROL8(r0,2)) ^ k1
//   lo0 = s1
//   lo1 = (((ROL8(s0,1) & ROL8(s0,7)) ^ l0) ^ ROL8(s0,2)) ^ k2
//   ro0 = s0
//   ro1 = (((ROL8(s1,1) & ROL8(s1,7)) ^ r0) ^ ROL8(s1,2)) ^ k3
//   output: l0 = lo0 (= s1), l1 = lo1, r0 = ro0 (= s0), r1 = ro1
//   k_j = RK_j ^ q_j (the masked key byte), q_j = the key mask.
void shadow32_round_masked(MaskedByte* l0, MaskedByte* l1,
                           MaskedByte* r0, MaskedByte* r1,
                           uint8_t m0, uint8_t m1, uint8_t m2, uint8_t m3,
                           uint8_t k0, uint8_t k1, uint8_t k2, uint8_t k3,
                           uint8_t q0, uint8_t q1, uint8_t q2, uint8_t q3,
                           uint8_t f0, uint8_t f1, uint8_t f2, uint8_t f3)
{
    // s0 = F(l0) ^ l1 ^ RK0
    MaskedByte l0_rol1 = masked_ROL8(l0, 1);
    MaskedByte l0_rol7 = masked_ROL8(l0, 7);
    l0_rol1 = mask_refreshing(&l0_rol1, f0);        // refresh (before the AND)
    MaskedByte and_l = ISW_AND(&l0_rol1, &l0_rol7, m0);
    MaskedByte l0_rol2 = masked_ROL8(l0, 2);
    MaskedByte s0 = masked_xor(&and_l, l1);
    s0 = masked_xor(&s0, &l0_rol2);
    masked_xor_key(&s0, k0, q0);

    // s1 = F(r0) ^ r1 ^ RK1
    MaskedByte r0_rol1 = masked_ROL8(r0, 1);
    MaskedByte r0_rol7 = masked_ROL8(r0, 7);
    r0_rol1 = mask_refreshing(&r0_rol1, f1);        // refresh (before the AND)
    MaskedByte and_r = ISW_AND(&r0_rol1, &r0_rol7, m1);
    MaskedByte r0_rol2 = masked_ROL8(r0, 2);
    MaskedByte s1 = masked_xor(&and_r, r1);
    s1 = masked_xor(&s1, &r0_rol2);
    masked_xor_key(&s1, k1, q1);

    // lo0 = s1
    MaskedByte lo0 = s1;

    // lo1 = F(s0) ^ l0 ^ RK2
    MaskedByte s0_rol1 = masked_ROL8(&s0, 1);
    MaskedByte s0_rol7 = masked_ROL8(&s0, 7);
    s0_rol1 = mask_refreshing(&s0_rol1, f2);        // refresh (before the AND)
    MaskedByte and_s0 = ISW_AND(&s0_rol1, &s0_rol7, m2);
    MaskedByte s0_rol2 = masked_ROL8(&s0, 2);
    MaskedByte lo1 = masked_xor(&and_s0, l0);
    lo1 = masked_xor(&lo1, &s0_rol2);
    masked_xor_key(&lo1, k2, q2);

    // ro0 = s0
    MaskedByte ro0 = s0;

    // ro1 = F(s1) ^ r0 ^ RK3
    MaskedByte s1_rol1 = masked_ROL8(&s1, 1);
    MaskedByte s1_rol7 = masked_ROL8(&s1, 7);
    s1_rol1 = mask_refreshing(&s1_rol1, f3);        // refresh (before the AND)
    MaskedByte and_s1 = ISW_AND(&s1_rol1, &s1_rol7, m3);
    MaskedByte s1_rol2 = masked_ROL8(&s1, 2);
    MaskedByte ro1 = masked_xor(&and_s1, r0);
    ro1 = masked_xor(&ro1, &s1_rol2);
    masked_xor_key(&ro1, k3, q3);

    // write outputs back
    *l0 = lo0;
    *l1 = lo1;
    *r0 = ro0;
    *r1 = ro1;
}

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
// 196 random bytes = 4 + 16 x 12 (as in Table 2 of the paper).
// ---------------------------------------------------------------------------
#include <string.h>
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

    uint8_t rk[64] = {
        0x0D, 0x3B, 0x60, 0x33, 0x43, 0x60, 0x25, 0x3C,
        0x13, 0x25, 0x89, 0xC5, 0x3C, 0x89, 0x0D, 0x5D,
        0x25, 0x0D, 0x40, 0xD1, 0x8D, 0x40, 0x14, 0x15,
        0x11, 0x14, 0x91, 0x56, 0xC5, 0x91, 0x03, 0x6D,
        0x16, 0x03, 0x02, 0xD6, 0x1D, 0x02, 0x08, 0x63,
        0x06, 0x08, 0x31, 0x39, 0x43, 0x31, 0x2C, 0x90,
        0x69, 0x2C, 0x01, 0x0A, 0x20, 0x01, 0x11, 0xAB,
        0x9A, 0x11, 0x00, 0xBC, 0x0B, 0x00, 0x04, 0xCE
    };
    uint8_t km[64];
    int i, j;
    // Key masking (outside the trigger): km = RK ^ q
    for (i = 0; i < 16; i++)
        for (j = 0; j < 4; j++)
            km[4*i + j] = rk[4*i + j] ^ rnd[12*i + 8 + j];

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
                              km[4*i], km[4*i + 1], km[4*i + 2], km[4*i + 3],
                              rr[8], rr[9], rr[10], rr[11],
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

#else  /* one round (the measurement firmware of Section 4.7 of the paper, v2) */

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

    uint8_t r_key0 = pt[12];
    uint8_t r_key1 = pt[13];
    uint8_t r_key2 = pt[14];
    uint8_t r_key3 = pt[15];

    // The refresh bytes before the ANDs
    uint8_t f0 = pt[16];
    uint8_t f1 = pt[17];
    uint8_t f2 = pt[18];
    uint8_t f3 = pt[19];

    uint8_t rk[64] = {
        0x0D, 0x3B, 0x60, 0x33, 0x43, 0x60, 0x25, 0x3C,
        0x13, 0x25, 0x89, 0xC5, 0x3C, 0x89, 0x0D, 0x5D,
        0x25, 0x0D, 0x40, 0xD1, 0x8D, 0x40, 0x14, 0x15,
        0x11, 0x14, 0x91, 0x56, 0xC5, 0x91, 0x03, 0x6D,
        0x16, 0x03, 0x02, 0xD6, 0x1D, 0x02, 0x08, 0x63,
        0x06, 0x08, 0x31, 0x39, 0x43, 0x31, 0x2C, 0x90,
        0x69, 0x2C, 0x01, 0x0A, 0x20, 0x01, 0x11, 0xAB,
        0x9A, 0x11, 0x00, 0xBC, 0x0B, 0x00, 0x04, 0xCE
    };

    // Key masking (outside the trigger): rk[j] is now RK_j ^ r_key_j
    rk[0] ^= r_key0;
    rk[1] ^= r_key1;
    rk[2] ^= r_key2;
    rk[3] ^= r_key3;

    MaskedByte ml0, ml1, mr0, mr1;

    // Input masking (outside the trigger)
    mask_byte(l0, &ml0, r_in0);
    mask_byte(l1, &ml1, r_in1);
    mask_byte(r0, &mr0, r_in2);
    mask_byte(r1, &mr1, r_in3);

    trigger_high();

    shadow32_round_masked(&ml0, &ml1, &mr0, &mr1, m0, m1, m2, m3,
                          rk[0], rk[1], rk[2], rk[3],
                          r_key0, r_key1, r_key2, r_key3,
                          f0, f1, f2, f3);

    // NOP padding: a 10,000-iteration idle loop after the round (at -O0 it is not optimized away
    // and actually runs).
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
    simpleserial_addcmd('p', 20, get_pt);   // 20-byte input (the four refresh bytes included)
    while(1)
        simpleserial_get();
}

#endif /* SHADOW32_FULL */
