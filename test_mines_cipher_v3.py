"""
mines_cipher_v3 검증 테스트.

빠른 구현(128비트 정수 비트 연산)을 칸 하나씩 계산하는 단순한 기준 구현과
비교해서, 두 구현이 비트 단위로 같은 결과를 내는지 확인한다.

실행: python -m unittest test_mines_cipher_v3 -v
"""

import hashlib
import os
import random
import unittest

import mines_cipher_v3 as mc
from mines_cipher_v3 import MinesCipherV3

H, W = 8, 16
RULE = {0, 3, 4, 8}
NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
COLORS = [[(i, j) for i in range(H) for j in range(W) if (i % 2, j % 2) == c]
          for c in [(0, 0), (0, 1), (1, 0), (1, 1)]]


# ---------------- 기준 구현 (칸 단위, 설명서 정의 그대로) ----------------

def ref_grid(b: bytes):
    return [[(b[(i * W + j) // 8] >> (7 - (i * W + j) % 8)) & 1 for j in range(W)] for i in range(H)]


def ref_bytes(g) -> bytes:
    out = bytearray(16)
    for i in range(H):
        for j in range(W):
            if g[i][j]:
                k = i * W + j
                out[k // 8] |= 1 << (7 - k % 8)
    return bytes(out)


def ref_count(g, i, j):
    return sum(g[(i + a) % H][(j + b) % W] for a, b in NB)


def ref_mine_sub(g, inv=False):
    for c in (range(3, -1, -1) if inv else range(4)):
        flips = [(i, j) for i, j in COLORS[c] if ref_count(g, i, j) in RULE]
        for i, j in flips:
            g[i][j] ^= 1


def ref_perm_pos(i, j):
    j2 = (j + 3 * i + 1) % W
    return (i + j2) % H, j2


def ref_mine_perm(g):
    out = [[0] * W for _ in range(H)]
    for i in range(H):
        for j in range(W):
            a, b = ref_perm_pos(i, j)
            out[a][b] = g[i][j]
    return out


def ref_evolve(b: bytes, subs=2) -> bytes:
    g = ref_grid(b)
    for _ in range(subs):
        ref_mine_sub(g)
    return ref_bytes(ref_mine_perm(g))


def xor(a, b):
    return bytes(p ^ q for p, q in zip(a, b))


def ref_round_keys(key: bytes):
    b = hashlib.sha256(key).digest()[:16]
    keys = [b]
    for r in range(1, 17):
        for _ in range(2):
            b = ref_evolve(b)
        b = xor(b, hashlib.sha256(b"MineLock_RC" + bytes([r])).digest()[:16])
        keys.append(b)
    return keys


def ref_encrypt_block(p: bytes, keys) -> bytes:
    s = p
    for r in range(16):
        s = ref_evolve(xor(s, keys[r]))
    return xor(s, keys[16])


# ---------------- 테스트 ----------------

class TestAgainstReference(unittest.TestCase):
    def setUp(self):
        random.seed(2026)

    def test_neighbor_count(self):
        for _ in range(50):
            b = os.urandom(16)
            x, g = mc.to_int(b), ref_grid(b)
            planes = mc.neighbor_count_planes(x)
            for i in range(H):
                for j in range(W):
                    fast = sum(mc.get_cell(p, i, j) << k for k, p in enumerate(planes))
                    self.assertEqual(fast, ref_count(g, i, j))

    def test_mine_sub_matches_reference(self):
        for _ in range(300):
            b = os.urandom(16)
            g = ref_grid(b)
            ref_mine_sub(g)
            self.assertEqual(mc.to_bytes(mc.mine_sub(mc.to_int(b))), ref_bytes(g))

    def test_mine_perm_matches_reference(self):
        for _ in range(300):
            b = os.urandom(16)
            self.assertEqual(mc.to_bytes(mc.mine_perm(mc.to_int(b))), ref_bytes(ref_mine_perm(ref_grid(b))))
        for i in range(H):
            for j in range(W):
                self.assertEqual(mc.perm_position(i, j), ref_perm_pos(i, j))

    def test_inverses(self):
        for _ in range(300):
            x = mc.to_int(os.urandom(16))
            self.assertEqual(mc.mine_sub_inv(mc.mine_sub(x)), x)
            self.assertEqual(mc.mine_perm_inv(mc.mine_perm(x)), x)
            self.assertEqual(MinesCipherV3.evolve_inv(MinesCipherV3.evolve(x)), x)

    def test_key_schedule_matches_reference(self):
        for key in (b"YSKL", b"", os.urandom(20)):
            c = MinesCipherV3(key)
            self.assertEqual([mc.to_bytes(k) for k in c.round_keys], ref_round_keys(key))

    def test_encrypt_block_matches_reference(self):
        for _ in range(20):
            key, p = os.urandom(16), os.urandom(16)
            c = MinesCipherV3(key)
            self.assertEqual(c.encrypt_block(p), ref_encrypt_block(p, ref_round_keys(key)))


class TestCipher(unittest.TestCase):
    def test_block_roundtrip(self):
        for _ in range(200):
            c = MinesCipherV3(os.urandom(random.randint(0, 40)))
            p = os.urandom(16)
            self.assertEqual(c.decrypt_block(c.encrypt_block(p)), p)

    def test_cbc_roundtrip(self):
        c = MinesCipherV3(b"YSKL")
        for n in (0, 1, 15, 16, 17, 100):
            data = os.urandom(n)
            self.assertEqual(c.decrypt(c.encrypt(data)), data)

    def test_bad_padding_rejected(self):
        c = MinesCipherV3(b"YSKL")
        ct = bytearray(c.encrypt(b"HELLO", iv=bytes(16)))
        ct[-1] ^= 1
        with self.assertRaises(ValueError):
            c.decrypt(bytes(ct))

    def test_hello_known_answer(self):
        # 설명서 5장 예시 값 (비밀키 YSKL, IV = 00 01 … 0F)
        c = MinesCipherV3(b"YSKL")
        iv = bytes(range(16))
        ct = c.encrypt(b"HELLO", iv=iv)
        self.assertEqual(ct[:16], iv)
        self.assertEqual(ct[16:], ref_encrypt_block(xor(b"HELLO" + bytes([11]) * 11, iv), ref_round_keys(b"YSKL")))
        self.assertEqual(c.decrypt(ct), b"HELLO")


if __name__ == "__main__":
    unittest.main()
