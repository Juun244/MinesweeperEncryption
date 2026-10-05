import hashlib
import hmac as hmac_mod
import random
import struct
import json
from mfn_shared import GRID_SIZE

def generate_keys(master_password: str):
    print("=" * 65)
    print(" [Step 1] 마스터 키를 이용한 라운드 키 생성 (Key Schedule)")
    print("=" * 65)
    
    master_seed = hashlib.sha256(master_password.encode('utf-8')).digest()
    print(f"1. 비밀번호 '{master_password}'를 해시하여 Seed 생성 완료.\n")
    
    # 지뢰 배치
    rng = random.Random(master_seed)
    all_pos = [(i, j) for i in range(GRID_SIZE) for j in range(GRID_SIZE)]
    rng.shuffle(all_pos)
    mine_positions = set(all_pos[:10]) # 10개의 지뢰
    
    print(f"2. 8x8 키 맵에 10개의 지뢰 무작위 매설 완료:")
    for i in range(GRID_SIZE):
        row_str = "   "
        for j in range(GRID_SIZE):
            row_str += "💣 " if (i, j) in mine_positions else "🟩 "
        print(row_str)
        
    # 인접 맵 생성
    adj = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            if (i, j) in mine_positions:
                adj[i][j] = 0xF
            else:
                count = sum(1 for di in [-1,0,1] for dj in [-1,0,1] 
                            if (di!=0 or dj!=0) and 0<=i+di<GRID_SIZE and 0<=j+dj<GRID_SIZE 
                            and (i+di, j+dj) in mine_positions)
                adj[i][j] = count
                
    # BFS 탐색 (상세 추적)
    start_pos = (master_seed[-2] % GRID_SIZE, master_seed[-1] % GRID_SIZE)
    visited = set([start_pos])
    order = []
    queue = [start_pos]
    
    print("\n3. 지뢰찾기 연쇄 오픈(BFS) 상세 추적 시작:")
    print("-" * 65)
    
    step_num = 1
    while len(visited) < GRID_SIZE * GRID_SIZE:
        # 큐에 하나만 있고 그것이 첫 시작점이거나 중간에 강제로 열린 점일 때 알림
        if len(queue) == 1:
            if queue[0] == start_pos:
                print(f" 🎯 [게임 시작] 첫 번째 좌표 {queue[0]} 클릭!")
            else:
                print(f"\n 🎯 [잔여 탐색] 남은 닫힌 칸 중 좌표 {queue[0]} 강제 클릭!")

        while queue:
            r, c = queue.pop(0)
            order.append((r, c))
            
            val = adj[r][c]
            if val == 0xF:
                disp = "지뢰 💣"
            else:
                disp = f"숫자 {val}"
                
            msg = f"  {step_num:02d}번째 오픈: ({r}, {c}) ➡ {disp}"
            
            # 빈칸(0)이면 연쇄 오픈 발동
            if val == 0:
                msg += " 🌪️ 연쇄 오픈 발동!"
                added = []
                for dr in [-1,0,1]:
                    for dc in [-1,0,1]:
                        if dr==0 and dc==0: continue
                        nr, nc = r+dr, c+dc
                        if 0<=nr<GRID_SIZE and 0<=nc<GRID_SIZE and (nr, nc) not in visited:
                            visited.add((nr, nc))
                            queue.append((nr, nc))
                            added.append(f"({nr},{nc})")
                if added:
                    msg += f"\n       └─ 대기열(Queue)에 추가됨: {', '.join(added)}"
            print(msg)
            step_num += 1
            
        # 큐가 비었는데 아직 안 열린 칸이 있으면 다음 칸 강제 오픈
        for i in range(GRID_SIZE):
            for j in range(GRID_SIZE):
                if (i, j) not in visited:
                    visited.add((i, j))
                    queue.append((i, j))
                    break
            if queue: break
    
    print("-" * 65)
    print(f"✅ 총 64칸 연쇄 오픈 경로 탐색 완료.")
    
    visit_bytes = b''.join(bytes([r, c]) for r, c in order)
    
    # 라운드 키 생성
    round_keys = []
    round_constants = []
    
    print("\n4. 위 연쇄 오픈 경로 데이터를 바탕으로 16개의 라운드 키 생성:")
    for r in range(16):
        rc_in = b"MinesCipher_v2_RC" + struct.pack('>I', r)
        rc = hashlib.sha256(rc_in).digest()[:8]
        round_constants.append(rc.hex())
        
        data = struct.pack('>I', r) + visit_bytes
        k_r = hmac_mod.new(master_seed, data, hashlib.sha256).digest()[:8]
        round_keys.append(k_r.hex())
        print(f"   [Round {r+1:02d}] Key: {k_r.hex().upper()}")
        
    with open('keys.json', 'w') as f:
        json.dump({'round_keys': round_keys, 'round_constants': round_constants}, f, indent=4)
        
    print("\n✅ 모든 키가 'keys.json'에 성공적으로 저장되었습니다.")

if __name__ == '__main__':
    PASSWORD = "MySecretPassword123"
    generate_keys(PASSWORD)
