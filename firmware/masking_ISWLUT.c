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
// Shadow32 2-공유 마스킹 — AND 는 LUT, 저장은 MaskedByte(인접, 도메인 분리 없음),
// 대신 "세척"만 적용. (마스킹 로직은 C, 세척은 작은 asm. 빌드 -O0, 난수는 pt.)
//
// [세척]  두 공유가 같은 레지스터/인접 버스에서 재결합해 HW(값)이 새는 것을 막기 위해:
//   - mask_refreshing: 두 공유 로드/저장 사이 레지스터·버스를 세척값 w 로 덮음.
//   - tableG: 룩업 전 y0 레지스터 세척 + 룩업 프리차지.
//   (도메인 분리는 쓰지 않음 — 두 공유는 MaskedByte 에 인접 저장.)
//
// [AND -> LUT]  g(x)=ROL(x,1)&ROL(x,7) 마스킹 테이블.
// [난수]  pt[4..7]=m(y0), pt[8..11]=r_in, pt[12..15]=r_key, pt[16..19]=f(refresh+세척).
// ---------------------------------------------------------------------------

static inline uint8_t ROL8(uint8_t val, int rot) {
    return ((val << rot) | (val >> (8 - rot))) & 0xFF;
}

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

// mask_refreshing + 세척: out.s0=a.s0^r, out.s1=a.s1^r 를 하되, 두 공유 접근 사이에
// 레지스터(r3)와 s1 슬롯 버스를 세척값 w 로 덮어 s0->s1 재결합(HW(값))을 끊는다.
static void mask_refreshing(MaskedByte *out, const MaskedByte *a, uint8_t r, uint8_t w) {
    __asm__ __volatile__(
        ".syntax unified\n\t"
        "movs r3,%[w]\n\t"
        "ldrb r3,[%[a],#0]\n\t"     // r3 = a.s0
        "eors r3,r3,%[r]\n\t"       // r3 = a.s0 ^ r
        "strb r3,[%[o],#0]\n\t"     // out.s0 = r3
        "movs r3,%[w]\n\t"          // r3 세척
        "strb %[w],[%[o],#1]\n\t"   // out.s1 = w (버스 프리차지)
        "ldrb r3,[%[a],#1]\n\t"     // r3 = a.s1
        "eors r3,r3,%[r]\n\t"       // r3 = a.s1 ^ r
        "strb r3,[%[o],#1]\n\t"     // out.s1 = r3
        "movs r3,%[w]\n\t"          // r3 세척
        ".syntax divided\n\t"
        : : [o]"r"(out), [a]"r"(a), [r]"r"(r), [w]"r"(w) : "r3", "memory");
}

// AND 부분 g(x)=ROL(x,1)&ROL(x,7) 테이블.
static uint8_t g_plain[256];
static uint8_t g_tab[256];

static void g_plain_init(void) {
    int v;
    for (v = 0; v < 256; v++)
        g_plain[v] = (uint8_t)(ROL8((uint8_t)v, 1) & ROL8((uint8_t)v, 7));
}

// LUT 기반 마스킹 AND + 세척. y0=출력마스크, w=세척값.
static MaskedByte tableG(const MaskedByte *in, uint8_t y0, uint8_t w) {
    int a;
    uint8_t x0 = in->s0;
    for (a = 0; a < 256; a++)
        g_tab[a] = (uint8_t)(g_plain[(uint8_t)(a ^ x0)] ^ y0);

    MaskedByte out;
    out.s0 = y0;

    // y0 레지스터 세척
    __asm__ __volatile__(
        "movs r2,%[w]\n\t movs r3,%[w]\n\t movs r4,%[w]\n\t"
        "movs r5,%[w]\n\t movs r6,%[w]\n\t movs r7,%[w]\n\t"
        : : [w]"r"(w) : "r2", "r3", "r4", "r5", "r6", "r7", "memory");

    // 공유1 룩업 (프리차지)
    const volatile uint8_t *px1 = &in->s1;
    uint8_t rv;
    __asm__ __volatile__(
        ".syntax unified\n\t"
        "movs r2,%[w]\n\t"
        "movs r3,%[w]\n\t"
        "ldrb r3,[%[px1]]\n\t"
        "ldrb %[rv],[%[gt],r3]\n\t"
        "movs r3,%[w]\n\t"
        ".syntax divided\n\t"
        : [rv]"=&l"(rv)
        : [w]"r"(w), [px1]"r"(px1), [gt]"r"(g_tab)
        : "r2", "r3", "memory");
    out.s1 = rv;
    return out;
}

// round (MaskedByte). 각 F: mask_refreshing(세척) -> tableG(세척) -> XOR.
//   s0=g(l0)^l1^ROL(l0,2)^k0, s1=g(r0)^r1^ROL(r0,2)^k1,
//   lo1=g(s0)^l0^ROL(s0,2)^k2, ro1=g(s1)^r0^ROL(s1,2)^k3
//   회전: l0=s1, l1=lo1, r0=s0, r1=ro1
void shadow32_round_masked(MaskedByte* l0, MaskedByte* l1,
                           MaskedByte* r0, MaskedByte* r1,
                           uint8_t m0, uint8_t m1, uint8_t m2, uint8_t m3,
                           uint8_t k0, uint8_t k1, uint8_t k2, uint8_t k3,
                           uint8_t f0, uint8_t f1, uint8_t f2, uint8_t f3)
{
    MaskedByte t, and_v, rol2;

    // s0
    mask_refreshing(&t, l0, f0, f0);
    and_v = tableG(&t, m0, f0);
    rol2 = masked_ROL8(l0, 2);
    MaskedByte s0 = masked_xor(&and_v, l1);
    s0 = masked_xor(&s0, &rol2);
    masked_xor_const_inplace(&s0, k0);

    // s1
    mask_refreshing(&t, r0, f1, f1);
    and_v = tableG(&t, m1, f1);
    rol2 = masked_ROL8(r0, 2);
    MaskedByte s1 = masked_xor(&and_v, r1);
    s1 = masked_xor(&s1, &rol2);
    masked_xor_const_inplace(&s1, k1);

    MaskedByte lo0 = s1;

    // lo1
    mask_refreshing(&t, &s0, f2, f2);
    and_v = tableG(&t, m2, f2);
    rol2 = masked_ROL8(&s0, 2);
    MaskedByte lo1 = masked_xor(&and_v, l0);
    lo1 = masked_xor(&lo1, &rol2);
    masked_xor_const_inplace(&lo1, k2);

    MaskedByte ro0 = s0;

    // ro1
    mask_refreshing(&t, &s1, f3, f3);
    and_v = tableG(&t, m3, f3);
    rol2 = masked_ROL8(&s1, 2);
    MaskedByte ro1 = masked_xor(&and_v, r0);
    ro1 = masked_xor(&ro1, &rol2);
    masked_xor_const_inplace(&ro1, k3);

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

    g_plain_init();

    rk[0] ^= r_key0;
    rk[1] ^= r_key1;
    rk[2] ^= r_key2;
    rk[3] ^= r_key3;

    MaskedByte ml0, ml1, mr0, mr1;
    mask_byte(l0, &ml0, r_in0);
    mask_byte(l1, &ml1, r_in1);
    mask_byte(r0, &mr0, r_in2);
    mask_byte(r1, &mr1, r_in3);

    trigger_high();

    shadow32_round_masked(&ml0, &ml1, &mr0, &mr1, m0, m1, m2, m3,
                          rk[0], rk[1], rk[2], rk[3], f0, f1, f2, f3);

    for (volatile uint32_t pad = 0; pad < 10000u; pad++) {
        asm("NOP");
    }

    trigger_low();

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
