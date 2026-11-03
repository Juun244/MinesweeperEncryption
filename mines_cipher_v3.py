"""
MinesCipher v3 — MineLock (지뢰판 SPN)

128비트 블록을 8×16 지뢰판으로 보고, 지뢰찾기 규칙(주변 지뢰 수)으로
치환(MineSub)하고 행·열 회전으로 전치(MinePerm)하는 SPN 블록 암호.

- 블록: 128비트 (16바이트) = 8행 × 16열 지뢰판 (1 = 지뢰, 0 = 빈칸)
- 키:   임의 길이 → SHA-256 앞 128비트 = 초기 지뢰판 B(0)
- 라운드: 16 × (⊕ K(r) → MineSub → MineSub → MinePerm), 마지막에 ⊕ K(16)
- 키 스케줄: B(r) = Evolve(Evolve(B(r-1))) ⊕ RC(r),  K(r) = B(r)
             Evolve = MinePerm ∘ MineSub ∘ MineSub  (키 없는 라운드와 같음)
- 운용 모드: CBC + PKCS#7 패딩

구현 메모: 지뢰판 전체를 128비트 정수 하나로 다룬다(비트 슬라이싱).
행 i는 상위부터 16비트씩, 열 j는 그 16비트의 상위 비트부터 차지한다.
즉 (행 i, 열 j) 칸 = 정수의 비트 (127 - 16*i - j).
판의 위아래·좌우는 이어져 있다(토러스): 모든 칸의 이웃이 정확히 8개.
"""

import hashlib
import os
import sys
import time

# Windows 터미널 UTF-8
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass


# ================================================================
# 지뢰판 상수
# ================================================================

ROWS, COLS = 8, 16
M128 = (1 << 128) - 1
LANE_LSB = int("0001" * 8, 16)   # 각 행의 맨 오른쪽 열(열 15)
LANE_MSB = int("8000" * 8, 16)   # 각 행의 맨 왼쪽 열(열 0)

# 4색 분할: (행 홀짝, 열 홀짝). 같은 색 칸끼리는 서로 이웃이 아니다.
_ROW_EVEN = int("FFFF0000" * 4, 16)
_ROW_ODD = int("0000FFFF" * 4, 16)
_COL_EVEN = int("AAAA" * 8, 16)   # 열 0, 2, 4, ...
_COL_ODD = int("5555" * 8, 16)    # 열 1, 3, 5, ...
COLOR_MASKS = [
    _ROW_EVEN & _COL_EVEN,   # 색 0: 짝수 행 · 짝수 열
    _ROW_EVEN & _COL_ODD,    # 색 1: 짝수 행 · 홀수 열
    _ROW_ODD & _COL_EVEN,    # 색 2: 홀수 행 · 짝수 열
    _ROW_ODD & _COL_ODD,     # 색 3: 홀수 행 · 홀수 열
]

# 반전 규칙: 주변 지뢰 수 c ∈ {0, 3, 4, 8} 이면 그 칸을 뒤집는다.
# (512개 규칙 중 0/1 균형 + 최대 선형 편향 1/16)
FLIP_RULE = (0, 3, 4, 8)

# MinePerm 행 회전량: 행 i를 오른쪽으로 (3i + 1)칸
ROW_SHIFTS = [(3 * i + 1) % COLS for i in range(ROWS)]
# MinePerm 열 회전: 열 j를 아래로 (j mod 8)칸. 같은 회전량을 갖는 열 묶음 마스크
_COL_GROUP = [int(f"{(1 << (15 - s)) | (1 << (7 - s)):04X}" * 8, 16) for s in range(ROWS)]


# ================================================================
# 지뢰판 변환 도우미
# ================================================================

def _rotl(x: int, n: int) -> int:
    n %= 128
    return ((x << n) | (x >> (128 - n))) & M128


def _rotr(x: int, n: int) -> int:
    return _rotl(x, 128 - n % 128)


def _from_up(x: int) -> int:
    """각 칸 자리에 '바로 위 칸(행 i-1)'의 값을 가져온다."""
    return _rotr(x, COLS)


def _from_down(x: int) -> int:
    """각 칸 자리에 '바로 아래 칸(행 i+1)'의 값을 가져온다."""
    return _rotl(x, COLS)


def _from_left(x: int) -> int:
    """각 칸 자리에 '바로 왼쪽 칸(열 j-1)'의 값을 가져온다 (행 안에서 회전)."""
    return ((x >> 1) & ~LANE_MSB & M128) | ((x << 15) & LANE_MSB)


def _from_right(x: int) -> int:
    """각 칸 자리에 '바로 오른쪽 칸(열 j+1)'의 값을 가져온다 (행 안에서 회전)."""
    return ((x << 1) & ~LANE_LSB & M128) | ((x >> 15) & LANE_LSB)


def neighbor_count_planes(x: int):
    """
    128칸 모두의 '주변 지뢰 수'(0~8)를 한꺼번에 센다.

    결과는 4개의 비트 평면 (c0, c1, c2, c3): 각 칸의 개수를 2진수로 쓴 자릿수.
    8개 이웃 평면을 비트 단위 덧셈기(반가산기 연쇄)로 더한다.
    """
    up, down = _from_up(x), _from_down(x)
    planes = (up, down, _from_left(x), _from_right(x),
              _from_left(up), _from_right(up), _from_left(down), _from_right(down))
    c = [0, 0, 0, 0]
    for p in planes:
        carry = p
        for k in range(4):
            c[k], carry = c[k] ^ carry, c[k] & carry
    return c


def flip_mask(x: int) -> int:
    """주변 지뢰 수가 {0, 3, 4, 8} 인 칸의 마스크."""
    c0, c1, c2, c3 = neighbor_count_planes(x)
    # c ≤ 8 이므로 c3 = 1 은 곧 c = 8
    zero_or_three = ~c2 & ~(c1 ^ c0)          # 0 (000) 또는 3 (011)
    four = c2 & ~c1 & ~c0                      # 4 (100)
    return (zero_or_three | four | c3) & M128


def neighbor_count(x: int, i: int, j: int) -> int:
    """(행 i, 열 j) 칸의 주변 지뢰 수 (설명·검증용)."""
    return sum(get_cell(x, (i + di) % ROWS, (j + dj) % COLS)
               for di in (-1, 0, 1) for dj in (-1, 0, 1) if (di, dj) != (0, 0))


# ================================================================
# MineSub (치환) / MinePerm (전치)
# ================================================================

def mine_sub(x: int) -> int:
    """MineSub: 색 0 → 1 → 2 → 3 순서로, 주변 지뢰 수가 {0,3,4,8}인 칸을 뒤집는다."""
    for m in COLOR_MASKS:
        x ^= flip_mask(x) & m
    return x


def mine_sub_inv(x: int) -> int:
    """MineSub의 역: 같은 규칙을 색 3 → 2 → 1 → 0 역순으로 적용한다."""
    for m in reversed(COLOR_MASKS):
        x ^= flip_mask(x) & m
    return x


def mine_sub_steps(x: int):
    """MineSub를 색 단계별로 기록한다 (설명용). [(색, 뒤집힌 칸 마스크, 단계 후 판), ...]"""
    steps = []
    for color, m in enumerate(COLOR_MASKS):
        flips = flip_mask(x) & m
        x ^= flips
        steps.append((color, flips, x))
    return steps


def _row(x: int, i: int) -> int:
    return (x >> (112 - COLS * i)) & 0xFFFF


def _set_rows(rows) -> int:
    x = 0
    for r in rows:
        x = (x << COLS) | r
    return x


def mine_perm(x: int) -> int:
    """
    MinePerm:
      ① 행 i를 오른쪽으로 (3i + 1)칸 회전   → 새 열 j' = (j + 3i + 1) mod 16
      ② 열 j'을 아래로 j'칸 회전              → 새 행 i' = (i + j') mod 8
    """
    rows = []
    for i in range(ROWS):
        r, s = _row(x, i), ROW_SHIFTS[i]
        rows.append(((r >> s) | (r << (COLS - s))) & 0xFFFF)
    x = _set_rows(rows)
    out = 0
    for s in range(ROWS):
        out |= _rotr(x & _COL_GROUP[s], COLS * s)
    return out


def mine_perm_inv(x: int) -> int:
    """MinePerm의 역: 열을 위로 되돌린 뒤 행을 왼쪽으로 되돌린다."""
    y = 0
    for s in range(ROWS):
        y |= _rotl(x & _COL_GROUP[s], COLS * s)
    rows = []
    for i in range(ROWS):
        r, s = _row(y, i), ROW_SHIFTS[i]
        rows.append(((r << s) | (r >> (COLS - s))) & 0xFFFF)
    return _set_rows(rows)


def perm_position(i: int, j: int):
    """MinePerm에서 (행 i, 열 j) 칸이 옮겨 가는 위치."""
    j2 = (j + ROW_SHIFTS[i]) % COLS
    return (i + j2) % ROWS, j2


# ================================================================
# 판 ↔ 바이트/격자 변환 (설명·시각화용)
# ================================================================

def to_int(block: bytes) -> int:
    return int.from_bytes(block, 'big')


def to_bytes(x: int) -> bytes:
    return x.to_bytes(16, 'big')


def get_cell(x: int, i: int, j: int) -> int:
    return (x >> (127 - COLS * i - j)) & 1


def to_grid(x: int):
    return [[get_cell(x, i, j) for j in range(COLS)] for i in range(ROWS)]


def mask_cells(m: int):
    """마스크에서 1인 칸의 (행, 열) 목록."""
    return [(i, j) for i in range(ROWS) for j in range(COLS) if get_cell(m, i, j)]


def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(p ^ q for p, q in zip(a, b))


def hamming_distance(a: bytes, b: bytes) -> int:
    return sum(bin(p ^ q).count('1') for p, q in zip(a, b))


def flip_bit(data: bytes, bit_pos: int) -> bytes:
    arr = bytearray(data)
    arr[bit_pos // 8] ^= 1 << (7 - bit_pos % 8)
    return bytes(arr)


# ================================================================
# MinesCipher v3
# ================================================================

class MinesCipherV3:
    """MineLock v3 블록 암호."""

    BLOCK_SIZE = 16        # 128 bits
    NUM_ROUNDS = 16
    SUBS_PER_ROUND = 2     # 라운드마다 MineSub 횟수
    KS_STEPS = 2           # 라운드 키 사이 지뢰판 진화 횟수

    def __init__(self, key: bytes):
        self.master_seed = hashlib.sha256(key).digest()
        # 라운드 상수 RC(r) = SHA-256("MineLock_RC" ∥ r)의 앞 128비트 (r = 1 … 16)
        self.round_constants = [None] + [
            to_int(hashlib.sha256(b"MineLock_RC" + bytes([r])).digest()[:16])
            for r in range(1, self.NUM_ROUNDS + 1)
        ]
        self.round_keys = self._key_schedule(to_int(self.master_seed[:16]))

    # ────────────────────────────────────────────
    # 라운드 변환 / 키 스케줄
    # ────────────────────────────────────────────

    @classmethod
    def evolve(cls, x: int) -> int:
        """키 없는 라운드: MineSub × 2 → MinePerm."""
        for _ in range(cls.SUBS_PER_ROUND):
            x = mine_sub(x)
        return mine_perm(x)

    @classmethod
    def evolve_inv(cls, x: int) -> int:
        x = mine_perm_inv(x)
        for _ in range(cls.SUBS_PER_ROUND):
            x = mine_sub_inv(x)
        return x

    def _key_schedule(self, b0: int) -> list:
        """
        지뢰판 진화 키 스케줄:
          K(0) = B(0) = SHA-256(비밀키)의 앞 128비트
          B(r) = Evolve(Evolve(B(r-1))) ⊕ RC(r),  K(r) = B(r)   (r = 1 … 16)
        """
        keys = [b0]
        b = b0
        for r in range(1, self.NUM_ROUNDS + 1):
            for _ in range(self.KS_STEPS):
                b = self.evolve(b)
            b ^= self.round_constants[r]
            keys.append(b)
        return keys

    # ────────────────────────────────────────────
    # 블록 암호화 / 복호화
    # ────────────────────────────────────────────

    def encrypt_block(self, plaintext: bytes) -> bytes:
        assert len(plaintext) == self.BLOCK_SIZE, f"블록 크기 불일치: {len(plaintext)} ≠ {self.BLOCK_SIZE}"
        s = to_int(plaintext)
        for r in range(self.NUM_ROUNDS):
            s = self.evolve(s ^ self.round_keys[r])
        return to_bytes(s ^ self.round_keys[self.NUM_ROUNDS])

    def decrypt_block(self, ciphertext: bytes) -> bytes:
        assert len(ciphertext) == self.BLOCK_SIZE, f"블록 크기 불일치: {len(ciphertext)} ≠ {self.BLOCK_SIZE}"
        s = to_int(ciphertext) ^ self.round_keys[self.NUM_ROUNDS]
        for r in range(self.NUM_ROUNDS - 1, -1, -1):
            s = self.evolve_inv(s) ^ self.round_keys[r]
        return to_bytes(s)

    # ────────────────────────────────────────────
    # CBC 운용 모드
    # ────────────────────────────────────────────

    @staticmethod
    def _pad(data: bytes, block_size: int) -> bytes:
        pad_len = block_size - (len(data) % block_size)
        return data + bytes([pad_len] * pad_len)

    @staticmethod
    def _unpad(data: bytes) -> bytes:
        pad_len = data[-1] if data else 0
        if pad_len == 0 or pad_len > len(data) or data[-pad_len:] != bytes([pad_len] * pad_len):
            raise ValueError("잘못된 패딩")
        return data[:-pad_len]

    def encrypt(self, plaintext: bytes, iv: bytes = None) -> bytes:
        """CBC 모드 암호화. 반환: IV ∥ C₁ ∥ C₂ ∥ ...  (iv를 주지 않으면 무작위)"""
        iv = os.urandom(self.BLOCK_SIZE) if iv is None else iv
        padded = self._pad(plaintext, self.BLOCK_SIZE)
        out, prev = bytearray(iv), iv
        for i in range(0, len(padded), self.BLOCK_SIZE):
            prev = self.encrypt_block(xor_bytes(padded[i:i + self.BLOCK_SIZE], prev))
            out += prev
        return bytes(out)

    def decrypt(self, ciphertext: bytes) -> bytes:
        """CBC 모드 복호화."""
        if len(ciphertext) < 2 * self.BLOCK_SIZE or len(ciphertext) % self.BLOCK_SIZE:
            raise ValueError("암호문 길이가 올바르지 않음")
        prev, out = ciphertext[:self.BLOCK_SIZE], bytearray()
        for i in range(self.BLOCK_SIZE, len(ciphertext), self.BLOCK_SIZE):
            block = ciphertext[i:i + self.BLOCK_SIZE]
            out += xor_bytes(self.decrypt_block(block), prev)
            prev = block
        return self._unpad(bytes(out))


# ================================================================
# 데모 & 테스트
# ================================================================

def _show_grid(x: int, indent: str = "  "):
    print(indent + "     " + " ".join(f"{j:X}" for j in range(COLS)))
    for i, row in enumerate(to_grid(x)):
        print(indent + f"행{i}: " + " ".join(str(v) for v in row))


if __name__ == '__main__':
    print("=" * 65)
    print("  MinesCipher v3 — MineLock (지뢰판 SPN)")
    print("=" * 65)

    # Demo 1: 가역성
    print("\n[Demo 1] 단일 블록 암복호화 가역성 검증")
    print("-" * 50)
    cipher = MinesCipherV3(b'SuperSecretKey123!')
    pt = bytes(range(16))
    ct = cipher.encrypt_block(pt)
    print(f"  평문 (PT): {pt.hex()}")
    print(f"  암호문(CT): {ct.hex()}")
    print(f"  복호문(DT): {cipher.decrypt_block(ct).hex()}")
    failures = 0
    for _ in range(1000):
        c = MinesCipherV3(os.urandom(16))
        p = os.urandom(16)
        failures += c.decrypt_block(c.encrypt_block(p)) != p
    print(f"  랜덤 1,000회: {'✅ 모두 통과' if failures == 0 else f'❌ {failures}건 실패'}")

    # Demo 2: CBC 모드
    print("\n[Demo 2] CBC 모드 한글 메시지 암복호화")
    print("-" * 50)
    msg = "안녕하세요, MineLock v3 지뢰판 SPN 암호화 테스트입니다!"
    ct_cbc = cipher.encrypt(msg.encode('utf-8'))
    dt_msg = cipher.decrypt(ct_cbc).decode('utf-8')
    print(f"  원본 메시지 : {msg}")
    print(f"  암호문 길이 : {len(ct_cbc)} bytes (IV {cipher.BLOCK_SIZE}B 포함)")
    print(f"  복호문 메시지: {dt_msg}")
    print(f"  검증: {'✅ 원본과 일치' if msg == dt_msg else '❌ 불일치!'}")

    # Demo 3: Avalanche
    print("\n[Demo 3] Avalanche Effect (평문 1비트 변경)")
    print("-" * 50)
    av = MinesCipherV3(b'AvalancheTestKey')
    base = b'A' * 16
    ct0 = av.encrypt_block(base)
    ratios = [hamming_distance(ct0, av.encrypt_block(flip_bit(base, b))) / 1.28 for b in range(128)]
    print(f"  128비트 위치 평균 {sum(ratios) / 128:.2f}%  (최소 {min(ratios):.2f}%, 최대 {max(ratios):.2f}%)")

    # Demo 4: 키 민감도
    print("\n[Demo 4] 키 민감도 (키 1비트 변경)")
    print("-" * 50)
    k1 = b'KeySensitivity!!'
    c1, c2 = MinesCipherV3(k1), MinesCipherV3(flip_bit(k1, 0))
    d = hamming_distance(c1.encrypt_block(b'\x55' * 16), c2.encrypt_block(b'\x55' * 16))
    print(f"  변경: {d}/128 비트 = {d / 1.28:.2f}%")

    # Demo 5: 라운드 1 시각화
    print("\n[Demo 5] 라운드 1 시각화 (HELLO, 비밀키 YSKL, CBC 생략)")
    print("-" * 50)
    vis = MinesCipherV3(b'YSKL')
    s = to_int(MinesCipherV3._pad(b'HELLO', 16)) ^ vis.round_keys[0]
    print("  [1] P ⊕ K0"); _show_grid(s)
    for n in range(1, MinesCipherV3.SUBS_PER_ROUND + 1):
        steps = mine_sub_steps(s)
        s = steps[-1][2]
        flips = ", ".join(f"색{c} {bin(m).count('1')}칸" for c, m, _ in steps)
        print(f"\n  [2-{n}] MineSub {n}회차 후 (반전: {flips})"); _show_grid(s)
    s = mine_perm(s)
    print("\n  [3] MinePerm 후 = 라운드 1 출력"); _show_grid(s)

    # Demo 6: 속도
    print("\n[Demo 6] 속도")
    print("-" * 50)
    t = time.perf_counter()
    for _ in range(200):
        MinesCipherV3(b'speed-test-key')
    ks_ms = (time.perf_counter() - t) / 200 * 1000
    data = os.urandom(64 * 1024)
    t = time.perf_counter()
    enc = cipher.encrypt(data)
    enc_s = time.perf_counter() - t
    t = time.perf_counter()
    assert cipher.decrypt(enc) == data
    dec_s = time.perf_counter() - t
    print(f"  키 스케줄       : {ks_ms:.2f} ms / 키")
    print(f"  64KB 암호화     : {enc_s * 1000:.0f} ms  ({len(data) / enc_s / 1024:.0f} KB/s)")
    print(f"  64KB 복호화     : {dec_s * 1000:.0f} ms  ({len(data) / dec_s / 1024:.0f} KB/s)")

    print("\n" + "=" * 65)
    print("  모든 데모 완료!")
    print("=" * 65)
