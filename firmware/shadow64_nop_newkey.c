/*
 * shadow64_nop_newkey.c
 * ------------------------------------------------------------------
 * Shadow-64 (full 32-round) — ChipWhisperer-Nano(STM32F0/Cortex-M0)
 * CPA 파형 수집용 **단일 자립 펌웨어**.
 *
 * 사이퍼(라운드 함수 / 암호화)와 simpleserial 글루가 이 한 파일에 모두 들어 있다.
 * 외부 .c 를 extern/VPATH 로 끌어오지 않는다.
 *
 * 키스케줄은 온디바이스로 돌리지 않는다: Shadow-64 키스케줄의 지역배열
 * b[128]+nb[128]=256B 가 Nano 스택을 넘겨 문제가 되므로, 마스터키
 * 07E9A4B27E3FCB472DA757EA31CAF4ED 의 rk[128] 을 미리 계산해 baked 한다
 * (첫 라운드키 = 872C E3FB 644A 72D7).
 * 다른 키가 필요하면 호스트에서 rk[128] 을 계산해 이 표를 교체하면 된다.
 *
 * ★ 반드시 -O0 로 빌드할 것 (makefile: OPT = 0). 근거는 shadow32_nop.c 참고.
 *
 * 커맨드 (SimpleSerial v1.1):
 *   'p' (8바이트) : 평문 8바이트(4x16bit, big-endian) 풀 사이퍼 암호화
 *                   (trigger_high..low), 암호문 8바이트를 16바이트 버퍼로 'r' 반환
 * ------------------------------------------------------------------
 */
#include "aes-independant.h"
#include "hal.h"
#include "simpleserial.h"
#include <stdint.h>

/* =====================================================================
 *  Shadow-64 사이퍼 (검증된 구현을 그대로 인라인)
 *  F(x) = (x<<<1 & x<<<7) ^ (x<<<2),  16-bit
 * ===================================================================== */
static inline uint16_t ROL16(uint16_t val, int rot)
{
    return ((val << rot) | (val >> (16 - rot))) & 0xFFFF;
}

static void shadow64_round(uint16_t* l0, uint16_t* l1, uint16_t* r0, uint16_t* r1,
                           uint16_t k0, uint16_t k1, uint16_t k2, uint16_t k3)
{
    uint16_t s0, s1;

    s0 = (ROL16(*l0, 1) & ROL16(*l0, 7)) ^ ROL16(*l0, 2) ^ *l1 ^ k0;
    s1 = (ROL16(*r0, 1) & ROL16(*r0, 7)) ^ ROL16(*r0, 2) ^ *r1 ^ k1;

    *l1 = (ROL16(s0, 1) & ROL16(s0, 7)) ^ ROL16(s0, 2) ^ *l0 ^ k2;
    *r1 = (ROL16(s1, 1) & ROL16(s1, 7)) ^ ROL16(s1, 2) ^ *r0 ^ k3;

    *l0 = s1;
    *r0 = s0;
}

static void shadow64_encrypt(const uint16_t pt[4], const uint16_t rk[128], uint16_t ct[4])
{
    uint16_t l0 = pt[0], l1 = pt[1], r0 = pt[2], r1 = pt[3];
    int i;

    for (i = 0; i < 32; i++)
        shadow64_round(&l0, &l1, &r0, &r1,
                       rk[4 * i], rk[4 * i + 1], rk[4 * i + 2], rk[4 * i + 3]);

    ct[0] = r0;
    ct[1] = l1;
    ct[2] = l0;
    ct[3] = r1;
}

/* =====================================================================
 *  SimpleSerial 글루 (baked rk, 'p' 만)
 * ===================================================================== */

/* 랜덤 마스터키 07E9A4B27E3FCB472DA757EA31CAF4ED 의 rk[128]
   (shadow64_key_schedule 로 생성). 첫 라운드키 = 0x872C 0xE3FB 0x644A 0x72D7
   reference/selftest.c 가 같은 마스터키로 이 값을 재현한다. */
static const uint16_t rk[128] = {
    0x872C, 0xE3FB, 0x644A, 0x72D7, 0x6604, 0x472D, 0x8A47, 0x725E,
    0x2814, 0xA725, 0x273A, 0xE843, 0x0263, 0x7E84, 0x0A01, 0x3020,
    0x8030, 0xA302, 0x0106, 0x0498, 0x6060, 0x1049, 0x0685, 0x8496,
    0x2018, 0x6849, 0x2505, 0x6112, 0x0200, 0x5611, 0x650C, 0x2000,
    0x2600, 0x5200, 0x1C07, 0x0008, 0x1120, 0xC000, 0x0716, 0x8816,
    0x4021, 0x7881, 0x0607, 0x6012, 0xC000, 0x6601, 0x0708, 0x2000,
    0x3000, 0x7200, 0x280B, 0x0002, 0x2240, 0x8000, 0x0B0C, 0x2001,
    0x6000, 0xB200, 0x0C0A, 0x1014, 0x8000, 0xC101, 0x4A0C, 0x400C,
    0x9420, 0xA400, 0x0C0D, 0xC003, 0x8010, 0xCC00, 0x0D0E, 0x3002,
    0x8040, 0xD300, 0x2E0D, 0x2007, 0xC200, 0xE200, 0x1D00, 0x7009,
    0xC110, 0xD700, 0x0001, 0x9008, 0xC020, 0x0900, 0x0106, 0x8009,
    0xC040, 0x1800, 0x1603, 0x9009, 0x0190, 0x6900, 0x0304, 0x900D,
    0x1080, 0x3900, 0x0407, 0xD00D, 0x6000, 0x4D00, 0x9707, 0xD00D,
    0x3900, 0x7D00, 0x8707, 0xD00D, 0x4890, 0x7D00, 0x0708, 0xD001,
    0x6040, 0x7D00, 0x0808, 0x1000, 0x6040, 0x8100, 0x980A, 0x0007,
    0x6940, 0x8000, 0x4A0B, 0x7002, 0x8410, 0xA700, 0x0B05, 0x2005
};

/* 'p' : 8바이트 평문(4x16bit BE) 풀 사이퍼 암호화 */
/* ===== 캡처 윈도우 뒤쪽을 채우는 NOP 패딩 =====
   shadow64: 32라운드 23796 cycle + 패딩 -> samples 25000 커버
   NOP 32개 블록 하나만 코드에 두고 for 문으로 80회 반복한다.
   (전부 펼쳐 넣으면 코드가 커지고 Thumb PC-상대 오프셋 한계에도 걸린다) */
#define NOP_BLK_ITER 80

static void __attribute__((noinline)) nop_blk(void)
{
    __asm__ volatile(".rept 32\n\t"
                     "nop\n\t"
                     ".endr\n\t" ::: "memory");
}

static void nop_pad(void)
{
    int i;
    for (i = 0; i < NOP_BLK_ITER; i++)
        nop_blk();
}

uint8_t enc(uint8_t* pt, uint8_t len)
{
    (void)len;
    uint16_t p[4], c[4];
    uint8_t out[16] = {0};
    int i;

    for (i = 0; i < 4; i++)
        p[i] = ((uint16_t)pt[2 * i] << 8) | (uint16_t)pt[2 * i + 1];

    aes_indep_enc_pretrigger(pt);
    trigger_high();
    shadow64_encrypt(p, rk, c);
    nop_pad();
    trigger_low();
    aes_indep_enc_posttrigger(pt);

    for (i = 0; i < 4; i++) {
        out[2 * i]     = (uint8_t)(c[i] >> 8);
        out[2 * i + 1] = (uint8_t)(c[i] & 0xFF);
    }
    simpleserial_put('r', 16, out);
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
    simpleserial_addcmd('p', 8, enc);
    while (1)
        simpleserial_get();
}
