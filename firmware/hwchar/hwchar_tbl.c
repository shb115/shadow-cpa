/*
 * Fig. 1 measurement firmware, table-lookup version (2026-10-04): the power at the moment r0
 * changes from 0 to v, measured by three methods.
 *
 *   'p', 16 bytes: pt[0] = index (or value), pt[1] = method. The response 'r' returns the input unchanged.
 *     method 0 (reference)      : ldrb r0, [p]            reads v from a fixed address (pt[0] = v)
 *     method 1 (identity table) : ldrb r0, [T_id, r2]     T_id[i] = i, index = v, so the low byte of the address is v as well
 *     method 2 (permuted table) : ldrb r0, [T_perm, r2]   T_perm[i] = sigma(i), index = sigma^-1(v), so the address is independent of HW(v)
 *   All three read the value v, with the same instruction sequence and the same timing:
 *
 *   trigger_high
 *     r0 = r1 = r2 = 0;  r1 = the table address (unused by method 0)
 *     NOP x 100
 *     ldrb r2, [p]          ; r2 : 0 -> index   (100 cycles before the measured instruction)
 *     NOP x 100
 *     <measured instruction> ; r0 : 0 -> v
 *     NOP x 100
 *     r0 = r1 = r2 = 0
 *     NOP x 20
 *   trigger_low
 *
 * The tables are in RAM, aligned to a 256-byte boundary so that the low byte of the address
 * equals the index. NOP = 0xBF00. Built at -O0.
 */
#include "hal.h"
#include "simpleserial.h"
#include <stdint.h>
#include "tbl_perm.h"

#define NOPS(n) ".rept " #n "\n\t.inst.n 0xbf00\n\t.endr\n\t"

static uint8_t T_id[256] __attribute__((aligned(256)));

#define EVENT(SLOT2)                                                        \
    __asm__ __volatile__(                                                   \
        ".syntax unified\n\t"                                               \
        "movs r0, #0\n\t"                                                   \
        "movs r1, #0\n\t"                                                   \
        "movs r2, #0\n\t"                                                   \
        "mov r1, %[t]\n\t"                                                  \
        NOPS(100)                                                           \
        "ldrb r2, [%[p], #0]\n\t"                                           \
        NOPS(100)                                                           \
        SLOT2                                                               \
        NOPS(100)                                                           \
        "movs r0, #0\n\t"                                                   \
        "movs r1, #0\n\t"                                                   \
        "movs r2, #0\n\t"                                                   \
        NOPS(20)                                                            \
        ".syntax divided\n\t"                                               \
        : : [p]"l"(p), [t]"l"(t) : "r0", "r1", "r2", "cc", "memory")

static void ev_fixed(const uint8_t *p, const uint8_t *t) { EVENT("ldrb r0, [%[p], #0]\n\t"); }
static void ev_table(const uint8_t *p, const uint8_t *t) { EVENT("ldrb r0, [r1, r2]\n\t"); }

/* Method 3: unrelated operations immediately before the identity-table lookup (load, EOR, ADD,
 * AND, shift and store on the random bytes pt[2..5] supplied by the host), so that the measured
 * instruction is not surrounded by NOPs only and, as in real code, unrelated data passes the bus
 * and the ALU just before it. 81 NOPs + about 15 cycles of these operations + 4 NOPs put it at
 * almost the same position as the 100 NOPs of method 1. r0 still changes from 0 to v. */
static void ev_table_pre(const uint8_t *p, const uint8_t *t)
{
    __asm__ __volatile__(
        ".syntax unified\n\t"
        "movs r0, #0\n\t"
        "movs r1, #0\n\t"
        "movs r2, #0\n\t"
        "mov r1, %[t]\n\t"
        NOPS(100)
        "ldrb r2, [%[p], #0]\n\t"
        NOPS(81)
        "ldrb r5, [%[p], #2]\n\t"
        "ldrb r6, [%[p], #3]\n\t"
        "eors r5, r6\n\t"
        "adds r6, r5, r6\n\t"
        "ands r6, r5\n\t"
        "lsls r5, r5, #3\n\t"
        "strb r6, [%[p], #8]\n\t"
        "ldrb r5, [%[p], #4]\n\t"
        "eors r5, r6\n\t"
        "ldrb r6, [%[p], #5]\n\t"
        NOPS(4)
        "ldrb r0, [r1, r2]\n\t"
        NOPS(100)
        "movs r0, #0\n\t"
        "movs r1, #0\n\t"
        "movs r2, #0\n\t"
        "movs r5, #0\n\t"
        "movs r6, #0\n\t"
        NOPS(20)
        ".syntax divided\n\t"
        : : [p]"l"(p), [t]"l"(t) : "r0", "r1", "r2", "r5", "r6", "cc", "memory");
}

uint8_t get_pt(uint8_t *pt, uint8_t len)
{
    uint8_t mode = pt[1];
    const uint8_t *t = (mode == 2) ? T_perm : T_id;
    if (mode == 0) {
        trigger_high(); ev_fixed(pt, t); trigger_low();
    } else if (mode == 3) {
        trigger_high(); ev_table_pre(pt, T_id); trigger_low();
    } else {
        trigger_high(); ev_table(pt, t); trigger_low();
    }
    simpleserial_put('r', 16, pt);
    return 0x00;
}

int main(void)
{
    int i;
    for (i = 0; i < 256; i++) T_id[i] = (uint8_t)i;
    platform_init();
    init_uart();
    trigger_setup();
    simpleserial_init();
    simpleserial_addcmd('p', 16, get_pt);
    while (1)
        simpleserial_get();
}
