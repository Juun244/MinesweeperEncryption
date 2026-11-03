"""
v3 순서도 생성기: 한 정의에서 .drawio(편집용)와 .png(발표/보고서용)를 함께 만든다.

실행: python tools/make_flowcharts.py <출력 폴더>
필요: Pillow, Windows 글꼴(맑은 고딕, Segoe UI Symbol)
"""
import html
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SCALE = 2
MARGIN = 24
FONT_MAIN = "C:/Windows/Fonts/malgun.ttf"
FONT_BOLD = "C:/Windows/Fonts/malgunbd.ttf"
FONT_SYM = "C:/Windows/Fonts/seguisym.ttf"
SYM_CHARS = set("⊕⋮⁻₀₂₃₄₅₆₇₈₉↺")

STYLES = {  # kind -> (drawio style, fill, stroke)
    "box":  ("rounded=1;whiteSpace=wrap;html=1;", "#ffffff", "#000000"),
    "key":  ("rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;", "#dae8fc", "#6c8ebf"),
    "core": ("rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;", "#fff2cc", "#d6b656"),
    "perm": ("rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;", "#e1d5e7", "#9673a6"),
    "out":  ("rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;", "#d5e8d4", "#82b366"),
    "ellipse": ("ellipse;whiteSpace=wrap;html=1;", "#ffffff", "#000000"),
    "text": ("text;html=1;align=center;verticalAlign=middle;strokeColor=none;fillColor=none;", None, None),
    "note": ("rounded=1;whiteSpace=wrap;html=1;dashed=1;fillColor=#f5f5f5;strokeColor=#666666;fontColor=#333333;align=left;spacingLeft=10;", "#f5f5f5", "#666666"),
    "groupS": ("rounded=1;whiteSpace=wrap;html=1;dashed=1;fillColor=#fffbea;strokeColor=#d6b656;verticalAlign=top;align=left;spacingLeft=10;spacingTop=2;fontStyle=1;", "#fffbea", "#d6b656"),
    "groupP": ("rounded=1;whiteSpace=wrap;html=1;dashed=1;fillColor=#f7f0fa;strokeColor=#9673a6;verticalAlign=top;align=left;spacingLeft=10;spacingTop=2;fontStyle=1;", "#f7f0fa", "#9673a6"),
}


class Diagram:
    def __init__(self, name, main=13, sub=10):
        self.name, self.main, self.sub = name, main, sub
        self.nodes, self.edges = {}, []

    def node(self, nid, kind, x, y, w, h, *lines):
        self.nodes[nid] = dict(kind=kind, x=x, y=y, w=w, h=h, lines=lines)

    def edge(self, src, tgt, pts, dashed=False, arrow=True, color=None):
        self.edges.append(dict(src=src, tgt=tgt, pts=pts, dashed=dashed, arrow=arrow, color=color))

    def bottom(self, n):
        d = self.nodes[n]
        return (d["x"] + d["w"] / 2, d["y"] + d["h"])

    def top(self, n):
        d = self.nodes[n]
        return (d["x"] + d["w"] / 2, d["y"])

    def down(self, a, b):
        self.edge(a, b, [self.bottom(a), self.top(b)])

    def chain(self, *ids):
        for a, b in zip(ids, ids[1:]):
            self.down(a, b)

    # ---------- drawio ----------
    def value(self, n):
        lines = n["lines"]
        if n["kind"] in ("groupS", "groupP"):
            return html.escape(lines[0])
        first = html.escape(lines[0])
        parts = [f"<b>{first}</b>" if n["kind"] == "note" else first]
        for ln in lines[1:]:
            parts.append(f'<font style="font-size:{self.sub}px">{html.escape(ln)}</font>')
        return "<br>".join(parts)

    def to_drawio(self):
        out = ['<mxfile host="app.diagrams.net">',
               f'  <diagram name="{html.escape(self.name)}" id="{abs(hash(self.name)) % 10**10}">',
               '    <mxGraphModel grid="0" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169" math="0" shadow="0">',
               '      <root>', '        <mxCell id="0" />', '        <mxCell id="1" parent="0" />']
        order = sorted(self.nodes.items(), key=lambda kv: 0 if kv[1]["kind"].startswith("group") else 1)
        for nid, n in order:
            style = STYLES[n["kind"]][0] + (f"fontSize={self.main};" if not n["kind"].startswith("group") else "fontSize=13;")
            out.append(f'        <mxCell id="{nid}" parent="1" style="{html.escape(style)}" value="{html.escape(self.value(n))}" vertex="1">')
            out.append(f'          <mxGeometry x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" as="geometry" />')
            out.append('        </mxCell>')
        for i, e in enumerate(self.edges):
            s, t = self.nodes[e["src"]], self.nodes[e["tgt"]]
            (sx, sy), (tx, ty) = e["pts"][0], e["pts"][-1]
            style = "html=1;rounded=0;"
            style += "endArrow=classic;endSize=6;" if e["arrow"] else "endArrow=none;"
            if e["dashed"]:
                style += "dashed=1;"
            style += f"strokeColor={e['color'] or ('#666666' if e['dashed'] else '#000000')};"
            style += f'exitX={(sx - s["x"]) / s["w"]:.4g};exitY={(sy - s["y"]) / s["h"]:.4g};exitDx=0;exitDy=0;'
            style += f'entryX={(tx - t["x"]) / t["w"]:.4g};entryY={(ty - t["y"]) / t["h"]:.4g};entryDx=0;entryDy=0;'
            out.append(f'        <mxCell id="e{i}" edge="1" parent="1" source="{e["src"]}" target="{e["tgt"]}" style="{style}" value="">')
            mids = e["pts"][1:-1]
            if mids:
                out.append('          <mxGeometry relative="1" as="geometry">')
                out.append('            <Array as="points">')
                for x, y in mids:
                    out.append(f'              <mxPoint x="{x}" y="{y}" />')
                out.append('            </Array>')
                out.append('          </mxGeometry>')
            else:
                out.append('          <mxGeometry relative="1" as="geometry" />')
            out.append('        </mxCell>')
        out += ['      </root>', '    </mxGraphModel>', '  </diagram>', '</mxfile>', '']
        return "\n".join(out)

    # ---------- png ----------
    def to_png(self, path):
        xs = [n["x"] for n in self.nodes.values()] + [n["x"] + n["w"] for n in self.nodes.values()]
        ys = [n["y"] for n in self.nodes.values()] + [n["y"] + n["h"] for n in self.nodes.values()]
        ox, oy = min(xs) - MARGIN, min(ys) - MARGIN
        W, H = int((max(xs) - ox + MARGIN) * SCALE), int((max(ys) - oy + MARGIN) * SCALE)
        img = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(img)
        P = lambda x, y: ((x - ox) * SCALE, (y - oy) * SCALE)  # noqa: E731
        fonts = {}

        def font(size, bold=False, sym=False):
            key = (size, bold, sym)
            if key not in fonts:
                fonts[key] = ImageFont.truetype(FONT_SYM if sym else (FONT_BOLD if bold else FONT_MAIN), int(size * SCALE))
            return fonts[key]

        def runs(text):
            cur, sym = "", None
            for ch in text:
                s = ch in SYM_CHARS
                if sym is not None and s != sym:
                    yield cur, sym
                    cur = ""
                cur += ch
                sym = s
            if cur:
                yield cur, sym

        def width(text, size, bold=False):
            return sum(d.textlength(t, font=font(size, bold, s)) for t, s in runs(text))

        def draw_line(x, y, text, size, color, bold=False):
            for t, s in runs(text):
                f = font(size, bold, s)
                d.text((x, y + size * SCALE * 0.62), t, font=f, fill=color, anchor="ls")
                x += d.textlength(t, font=f)

        order = sorted(self.nodes.values(), key=lambda n: 0 if n["kind"].startswith("group") else 1)
        for n in order:
            _, fill, stroke = STYLES[n["kind"]]
            x0, y0 = P(n["x"], n["y"])
            x1, y1 = P(n["x"] + n["w"], n["y"] + n["h"])
            if n["kind"] == "ellipse":
                d.ellipse([x0, y0, x1, y1], fill=fill, outline=stroke, width=SCALE)
            elif fill:
                r = min(min(n["w"], n["h"]) * 0.12, 12) * SCALE
                d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=fill, outline=stroke, width=SCALE)
                if "dashed" in STYLES[n["kind"]][0]:
                    for xx in range(int(x0 + r), int(x1 - r), 10 * SCALE):
                        d.line([(xx + 6 * SCALE, y0), (xx + 9 * SCALE, y0)], fill=fill, width=SCALE + 1)
                        d.line([(xx + 6 * SCALE, y1), (xx + 9 * SCALE, y1)], fill=fill, width=SCALE + 1)
                    for yy in range(int(y0 + r), int(y1 - r), 10 * SCALE):
                        d.line([(x0, yy + 6 * SCALE), (x0, yy + 9 * SCALE)], fill=fill, width=SCALE + 1)
                        d.line([(x1, yy + 6 * SCALE), (x1, yy + 9 * SCALE)], fill=fill, width=SCALE + 1)
            color = "#333333" if n["kind"] == "note" else "#000000"
            if n["kind"] in ("groupS", "groupP"):
                draw_line(x0 + 10 * SCALE, y0 + 5 * SCALE, n["lines"][0], 13, color, bold=True)
                continue
            sizes = [self.main] + [self.sub] * (len(n["lines"]) - 1)
            lh = [s * 1.3 * SCALE for s in sizes]
            y = (y0 + y1) / 2 - sum(lh) / 2
            for k, (text, s, hgt) in enumerate(zip(n["lines"], sizes, lh)):
                x = x0 + 10 * SCALE if n["kind"] == "note" else (x0 + x1) / 2 - width(text, s) / 2
                draw_line(x, y + (hgt - s * SCALE) / 2, text, s, color, bold=(n["kind"] == "note" and k == 0))
                y += hgt

        for e in self.edges:
            pts = [P(x, y) for x, y in e["pts"]]
            color = e["color"] or ("#666666" if e["dashed"] else "#000000")
            if e["dashed"]:
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    L = max(abs(bx - ax), abs(by - ay))
                    step = 6 * SCALE
                    for k in range(0, int(L), step * 2):
                        f0, f1 = k / L, min(k + step, L) / L
                        d.line([(ax + (bx - ax) * f0, ay + (by - ay) * f0), (ax + (bx - ax) * f1, ay + (by - ay) * f1)], fill=color, width=SCALE)
            else:
                d.line(pts, fill=color, width=SCALE, joint="curve")
            if e["arrow"]:
                (ax, ay), (bx, by) = pts[-2], pts[-1]
                L = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
                ux, uy = (bx - ax) / L, (by - ay) / L
                al, aw = 9 * SCALE, 4 * SCALE
                d.polygon([(bx, by), (bx - ux * al - uy * aw, by - uy * al + ux * aw),
                           (bx - ux * al + uy * aw, by - uy * al - ux * aw)], fill=color)
        img.save(path)


def save(diag, out_dir, base):
    with open(os.path.join(out_dir, base + ".drawio"), "w", encoding="utf-8") as f:
        f.write(diag.to_drawio())
    diag.to_png(os.path.join(out_dir, base + ".png"))
    print("wrote", base)


def key_column(g, last_label):
    """오른쪽 키 생성 열 (암호화·복호화 공통)."""
    g.node("k1", "box", 360, 0, 230, 50, "비밀키")
    g.node("k2", "box", 360, 100, 230, 50, "SHA-256 해시", "(앞 128비트 사용)")
    g.node("k3", "box", 360, 175, 230, 50, "초기 지뢰판 B(0) 생성", "(8×16 크기, K0 = B(0))")
    g.node("k4", "key", 360, 250, 230, 80, "지뢰판 진화 (r = 1 … 16)",
           "B(r) = Evolve(Evolve(B(r-1))) ⊕ RC(r)",
           "Evolve = MineSub ×2 → MinePerm", "K(r) = B(r)")
    g.node("k5", "key", 360, 355, 230, 50, "라운드 키 생성", last_label)
    g.chain("k1", "k2", "k3", "k4", "k5")


def build(out_dir):
    # ================= 1. 암호화 전체 구성도 =================
    g = Diagram("암호화 구성도 (v3)")
    g.node("p1", "box", 0, 0, 160, 50, "평문")
    g.node("p2", "box", 0, 100, 160, 50, "패딩 (PKCS#7)")
    g.node("p3", "box", 0, 200, 160, 50, "16바이트 블록 분할")
    g.node("p4", "box", 0, 300, 160, 55, "CBC 연결", "(이전 암호문 블록 ⊕,", "첫 블록은 IV)")
    g.node("p5", "box", 0, 405, 160, 55, "8×16 지뢰판으로 변환", "(128비트 = 128칸)")
    g.chain("p1", "p2", "p3", "p4", "p5")
    key_column(g, "(K0 … K16, 17개 × 128비트)")
    g.node("r1", "core", 165, 510, 220, 60, "라운드 1", "(⊕ K0 → MineSub ×2 → MinePerm)")
    g.node("r2", "core", 165, 620, 220, 50, "라운드 2", "(⊕ K1 → MineSub ×2 → MinePerm)")
    g.node("dots", "text", 165, 685, 220, 30, "⋮")
    g.node("r16", "core", 165, 730, 220, 50, "라운드 16", "(⊕ K15 → MineSub ×2 → MinePerm)")
    g.node("fk", "key", 165, 830, 220, 50, "최종 키 혼합", "(⊕ K16)")
    g.node("ct", "out", 165, 930, 220, 55, "암호문 블록", "(다음 블록의 CBC 입력)")
    g.node("n1", "note", 410, 610, 210, 70, "한 라운드", "키 혼합 → MineSub ×2 (치환)", "→ MinePerm (전치)", "※ 라운드 함수 구성도 참고")
    g.edge("p5", "r1", [(160, 432.5), (275, 432.5), (275, 510)])
    g.edge("k5", "r1", [(475, 405), (475, 480), (275, 480), (275, 510)])
    g.chain("r1", "r2")
    g.chain("r16", "fk", "ct")
    g.edge("n1", "r2", [(410, 645), (385, 645)], dashed=True, arrow=False)
    save(g, out_dir, "암호화 구성도_v3")

    # ================= 2. 복호화 전체 구성도 =================
    g = Diagram("복호화 구성도 (v3)")
    g.node("c1", "box", 0, 0, 160, 50, "암호문", "(IV ∥ C1 ∥ C2 ∥ …)")
    g.node("c2", "box", 0, 100, 160, 50, "IV 분리 후", "16바이트 블록 분할")
    g.node("c3", "box", 0, 200, 160, 50, "8×16 지뢰판으로 변환", "(128비트 = 128칸)")
    g.chain("c1", "c2", "c3")
    key_column(g, "(K0 … K16, 역순으로 사용)")
    g.node("d0", "key", 165, 510, 220, 50, "최종 키 제거", "(⊕ K16)")
    g.node("d16", "core", 165, 610, 220, 60, "역라운드 16", "(역 MinePerm → 역 MineSub ×2 → ⊕ K15)")
    g.node("d15", "core", 165, 720, 220, 50, "역라운드 15", "(역 MinePerm → 역 MineSub ×2 → ⊕ K14)")
    g.node("dots", "text", 165, 785, 220, 30, "⋮")
    g.node("d1", "core", 165, 830, 220, 50, "역라운드 1", "(역 MinePerm → 역 MineSub ×2 → ⊕ K0)")
    g.node("cb", "box", 165, 930, 220, 55, "CBC 해제", "(이전 암호문 블록 ⊕, 첫 블록은 IV)")
    g.node("up", "box", 165, 1035, 220, 50, "패딩 제거 (PKCS#7)")
    g.node("pt", "out", 165, 1135, 220, 50, "평문")
    g.node("n1", "note", 410, 610, 210, 70, "역라운드", "암호화 라운드의 단계를", "역순·역연산으로 수행", "※ 역라운드 함수 구성도 참고")
    g.edge("c3", "d0", [(160, 225), (275, 225), (275, 510)])
    g.edge("k5", "d0", [(475, 405), (475, 480), (275, 480), (275, 510)])
    g.chain("d0", "d16", "d15")
    g.chain("d1", "cb", "up", "pt")
    g.edge("n1", "d16", [(410, 640), (385, 640)], dashed=True, arrow=False)
    save(g, out_dir, "복호화 구성도_v3")

    # ================= 3. 라운드 함수 구성도 =================
    g = Diagram("라운드 함수 구성도 (v3)", main=15, sub=12)
    g.node("gS", "groupS", 210, 125, 340, 370, "MineSub ×2 (치환)")
    g.node("gP", "groupP", 210, 525, 340, 200, "MinePerm (전치)")
    g.node("S", "box", 20, 40, 200, 55, "상태 S", "(8×16 지뢰판, 128비트)")
    g.node("K", "key", 560, 40, 200, 55, "라운드 키 K(r)", "(128비트)")
    g.node("x", "ellipse", 300, 42.5, 160, 50, "XOR 연산", "S ⊕ K(r)")
    g.node("m0", "core", 240, 160, 280, 55, "① 색 0 칸 갱신", "(짝수 행 · 짝수 열)")
    g.node("m1", "core", 240, 245, 280, 55, "② 색 1 칸 갱신", "(짝수 행 · 홀수 열)")
    g.node("m2", "core", 240, 330, 280, 55, "③ 색 2 칸 갱신", "(홀수 행 · 짝수 열)")
    g.node("m3", "core", 240, 415, 280, 55, "④ 색 3 칸 갱신", "(홀수 행 · 홀수 열)")
    g.node("p1", "perm", 240, 560, 280, 60, "① 행 회전", "행 i를 오른쪽으로 (3i + 1)칸")
    g.node("p2", "perm", 240, 645, 280, 60, "② 열 회전", "열 j를 아래로 j칸")
    g.node("o", "out", 270, 770, 220, 55, "다음 라운드 상태 S'")
    g.node("nS", "note", 580, 220, 230, 170, "갱신 규칙", "해당 색의 칸마다 이웃 8칸의", "지뢰(1) 수 c를 세어", "c ∈ {0, 3, 4, 8}이면 반전", "(지뢰 ↔ 빈칸)", "판의 위·아래, 좌·우는 이어짐", "①~④를 마치면 한 번 더 반복")
    g.node("nP", "note", 580, 580, 230, 90, "전치 성질", "128칸이 1:1로 대응하는 고정 전치", "이웃했던 비트를 판 전체로 흩뜨림")
    g.edge("S", "x", [(220, 67.5), (300, 67.5)])
    g.edge("K", "x", [(560, 67.5), (460, 67.5)])
    g.edge("x", "m0", [(380, 92.5), (380, 160)])
    g.chain("m0", "m1", "m2", "m3", "p1", "p2", "o")
    g.edge("m3", "m0", [(520, 442.5), (536, 442.5), (536, 187.5), (520, 187.5)], color="#b08a1e")
    g.edge("nS", "gS", [(580, 305), (550, 305)], dashed=True, arrow=False)
    g.edge("nP", "gP", [(580, 625), (550, 625)], dashed=True, arrow=False)
    save(g, out_dir, "라운드 함수 구성도_v3")

    # ================= 4. 역라운드 함수 구성도 =================
    g = Diagram("역라운드 함수 구성도 (v3)", main=15, sub=12)
    g.node("gP", "groupP", 210, 115, 340, 200, "역 MinePerm")
    g.node("gS", "groupS", 210, 345, 340, 370, "역 MineSub ×2")
    g.node("S", "box", 270, 20, 220, 55, "현재 상태 S'", "(8×16 지뢰판, 128비트)")
    g.node("p2", "perm", 240, 150, 280, 60, "② 열 되돌리기", "열 j를 위로 j칸")
    g.node("p1", "perm", 240, 235, 280, 60, "① 행 되돌리기", "행 i를 왼쪽으로 (3i + 1)칸")
    g.node("m3", "core", 240, 380, 280, 55, "④ 색 3 칸 갱신", "(홀수 행 · 홀수 열)")
    g.node("m2", "core", 240, 465, 280, 55, "③ 색 2 칸 갱신", "(홀수 행 · 짝수 열)")
    g.node("m1", "core", 240, 550, 280, 55, "② 색 1 칸 갱신", "(짝수 행 · 홀수 열)")
    g.node("m0", "core", 240, 635, 280, 55, "① 색 0 칸 갱신", "(짝수 행 · 짝수 열)")
    g.node("x", "ellipse", 300, 755, 160, 50, "XOR 연산", "S ⊕ K(r)")
    g.node("K", "key", 560, 752.5, 200, 55, "라운드 키 K(r)", "(128비트)")
    g.node("o", "out", 270, 850, 220, 55, "이전 라운드 상태 S")
    g.node("nP", "note", 580, 170, 230, 90, "전치 되돌리기", "암호화의 ①→② 순서를 거꾸로,", "이동 방향도 반대로")
    g.node("nS", "note", 580, 440, 230, 170, "치환 되돌리기", "암호화와 같은 반전 규칙을", "색 3 → 2 → 1 → 0 역순으로 적용", "같은 색 칸끼리는 이웃이 아니라", "이웃 지뢰 수 c가 그대로 유지", "→ 같은 반전으로 원래대로 복원", "④~①을 마치면 한 번 더 반복")
    g.chain("S", "p2", "p1", "m3", "m2", "m1", "m0")
    g.edge("m0", "m3", [(520, 662.5), (536, 662.5), (536, 407.5), (520, 407.5)], color="#b08a1e")
    g.edge("m0", "x", [(380, 690), (380, 755)])
    g.edge("K", "x", [(560, 780), (460, 780)])
    g.edge("x", "o", [(380, 805), (380, 850)])
    g.edge("nP", "gP", [(580, 215), (550, 215)], dashed=True, arrow=False)
    g.edge("nS", "gS", [(580, 525), (550, 525)], dashed=True, arrow=False)
    save(g, out_dir, "역라운드 함수 구성도_v3")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else ".")
