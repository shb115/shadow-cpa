#include <stdint.h>

static inline uint16_t ROL16(uint16_t val, int rot) {
    return ((val << rot) | (val >> (16 - rot))) & 0xFFFF;
}

static const uint8_t SHADOW64_PERM[128] = {
    104, 105, 106, 107,  32,  33,  34,  35,  36,  37,  38,  39,  40,  41,  42,  43,
    108, 109, 110, 111,  44,  45,  46,  47,  48,  49,  50,  51,  52,  53,  54,  55,
    112, 113, 114, 115,  56,  57,  58,  59,  60,  61,  62,  63,  64,  65,  66,  67,
    116, 117, 118, 119,  68,  69,  70,  71,  72,  73,  74,  75,  76,  77,  78,  79,
    120, 121, 122, 123,  80,  81,  82,  83,  84,  85,  86,  87,  88,  89,  90,  91,
    124, 125, 126, 127,  92,  93,  94,  95,  96,  97,  98,  99, 100, 101, 102, 103,
      0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
     16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,  28,  29,  30,  31
};

void shadow64_round(uint16_t* l0, uint16_t* l1, uint16_t* r0, uint16_t* r1, uint16_t k0, uint16_t k1, uint16_t k2, uint16_t k3)
{
    uint16_t s0, s1;

    s0 = (ROL16(*l0, 1) & ROL16(*l0, 7)) ^ ROL16(*l0, 2) ^ *l1 ^ k0;
    s1 = (ROL16(*r0, 1) & ROL16(*r0, 7)) ^ ROL16(*r0, 2) ^ *r1 ^ k1;

    *l1 = (ROL16(s0, 1) & ROL16(s0, 7)) ^ ROL16(s0, 2) ^ *l0 ^ k2;
    *r1 = (ROL16(s1, 1) & ROL16(s1, 7)) ^ ROL16(s1, 2) ^ *r0 ^ k3;

    *l0 = s1;
    *r0 = s0;
}

void shadow64_inv_round(uint16_t* l0, uint16_t* l1, uint16_t* r0, uint16_t* r1, uint16_t k0, uint16_t k1, uint16_t k2, uint16_t k3)
{
    uint16_t s0, s1, x0, x2;

    s1 = *l0;
    s0 = *r0;

    x0 = (ROL16(s0, 1) & ROL16(s0, 7)) ^ ROL16(s0, 2) ^ *l1 ^ k2;
    x2 = (ROL16(s1, 1) & ROL16(s1, 7)) ^ ROL16(s1, 2) ^ *r1 ^ k3;

    *l1 = (ROL16(x0, 1) & ROL16(x0, 7)) ^ ROL16(x0, 2) ^ s0 ^ k0;
    *r1 = (ROL16(x2, 1) & ROL16(x2, 7)) ^ ROL16(x2, 2) ^ s1 ^ k1;

    *l0 = x0;
    *r0 = x2;
}

void shadow64_encrypt(const uint16_t pt[4], const uint16_t rk[128], uint16_t ct[4])
{
    uint16_t l0 = pt[0], l1 = pt[1], r0 = pt[2], r1 = pt[3];
    int i;

    for (i = 0; i < 32; i++)
        shadow64_round(&l0, &l1, &r0, &r1, rk[4 * i], rk[4 * i + 1], rk[4 * i + 2], rk[4 * i + 3]);

    ct[0] = r0;
    ct[1] = l1;
    ct[2] = l0;
    ct[3] = r1;
}

void shadow64_decrypt(const uint16_t ct[4], const uint16_t rk[128], uint16_t pt[4])
{
    uint16_t l0 = ct[2], l1 = ct[1], r0 = ct[0], r1 = ct[3];
    int i;

    for (i = 31; i >= 0; i--)
        shadow64_inv_round(&l0, &l1, &r0, &r1, rk[4 * i], rk[4 * i + 1], rk[4 * i + 2], rk[4 * i + 3]);

    pt[0] = l0;
    pt[1] = l1;
    pt[2] = r0;
    pt[3] = r1;
}

static void nx64(uint8_t* b)
{
    uint8_t nb[24], t;
    int p, q;

    for (p = 104; p <= 126; p += 2) {
        t = b[126];
        for (q = 104; q <= p - 2; q += 2)
            t ^= b[q];
        nb[p - 104] = b[p] & (b[p] ^ t);
    }
    for (p = 105; p <= 127; p += 2) {
        t = b[127];
        for (q = 105; q <= p - 2; q += 2)
            t ^= b[q];
        nb[p - 104] = b[p] & (b[p] ^ t);
    }
    for (p = 104; p < 128; p++)
        b[p] = nb[p - 104];
}

static uint16_t pack16(const uint8_t* b, const int* idx)
{
    uint16_t v = 0;
    int i;

    for (i = 0; i < 16; i++)
        v = (v << 1) | (b[idx[i]] & 1);

    return v;
}

void shadow64_key_schedule(const uint8_t master[16], uint16_t rk[128])
{
    static const int K0[16] = {  0,  1,  2,  3,  4,  5,  6,  7, 16, 17, 18, 19, 24, 25, 26, 27 };
    static const int K1[16] = {  8,  9, 10, 11, 12, 13, 14, 15, 20, 21, 22, 23, 28, 29, 30, 31 };
    static const int K2[16] = { 32, 33, 34, 35, 36, 37, 38, 39, 48, 49, 50, 51, 56, 57, 58, 59 };
    static const int K3[16] = { 40, 41, 42, 43, 44, 45, 46, 47, 52, 53, 54, 55, 60, 61, 62, 63 };

    uint8_t b[128], nb[128], rc;
    int i, r;

    for (i = 0; i < 128; i++)
        b[i] = (master[i >> 3] >> (7 - (i & 7))) & 1;

    for (r = 0; r < 32; r++) {
        rc = r + 1;
        b[2] ^= (rc >> 5) & 1;
        b[3] ^= (rc >> 4) & 1;
        b[4] ^= (rc >> 3) & 1;
        b[5] ^= (rc >> 2) & 1;
        b[6] ^= (rc >> 1) & 1;
        b[7] ^= rc & 1;

        nx64(b);

        for (i = 0; i < 128; i++)
            nb[i] = b[SHADOW64_PERM[i]];
        for (i = 0; i < 128; i++)
            b[i] = nb[i];

        rk[4 * r]     = pack16(b, K0);
        rk[4 * r + 1] = pack16(b, K1);
        rk[4 * r + 2] = pack16(b, K2);
        rk[4 * r + 3] = pack16(b, K3);
    }
}
