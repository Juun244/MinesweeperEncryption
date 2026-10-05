import json
from mfn_shared import pad, round_function, xor_bytes

def encrypt_data(plaintext_str: str):
    print("=" * 60)
    print(" [Step 2] 평문을 암호문으로 변환 (Encryption Process)")
    print("=" * 60)
    
    # 키 로드
    try:
        with open('keys.json', 'r') as f:
            keys_data = json.load(f)
            round_keys = [bytes.fromhex(k) for k in keys_data['round_keys']]
            round_constants = [bytes.fromhex(k) for k in keys_data['round_constants']]
    except FileNotFoundError:
        print("❌ 오류: 'keys.json' 파일이 없습니다. step1_keygen.py를 먼저 실행하세요.")
        return

    print(f"1. 평문 입력: '{plaintext_str}'")
    pt_bytes = plaintext_str.encode('utf-8')
    padded_pt = pad(pt_bytes, 16)  # 1 블록(16바이트)로 패딩
    
    # 데모를 위해 첫 번째 블록(16바이트)만 암호화 과정을 상세히 보여줍니다.
    block = padded_pt[:16]
    print(f"2. 16바이트 블록 분할 및 패딩 완료: {block.hex().upper()}")
    
    L = block[:8]
    R = block[8:]
    print(f"\n[초기 상태] L = {L.hex().upper()} | R = {R.hex().upper()}")
    
    print("\n3. Feistel Network 16라운드 시작 (정방향):")
    for r in range(16):
        K_r = round_keys[r]
        RC_r = round_constants[r]
        
        # F 함수 통과
        F_out = round_function(R, K_r, RC_r)
        
        # L과 XOR 후 스왑
        new_L = R
        new_R = xor_bytes(L, F_out)
        
        print(f"  --- [Round {r+1:02d}] ---")
        print(f"  > 사용된 Key : {K_r.hex().upper()}")
        print(f"  > F함수 출력 : {F_out.hex().upper()}")
        print(f"  > XOR & Swap : L -> {new_L.hex().upper()} | R -> {new_R.hex().upper()}")
        
        L = new_L
        R = new_R
        
    # 마지막엔 L과 R을 한 번 더 바꿈 (Feistel 최종 스왑)
    ciphertext = R + L
    print(f"\n4. 암호화 완료 (최종 스왑 적용)")
    print(f"   최종 암호문(Hex): {ciphertext.hex().upper()}")
    
    with open('ciphertext.bin', 'wb') as f:
        f.write(ciphertext)
    print("\n✅ 암호문이 'ciphertext.bin'에 성공적으로 저장되었습니다.")

if __name__ == '__main__':
    TEXT_TO_ENCRYPT = "HELLO"
    encrypt_data(TEXT_TO_ENCRYPT)
