/*
 * shadow32_nop.c
 * ------------------------------------------------------------------
 * Shadow-32 (the full 16-round encryption) on the ChipWhisperer-Nano (STM32F030, Cortex-M0):
 * the single self-contained capture firmware of the unprotected CPA traces.
 *
 * The cipher (round function, encryption, key schedule) and the SimpleSerial glue are all in
 * this one file; no external .c file (shadow32.c or other) is pulled in through extern or
 * VPATH. The only #includes are the headers of the ChipWhisperer target framework
 * (hal, simpleserial, aes-independant).
 *
 * Build at -O0 (makefile: OPT = 0). At -O0 every intermediate value is stored to stack
 *   memory on each operation, which gives the strong Hamming-weight leakage on the bus that
 *   the attack targets (correct-key correlation of about 0.9 on the deposited traces). An
 *   optimized build keeps the intermediate values in registers and is expected to leak less.
 *
 * Commands (SimpleSerial v1.1):
 *   'd' (0 bytes) : reset rk to the baked reference table (RK1 = 0D 3B 60 33 ...)   (fixed-key set)
 *   'k' (8 bytes) : 8-byte master key -> on-device key schedule -> rk[64]            (ten-key sets)
 *   'p' (4 bytes) : full encryption of the 4-byte plaintext (trigger_high .. trigger_low);
 *                   the 4-byte ciphertext is returned in a 16-byte buffer with 'r'
 * ------------------------------------------------------------------
 */
#include "aes-independant.h"
#include "hal.h"
#include "simpleserial.h"
#include <stdint.h>

/* =====================================================================
 *  The Shadow-32 cipher (the verified implementation, inlined as is)
 *  F(x) = (x<<<1 & x<<<7) ^ (x<<<2),  8-bit
 * ===================================================================== */
static inline uint8_t ROL8(uint8_t val, int rot)
{
    return ((val << rot) | (val >> (8 - rot))) & 0xFF;
}

static const uint8_t SHADOW32_PERM[64] = {
    56, 57, 58, 59, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27,
    60, 61, 62, 63, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
    40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15
};

/* One round, through pointers (stack memory): strong Hamming-weight leakage at -O0 */
static void shadow32_round(uint8_t* l0, uint8_t* l1, uint8_t* r0, uint8_t* r1,
                           uint8_t k0, uint8_t k1, uint8_t k2, uint8_t k3)
{
    uint8_t s0, s1;

    s0 = (ROL8(*l0, 1) & ROL8(*l0, 7)) ^ ROL8(*l0, 2) ^ *l1 ^ k0;
    s1 = (ROL8(*r0, 1) & ROL8(*r0, 7)) ^ ROL8(*r0, 2) ^ *r1 ^ k1;

    *l1 = (ROL8(s0, 1) & ROL8(s0, 7)) ^ ROL8(s0, 2) ^ *l0 ^ k2;
    *r1 = (ROL8(s1, 1) & ROL8(s1, 7)) ^ ROL8(s1, 2) ^ *r0 ^ k3;

    *l0 = s1;
    *r0 = s0;
}

static void shadow32_encrypt(const uint8_t pt[4], const uint8_t rk[64], uint8_t ct[4])
{
    uint8_t l0 = pt[0], l1 = pt[1], r0 = pt[2], r1 = pt[3];
    int i;

    for (i = 0; i < 16; i++)
        shadow32_round(&l0, &l1, &r0, &r1,
                       rk[4 * i], rk[4 * i + 1], rk[4 * i + 2], rk[4 * i + 3]);

    ct[0] = r0;
    ct[1] = l1;
    ct[2] = l0;
    ct[3] = r1;
}

static uint8_t pack8(const uint8_t* b, const int* idx)
{
    uint8_t v = 0;
    int i;
    for (i = 0; i < 8; i++)
        v = (v << 1) | (b[idx[i]] & 1);
    return v;
}

static void shadow32_key_schedule(const uint8_t master[8], uint8_t rk[64])
{
    static const int K0[8] = {  0,  1,  2,  3,  8,  9, 10, 11 };
    static const int K1[8] = {  4,  5,  6,  7, 12, 13, 14, 15 };
    static const int K2[8] = { 16, 17, 18, 19, 24, 25, 26, 27 };
    static const int K3[8] = { 20, 21, 22, 23, 28, 29, 30, 31 };

    uint8_t b[64], nb[64];
    uint8_t k56, k57, k58, k59, k60, k61, k62, k63, rc;
    int i, r;

    for (i = 0; i < 64; i++)
        b[i] = (master[i >> 3] >> (7 - (i & 7))) & 1;

    for (r = 0; r < 16; r++) {
        rc = r + 1;
        b[3] ^= (rc >> 4) & 1;
        b[4] ^= (rc >> 3) & 1;
        b[5] ^= (rc >> 2) & 1;
        b[6] ^= (rc >> 1) & 1;
        b[7] ^= rc & 1;

        k56 = b[56]; k57 = b[57]; k58 = b[58]; k59 = b[59];
        k60 = b[60]; k61 = b[61]; k62 = b[62]; k63 = b[63];

        b[56] = k56 & (k56 ^ k62);
        b[57] = k57 & (k57 ^ k63);
        b[58] = k58 & (k58 ^ k56 ^ k62);
        b[59] = k59 & (k59 ^ k57 ^ k63);
        b[60] = k60 & (k60 ^ k58 ^ k56 ^ k62);
        b[61] = k61 & (k61 ^ k59 ^ k57 ^ k63);
        b[62] = k62 & (k60 ^ k58 ^ k56);
        b[63] = k63 & (k61 ^ k59 ^ k57);

        for (i = 0; i < 64; i++)
            nb[i] = b[SHADOW32_PERM[i]];
        for (i = 0; i < 64; i++)
            b[i] = nb[i];

        rk[4 * r]     = pack8(b, K0);
        rk[4 * r + 1] = pack8(b, K1);
        rk[4 * r + 2] = pack8(b, K2);
        rk[4 * r + 3] = pack8(b, K3);
    }
}

/* =====================================================================
 *  SimpleSerial glue
 * ===================================================================== */

/* The round keys of the fixed-key set, baked in as a table instead of running the key
   schedule. RK1 = 0D 3B 60 33. A master key that produces these round keys is
   DC4A3DB3035C950E, with which reference/selftest.c reproduces this table. */
static const uint8_t RK_DEFAULT[64] = {
    0x0D, 0x3B, 0x60, 0x33, 0x43, 0x60, 0x25, 0x3C,
    0x13, 0x25, 0x89, 0xC5, 0x3C, 0x89, 0x0D, 0x5D,
    0x25, 0x0D, 0x40, 0xD1, 0x8D, 0x40, 0x14, 0x15,
    0x11, 0x14, 0x91, 0x56, 0xC5, 0x91, 0x03, 0x6D,
    0x16, 0x03, 0x02, 0xD6, 0x1D, 0x02, 0x08, 0x63,
    0x06, 0x08, 0x31, 0x39, 0x43, 0x31, 0x2C, 0x90,
    0x69, 0x2C, 0x01, 0x0A, 0x20, 0x01, 0x11, 0xAB,
    0x9A, 0x11, 0x00, 0xBC, 0x0B, 0x00, 0x04, 0xCE
};

static uint8_t rk[64];   /* the current round keys */

static void rk_reset(void)
{
    int i;
    for (i = 0; i < 64; i++)
        rk[i] = RK_DEFAULT[i];
}

/* 'd' : reset to the reference round keys */
uint8_t set_default(uint8_t* x, uint8_t len)
{
    (void)x; (void)len;
    rk_reset();
    return 0x00;
}

/* 'k' : 8-byte master key -> key schedule -> rk[64] */
uint8_t set_key(uint8_t* mk, uint8_t len)
{
    (void)len;
    shadow32_key_schedule(mk, rk);
    return 0x00;
}

/* 'p' : full encryption of the 4-byte plaintext (the trigger spans all 16 rounds) */
/* ===== NOP padding that fills the rest of the capture window =====
   Shadow-32: 16 rounds of 11,968 cycles plus the padding cover the 12,500 samples.
   One block of 32 NOPs is kept in the code and repeated 40 times by a for loop
   (unrolling it all would enlarge the code and exceed the Thumb pc-relative offset range). */
#define NOP_BLK_ITER 40

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
    uint8_t ct[4];
    uint8_t out[16] = {0};

    aes_indep_enc_pretrigger(pt);
    trigger_high();
    shadow32_encrypt(pt, rk, ct);
    nop_pad();
    trigger_low();
    aes_indep_enc_posttrigger(pt);

    out[0] = ct[0]; out[1] = ct[1]; out[2] = ct[2]; out[3] = ct[3];
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

    rk_reset();

    simpleserial_init();
    simpleserial_addcmd('d', 0, set_default);
    simpleserial_addcmd('k', 8, set_key);
    simpleserial_addcmd('p', 4, enc);
    while (1)
        simpleserial_get();
}
