/*
 * selftest.c
 * ------------------------------------------------------------------
 * Checks the reference implementations against the values reported in
 * the paper, so that they can be verified without the capture hardware.
 *
 *   gcc -O2 -o selftest selftest.c shadow32.c shadow64.c
 *   ./selftest
 *
 * It reproduces
 *   - the Shadow-32 round keys of the fixed-key trace set,
 *   - the Shadow-32 round keys of the first of the ten random key sets,
 *   - the Shadow-64 first round key of the deposited trace set,
 * and runs an encrypt/decrypt round trip for both ciphers.
 * ------------------------------------------------------------------
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

void shadow32_key_schedule(const uint8_t master[8], uint8_t rk[64]);
void shadow32_encrypt(const uint8_t pt[4], const uint8_t rk[64], uint8_t ct[4]);
void shadow32_decrypt(const uint8_t ct[4], const uint8_t rk[64], uint8_t pt[4]);

void shadow64_key_schedule(const uint8_t master[16], uint16_t rk[128]);
void shadow64_encrypt(const uint16_t pt[4], const uint16_t rk[128], uint16_t ct[4]);
void shadow64_decrypt(const uint16_t ct[4], const uint16_t rk[128], uint16_t pt[4]);

static int fails = 0;

static void report(const char *what, int ok)
{
    printf("  %-46s %s\n", what, ok ? "PASS" : "FAIL");
    if (!ok) fails++;
}

/* Shadow-32 : master key -> RK1..RK4 (the first sixteen round-key bytes). */
static void check32(const char *label, const uint8_t master[8], const uint8_t want[16])
{
    uint8_t rk[64];
    int i;

    shadow32_key_schedule(master, rk);

    printf("\n%s\n", label);
    printf("  master   ");
    for (i = 0; i < 8; i++) printf("%02X", master[i]);
    printf("\n  RK1..RK4 ");
    for (i = 0; i < 16; i++) printf("%02X%s", rk[i], (i % 4 == 3 && i != 15) ? " / " : " ");
    printf("\n");
    report("RK1..RK4 match the reported values", memcmp(rk, want, 16) == 0);
}

int main(void)
{
    /* Fixed-key trace set: data/shadow32_fixedkey/s32_ref_12500.npz.
       The firmware carries the round keys as a table, and this master key
       regenerates them. */
    static const uint8_t m32_fixed[8]  = {0xDC,0x4A,0x3D,0xB3,0x03,0x5C,0x95,0x0E};
    static const uint8_t rk32_fixed[16] = {
        0x0D,0x3B,0x60,0x33, 0x43,0x60,0x25,0x3C,
        0x13,0x25,0x89,0xC5, 0x3C,0x89,0x0D,0x5D};

    /* First of the ten random key sets: data/shadow32_10keys/s32_key01_12500.npz. */
    static const uint8_t m32_key01[8]  = {0xE1,0x00,0x20,0xBD,0x4E,0x59,0x0E,0x12};
    static const uint8_t rk32_key01[16] = {
        0x10,0x2B,0x04,0xDE, 0x0D,0x04,0x05,0xE9,
        0x0E,0x05,0x20,0x9E, 0xC9,0x20,0x4E,0xE0};

    /* Shadow-64 trace set: data/shadow64/s64_ref_25000.npz. */
    static const uint8_t m64[16] = {
        0x07,0xE9,0xA4,0xB2,0x7E,0x3F,0xCB,0x47,
        0x2D,0xA7,0x57,0xEA,0x31,0xCA,0xF4,0xED};
    static const uint16_t rk64_want[4] = {0x872C,0xE3FB,0x644A,0x72D7};

    uint16_t rk64[128], pt64[4] = {0x0123,0x4567,0x89AB,0xCDEF}, ct64[4], back64[4];
    uint8_t  rk32[64],  pt32[4] = {0x01,0x23,0x45,0x67},          ct32[4], back32[4];
    int i;

    printf("Shadow reference implementation self-test\n");
    printf("=========================================\n");

    check32("Shadow-32, fixed-key trace set", m32_fixed, rk32_fixed);
    check32("Shadow-32, random key set 01",   m32_key01, rk32_key01);

    shadow64_key_schedule(m64, rk64);
    printf("\nShadow-64 trace set\n  master   ");
    for (i = 0; i < 16; i++) printf("%02X", m64[i]);
    printf("\n  RK1      ");
    for (i = 0; i < 4; i++) printf("%04X ", rk64[i]);
    printf("\n");
    report("RK1 matches the reported value",
           memcmp(rk64, rk64_want, sizeof rk64_want) == 0);

    printf("\nRound trip\n");
    shadow32_key_schedule(m32_fixed, rk32);
    shadow32_encrypt(pt32, rk32, ct32);
    shadow32_decrypt(ct32, rk32, back32);
    printf("  Shadow-32  pt ");
    for (i = 0; i < 4; i++) printf("%02X", pt32[i]);
    printf("  ->  ct ");
    for (i = 0; i < 4; i++) printf("%02X", ct32[i]);
    printf("\n");
    report("Shadow-32 decrypt(encrypt(pt)) == pt", memcmp(pt32, back32, 4) == 0);

    shadow64_encrypt(pt64, rk64, ct64);
    shadow64_decrypt(ct64, rk64, back64);
    printf("  Shadow-64  pt ");
    for (i = 0; i < 4; i++) printf("%04X", pt64[i]);
    printf("  ->  ct ");
    for (i = 0; i < 4; i++) printf("%04X", ct64[i]);
    printf("\n");
    report("Shadow-64 decrypt(encrypt(pt)) == pt",
           memcmp(pt64, back64, sizeof pt64) == 0);

    printf("\n%s\n", fails ? "SELF-TEST FAILED" : "All checks passed.");
    return fails ? 1 : 0;
}
