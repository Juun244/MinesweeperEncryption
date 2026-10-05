import json
from mfn_shared import unpad, round_function, xor_bytes

def decrypt_data():
    print("=" * 60)
    print(" [Step 3] 암호문을 평문으로 복원 (Decryption Process)")
    print("=" * 60)
    
    # 키 및 암호문 로드
    try:
        with open('keys.json', 'r') as f:
            keys_data = json.load(f)
            round_keys = [bytes.fromhex(k) for k in keys_data['round_keys']]
            round_constants = [bytes.fromhex(k) for k in keys_data['round_constants']]
            
        with open('ciphertext.bin', 'rb') as f:
            ciphertext = f.read()
    except FileNotFoundError:
        print("❌ 오류: 'keys.json' 또는 'ciphertext.bin' 파일이 없습니다. 이전 단계를 실행하세요.")
        return

    print(f"1. 암호문 로드 완료: {ciphertext.hex().upper()}")
    
    block = ciphertext[:16]
    L = block[:8]
    R = block[8:]
    print(f"\n[초기 상태] L = {L.hex().upper()} | R = {R.hex().upper()}")
    
    print("\n2. Feistel Network 16라운드 역추적 시작 (열쇠는 역순!):")
    # 열쇠를 역순(15 -> 0)으로 사용합니다.
    for r in range(15, -1, -1):
        K_r = round_keys[r]
        RC_r = round_constants[r]
        
        # F 함수 통과 (암호화 때와 동일한 정방향 믹서기!)
        F_out = round_function(R, K_r, RC_r)
        
        # L과 XOR 후 스왑
        new_L = R
        new_R = xor_bytes(L, F_out)
        
        print(f"  --- [Round {r+1:02d} 키 사용] ---")
        print(f"  > 사용된 Key : {K_r.hex().upper()}")
        print(f"  > F함수 출력 : {F_out.hex().upper()}")
        print(f"  > XOR & Swap : L -> {new_L.hex().upper()} | R -> {new_R.hex().upper()}")
        
        L = new_L
        R = new_R
        
    # 마지막 스왑
    plaintext_padded = R + L
    print(f"\n3. 복호화 완료 (최종 스왑 적용)")
    print(f"   복원된 패딩 데이터(Hex): {plaintext_padded.hex().upper()}")
    
    try:
        plaintext_bytes = unpad(plaintext_padded)
        plaintext_str = plaintext_bytes.decode('utf-8')
        print(f"\n🎉 최종 복원된 평문: '{plaintext_str}'")
    except Exception as e:
        print(f"\n❌ 패딩 제거 또는 텍스트 디코딩 실패: {e}")

if __name__ == '__main__':
    decrypt_data()
