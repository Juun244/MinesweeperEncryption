"""
설명서 5장 'HELLO 예시'에 들어갈 값을 mines_cipher_v3로 단계별로 계산해 JSON으로 저장한다.

실행: python tools/trace_hello.py <출력.json>
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import mines_cipher_v3 as mc  # noqa: E402
from mines_cipher_v3 import MinesCipherV3  # noqa: E402

KEY = b"YSKL"
PLAINTEXT = b"HELLO"
IV = bytes(range(16))          # 예시용 고정 IV (실제로는 무작위)


def hx(x) -> str:
    b = mc.to_bytes(x) if isinstance(x, int) else x
    return " ".join(f"{v:02X}" for v in b)


def board(x: int) -> dict:
    return {"hex": hx(x), "grid": mc.to_grid(x)}


def sub_detail(x: int, examples=0) -> dict:
    """MineSub 한 번을 색 단계별로 기록 (+ 색 0 예시 칸)."""
    steps = mc.mine_sub_steps(x)
    out = {
        "before": board(x),
        "colors": [{"color": c, "flips": bin(m).count("1")} for c, m, _ in steps],
        "after": board(steps[-1][2]),
        "changed": [list(p) for p in mc.mask_cells(x ^ steps[-1][2])],
    }
    if examples:
        flipped = set(mc.mask_cells(steps[0][1]))
        color0 = [(i, j) for i in range(8) for j in range(16) if i % 2 == 0 and j % 2 == 0]
        picks = [next(p for p in color0 if p in flipped), next(p for p in color0 if p not in flipped)]
        out["examples"] = [{
            "cell": [i, j], "value": mc.get_cell(x, i, j),
            "nb": [[mc.get_cell(x, (i + a) % 8, (j + b) % 16) for b in (-1, 0, 1)] for a in (-1, 0, 1)],
            "c": mc.neighbor_count(x, i, j), "flip": (i, j) in flipped,
        } for i, j in picks]
    return out


def evolve_detail(x: int) -> dict:
    s1 = sub_detail(x)
    s2 = sub_detail(mc.mine_sub(x))
    after_sub = mc.mine_sub(mc.mine_sub(x))
    return {"sub1": s1, "sub2": s2, "perm": board(mc.mine_perm(after_sub))}


def main(out_path):
    c = MinesCipherV3(KEY)
    K = c.round_keys
    RC = c.round_constants
    D = {"key": KEY.decode(), "sha256": hashlib.sha256(KEY).hexdigest().upper(), "iv": hx(IV)}

    # ---------------- 키 스케줄 ----------------
    b0 = K[0]
    e1 = evolve_detail(b0)
    b_step1 = c.evolve(b0)
    e2 = c.evolve(b_step1)
    D["ks"] = {
        "B0": board(b0),
        "step1": e1,
        "step1_out": hx(b_step1),
        "step2_out": hx(e2),
        "RC1": hx(RC[1]),
        "K1": board(K[1]),
        "RC": [None] + [hx(r) for r in RC[1:]],
        "K": [hx(k) for k in K],
    }
    assert e2 ^ RC[1] == K[1]

    # ---------------- 암호화 ----------------
    padded = MinesCipherV3._pad(PLAINTEXT, 16)
    x_in = mc.to_int(mc.xor_bytes(padded, IV))
    s = x_in ^ K[0]
    sub1 = sub_detail(s, examples=2)
    s_a = mc.mine_sub(s)
    sub2 = sub_detail(s_a)
    s_b = mc.mine_sub(s_a)
    r1 = mc.mine_perm(s_b)
    D["enc"] = {
        "padded": hx(padded), "p_xor_iv": board(x_in),
        "r1_xor": board(s), "r1_sub1": sub1, "r1_sub2": sub2,
        "r1_perm": board(r1),
        "perm_examples": [[[i, j], list(mc.perm_position(i, j)), mc.get_cell(s_b, i, j)] for i, j in [(0, 0), (1, 0), (7, 15)]],
    }
    outs, state = [hx(r1)], r1
    states = [x_in, r1]          # states[r] = 라운드 r 출력 (states[0] = 입력)
    for r in range(1, 16):
        state = c.evolve(state ^ K[r])
        outs.append(hx(state))
        states.append(state)
    ct_block = state ^ K[16]
    ct = c.encrypt(PLAINTEXT, iv=IV)
    assert ct[16:] == mc.to_bytes(ct_block)
    D["enc"]["rounds"] = outs
    D["enc"]["c1"] = hx(ct_block)
    D["enc"]["ciphertext"] = hx(ct)

    # ---------------- 복호화 ----------------
    y = ct_block ^ K[16]                      # = 라운드 16 출력
    ip = mc.mine_perm_inv(y)                  # = 라운드 16의 MineSub 2회차 후
    inv_sub2 = mc.mine_sub_inv(ip)            # = 라운드 16의 MineSub 1회차 후
    inv_sub1 = mc.mine_sub_inv(inv_sub2)      # = 라운드 16 입력 (⊕K15 직후)
    r15 = inv_sub1 ^ K[15]
    assert y == states[16] and r15 == states[15]
    # 역 MineSub의 색 단계별 반전 수 (3 → 0 순서)
    def inv_colors(x):
        out = []
        for color in (3, 2, 1, 0):
            flips = mc.flip_mask(x) & mc.COLOR_MASKS[color]
            out.append({"color": color, "flips": bin(flips).count("1")})
            x ^= flips
        return out
    D["dec"] = {
        "y": hx(y), "inv_perm": hx(ip), "inv_sub2": hx(inv_sub2), "inv_sub2_colors": inv_colors(ip),
        "inv_sub1": hx(inv_sub1), "inv_sub1_colors": inv_colors(inv_sub2), "r15": hx(r15),
        "inv_perm_board": board(ip),
    }
    inv_outs, st = [], r15
    for r in range(15, 0, -1):               # 역라운드 15 … 1
        st = c.evolve_inv(st) ^ K[r - 1]
        inv_outs.append(hx(st))
    assert st == x_in
    D["dec"]["inv_rounds"] = inv_outs        # 역라운드 15 … 1 결과
    D["dec"]["after_iv"] = hx(mc.xor_bytes(mc.to_bytes(st), IV))
    D["dec"]["plaintext"] = c.decrypt(ct).decode()

    # ---------------- 1비트 변경 ----------------
    ct2 = c.encrypt(b"HELLN", iv=IV)
    D["avalanche"] = {"ct": hx(ct[16:]), "ct2": hx(ct2[16:]), "diff": mc.hamming_distance(ct[16:], ct2[16:])}

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(D, f, ensure_ascii=False)
    print("저장:", out_path, "| 암호문", D["enc"]["ciphertext"], "| HELLN 차이", D["avalanche"]["diff"], "비트")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "hello_trace.json")
