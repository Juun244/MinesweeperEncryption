import hashlib
import random
import os
import struct
import sys

# Windows 터미널 한글 깨짐 방지
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass


class MineMap:
    """지뢰 맵과 인접 숫자, 행/열별 지뢰 수를 저장하는 클래스"""
    def __init__(self, mine_positions: set, adj_map: list, row_counts: list, col_counts: list):
        self.mine_positions = set(mine_positions)
        self.adj = adj_map
        self.row_counts = row_counts
        self.col_counts = col_counts

    def copy(self):
        return MineMap(
            self.mine_positions.copy(),
            [row[:] for row in self.adj],
            self.row_counts[:],
            self.col_counts[:]
        )

def _calc_map(mine_positions: set, N: int) -> MineMap:
    """지뢰 위치를 기반으로 인접 숫자 맵과 지뢰 수를 계산합니다."""
    adj_map = [[0]*N for _ in range(N)]
    for i in range(N):
        for j in range(N):
            if (i, j) in mine_positions:
                adj_map[i][j] = 0xF
            else:
                count = 0
                for di in [-1, 0, 1]:
                    for dj in [-1, 0, 1]:
                        if di == 0 and dj == 0:
                            continue
                        ni, nj = i + di, j + dj
                        if 0 <= ni < N and 0 <= nj < N:
                            if (ni, nj) in mine_positions:
                                count += 1
                adj_map[i][j] = count
                
    row_counts = [sum(1 for j in range(N) if (i, j) in mine_positions) for i in range(N)]
    col_counts = [sum(1 for i in range(N) if (i, j) in mine_positions) for j in range(N)]
    return MineMap(mine_positions, adj_map, row_counts, col_counts)

def generate_mine_map(key: bytes, N: int, M: int) -> MineMap:
    """마스터 키로부터 초기 지뢰 맵을 생성합니다."""
    seed = hashlib.sha256(key).digest()
    rng = random.Random(seed)
    
    all_positions = [(i, j) for i in range(N) for j in range(N)]
    rng.shuffle(all_positions)
    mine_positions = set(all_positions[:M])
    
    return _calc_map(mine_positions, N)

def bfs_reveal(start_pos: tuple, mine_map: MineMap, N: int) -> list:
    """BFS를 이용해 지뢰찾기 게임의 연쇄 오픈 순서를 시뮬레이션합니다."""
    visited = set()
    order = []
    queue = [start_pos]
    visited.add(start_pos)
    
    idx = 0
    while len(visited) < N * N:
        while idx < len(queue):
            r, c = queue[idx]
            idx += 1
            order.append((r, c))
            
            if mine_map.adj[r][c] == 0:
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < N and 0 <= nc < N:
                            if (nr, nc) not in visited:
                                visited.add((nr, nc))
                                queue.append((nr, nc))
        # 만약 방문하지 않은 영역이 남아있다면 가장 처음 발견되는 곳에서 다시 시작
        for i in range(N):
            found_unvisited = False
            for j in range(N):
                if (i, j) not in visited:
                    visited.add((i, j))
                    queue.append((i, j))
                    found_unvisited = True
                    break
            if found_unvisited:
                break
            
    return order


def pad(data: bytes, block_size: int) -> bytes:
    """PKCS#7 패딩을 적용합니다."""
    padding_len = block_size - (len(data) % block_size)
    return data + bytes([padding_len] * padding_len)

def unpad(data: bytes) -> bytes:
    """PKCS#7 패딩을 제거합니다."""
    padding_len = data[-1]
    return data[:-padding_len]


class MinesCipher:
    def __init__(self, key: bytes, grid_size: int = 8, num_mines: int = 10, num_rounds: int = 10):
        self.key = key
        self.N = grid_size
        self.M = num_mines
        self.R = num_rounds
        self.block_size_bytes = (self.N * self.N) // 2
        
        self.master_seed = hashlib.sha256(key).digest()
        # 시드의 마지막 2바이트로 시작 위치 결정
        r0 = self.master_seed[-2] % self.N
        c0 = self.master_seed[-1] % self.N
        self.start_pos = (r0, c0)

    def _add_mine_key(self, state: list, adj_map: list, sub_key_grid: list = None) -> list:
        """평문과 지뢰 맵(인접 숫자 맵 + 서브키)을 XOR합니다."""
        for i in range(self.N):
            for j in range(self.N):
                state[i][j] ^= adj_map[i][j]
                if sub_key_grid:
                    state[i][j] ^= sub_key_grid[i][j]
        return state

    def _mine_row_shift(self, state: list, row_counts: list) -> list:
        """각 행의 지뢰 수만큼 왼쪽으로 순환 시프트합니다."""
        for i in range(self.N):
            shift = row_counts[i] % self.N
            if shift:
                state[i] = state[i][shift:] + state[i][:shift]
        return state

    def _mine_col_shift(self, state: list, col_counts: list) -> list:
        """각 열의 지뢰 수만큼 아래로 순환 시프트합니다."""
        for j in range(self.N):
            shift = col_counts[j] % self.N
            if shift:
                col = [state[i][j] for i in range(self.N)]
                col = col[-shift:] + col[:-shift]
                for i in range(self.N):
                    state[i][j] = col[i]
        return state

    def _inv_mine_row_shift(self, state: list, row_counts: list) -> list:
        """각 행의 지뢰 수만큼 오른쪽으로 순환 시프트합니다."""
        for i in range(self.N):
            shift = row_counts[i] % self.N
            if shift:
                state[i] = state[i][-shift:] + state[i][:-shift]
        return state

    def _inv_mine_col_shift(self, state: list, col_counts: list) -> list:
        """각 열의 지뢰 수만큼 위로 순환 시프트합니다."""
        for j in range(self.N):
            shift = col_counts[j] % self.N
            if shift:
                col = [state[i][j] for i in range(self.N)]
                col = col[shift:] + col[:shift]
                for i in range(self.N):
                    state[i][j] = col[i]
        return state

    def _mutate_map(self, mine_map: MineMap, key: bytes, round_num: int) -> MineMap:
        """결정론적 해시를 이용하여 라운드간 지뢰 맵을 변형합니다."""
        new_positions = set()
        # 결정론적 순서를 위해 정렬
        sorted_mines = sorted(list(mine_map.mine_positions))
        
        for k_idx, (r_k, c_k) in enumerate(sorted_mines):
            hash_in = key + struct.pack('>I', round_num) + struct.pack('>I', k_idx)
            hash_val = hashlib.sha256(hash_in).digest()
            new_r = (r_k + hash_val[0]) % self.N
            new_c = (c_k + hash_val[1]) % self.N
            
            while (new_r, new_c) in new_positions:
                new_r = (new_r + 1) % self.N
            new_positions.add((new_r, new_c))
            
        return _calc_map(new_positions, self.N)

    def _generate_sub_keys(self, base_map: MineMap) -> list:
        """BFS 순서를 바탕으로 라운드별 추가 서브 키(그리드)를 생성합니다."""
        visit_order = bfs_reveal(self.start_pos, base_map, self.N)
        order_bytes = b''.join([bytes([r, c]) for r, c in visit_order])
        
        sub_keys = []
        for r in range(self.R):
            h = hashlib.sha256(self.key + struct.pack('>I', r) + order_bytes).digest()
            grid = [[0]*self.N for _ in range(self.N)]
            idx = 0
            for i in range(self.N):
                for j in range(self.N):
                    # 해시의 각 바이트 하위 4비트(nibble) 추출
                    grid[i][j] = h[idx % 32] & 0x0F
                    idx += 1
            sub_keys.append(grid)
        return sub_keys

    def encrypt_block(self, plaintext_grid: list) -> list:
        """1개 블록(N*N 그리드)을 암호화합니다."""
        mine_map = generate_mine_map(self.key, self.N, self.M)
        sub_keys = self._generate_sub_keys(mine_map)
        
        state = [row[:] for row in plaintext_grid]
        
        for r in range(self.R):
            state = self._add_mine_key(state, mine_map.adj, sub_keys[r])
            state = self._mine_row_shift(state, mine_map.row_counts)
            state = self._mine_col_shift(state, mine_map.col_counts)
            
            if r < self.R - 1:
                mine_map = self._mutate_map(mine_map, self.key, r)
                
        return state

    def decrypt_block(self, ciphertext_grid: list) -> list:
        """1개 블록(N*N 그리드)을 복호화합니다."""
        maps = []
        mine_map = generate_mine_map(self.key, self.N, self.M)
        sub_keys = self._generate_sub_keys(mine_map)
        
        for r in range(self.R):
            maps.append(mine_map)
            if r < self.R - 1:
                mine_map = self._mutate_map(mine_map, self.key, r)
                
        state = [row[:] for row in ciphertext_grid]
        
        for r in range(self.R - 1, -1, -1):
            mm = maps[r]
            state = self._inv_mine_col_shift(state, mm.col_counts)
            state = self._inv_mine_row_shift(state, mm.row_counts)
            state = self._add_mine_key(state, mm.adj, sub_keys[r])
            
        return state

    def _bytes_to_grid(self, data: bytes) -> list:
        """바이트 배열을 N*N 크기의 nibble 그리드로 변환합니다."""
        grid = [[0]*self.N for _ in range(self.N)]
        idx = 0
        for b in data:
            if idx >= self.N * self.N: break
            grid[idx // self.N][idx % self.N] = (b >> 4) & 0x0F
            idx += 1
            if idx >= self.N * self.N: break
            grid[idx // self.N][idx % self.N] = b & 0x0F
            idx += 1
        return grid

    def _grid_to_bytes(self, grid: list) -> bytes:
        """N*N 크기의 nibble 그리드를 바이트 배열로 변환합니다."""
        res = bytearray()
        flat = []
        for i in range(self.N):
            for j in range(self.N):
                flat.append(grid[i][j])
        for i in range(0, len(flat), 2):
            b = (flat[i] << 4) | flat[i+1]
            res.append(b)
        return bytes(res)

    def encrypt(self, plaintext: bytes) -> bytes:
        """CBC 모드를 이용해 임의 길이의 데이터를 암호화합니다."""
        padded_pt = pad(plaintext, self.block_size_bytes)
        iv = os.urandom(self.block_size_bytes)
        ciphertext = iv
        
        prev_ct = iv
        for i in range(0, len(padded_pt), self.block_size_bytes):
            block = padded_pt[i:i+self.block_size_bytes]
            # CBC: XOR with previous ciphertext
            xored_block = bytes(a ^ b for a, b in zip(block, prev_ct))
            
            pt_grid = self._bytes_to_grid(xored_block)
            ct_grid = self.encrypt_block(pt_grid)
            ct_bytes = self._grid_to_bytes(ct_grid)
            
            ciphertext += ct_bytes
            prev_ct = ct_bytes
            
        return ciphertext

    def decrypt(self, ciphertext: bytes) -> bytes:
        """CBC 모드를 이용해 암호문을 복호화합니다."""
        iv = ciphertext[:self.block_size_bytes]
        pt_blocks = bytearray()
        
        prev_ct = iv
        for i in range(self.block_size_bytes, len(ciphertext), self.block_size_bytes):
            block = ciphertext[i:i+self.block_size_bytes]
            
            ct_grid = self._bytes_to_grid(block)
            pt_grid = self.decrypt_block(ct_grid)
            pt_bytes = self._grid_to_bytes(pt_grid)
            
            # CBC: XOR with previous ciphertext
            xored_block = bytes(a ^ b for a, b in zip(pt_bytes, prev_ct))
            pt_blocks.extend(xored_block)
            
            prev_ct = block
            
        return unpad(bytes(pt_blocks))


if __name__ == '__main__':
    print("="*60)
    print("MinesCipher 데모 스크립트")
    print("="*60)
    
    # ---------------------------------------------------------
    # Demo 1: 4x4 Grid Spec Example
    # ---------------------------------------------------------
    print("\n[Demo 1] 4x4 그리드 수동 1라운드 스텝 (명세서 예제)")
    pt_flat = [0x5, 0x3, 0xA, 0x7,
               0x1, 0xF, 0x0, 0x2,
               0x8, 0x4, 0xC, 0x6,
               0xD, 0x9, 0xB, 0xE]
    pt_grid_4x4 = [[pt_flat[i*4 + j] for j in range(4)] for i in range(4)]
    
    mines_4x4 = {(0,1), (2,0), (3,3)}
    mine_map_4x4 = _calc_map(mines_4x4, 4)
    
    print("초기 평문 그리드:")
    for row in pt_grid_4x4: print([hex(x) for x in row])
    
    print("\n인접 숫자 맵 (지뢰는 0xf):")
    for row in mine_map_4x4.adj: print([hex(x) for x in row])
    
    cipher_demo = MinesCipher(b'dummy_key', grid_size=4, num_mines=3, num_rounds=1)
    
    # 1-1. AddMineKey
    # 명세서 데모에서는 서브키를 안 쓰고 기본 맵만 적용하는 것을 보여주기 위해 서브키=None 사용
    state = cipher_demo._add_mine_key([row[:] for row in pt_grid_4x4], mine_map_4x4.adj, sub_key_grid=None)
    print("\nStep 1: AddMineKey 결과:")
    for row in state: print([hex(x) for x in row])
    
    # 1-2. MineRowShift
    state = cipher_demo._mine_row_shift(state, mine_map_4x4.row_counts)
    print("\nStep 2: MineRowShift 결과:")
    for row in state: print([hex(x) for x in row])
        
    # 1-3. MineColShift
    state = cipher_demo._mine_col_shift(state, mine_map_4x4.col_counts)
    print("\nStep 3: MineColShift 결과:")
    for row in state: print([hex(x) for x in row])
    
    
    # ---------------------------------------------------------
    # Demo 2: 8x8 Grid Full Encryption/Decryption
    # ---------------------------------------------------------
    print("\n\n[Demo 2] 8x8 Standard 암호화/복호화 검증")
    key = b'SuperSecretKey123!'
    mc = MinesCipher(key, grid_size=8, num_mines=10, num_rounds=10)
    
    msg = "안녕하세요, MinesCipher 암호화 테스트입니다. 긴 메시지도 잘 작동합니다!"
    plaintext = msg.encode('utf-8')
    
    print(f"원본 메시지: {msg}")
    print(f"평문 바이트 (Hex): {plaintext.hex()}")
    
    ciphertext = mc.encrypt(plaintext)
    print(f"암호문 (Hex): {ciphertext.hex()}")
    
    decrypted = mc.decrypt(ciphertext)
    decrypted_msg = decrypted.decode('utf-8')
    print(f"복호화 메시지: {decrypted_msg}")
    
    if msg == decrypted_msg:
        print("-> 복호화 성공: 원본 메시지와 일치합니다.")
    else:
        print("-> 복호화 실패!")


    # ---------------------------------------------------------
    # Demo 3: Avalanche Test (1 bit flip)
    # ---------------------------------------------------------
    print("\n\n[Demo 3] Avalanche Test (1비트 변경에 따른 암호문 확산)")
    mc_av = MinesCipher(b'AvalancheKey456', grid_size=8, num_mines=12, num_rounds=10)
    
    pt1 = b'A' * 32  # 32 bytes = 256 bits (1 block for 8x8)
    
    # pt1에서 1비트만 플립한 pt2 생성
    pt2_list = bytearray(pt1)
    pt2_list[0] ^= 0x01
    pt2 = bytes(pt2_list)
    
    ct1 = mc_av.encrypt(pt1)
    ct2 = mc_av.encrypt(pt2)
    
    # 암호문 비교 (IV를 제외한 실제 블록부터 비교)
    ct1_block = ct1[32:]
    ct2_block = ct2[32:]
    
    diff_bits = 0
    total_bits = len(ct1_block) * 8
    
    for b1, b2 in zip(ct1_block, ct2_block):
        # XOR 후 1인 비트의 개수 카운트
        diff = b1 ^ b2
        diff_bits += bin(diff).count('1')
        
    print(f"원본 평문 암호문 (Hex, 첫 16바이트): {ct1_block[:16].hex()}...")
    print(f"1비트 플립 평문 암호문 (Hex, 첫 16바이트): {ct2_block[:16].hex()}...")
    print(f"전체 {total_bits}비트 중 {diff_bits}비트 변경됨")
    print(f"Avalanche 비율: ( {diff_bits} / {total_bits} ) = {diff_bits / total_bits * 100:.2f}%")
