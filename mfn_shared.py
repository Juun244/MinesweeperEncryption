import sys

# Windows 터미널 한글 깨짐 방지
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

GRID_SIZE = 8

def xor_bytes(a: bytes, b: bytes) -> bytes:
    """두 바이트열을 XOR합니다."""
    return bytes(x ^ y for x, y in zip(a, b))

def bytes_to_binary_grid(data: bytes) -> list:
    """8바이트(64비트) → 8×8 이진 그리드 변환"""
    grid = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
    for i in range(GRID_SIZE):
        byte_val = data[i]
        for j in range(GRID_SIZE):
            grid[i][j] = (byte_val >> (7 - j)) & 1
    return grid

def minesweeper_adjacency(grid: list) -> list:
    """8×8 이진 그리드에서 지뢰찾기 인접 숫자 계산 (1=지뢰, 0=안전)"""
    adj = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            if grid[i][j] == 1:
                adj[i][j] = 0xF  # 지뢰 마커
            else:
                count = 0
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        if di == 0 and dj == 0: continue
                        ni, nj = i + di, j + dj
                        if 0 <= ni < GRID_SIZE and 0 <= nj < GRID_SIZE and grid[ni][nj] == 1:
                            count += 1
                adj[i][j] = count
    return adj

def xor_fold(adj: list) -> bytes:
    """8×8 nibble 그리드(256비트) → 64비트 XOR 폴딩"""
    flat = [val & 0xF for row in adj for val in row]
    packed = bytearray(32)
    for k in range(32):
        packed[k] = (flat[2 * k] << 4) | flat[2 * k + 1]
    
    result = bytearray(8)
    for chunk in range(4):
        for b in range(8):
            result[b] ^= packed[chunk * 8 + b]
    return bytes(result)

def round_function(R: bytes, K_r: bytes, RC_r: bytes) -> bytes:
    """Feistel 라운드 함수 F"""
    X = xor_bytes(xor_bytes(R, K_r), RC_r)
    grid = bytes_to_binary_grid(X)
    adj = minesweeper_adjacency(grid)
    return xor_fold(adj)

def pad(data: bytes, block_size: int = 16) -> bytes:
    """PKCS#7 패딩"""
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)

def unpad(data: bytes) -> bytes:
    """PKCS#7 언패딩"""
    pad_len = data[-1]
    return data[:-pad_len]
