M16 = 0xFFFF

SHADOW64_PERM = [
    104,105,106,107, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43,
    108,109,110,111, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
    112,113,114,115, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67,
    116,117,118,119, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79,
    120,121,122,123, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91,
    124,125,126,127, 92, 93, 94, 95, 96, 97, 98, 99,100,101,102,103,
      0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
     16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
]

K0 = [ 0, 1, 2, 3, 4, 5, 6, 7, 16, 17, 18, 19, 24, 25, 26, 27]
K1 = [ 8, 9,10,11,12,13,14,15, 20, 21, 22, 23, 28, 29, 30, 31]
K2 = [32,33,34,35,36,37,38,39, 48, 49, 50, 51, 56, 57, 58, 59]
K3 = [40,41,42,43,44,45,46,47, 52, 53, 54, 55, 60, 61, 62, 63]

def nx64(b):
    nb = [0] * 24
    for p in range(104, 127, 2):
        t = b[126]
        for q in range(104, p - 1, 2):
            t ^= b[q]
        nb[p - 104] = b[p] & (b[p] ^ t)
    for p in range(105, 128, 2):
        t = b[127]
        for q in range(105, p - 1, 2):
            t ^= b[q]
        nb[p - 104] = b[p] & (b[p] ^ t)
    for p in range(104, 128):
        b[p] = nb[p - 104]

def pack16(b, idx):
    v = 0
    for i in range(16):
        v = (v << 1) | (b[idx[i]] & 1)
    return v

def ks64(master16):
    b = [(master16[i >> 3] >> (7 - (i & 7))) & 1 for i in range(128)]
    rk = []
    for r in range(32):
        rc = r + 1
        b[2] ^= (rc >> 5) & 1
        b[3] ^= (rc >> 4) & 1
        b[4] ^= (rc >> 3) & 1
        b[5] ^= (rc >> 2) & 1
        b[6] ^= (rc >> 1) & 1
        b[7] ^= rc & 1
        nx64(b)
        b = [b[SHADOW64_PERM[i]] for i in range(128)]
        rk += [pack16(b, K0), pack16(b, K1), pack16(b, K2), pack16(b, K3)]
    return rk

def ROL16(v, r): return ((v << r) | (v >> (16 - r))) & M16
def F16(x):      return (ROL16(x, 1) & ROL16(x, 7)) ^ ROL16(x, 2)

def enc64(pt4, rk):
    l0, l1, r0, r1 = pt4
    for i in range(32):
        k0, k1, k2, k3 = rk[4*i:4*i+4]
        s0 = F16(l0) ^ l1 ^ k0
        s1 = F16(r0) ^ r1 ^ k1
        l1 = F16(s0) ^ l0 ^ k2
        r1 = F16(s1) ^ r0 ^ k3
        l0, r0 = s1, s0
    return [r0, l1, l0, r1]

# 아래 표는 레퍼런스 마스터키 000102..0F 의 라운드키다. 이 파일의 자체검증은
# 키 스케줄 구현이 맞는지만 확인한다. 공개한 Shadow-64 파형은 다른 마스터키
# 07E9A4B27E3FCB472DA757EA31CAF4ED 로 수집했으므로, 그 쪽과의 대조는
# data/shadow64/s64_ref_25000.npz 의 rk 필드로 하면 된다.
RK_REF = [
0x0010,0x4056,0x0080,0x7089,0x0008,0x0708,0x000A,0x9000,
0x4000,0x0900,0x0A4B,0x00C0,0x0064,0xA00C,0x0B0C,0x0030,
0x0090,0xB003,0x0C01,0x0040,0x8000,0xC004,0x6102,0x0080,
0x2600,0x1008,0x1203,0x0004,0xC100,0x2000,0x0304,0x4040,
0x1000,0x3404,0x0405,0x0020,0x2000,0x4002,0x0506,0x0008,
0x3000,0x5000,0x0607,0x8082,0x4000,0x6808,0x070E,0x200C,
0x4000,0x7200,0x0E08,0xC041,0x6000,0xEC04,0x080A,0x1002,
0x6000,0x8100,0x0A0B,0x2003,0xC080,0xA200,0x0B0C,0x3084,
0x8010,0xB308,0x0C0D,0x4004,0x8020,0xC400,0x0D0E,0x4046,
0x9020,0xD404,0x1E0F,0x6007,0xC100,0xE600,0x0F00,0x700D,
0xC040,0xF700,0x0001,0xD009,0xC020,0x0D00,0x0102,0x9009,
0xC060,0x1900,0x4203,0x9008,0x04C0,0x2900,0x0304,0x800D,
0x1080,0x3800,0x4404,0xD00D,0x2410,0x4D00,0x8406,0xD00D,
0x3800,0x4D00,0x8607,0xD00D,0x4890,0x6D00,0x0708,0xD001,
0x4090,0x7D00,0x080D,0x1000,0x6010,0x8100,0x8D0A,0x0003,
0x6840,0xD000,0x9A0F,0x3002,0x8910,0xA300,0x0F04,0x2005]

if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    ref_master = list(range(16))
    rk = ks64(ref_master)
    same = sum(a == b for a, b in zip(rk, RK_REF))
    print("레퍼런스 마스터키 %s" % " ".join("%02X" % x for x in ref_master))
    print("키스케줄 출력 rk[0..3] = %s" % " ".join("%04X" % x for x in rk[:4]))
    print("RK_REF 표     rk[0..3] = %s" % " ".join("%04X" % x for x in RK_REF[:4]))
    print("128 워드 중 일치 : %d/128  -> %s" % (same, "검증 PASS" if same == 128 else "불일치!"))
    if same != 128:
        bad = [i for i in range(128) if rk[i] != RK_REF[i]][:8]
        for i in bad:
            print("   rk[%3d] 계산 %04X vs baked %04X" % (i, rk[i], RK_REF[i]))
