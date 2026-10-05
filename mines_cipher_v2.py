"""
MinesCipher v2 — Minesweeper Feistel Network (MFN)

지뢰찾기의 인접 숫자 계산(비가역적 일방향 함수)을
Feistel 라운드 함수의 비선형 변환으로 활용한 대칭키 블록 암호.

- 블록: 128비트 (16바이트)
- 키:   임의 길이 (SHA-256으로 256비트 정규화)
- 라운드: 16 (Balanced Feistel Network)
- 운용 모드: CBC + PKCS#7 패딩
"""

import hashlib
import hmac as hmac_mod
import random
import os
import struct
import sys

# Windows 터미널 UTF-8
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass


# ================================================================
# 유틸리티
# ================================================================

def xor_bytes(a: bytes, b: bytes) -> bytes:
    """두 바이트열을 XOR합니다."""
    return bytes(x ^ y for x, y in zip(a, b))


def flip_bit(data: bytes, bit_pos: int) -> bytes:
    """data의 bit_pos번째 비트를 반전합니다 (MSB-first)."""
    byte_idx = bit_pos // 8
    bit_idx = 7 - (bit_pos % 8)
    arr = bytearray(data)
    arr[byte_idx] ^= (1 << bit_idx)
    return bytes(arr)


def hamming_distance(a: bytes, b: bytes) -> int:
    """두 바이트열 간의 해밍 거리 (다른 비트 수)."""
    return sum(bin(x ^ y).count('1') for x, y in zip(a, b))


# ================================================================
# MinesCipher v2 — Minesweeper Feistel Network
# ================================================================

class MinesCipherV2:
    """
    Minesweeper Feistel Network (MFN) 블록 암호.

    라운드 함수 F:
      1. 키 혼합:  X = R ⊕ K_r ⊕ RC_r
      2. 그리드 변환: X(64비트) → 8×8 이진 그리드
      3. 지뢰찾기 인접 숫자 계산 (비선형!):
         - 비트 1인 셀 = 💣 지뢰 → 출력 0xF
         - 비트 0인 셀 = 안전 → 출력 = 이웃 지뢰 수 (0~8)
      4. XOR 폴딩: 8×8 nibble(256비트) → 64비트

    Feistel 구조이므로 F가 비가역이어도 전체 암복호화는 가역.
    """

    BLOCK_SIZE = 16   # 128 bits
    HALF_BLOCK = 8    # 64 bits
    NUM_ROUNDS = 16
    GRID_SIZE = 8     # 8×8 binary grid
    NUM_MINES_KS = 10 # 키 스케줄용 지뢰 수

    def __init__(self, key: bytes):
        self.master_seed = hashlib.sha256(key).digest()

        # 라운드 상수 생성 (Slide Attack 방어 + 퇴화 입력 방지)
        self.round_constants = []
        for r in range(self.NUM_ROUNDS):
            rc_in = b"MinesCipher_v2_RC" + struct.pack('>I', r)
            self.round_constants.append(hashlib.sha256(rc_in).digest()[:self.HALF_BLOCK])

        # BFS 기반 키 스케줄로 라운드 키 생성
        self.round_keys = self._generate_round_keys()

    # ────────────────────────────────────────────
    # 키 스케줄
    # ────────────────────────────────────────────

    def _generate_round_keys(self) -> list:
        """
        키 스케줄:
          1. 마스터 시드 → 8×8 지뢰 보드 생성
          2. BFS 탐색 순서 결정
          3. HMAC-SHA256(seed, r ∥ visit_order) → 라운드 키
        """
        N = self.GRID_SIZE
        rng = random.Random(self.master_seed)

        # 지뢰 배치
        all_pos = [(i, j) for i in range(N) for j in range(N)]
        rng.shuffle(all_pos)
        mine_positions = set(all_pos[:self.NUM_MINES_KS])

        # 인접 숫자 맵 계산
        adj_map = self._compute_adjacency_from_mines(mine_positions)

        # BFS 시작 위치 (마스터 시드 기반)
        r0 = self.master_seed[-2] % N
        c0 = self.master_seed[-1] % N

        # BFS 탐색 (지뢰찾기 연쇄 오픈 시뮬레이션)
        visit_order = self._bfs_reveal((r0, c0), adj_map, mine_positions)
        visit_bytes = b''.join(bytes([r, c]) for r, c in visit_order)

        # HMAC 기반 라운드 키 파생 (바이트 재사용 없음)
        round_keys = []
        for r in range(self.NUM_ROUNDS):
            data = struct.pack('>I', r) + visit_bytes
            k_r = hmac_mod.new(self.master_seed, data, hashlib.sha256).digest()[:self.HALF_BLOCK]
            round_keys.append(k_r)

        return round_keys

    def _compute_adjacency_from_mines(self, mine_positions: set) -> list:
        """지뢰 위치 집합으로부터 인접 숫자 맵을 계산합니다."""
        N = self.GRID_SIZE
        adj = [[0] * N for _ in range(N)]
        for i in range(N):
            for j in range(N):
                if (i, j) in mine_positions:
                    adj[i][j] = 0xF
                else:
                    count = 0
                    for di in (-1, 0, 1):
                        for dj in (-1, 0, 1):
                            if di == 0 and dj == 0:
                                continue
                            ni, nj = i + di, j + dj
                            if 0 <= ni < N and 0 <= nj < N and (ni, nj) in mine_positions:
                                count += 1
                    adj[i][j] = count
        return adj

    def _bfs_reveal(self, start: tuple, adj_map: list, mine_positions: set) -> list:
        """지뢰찾기 BFS 연쇄 오픈을 시뮬레이션합니다."""
        N = self.GRID_SIZE
        visited = set()
        order = []
        queue = [start]
        visited.add(start)
        idx = 0

        while len(visited) < N * N:
            while idx < len(queue):
                r, c = queue[idx]
                idx += 1
                order.append((r, c))

                # 빈 칸(인접 지뢰 0개)이면 연쇄 오픈
                if adj_map[r][c] == 0:
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            if dr == 0 and dc == 0:
                                continue
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < N and 0 <= nc < N and (nr, nc) not in visited:
                                visited.add((nr, nc))
                                queue.append((nr, nc))

            # 미방문 셀이 있으면 다음 셀에서 재시작
            for i in range(N):
                found = False
                for j in range(N):
                    if (i, j) not in visited:
                        visited.add((i, j))
                        queue.append((i, j))
                        found = True
                        break
                if found:
                    break

        return order

    # ────────────────────────────────────────────
    # 라운드 함수 F (핵심: 지뢰찾기 비선형 변환)
    # ────────────────────────────────────────────

    def _bytes_to_binary_grid(self, data: bytes) -> list:
        """8바이트(64비트) → 8×8 이진 그리드 변환."""
        N = self.GRID_SIZE
        grid = [[0] * N for _ in range(N)]
        for i in range(N):
            byte_val = data[i]
            for j in range(N):
                grid[i][j] = (byte_val >> (7 - j)) & 1
        return grid

    def _minesweeper_adjacency(self, grid: list) -> list:
        """
        ★ 핵심 비선형 변환 ★

        8×8 이진 그리드에서 지뢰찾기 인접 숫자를 계산합니다.
          - grid[i][j] == 1 → 💣 지뢰 → adj = 0xF (15)
          - grid[i][j] == 0 → 안전  → adj = 이웃 지뢰 수 (0~8)

        비선형성 원천: 8개 이웃의 정수 합에서 발생하는 올림(carry)이
        GF(2) 위의 비선형성을 제공합니다.
        """
        N = self.GRID_SIZE
        adj = [[0] * N for _ in range(N)]

        for i in range(N):
            for j in range(N):
                if grid[i][j] == 1:
                    adj[i][j] = 0xF  # 지뢰 마커
                else:
                    count = 0
                    for di in (-1, 0, 1):
                        for dj in (-1, 0, 1):
                            if di == 0 and dj == 0:
                                continue
                            ni, nj = i + di, j + dj
                            if 0 <= ni < N and 0 <= nj < N and grid[ni][nj] == 1:
                                count += 1
                    adj[i][j] = count

        return adj

    def _xor_fold(self, adj: list) -> bytes:
        """
        8×8 nibble 그리드(256비트) → 64비트 XOR 폴딩.

        64개 nibble → 32바이트 패킹 → 4×8바이트 청크 XOR → 8바이트.
        """
        # 평탄화
        flat = []
        for row in adj:
            for val in row:
                flat.append(val & 0xF)

        # nibble → byte 패킹 (2개 nibble = 1바이트)
        packed = bytearray(32)
        for k in range(32):
            packed[k] = (flat[2 * k] << 4) | flat[2 * k + 1]

        # 4-way XOR fold: 32바이트 → 8바이트
        result = bytearray(8)
        for chunk in range(4):
            for b in range(8):
                result[b] ^= packed[chunk * 8 + b]

        return bytes(result)

    def round_function(self, R: bytes, K_r: bytes, RC_r: bytes) -> bytes:
        """
        Feistel 라운드 함수 F(R, K_r, RC_r) → 64비트.

        지뢰찾기 인접 숫자 계산을 비선형 변환으로 사용합니다.
        """
        # Step 1: 키 혼합
        X = xor_bytes(xor_bytes(R, K_r), RC_r)

        # Step 2: 8×8 이진 그리드 변환
        grid = self._bytes_to_binary_grid(X)

        # Step 3: 지뢰찾기 인접 숫자 계산 (비선형!)
        adj = self._minesweeper_adjacency(grid)

        # Step 4: XOR 폴딩 (256비트 → 64비트)
        return self._xor_fold(adj)

    # ────────────────────────────────────────────
    # 블록 암호화 / 복호화 (Feistel)
    # ────────────────────────────────────────────

    def encrypt_block(self, plaintext: bytes) -> bytes:
        """128비트 블록 암호화 (16라운드 Feistel)."""
        assert len(plaintext) == self.BLOCK_SIZE, f"블록 크기 불일치: {len(plaintext)} ≠ {self.BLOCK_SIZE}"

        L = plaintext[:self.HALF_BLOCK]
        R = plaintext[self.HALF_BLOCK:]

        for r in range(self.NUM_ROUNDS):
            f_out = self.round_function(R, self.round_keys[r], self.round_constants[r])
            L, R = R, xor_bytes(L, f_out)

        return R + L  # 최종 스왑

    def decrypt_block(self, ciphertext: bytes) -> bytes:
        """128비트 블록 복호화 (16라운드 Feistel, 역순 키)."""
        assert len(ciphertext) == self.BLOCK_SIZE, f"블록 크기 불일치: {len(ciphertext)} ≠ {self.BLOCK_SIZE}"

        L = ciphertext[:self.HALF_BLOCK]
        R = ciphertext[self.HALF_BLOCK:]

        for r in range(self.NUM_ROUNDS - 1, -1, -1):
            f_out = self.round_function(R, self.round_keys[r], self.round_constants[r])
            L, R = R, xor_bytes(L, f_out)

        return R + L  # 최종 스왑

    # ────────────────────────────────────────────
    # CBC 운용 모드
    # ────────────────────────────────────────────

    @staticmethod
    def _pad(data: bytes, block_size: int) -> bytes:
        """PKCS#7 패딩."""
        pad_len = block_size - (len(data) % block_size)
        return data + bytes([pad_len] * pad_len)

    @staticmethod
    def _unpad(data: bytes) -> bytes:
        """PKCS#7 언패딩."""
        pad_len = data[-1]
        if pad_len == 0 or pad_len > len(data):
            raise ValueError("잘못된 패딩")
        return data[:-pad_len]

    def encrypt(self, plaintext: bytes) -> bytes:
        """CBC 모드 암호화. 반환: IV ∥ C₁ ∥ C₂ ∥ ..."""
        padded = self._pad(plaintext, self.BLOCK_SIZE)
        iv = os.urandom(self.BLOCK_SIZE)
        ciphertext = iv

        prev = iv
        for i in range(0, len(padded), self.BLOCK_SIZE):
            block = padded[i:i + self.BLOCK_SIZE]
            xored = xor_bytes(block, prev)
            ct_block = self.encrypt_block(xored)
            ciphertext += ct_block
            prev = ct_block

        return ciphertext

    def decrypt(self, ciphertext: bytes) -> bytes:
        """CBC 모드 복호화."""
        iv = ciphertext[:self.BLOCK_SIZE]
        result = bytearray()

        prev = iv
        for i in range(self.BLOCK_SIZE, len(ciphertext), self.BLOCK_SIZE):
            block = ciphertext[i:i + self.BLOCK_SIZE]
            pt_block = self.decrypt_block(block)
            xored = xor_bytes(pt_block, prev)
            result.extend(xored)
            prev = block

        return self._unpad(bytes(result))


# ================================================================
# 데모 & 테스트
# ================================================================

if __name__ == '__main__':
    print("=" * 65)
    print("  MinesCipher v2 — Minesweeper Feistel Network (MFN)")
    print("=" * 65)

    # ─────────────────────────────────────────────
    # Demo 1: 단일 블록 가역성 검증
    # ─────────────────────────────────────────────
    print("\n[Demo 1] 단일 블록 암복호화 가역성 검증")
    print("-" * 50)

    key = b'SuperSecretKey123!'
    cipher = MinesCipherV2(key)

    pt = bytes(range(16))  # 0x00 ~ 0x0F
    ct = cipher.encrypt_block(pt)
    dt = cipher.decrypt_block(ct)

    print(f"  평문 (PT): {pt.hex()}")
    print(f"  암호문(CT): {ct.hex()}")
    print(f"  복호문(DT): {dt.hex()}")
    print(f"  검증: {'✅ PT == DT 일치' if pt == dt else '❌ PT ≠ DT 불일치!'}")

    # 랜덤 1000회
    print("\n  랜덤 블록 1,000회 가역성 테스트...")
    failures = 0
    for _ in range(1000):
        rk = os.urandom(random.randint(8, 32))
        rp = os.urandom(16)
        c = MinesCipherV2(rk)
        if c.decrypt_block(c.encrypt_block(rp)) != rp:
            failures += 1

    print(f"  결과: {'✅ 1,000/1,000 통과' if failures == 0 else f'❌ {failures}건 실패'}")

    # ─────────────────────────────────────────────
    # Demo 2: CBC 모드 문자열 암복호화
    # ─────────────────────────────────────────────
    print(f"\n\n[Demo 2] CBC 모드 한글 메시지 암복호화")
    print("-" * 50)

    msg = "안녕하세요, MinesCipher v2 Feistel 암호화 테스트입니다! 긴 메시지도 정상 동작합니다."
    plaintext_bytes = msg.encode('utf-8')

    ct_cbc = cipher.encrypt(plaintext_bytes)
    dt_cbc = cipher.decrypt(ct_cbc)
    dt_msg = dt_cbc.decode('utf-8')

    print(f"  원본 메시지 : {msg}")
    print(f"  평문 길이   : {len(plaintext_bytes)} bytes")
    print(f"  암호문 길이 : {len(ct_cbc)} bytes (IV {cipher.BLOCK_SIZE}B 포함)")
    print(f"  암호문 (앞 32B): {ct_cbc[:32].hex()}...")
    print(f"  복호문 메시지: {dt_msg}")
    print(f"  검증: {'✅ 원본과 일치' if msg == dt_msg else '❌ 불일치!'}")

    # ─────────────────────────────────────────────
    # Demo 3: Avalanche Effect (블록 단위 — IV 문제 없음!)
    # ─────────────────────────────────────────────
    print(f"\n\n[Demo 3] Avalanche Effect (평문 1비트 변경 → 암호문 변화율)")
    print("-" * 50)
    print("  ※ encrypt_block() 직접 호출 — CBC IV 문제 없음")

    av_cipher = MinesCipherV2(b'AvalancheTestKey')
    pt_av = b'A' * 16  # 128비트 고정 평문
    ct_av = av_cipher.encrypt_block(pt_av)

    ratios = []
    print(f"\n  {'비트 위치':>10}  {'변경 비트':>10}  {'비율':>8}")
    print(f"  {'─' * 10}  {'─' * 10}  {'─' * 8}")

    for bit in range(128):
        pt_flip = flip_bit(pt_av, bit)
        ct_flip = av_cipher.encrypt_block(pt_flip)
        diff = hamming_distance(ct_av, ct_flip)
        ratio = diff / 128 * 100
        ratios.append(ratio)
        # 대표 8개만 출력
        if bit % 16 == 0:
            print(f"  {bit:>10}  {diff:>7}/128  {ratio:>7.2f}%")

    avg = sum(ratios) / len(ratios)
    min_r = min(ratios)
    max_r = max(ratios)

    print(f"\n  ── 128비트 전체 통계 ──")
    print(f"  평균: {avg:.2f}%")
    print(f"  최소: {min_r:.2f}%")
    print(f"  최대: {max_r:.2f}%")
    print(f"  이상적 목표: 50.00%")

    # ─────────────────────────────────────────────
    # Demo 4: 키 민감도 테스트
    # ─────────────────────────────────────────────
    print(f"\n\n[Demo 4] 키 민감도 (키 1비트 변경 → 암호문 변화율)")
    print("-" * 50)

    key1 = b'KeySensitivity!!'
    key2 = flip_bit(key1, 0)

    c1 = MinesCipherV2(key1)
    c2 = MinesCipherV2(key2)

    pt_ks = b'\x55' * 16
    ct1 = c1.encrypt_block(pt_ks)
    ct2 = c2.encrypt_block(pt_ks)

    ks_diff = hamming_distance(ct1, ct2)
    ks_ratio = ks_diff / 128 * 100

    print(f"  Key 1 : {key1.hex()}")
    print(f"  Key 2 : {key2.hex()} (비트 0만 반전)")
    print(f"  CT(K1): {ct1.hex()}")
    print(f"  CT(K2): {ct2.hex()}")
    print(f"  변경: {ks_diff}/128 비트 = {ks_ratio:.2f}%")

    # ─────────────────────────────────────────────
    # Demo 5: 라운드 함수 F 동작 시각화
    # ─────────────────────────────────────────────
    print(f"\n\n[Demo 5] 라운드 함수 F 1스텝 시각화")
    print("-" * 50)

    vis_cipher = MinesCipherV2(b'VisualDemo')

    R_demo = b'\xA3\x5C\xF1\x08\x7E\xD2\x4B\x96'
    K0 = vis_cipher.round_keys[0]
    RC0 = vis_cipher.round_constants[0]

    # Step 1: 키 혼합
    X = xor_bytes(xor_bytes(R_demo, K0), RC0)
    print(f"  R      = {R_demo.hex()}")
    print(f"  K₀     = {K0.hex()}")
    print(f"  RC₀    = {RC0.hex()}")
    print(f"  X = R⊕K₀⊕RC₀ = {X.hex()}")

    # Step 2: 8×8 이진 그리드
    grid = vis_cipher._bytes_to_binary_grid(X)
    mine_count = sum(grid[i][j] for i in range(8) for j in range(8))

    print(f"\n  8×8 이진 그리드 (1=💣, 0=·)  [지뢰 {mine_count}개/64칸]")
    print("     0 1 2 3 4 5 6 7")
    for i in range(8):
        row_str = f"  {i}: "
        for j in range(8):
            row_str += "💣" if grid[i][j] == 1 else " ·"
        print(row_str)

    # Step 3: 인접 숫자 계산
    adj = vis_cipher._minesweeper_adjacency(grid)

    print(f"\n  인접 숫자 맵 (F=지뢰)")
    print("     0 1 2 3 4 5 6 7")
    for i in range(8):
        row_str = f"  {i}: "
        for j in range(8):
            v = adj[i][j]
            row_str += " F" if v == 0xF else f" {v}"
        print(row_str)

    # Step 4: XOR 폴딩
    f_result = vis_cipher.round_function(R_demo, K0, RC0)
    print(f"\n  XOR 폴딩 → F(R, K₀, RC₀) = {f_result.hex()}")

    print("\n" + "=" * 65)
    print("  모든 데모 완료!")
    print("=" * 65)
