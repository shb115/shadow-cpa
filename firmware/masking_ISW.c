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
// Shadow32 2-공유 ISW 마스킹 — PIPO 참조코드(simpleserial-aes_PIPO_SHARES3)의
// ISW_AND_HO(정통 ISW 곱셈) 와 mask_refreshing(AND 앞 refresh) 를 우리 코드에 적용.
// 순수 C, 온디바이스 PRNG 없음(모든 난수는 pt 입력), 빌드 -O0, refresh 는 AND 앞 고정.
//
// [난수]  pt[0..3]=평문, pt[4..7]=m(ISW AND 난수), pt[8..11]=r_in(입력마스크),
//         pt[12..15]=r_key(키마스크), pt[16..19]=f(AND 앞 refresh 난수).
//
// [ISW_AND] PIPO ISW_AND_HO 를 SHARES=2 로 특수화:
//   r10 = r ^ (a0&b1) ^ (a1&b0)
//   c0  = a0&b0 ^ r
//   c1  = a1&b1 ^ r10
//
// [mask_refreshing] PIPO mask_refreshing 를 SHARES=2 로: 값 불변, 두 공유 ^= r.
//   각 AND 앞에서 피연산자 a 를 refresh 한다(PIPO 의 sbox 패턴과 동일).
//
// [키 마스킹] rk[j]^=r_key_j 후 한 공유에 XOR.
//            트리거는 입력·키 마스킹 이후, 라운드만 측정.
// ---------------------------------------------------------------------------

static inline uint8_t ROL8(uint8_t val, int rot) {
    return ((val << rot) | (val >> (8 - rot))) & 0xFF;
}

// 마스킹된 바이트: 두 공유(s0, s1)
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

static inline void masked_xor_const_inplace(MaskedByte *a, uint8_t k) {
    a->s0 ^= k;
}

// mask_refreshing (PIPO, SHARES=2): 값(s0^s1) 불변, 두 공유를 r 로 재마스킹.
static inline MaskedByte mask_refreshing(const MaskedByte *a, uint8_t r) {
    MaskedByte out;
    out.s0 = a->s0 ^ r;
    out.s1 = a->s1 ^ r;
    return out;
}

// ISW_AND (PIPO ISW_AND_HO, SHARES=2). a=a0^a1, b=b0^b1. 랜덤 r은 외부(pt).
static inline MaskedByte ISW_AND(const MaskedByte *a, const MaskedByte *b, uint8_t r) {
    uint8_t r10 = (r ^ (a->s0 & b->s1)) ^ (a->s1 & b->s0);
    MaskedByte c;
    c.s0 = (a->s0 & b->s0) ^ r;
    c.s1 = (a->s1 & b->s1) ^ r10;
    return c;
}

// round (원본 masking.c 의 연산 순서). 각 AND 앞에 mask_refreshing(피연산자 a).
//   s0  = (((ROL8(l0,1) & ROL8(l0,7)) ^ l1) ^ ROL8(l0,2)) ^ k0
//   s1  = (((ROL8(r0,1) & ROL8(r0,7)) ^ r1) ^ ROL8(r0,2)) ^ k1
//   lo0 = s1
//   lo1 = (((ROL8(s0,1) & ROL8(s0,7)) ^ l0) ^ ROL8(s0,2)) ^ k2
//   ro0 = s0
//   ro1 = (((ROL8(s1,1) & ROL8(s1,7)) ^ r0) ^ ROL8(s1,2)) ^ k3
//   출력: l0=lo0(=s1), l1=lo1, r0=ro0(=s0), r1=ro1
void shadow32_round_masked(MaskedByte* l0, MaskedByte* l1,
                           MaskedByte* r0, MaskedByte* r1,
                           uint8_t m0, uint8_t m1, uint8_t m2, uint8_t m3,
                           uint8_t k0, uint8_t k1, uint8_t k2, uint8_t k3,
                           uint8_t f0, uint8_t f1, uint8_t f2, uint8_t f3)
{
    // s0 = F(l0) ^ l1 ^ k0
    MaskedByte l0_rol1 = masked_ROL8(l0, 1);
    MaskedByte l0_rol7 = masked_ROL8(l0, 7);
    l0_rol1 = mask_refreshing(&l0_rol1, f0);        // refresh (AND 앞)
    MaskedByte and_l = ISW_AND(&l0_rol1, &l0_rol7, m0);
    MaskedByte l0_rol2 = masked_ROL8(l0, 2);
    MaskedByte s0 = masked_xor(&and_l, l1);
    s0 = masked_xor(&s0, &l0_rol2);
    masked_xor_const_inplace(&s0, k0);

    // s1 = F(r0) ^ r1 ^ k1
    MaskedByte r0_rol1 = masked_ROL8(r0, 1);
    MaskedByte r0_rol7 = masked_ROL8(r0, 7);
    r0_rol1 = mask_refreshing(&r0_rol1, f1);        // refresh (AND 앞)
    MaskedByte and_r = ISW_AND(&r0_rol1, &r0_rol7, m1);
    MaskedByte r0_rol2 = masked_ROL8(r0, 2);
    MaskedByte s1 = masked_xor(&and_r, r1);
    s1 = masked_xor(&s1, &r0_rol2);
    masked_xor_const_inplace(&s1, k1);

    // lo0 = s1
    MaskedByte lo0 = s1;

    // lo1 = F(s0) ^ l0 ^ k2
    MaskedByte s0_rol1 = masked_ROL8(&s0, 1);
    MaskedByte s0_rol7 = masked_ROL8(&s0, 7);
    s0_rol1 = mask_refreshing(&s0_rol1, f2);        // refresh (AND 앞)
    MaskedByte and_s0 = ISW_AND(&s0_rol1, &s0_rol7, m2);
    MaskedByte s0_rol2 = masked_ROL8(&s0, 2);
    MaskedByte lo1 = masked_xor(&and_s0, l0);
    lo1 = masked_xor(&lo1, &s0_rol2);
    masked_xor_const_inplace(&lo1, k2);

    // ro0 = s0
    MaskedByte ro0 = s0;

    // ro1 = F(s1) ^ r0 ^ k3
    MaskedByte s1_rol1 = masked_ROL8(&s1, 1);
    MaskedByte s1_rol7 = masked_ROL8(&s1, 7);
    s1_rol1 = mask_refreshing(&s1_rol1, f3);        // refresh (AND 앞)
    MaskedByte and_s1 = ISW_AND(&s1_rol1, &s1_rol7, m3);
    MaskedByte s1_rol2 = masked_ROL8(&s1, 2);
    MaskedByte ro1 = masked_xor(&and_s1, r0);
    ro1 = masked_xor(&ro1, &s1_rol2);
    masked_xor_const_inplace(&ro1, k3);

    // write outputs back
    *l0 = lo0;
    *l1 = lo1;
    *r0 = ro0;
    *r1 = ro1;
}

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

    // AND 앞 refresh 난수
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

    // 키 마스킹 (트리거 밖)
    rk[0] ^= r_key0;
    rk[1] ^= r_key1;
    rk[2] ^= r_key2;
    rk[3] ^= r_key3;

    MaskedByte ml0, ml1, mr0, mr1;

    // 입력 마스킹 (트리거 밖)
    mask_byte(l0, &ml0, r_in0);
    mask_byte(l1, &ml1, r_in1);
    mask_byte(r0, &mr0, r_in2);
    mask_byte(r1, &mr1, r_in3);

    trigger_high();

    shadow32_round_masked(&ml0, &ml1, &mr0, &mr1, m0, m1, m2, m3,
                          rk[0], rk[1], rk[2], rk[3],
                          f0, f1, f2, f3);

    // NOP 패딩: 라운드 뒤 1만회 루프 (-O0 라 생략되지 않고 실제 실행).
    for (volatile uint32_t pad = 0; pad < 10000u; pad++) {
        asm("NOP");
    }

    trigger_low();

    // 정확성 확인용(KAT). make ... EXTRA_OPTS=SHADOW32_KAT 로만 활성화.
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
    simpleserial_addcmd('p', 20, get_pt);   // pt 20바이트 (refresh 난수 4개 포함)
    while(1)
        simpleserial_get();
}
