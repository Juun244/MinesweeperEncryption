"""
설명서 6장(검증 결과)에 들어갈 수치를 mines_cipher_v3로 측정한다.

실행: python tools/measure_v3.py <출력.json>
"""

import json
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import mines_cipher_v3 as mc  # noqa: E402
from mines_cipher_v3 import MinesCipherV3  # noqa: E402

random.seed(2026)


def enc_rounds(c, x, R):
    """R라운드만 수행 (마지막 키 혼합 포함)."""
    for r in range(R):
        x = c.evolve(x ^ c.round_keys[r])
    return x ^ c.round_keys[R]


def popcount(x):
    return bin(x).count("1")


def main(out_path):
    M = {}
    # 1. 가역성
    fails = 0
    for _ in range(1000):
        c = MinesCipherV3(os.urandom(random.randint(1, 32)))
        p = os.urandom(16)
        fails += c.decrypt_block(c.encrypt_block(p)) != p
    M["invert_fail"] = fails

    # 2. 라운드 수별 확산 (키 20개 × 비트 128개)
    aval = {}
    for R in (1, 2, 3, 4, 5, 6, 8, 16):
        tot = []
        for _ in range(20):
            c = MinesCipherV3(os.urandom(16))
            p = mc.to_int(os.urandom(16))
            base = enc_rounds(c, p, R)
            tot += [popcount(base ^ enc_rounds(c, p ^ (1 << k), R)) for k in range(128)]
        aval[R] = {"avg": sum(tot) / len(tot) / 1.28, "min": min(tot) / 1.28, "max": max(tot) / 1.28}
    M["avalanche"] = aval

    # 3. 키 민감도: 초기 지뢰판 B(0) 1비트 변경 → 암호문 (20개 × 128비트)
    tot = []
    for _ in range(20):
        b0 = mc.to_int(os.urandom(16))
        c1 = MinesCipherV3(b"x")
        c1.round_keys = c1._key_schedule(b0)
        p = os.urandom(16)
        ct = c1.encrypt_block(p)
        for k in range(128):
            c2 = MinesCipherV3(b"x")
            c2.round_keys = c2._key_schedule(b0 ^ (1 << k))
            tot.append(mc.hamming_distance(ct, c2.encrypt_block(p)))
    M["keysens"] = {"avg": sum(tot) / len(tot) / 1.28, "min": min(tot) / 1.28, "n": len(tot)}

    # 4. 라운드 키 확산: B(0) 1비트 변경 → K1 … K4
    rk = [[] for _ in range(5)]
    for _ in range(25):
        b0 = mc.to_int(os.urandom(16))
        c = MinesCipherV3(b"x")
        a = c._key_schedule(b0)
        for k in range(128):
            b = c._key_schedule(b0 ^ (1 << k))
            for r in range(1, 5):
                rk[r].append(popcount(a[r] ^ b[r]))
    M["rk_diff"] = [{"avg": sum(v) / len(v) / 1.28, "min": min(v) / 1.28} for v in rk[1:]]

    # 5. MineSub 1회 선형 일치율 (출력 비트 = 같은 칸 입력 비트)
    N = 5000
    agree = [0] * 128
    for _ in range(N):
        x = mc.to_int(os.urandom(16))
        same = ~(x ^ mc.mine_sub(x)) & mc.M128
        for k in range(128):
            agree[k] += (same >> k) & 1
    a = [v / N * 100 for v in agree]
    M["lin_agree"] = {"min": min(a), "max": max(a)}

    # 6. 1비트 차분 유지 확률 (1라운드 = MineSub×2 → MinePerm)
    N = 200000
    hit = 0
    for _ in range(N):
        x = mc.to_int(os.urandom(16))
        d = 1 << random.randrange(128)
        hit += popcount(MinesCipherV3.evolve(x) ^ MinesCipherV3.evolve(x ^ d)) == 1
    M["trail1"] = {"hits": hit, "n": N, "log2": math.log2(hit / N)}

    # 7. 속도
    t = time.perf_counter()
    for _ in range(200):
        MinesCipherV3(b"speed-test")
    M["ks_ms"] = (time.perf_counter() - t) / 200 * 1000
    c = MinesCipherV3(b"speed-test")
    blocks = [os.urandom(16) for _ in range(3000)]
    t = time.perf_counter()
    for b in blocks:
        c.encrypt_block(b)
    M["block_ms"] = (time.perf_counter() - t) / len(blocks) * 1000

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(M, f, ensure_ascii=False, indent=1)
    print(json.dumps(M, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "measure_v3.json")
