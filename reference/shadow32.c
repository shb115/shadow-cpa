#include <stdint.h>

static inline uint8_t ROL8(uint8_t val, int rot) {
    return ((val << rot) | (val >> (8 - rot))) & 0xFF;
}

static const uint8_t SHADOW32_PERM[64] = {
    56, 57, 58, 59, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27,
    60, 61, 62, 63, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
    40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15
};

void shadow32_round(uint8_t* l0, uint8_t* l1, uint8_t* r0, uint8_t* r1, uint8_t k0, uint8_t k1, uint8_t k2, uint8_t k3)
{
    uint8_t s0, s1;

    s0 = (ROL8(*l0, 1) & ROL8(*l0, 7)) ^ ROL8(*l0, 2) ^ *l1 ^ k0;
    s1 = (ROL8(*r0, 1) & ROL8(*r0, 7)) ^ ROL8(*r0, 2) ^ *r1 ^ k1;

    *l1 = (ROL8(s0, 1) & ROL8(s0, 7)) ^ ROL8(s0, 2) ^ *l0 ^ k2;
    *r1 = (ROL8(s1, 1) & ROL8(s1, 7)) ^ ROL8(s1, 2) ^ *r0 ^ k3;

    *l0 = s1;
    *r0 = s0;
}

void shadow32_inv_round(uint8_t* l0, uint8_t* l1, uint8_t* r0, uint8_t* r1, uint8_t k0, uint8_t k1, uint8_t k2, uint8_t k3)
{
    uint8_t s0, s1, x0, x2;

    s1 = *l0;
    s0 = *r0;

    x0 = (ROL8(s0, 1) & ROL8(s0, 7)) ^ ROL8(s0, 2) ^ *l1 ^ k2;
    x2 = (ROL8(s1, 1) & ROL8(s1, 7)) ^ ROL8(s1, 2) ^ *r1 ^ k3;

    *l1 = (ROL8(x0, 1) & ROL8(x0, 7)) ^ ROL8(x0, 2) ^ s0 ^ k0;
    *r1 = (ROL8(x2, 1) & ROL8(x2, 7)) ^ ROL8(x2, 2) ^ s1 ^ k1;

    *l0 = x0;
    *r0 = x2;
}

void shadow32_encrypt(const uint8_t pt[4], const uint8_t rk[64], uint8_t ct[4])
{
    uint8_t l0 = pt[0], l1 = pt[1], r0 = pt[2], r1 = pt[3];
    int i;

    for (i = 0; i < 16; i++)
        shadow32_round(&l0, &l1, &r0, &r1, rk[4 * i], rk[4 * i + 1], rk[4 * i + 2], rk[4 * i + 3]);

    ct[0] = r0;
    ct[1] = l1;
    ct[2] = l0;
    ct[3] = r1;
}

void shadow32_decrypt(const uint8_t ct[4], const uint8_t rk[64], uint8_t pt[4])
{
    uint8_t l0 = ct[2], l1 = ct[1], r0 = ct[0], r1 = ct[3];
    int i;

    for (i = 15; i >= 0; i--)
        shadow32_inv_round(&l0, &l1, &r0, &r1, rk[4 * i], rk[4 * i + 1], rk[4 * i + 2], rk[4 * i + 3]);

    pt[0] = l0;
    pt[1] = l1;
    pt[2] = r0;
    pt[3] = r1;
}

static uint8_t pack8(const uint8_t* b, const int* idx)
{
    uint8_t v = 0;
    int i;

    for (i = 0; i < 8; i++)
        v = (v << 1) | (b[idx[i]] & 1);

    return v;
}

void shadow32_key_schedule(const uint8_t master[8], uint8_t rk[64])
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
