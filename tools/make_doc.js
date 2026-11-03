// MineLock v3 설계 설명서(.docx) 생성기
//
// 실행: node tools/make_doc.js <출력.docx> <hello.json> <measure.json> <그림 폴더>
//   hello.json   ← python tools/trace_hello.py
//   measure.json ← python tools/measure_v3.py
//   그림 폴더    ← python tools/make_flowcharts.py 로 만든 PNG가 있는 곳 (docs/2차)
// 필요: npm 패키지 docx (npm install docx)
// 목차는 Word에서 열어 '필드 업데이트'를 해야 쪽 번호가 채워진다.

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, VerticalAlign, ImageRun, Footer, PageNumber, LevelFormat,
  TableOfContents, PageBreak,
} = require("docx");

const [OUT, HELLO, MEASURE, IMG_DIR] = process.argv.slice(2);
const D = JSON.parse(fs.readFileSync(HELLO, "utf8"));
const M = JSON.parse(fs.readFileSync(MEASURE, "utf8"));

const KF = "Malgun Gothic";
const MF = "Consolas";
const font = (f) => ({ ascii: f, eastAsia: KF, hAnsi: f, cs: f });
const NAVY = "1F2A5A", BLUE = "3F57D9", ORANGE = "C4521C";
const CONTENT_W = 9638; // A4, 좌우 여백 2cm
const HEXCOL = "0123456789ABCDEF".split("");
const pct = (v) => `${v.toFixed(1)}%`;

// ---------- 텍스트 도우미 ----------
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const s = m[0];
    if (s.startsWith("**")) out.push(new TextRun({ text: s.slice(2, -2), bold: true, ...base }));
    else out.push(new TextRun({ text: s.slice(1, -1), font: font(MF), ...base }));
    last = m.index + s.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}
const p = (text, opts = {}) => new Paragraph({ children: runs(text, opts.run), spacing: { after: 120, line: 300 }, ...opts.para });
const pk = (text) => p(text, { para: { keepNext: true } });
let firstH1 = true;
const h1 = (text) => { const pb = !firstH1; firstH1 = false; return new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: pb, children: [new TextRun(text)] }); };
const h2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
const h3 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)] });
const h4 = (text) => new Paragraph({ keepNext: true, spacing: { before: 160, after: 80 }, children: [new TextRun({ text, bold: true, color: BLUE })] });
const bullet = (text, level = 0) => new Paragraph({ numbering: { reference: "bullets", level }, children: runs(text), spacing: { after: 60, line: 300 } });
const numberingConfigs = [
  { reference: "bullets", levels: [
    { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 280 } } } },
    { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1000, hanging: 280 } } } },
  ] },
];
let numRef = 0;
function steps(items) {
  const ref = `steps${numRef++}`;
  numberingConfigs.push({ reference: ref, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 360 } } } }] });
  return items.map((t) => new Paragraph({ numbering: { reference: ref, level: 0 }, children: runs(t), spacing: { after: 60, line: 300 } }));
}
function code(lines, keepNextAll = false) {
  return lines.map((l, i) => new Paragraph({
    keepNext: keepNextAll || i < lines.length - 1, keepLines: true,
    children: [new TextRun({ text: l, font: font(MF), size: 18 })],
    shading: { type: ShadingType.CLEAR, fill: "F3F4F8", color: "auto" },
    spacing: { before: i === 0 ? 60 : 0, after: i === lines.length - 1 ? 160 : 0, line: 260 },
    indent: { left: 200, right: 200 },
  }));
}
const caption = (text) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 240 }, children: [new TextRun({ text, size: 18, color: "666666" })] });

// ---------- 표 도우미 ----------
const border = { style: BorderStyle.SINGLE, size: 4, color: "C8CCDA" };
const borders = { top: border, bottom: border, left: border, right: border };
const NOB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
function cell(content, width, o = {}) {
  const paras = (Array.isArray(content) ? content : [content]).map((c) =>
    c instanceof Paragraph ? c : new Paragraph({
      alignment: o.align || AlignmentType.LEFT, keepNext: !!o.keepNext,
      spacing: { after: 0, line: o.line || 276 },
      children: runs(String(c), { bold: o.bold, color: o.color, size: o.size, font: o.mono ? font(MF) : undefined }),
    }));
  return new TableCell({
    width: { size: width, type: WidthType.DXA }, borders,
    shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill, color: "auto" } : undefined,
    margins: { top: o.pad ?? 60, bottom: o.pad ?? 60, left: o.padX ?? 100, right: o.padX ?? 100 },
    verticalAlign: VerticalAlign.CENTER, children: paras,
  });
}
function table(headers, rows, widths, o = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const trs = [];
  if (headers) trs.push(new TableRow({ tableHeader: true, cantSplit: true, children: headers.map((h, i) => cell(h, widths[i], { fill: NAVY, color: "FFFFFF", bold: true, size: o.size, keepNext: true })) }));
  rows.forEach((r, ri) => trs.push(new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, widths[i], { size: o.size, keepNext: rows.length <= 12 && ri < rows.length - 1, mono: o.mono && o.mono(i), fill: (o.rowFill && o.rowFill(ri, i)) || (ri % 2 ? "F7F8FC" : undefined) })) })));
  return [new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, rows: trs }), new Paragraph({ spacing: { after: 120 }, children: [] })];
}
function callout(title, lines, fill = "EEF2FF", titleColor = BLUE) {
  const bd = { style: BorderStyle.SINGLE, size: 4, color: "B8C3F5" };
  const children = [new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: title, bold: true, color: titleColor })] })]
    .concat(lines.map((l) => new Paragraph({ spacing: { after: 40, line: 300 }, children: runs(l) })));
  return [new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
    rows: [new TableRow({ cantSplit: true, children: [new TableCell({
      width: { size: CONTENT_W, type: WidthType.DXA }, borders: { top: bd, bottom: bd, left: bd, right: bd },
      shading: { type: ShadingType.CLEAR, fill, color: "auto" },
      margins: { top: 140, bottom: 140, left: 200, right: 200 }, children,
    })] })],
  }), new Paragraph({ spacing: { after: 120 }, children: [] })];
}

// 8×16 지뢰판 표. mark: [[i,j]...] 바뀐 칸
function board(grid, o = {}) {
  const LW = 1078, CW = 535; // 1078 + 16*535 = 9638
  const widths = [LW].concat(Array(16).fill(CW));
  const mark = new Set((o.mark || []).map(([i, j]) => `${i},${j}`));
  const hdr = new TableRow({ cantSplit: true, children: [cell("", LW, { fill: "E9ECF5", pad: 20, keepNext: true })].concat(HEXCOL.map((c) => cell(c, CW, { fill: "E9ECF5", align: AlignmentType.CENTER, size: 16, bold: true, pad: 20, padX: 0, keepNext: true }))) });
  const rows = grid.map((row, i) => new TableRow({ cantSplit: true, children: [cell(o.labels ? o.labels[i] : `행${i}`, LW, { fill: "E9ECF5", size: 16, bold: true, pad: 20, padX: 60, keepNext: true })]
    .concat(row.map((v, j) => {
      let fill = v ? "C9D3FF" : "FFFFFF";
      if (mark.has(`${i},${j}`)) fill = v ? "F4A26B" : "FBD9C2";
      return cell(String(v), CW, { fill, align: AlignmentType.CENTER, size: 17, bold: !!v, mono: true, pad: 20, padX: 0, keepNext: true });
    })) }));
  return [new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths, rows: [hdr, ...rows] })];
}
function legend(items) {
  return new Paragraph({ spacing: { before: 80, after: 200 }, children: items.flatMap(([fill, text], k) => [
    new TextRun({ text: "     ", shading: { type: ShadingType.CLEAR, fill, color: "auto" }, size: 18 }),
    new TextRun({ text: ` ${text}${k < items.length - 1 ? "     " : ""}`, size: 18, color: "555555" }),
  ]) });
}
const LEG_MINE = [["C9D3FF", "지뢰 (1)"], ["FFFFFF", "빈칸 (0)"]];
const LEG_CHANGED = [["C9D3FF", "지뢰 (1)"], ["F4A26B", "바뀌어서 지뢰가 된 칸"], ["FBD9C2", "바뀌어서 빈칸이 된 칸"]];
function neighborhood(ex) {
  const W3 = 700;
  const marked = new Set((ex.marks || []).map(([a, b]) => `${a},${b}`));
  const rows = ex.nb.map((r, a) => new TableRow({ children: r.map((v, b) => (a === 1 && b === 1)
    ? cell("■", W3, { fill: "1F2A5A", color: "FFFFFF", align: AlignmentType.CENTER, bold: true })
    : cell(String(v), W3, { fill: marked.has(`${a},${b}`) ? (v ? "F4A26B" : "FBD9C2") : (v ? "C9D3FF" : "FFFFFF"), align: AlignmentType.CENTER, mono: true, bold: !!v })) }));
  return new Table({ width: { size: W3 * 3, type: WidthType.DXA }, columnWidths: [W3, W3, W3], rows });
}
function exampleCells(examples) {
  const W2 = 4819;
  const mk = (ex) => [new Paragraph({ spacing: { after: 80 }, children: runs(`**(행${ex.cell[0]}, 열${HEXCOL[ex.cell[1]]})** — 현재 값 ${ex.value}`) }), neighborhood(ex),
    new Paragraph({ spacing: { before: 80, after: 0 }, children: runs(`c = ${ex.c} → ${ex.flip ? `{0,3,4,8}에 포함 → **반전** (${ex.value} → ${1 - ex.value})` : `포함 안 됨 → **유지** (${ex.value})`}`) })];
  const rows = [];
  for (let k = 0; k < examples.length; k += 2) {
    const pair = examples.slice(k, k + 2).map(mk);
    while (pair.length < 2) pair.push([new Paragraph({ children: [] })]);
    rows.push(new TableRow({ cantSplit: true, children: pair.map((ch) => new TableCell({
      width: { size: W2, type: WidthType.DXA }, children: ch, margins: { top: 100, bottom: 100, left: 120, right: 120 },
      borders: { top: NOB, bottom: NOB, left: NOB, right: NOB },
    })) }));
  }
  return [new Table({ width: { size: W2 * 2, type: WidthType.DXA }, columnWidths: [W2, W2], rows }), new Paragraph({ spacing: { after: 120 }, children: [] })];
}
// 한 행(16칸) 또는 한 열(8칸)의 비트를 칸 모양으로 보여 주는 작은 표
function bitStrip(rowsSpec, cellW) {
  // rowsSpec: [[라벨, [비트...], 강조할 칸 인덱스 Set], ...]
  const LW = 2200;
  const n = rowsSpec[0][1].length;
  const widths = [LW].concat(Array(n).fill(cellW));
  const trs = rowsSpec.map(([label, bits, hi]) => new TableRow({ cantSplit: true, children: [cell(label, LW, { fill: "E9ECF5", size: 17, bold: true, pad: 30, keepNext: true })]
    .concat(bits.map((v, k) => cell(String(v), cellW, { fill: hi && hi.has(k) ? (v ? "F4A26B" : "FBD9C2") : (v ? "C9D3FF" : "FFFFFF"), align: AlignmentType.CENTER, size: 17, bold: !!v, mono: true, pad: 30, padX: 0, keepNext: true }))) }));
  return [new Table({ width: { size: LW + n * cellW, type: WidthType.DXA }, columnWidths: widths, rows: trs }), new Paragraph({ spacing: { after: 160 }, children: [] })];
}
const COLOR_NAMES = ["짝수 행·짝수 열", "짝수 행·홀수 열", "홀수 행·짝수 열", "홀수 행·홀수 열"];
function colorTable(colorsList, titles) {
  // colorsList: [[{color, flips}...], ...]  (열마다 한 번의 MineSub)
  const order = colorsList[0].map((c) => c.color);
  const rows = order.map((col, k) => [`색 ${col} (${COLOR_NAMES[col]})`].concat(colorsList.map((cs) => `${cs[k].flips}칸`)));
  rows.push(["**합계**"].concat(colorsList.map((cs) => `**${cs.reduce((a, c) => a + c.flips, 0)}칸**`)));
  const w0 = 4000, wr = Math.floor((CONTENT_W - w0) / colorsList.length);
  return table(["단계 (각 색 32칸)"].concat(titles), rows, [w0].concat(Array(colorsList.length).fill(wr)));
}
function image(file, widthPx, alt) {
  const buf = fs.readFileSync(path.join(IMG_DIR, file));
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  return new Paragraph({ keepNext: true, alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, children: [new ImageRun({
    type: "png", data: buf, transformation: { width: widthPx, height: Math.round(widthPx * h / w) },
    altText: { title: alt, description: alt, name: file },
  })] });
}
const rowLabels = (hex) => { const b = hex.split(" "); return [0, 1, 2, 3, 4, 5, 6, 7].map((i) => `행${i} ${b[2 * i]} ${b[2 * i + 1]}`); };
const sumFlips = (cs) => cs.reduce((a, c) => a + c.flips, 0);

// ---------- 측정값 ----------
const T1 = -M.trail1.log2;                       // 라운드당 1비트 차분 유지 확률의 -log2
const T16 = 16 * T1, T_NEED = Math.ceil(128 / T1);
const AV = M.avalanche, RK = M.rk_diff;

// ================= 본문 =================
const C = [];
// 표지
C.push(new Paragraph({ spacing: { before: 2400, after: 200 }, children: [new TextRun({ text: "MineLock v3 설계 설명서", bold: true, size: 56, color: NAVY })] }));
C.push(new Paragraph({ spacing: { after: 600 }, children: [new TextRun({ text: "지뢰찾기 규칙으로 만든 블록 암호 — 처음 읽는 사람을 위한 안내", size: 28, color: "4A4F6A" })] }));
C.push(new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: "현대암호학 2조 (YSKL) · 손홍배 강인석 여태준 이채은", size: 22 })] }));
C.push(new Paragraph({ spacing: { after: 800 }, children: [new TextRun({ text: "2026년 11월", size: 22, color: "666666" })] }));
C.push(...callout("이 문서를 읽기 전에", [
  "이 문서는 1차 발표 설계(코드 `mines_cipher_v2.py`)를 피드백에 맞춰 고친 **v3 설계**를 설명합니다. 2차 발표자료에서는 같은 계열의 설계를 \"MineLock v2\"로 표기했습니다.",
  "v3는 검토 피드백을 반영해 **라운드마다 MineSub를 2번**, **키 스케줄에서 지뢰판을 2번씩 진화**시키도록 확정했습니다(4.3절, 4.5절, 6.3절).",
  "암호학을 처음 접하는 사람도 읽을 수 있도록 1장에서 기본 개념을 먼저 설명합니다. 이미 알고 있다면 2장부터 읽어도 됩니다.",
  "모든 예시 값과 수치는 정식 구현 `mines_cipher_v3.py`로 계산했습니다(테스트 `test_mines_cipher_v3.py`, 측정 `tools/measure_v3.py`).",
]));
C.push(new Paragraph({ children: [new PageBreak()] }));
C.push(new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "목차", bold: true, size: 32, color: NAVY })] }));
C.push(new TableOfContents("목차", { hyperlink: true, headingStyleRange: "1-2" }));

// ---------- 1장 ----------
C.push(h1("1. 먼저 알아야 할 기본 개념"));
C.push(h2("1.1 블록 암호"));
C.push(p("블록 암호는 데이터를 **일정한 크기의 덩어리(블록)**로 잘라서, 같은 비밀키로 암호화하고 복호화하는 방식입니다. 널리 쓰이는 AES가 대표적인 블록 암호이고, MineLock도 같은 종류입니다."));
C.push(bullet("**대칭키**: 암호화와 복호화에 같은 비밀키를 씁니다."));
C.push(bullet("**비트와 바이트**: 비트는 0 또는 1 하나, 바이트는 비트 8개입니다. 바이트는 보통 16진수 두 자리로 씁니다. 예) `48` = `0100 1000`"));
C.push(bullet("**MineLock의 블록 크기**: 128비트 = 16바이트. 이보다 긴 데이터는 16바이트씩 잘라서 처리합니다."));
C.push(h2("1.2 XOR (⊕) — 키를 섞는 연산"));
C.push(p("XOR은 두 비트가 **다르면 1, 같으면 0**이 되는 연산입니다. 기호로 ⊕를 씁니다."));
C.push(...table(["A", "B", "A ⊕ B"], [["0", "0", "0"], ["0", "1", "1"], ["1", "0", "1"], ["1", "1", "0"]], [1500, 1500, 1500]));
C.push(p("쉽게 말해 **\"키가 1인 자리의 비트만 뒤집는다\"**고 생각하면 됩니다. 같은 키로 두 번 XOR하면 두 번 뒤집혀서 원래 값으로 돌아옵니다. 그래서 암호화와 복호화에 같은 키를 쓸 수 있습니다."));
C.push(...code(["  0100 1000   (48)", "⊕ 1000 1000   (88)  ← 키", "= 1100 0000   (C0)", "⊕ 1000 1000   (88)  ← 같은 키로 한 번 더", "= 0100 1000   (48)  ← 원래 값"]));
C.push(h2("1.3 치환과 전치"));
C.push(p("블록 암호는 두 가지 기본 연산을 번갈아 반복합니다."));
C.push(...table(["연산", "하는 일", "비유", "유명한 예"], [
  ["**치환** (Substitution)", "비트의 **값**을 바꿈", "카드를 뒤집기", "DES의 S-box, AES의 SubBytes"],
  ["**전치** (Permutation)", "비트의 **위치**를 바꿈", "카드 순서를 섞기", "DES의 P, AES의 ShiftRows"],
], [2300, 2300, 2000, 3038]));
C.push(p("치환만 있으면 변화가 한 자리에만 머물고, 전치만 있으면 값 자체는 그대로라서 쉽게 풀립니다. 둘을 함께 여러 번 반복해야 안전한 암호가 됩니다."));
C.push(h2("1.4 라운드와 라운드 키"));
C.push(p("같은 과정을 여러 번 반복할 때 한 회차를 **라운드**라고 합니다. 라운드마다 서로 다른 키를 쓰는데, 이것을 **라운드 키**라고 합니다. 비밀키 하나로부터 라운드 키 여러 개를 만들어 내는 과정을 **키 스케줄**이라고 합니다."));
C.push(h2("1.5 좋은 블록 암호의 조건"));
C.push(bullet("**가역성**: 복호화하면 원래 평문이 정확히 나와야 합니다."));
C.push(bullet("**확산 (눈사태 효과)**: 평문을 1비트만 바꿔도 암호문의 약 절반(50%)이 바뀌어야 합니다. 그래야 비슷한 평문끼리 비교해서 정보를 얻을 수 없습니다."));
C.push(bullet("**비선형성**: 출력 비트가 입력 비트 몇 개의 단순한 XOR로 예측되면 안 됩니다. 이런 관계가 있으면 \"선형 공격\"으로 키를 찾을 수 있습니다."));
C.push(bullet("**차분 저항성**: 두 입력의 차이가 높은 확률로 특정한 출력 차이로 이어지면 안 됩니다. 이런 경로가 있으면 \"차분 공격\"이 가능합니다."));
C.push(h2("1.6 지뢰찾기 규칙"));
C.push(p("지뢰찾기에서 숫자 칸은 **주변 8칸에 있는 지뢰의 수**를 나타냅니다. 아래 예에서 가운데 칸(■)의 주변에는 지뢰(1)가 3개 있으므로 숫자는 3입니다."));
C.push(neighborhood({ nb: [[1, 0, 0], [1, 0, 0], [0, 1, 0]] }));
C.push(caption("가운데 칸의 주변 지뢰 수 = 3"));
C.push(p("MineLock은 이 \"주변 지뢰 수 세기\"를 암호 연산의 핵심으로 사용합니다."));

// ---------- 2장 ----------
C.push(h1("2. 1차 설계와 문제점"));
C.push(h2("2.1 1차 설계 요약"));
C.push(p("1차 설계는 **Feistel 구조**를 사용했습니다. 16바이트 블록을 왼쪽(L)과 오른쪽(R) 8바이트로 나눈 뒤, 매 라운드 R과 라운드 키로 F 함수를 계산해 L에 XOR하고 좌우를 바꿉니다. 이것을 16번 반복합니다."));
C.push(...code(["L(i) = R(i-1)", "R(i) = L(i-1) ⊕ F(R(i-1), K(i))"]));
C.push(pk("F 함수는 다음 4단계였습니다."));
C.push(...table(["단계", "내용"], [
  ["1. 키 혼합", "R(8바이트) ⊕ 라운드 키 K"],
  ["2. 8×8 그리드", "64비트를 8×8 판으로 펼침 (1 = 지뢰, 0 = 빈칸)"],
  ["3. 인접 숫자 변환", "지뢰 칸은 F, 빈칸은 주변 지뢰 수(0~8)로 바꿈"],
  ["4. 세로 XOR 폴딩", "32바이트가 된 숫자 맵을 세로로 XOR해 8바이트로 줄임"],
], [2600, 7038]));
C.push(p("키 스케줄은 비밀키를 SHA-256으로 해시해 8×8 지뢰맵(지뢰 10개)을 만들고, 빈칸이 연쇄적으로 열리는 순서(BFS)를 HMAC-SHA256에 넣어 라운드 키 16개를 만들었습니다."));
C.push(h2("2.2 1차 발표 피드백"));
C.push(bullet("단순한 Feistel 구조에서 변화를 주는 것이 좋겠다."));
C.push(bullet("F 함수에서 어떤 부분이 치환이고 어떤 부분이 전치인지 구체적으로 명시해야 한다."));
C.push(h2("2.3 실험으로 확인한 문제"));
C.push(h3("문제 ① 인접 숫자 맵이 입력을 그대로 드러낸다"));
C.push(pk("1차 보고서 예시의 1행(0x60)을 보면, 인접 숫자 맵에서 F가 있는 자리만 1로 읽으면 입력이 그대로 복원됩니다."));
C.push(...code(["입력       : 0 1 1 0 0 0 0 0   (0x60)", "인접 숫자  : 2 F F 3 3 2 1 0", "F 위치 읽기: 0 1 1 0 0 0 0 0   → 0x60 그대로 복원"]));
C.push(p("실제 지뢰찾기가 어려운 이유는 지뢰 위치가 **가려져 있기** 때문인데, 1차 설계는 지뢰를 F로 **표시**해 버렸습니다. 그래서 \"지뢰 위치 역추론은 어렵다(NP-완전)\"는 주장이 이 구조에서는 성립하지 않습니다."));
C.push(h3("문제 ② F 출력의 4분의 1이 사실상 선형이다"));
C.push(p("각 칸 값(4비트)의 최상위 비트(8의 자리)는 칸이 지뢰(F = 1111)이거나 주변 8칸이 모두 지뢰(8 = 1000)일 때만 1입니다. 후자는 매우 드물기 때문에, 이 비트는 거의 항상 **그 칸의 입력 비트와 같습니다**. 세로 XOR 폴딩을 거쳐도 이 관계가 남아서, F 출력 64비트 중 **16비트가 입력 비트 4개의 XOR과 99.4~100% 일치**했습니다(무작위 입력 20,000개로 측정). 가장자리 칸은 이웃이 5칸뿐이라 8이 나올 수 없어 정확히 100%였습니다."));
C.push(h3("문제 ③ 전치가 없고, 키 스케줄의 지뢰찾기 요소가 장식에 가깝다"));
C.push(bullet("F 함수 안에 비트 위치를 옮기는 단계가 없습니다. 위치가 바뀌는 것은 Feistel의 좌우 교환뿐입니다."));
C.push(bullet("키 스케줄의 HMAC은 이미 비밀키(시드)를 키로 쓰기 때문에, BFS 순서를 빼도 라운드 키의 안전성은 똑같습니다."));
C.push(...callout("개선 방향", [
  "• Feistel 대신, 매 라운드 **블록 전체**를 바꾸는 구조로 바꾼다.",
  "• 지뢰찾기 규칙을 **명확한 치환(MineSub)**으로, 비트 재배치를 **명확한 전치(MinePerm)**로 분리한다.",
  "• 키 스케줄도 **같은 지뢰판 연산**으로 만든다.",
]));

// ---------- 3장 ----------
C.push(h1("3. v3 설계 한눈에 보기"));
C.push(...table(["항목", "내용"], [
  ["구조", "SPN (치환-전치 반복 구조, AES와 같은 계열)"],
  ["블록", "128비트 = **8행 × 16열 지뢰판**"],
  ["비밀키", "길이 제한 없음 → SHA-256 해시의 앞 128비트 사용"],
  ["라운드 수", "16"],
  ["한 라운드", "키 섞기(⊕ K) → **MineSub × 2**(치환) → **MinePerm**(전치)"],
  ["키 스케줄", "지뢰판 진화: 라운드 키마다 지뢰판을 **2번 진화**(Evolve = MineSub × 2 → MinePerm)시키고 라운드 상수 RC를 XOR"],
  ["라운드 키", "K0 ~ K16, 17개 × 128비트 (마지막 K16은 끝에 한 번 더 섞음)"],
  ["운용 모드", "CBC + PKCS#7 패딩 (1차와 동일)"],
], [2400, 7238]));
C.push(p("**SPN**(Substitution-Permutation Network)은 치환과 전치를 반복하는 구조입니다. 블록의 절반만 F 함수를 거치는 Feistel과 달리, **매 라운드 128비트 전체가 바뀝니다**. 대신 모든 단계가 되돌릴 수 있는 연산이어야 하는데, MineSub와 MinePerm은 모두 되돌릴 수 있게 설계했습니다(4장)."));
C.push(image("암호화 구성도_v3.png", 520, "v3 암호화 전체 구성도"));
C.push(caption("그림 1. v3 암호화 전체 구성도"));

// ---------- 4장 ----------
C.push(h1("4. 구성 요소 자세히 보기"));
C.push(h2("4.1 지뢰판"));
C.push(p("16바이트 블록을 한 행에 2바이트(16비트)씩 8행으로 펼칩니다. 비트 1은 지뢰, 0은 빈칸입니다."));
C.push(p("판의 **위아래와 좌우는 서로 이어져 있다**고 봅니다. 맨 오른쪽 칸의 오른쪽 이웃은 같은 행의 맨 왼쪽 칸이고, 맨 위 행의 위쪽 이웃은 맨 아래 행입니다(도넛 모양). 이렇게 하면 **모든 칸의 이웃이 정확히 8개**가 됩니다. 1차 설계에서는 가장자리 칸의 이웃이 5개뿐이라 문제 ②의 100% 일치가 생겼습니다."));
C.push(h2("4.2 키 섞기 (⊕ K)"));
C.push(p("라운드 키도 같은 크기의 8×16 판입니다. 두 판을 겹쳐 XOR하면 **키 판에서 1인 칸만 지뢰↔빈칸이 뒤집힙니다**. 키를 모르는 사람은 이후의 판 상태를 알 수 없게 됩니다."));
C.push(h2("4.3 MineSub — 지뢰찾기 규칙으로 칸 뒤집기 (치환)"));
C.push(p("MineSub는 Mine(지뢰) + Substitution(치환)에서 따온 이름입니다. 판의 **값**을 바꾸는 단계입니다."));
C.push(...callout("MineSub 한눈에 보기", [
  "• **입력과 출력**: 8×16 지뢰판(128비트) → 8×16 지뢰판(128비트). 칸의 위치는 그대로이고 **값(지뢰/빈칸)만** 바뀝니다.",
  "• **하는 일**: 칸마다 주변 지뢰 수를 세어, 그 수가 0·3·4·8이면 그 칸을 뒤집습니다.",
  "• **핵심 두 가지**: ① 칸들을 4색으로 나눠 **색 순서대로** 처리하고, 앞 색에서 바뀐 값은 다음 색을 처리할 때 **바로 반영**됩니다. ② 이 순서 덕분에 **되돌릴 수 있습니다**.",
  "• **어디에 쓰이나**: 암호화 라운드(라운드마다 2번)와 키 스케줄(진화 한 번에 2번). 5.1절 ③에서 실제 값으로 한 단계씩 보여 줍니다.",
]));
C.push(h3("규칙"));
C.push(...steps([
  "판의 칸을 (행 번호의 홀짝, 열 번호의 홀짝)에 따라 **4가지 색**으로 나눕니다.",
  "**색 0 → 1 → 2 → 3** 순서로 진행합니다.",
  "해당 색의 각 칸에서 **주변 8칸의 지뢰 수 c**를 셉니다.",
  "**c가 0, 3, 4, 8 중 하나이면 그 칸을 뒤집고**(지뢰↔빈칸), 아니면 그대로 둡니다.",
]));
const COLOR_FILL = ["7F93F5", "D3DAFC", "F0A060", "FBDCC4"];
{
  const W = Math.floor(9638 / 8), widths = Array(8).fill(W);
  const rows = [0, 1, 2, 3].map((i) => new TableRow({ children: widths.map((w, j) => {
    const c = (i % 2) * 2 + (j % 2);
    return cell(`색 ${c}`, w, { fill: COLOR_FILL[c], align: AlignmentType.CENTER, size: 18 });
  }) }));
  C.push(new Table({ width: { size: W * 8, type: WidthType.DXA }, columnWidths: widths, rows }));
  C.push(caption("4색 분할 (판의 일부). 어떤 칸이든 주변 8칸은 모두 자기와 다른 색이다."));
}
C.push(h3("왜 한꺼번에 바꾸지 않고 색을 나누나요?"));
C.push(p("모든 칸을 동시에 바꾸면 내 이웃도 동시에 바뀝니다. 그러면 복호화할 때 내가 셌던 주변 지뢰 수를 다시 셀 방법이 없어서 원래대로 되돌릴 수 없습니다."));
C.push(p("4색으로 나누면 **같은 색 칸끼리는 절대 이웃이 아닙니다**. 그래서 색 0 칸들을 바꾸는 동안, 색 0 칸들이 세는 이웃(색 1·2·3)은 하나도 바뀌지 않습니다."));
C.push(h3("왜 되돌릴 수 있나요? (복호화 원리)"));
C.push(...steps([
  "같은 칸을 두 번 뒤집으면 원래대로 돌아옵니다.",
  "복호화는 색 **3 → 2 → 1 → 0** 역순으로 진행합니다.",
  "색 0을 되돌릴 차례가 되면 색 1·2·3은 이미 원래 상태로 돌아와 있으므로, 색 0 칸들의 주변 지뢰 수 c가 암호화 때와 **똑같이** 세어집니다.",
  "같은 c이므로 같은 칸이 다시 뒤집히고, 원래 값이 복원됩니다.",
]));
C.push(h3("왜 하필 {0, 3, 4, 8}인가요?"));
C.push(p("c는 0~8 중 하나이므로 \"어떤 값일 때 뒤집을지\" 고르는 방법은 2⁹ = 512가지입니다. 이것을 모두 검사해서 다음 두 조건을 가장 잘 만족하는 규칙을 골랐습니다."));
C.push(bullet("**균형**: 무작위 판에서 뒤집힐 확률이 정확히 반반이어야 합니다."));
C.push(bullet("**예측 어려움**: 결과를 입력 비트의 XOR로 맞힐 수 있는 정도(선형 편향)가 가장 작아야 합니다."));
C.push(...table(["규칙 (c가 이 값이면 반전)", "균형", "최대 선형 편향", "평가"], [
  ["**{0, 3, 4, 8}**", "예", "1/16", "**채택**"],
  ["{1, 2, 3, 6, 7}", "예", "1/16", "같은 수준"],
  ["{0, 2, 4, 6, 8} (짝수)", "예", "1/2", "완전 선형 — 사용 금지"],
], [3400, 1400, 2200, 2638], { rowFill: (r) => (r === 0 ? "E7EBFF" : undefined) }));
C.push(p("\"c가 짝수면 뒤집기\"는 결과가 주변 8칸의 단순 XOR과 같아서 쉽게 예측됩니다. 참고로 1차 설계 F 함수의 상위 비트는 편향이 약 1/2(거의 항상 예측 가능)이었습니다."));
C.push(h3("왜 라운드마다 두 번 하나요?"));
C.push(p("MineSub에서 각 칸은 **'자기 값 ⊕ h(이웃)'**으로 바뀌므로, 어떤 칸에 차이가 있으면 그 차이는 그 칸에 항상 남습니다. 주변 칸들이 우연히 반응하지 않으면 1비트 차이가 그대로 다음 라운드로 넘어가는데, 이것이 검토에서 지적된 차분 경로입니다(6.3절). MineSub를 2번 하면 이 우연이 한 라운드 안에서 두 번 연속 일어나야 하므로 확률이 크게 줄어듭니다."));
C.push(...table(["항목", "MineSub 1회 (이전 시제품)", "MineSub 2회 (v3)"], [
  ["1라운드 뒤 1비트 차이 유지 확률", "약 2^-6.3", `**약 2^-${T1.toFixed(1)}**`],
  ["16라운드로 이었을 때", "약 2^-102 (2^-128보다 큼 → 부족)", `**약 2^-${Math.round(T16)}**`],
  ["확산 50% 도달", "5라운드", `**${[1, 2, 3, 4, 5].find((r) => AV[r].avg >= 49.5)}라운드**`],
  ["블록당 암호화 시간 (Python)", "4.2 ms (시제품)", `${M.block_ms.toFixed(1)} ms (비트 연산 구현)`],
], [3600, 3000, 3038]));
C.push(image("라운드 함수 구성도_v3.png", 560, "v3 라운드 함수 구성도"));
C.push(caption("그림 2. v3 라운드 함수 구성도 (MineSub의 ①~④를 2번 반복)"));
C.push(h2("4.4 MinePerm — 칸 위치 섞기 (전치)"));
C.push(p("MinePerm은 Mine + Permutation(전치)에서 따온 이름입니다. 값은 그대로 두고 **위치만** 옮깁니다."));
C.push(...callout("MinePerm 한눈에 보기", [
  "• **입력과 출력**: 8×16 지뢰판 → 8×16 지뢰판. 지뢰 개수와 각 칸의 값은 그대로이고 **자리만** 바뀝니다.",
  "• **하는 일**: ① 각 행을 옆으로 돌린 뒤 ② 각 열을 아래로 돌립니다. 돌리는 칸 수는 행·열 번호로 정해진 고정값이라 키와 무관합니다.",
  "• **왜 필요한가**: MineSub는 바로 옆 칸끼리만 영향을 주므로, 칸을 멀리 흩어야 변화가 판 전체로 퍼집니다.",
  "• **어디에 쓰이나**: 암호화 라운드와 키 스케줄의 진화마다 한 번. 5.1절 ③에서 실제 값으로 보여 줍니다.",
]));
C.push(...steps([
  "**행 회전**: i번째 행을 오른쪽으로 (3i + 1)칸 돌립니다.",
  "**열 회전**: 각 열을 (새) 열 번호만큼 아래로 돌립니다.",
]));
C.push(...code(["새 열 j' = (j + 3i + 1) mod 16", "새 행 i' = (i + j')    mod 8"]));
C.push(...table(["원래 위치 (행, 열)", "계산", "이동 후 위치"], [
  ["(0, 0)", "j' = 0+0+1 = 1,  i' = 0+1 = 1", "(1, 1)"],
  ["(1, 0)", "j' = 0+3+1 = 4,  i' = 1+4 = 5", "(5, 4)"],
  ["(7, 15)", "j' = (15+22) mod 16 = 5,  i' = (7+5) mod 8 = 4", "(4, 5)"],
], [2400, 4838, 2400]));
C.push(h3("왜 필요한가요?"));
C.push(p("MineSub는 **바로 옆 8칸**의 영향만 받습니다. 위치를 섞지 않으면 같은 이웃끼리만 계속 영향을 주고받아, 1비트의 변화가 판 전체로 퍼지지 않습니다. MinePerm이 칸을 멀리 흩어 놓아야 다음 라운드에서 새로운 이웃과 섞입니다. 128칸이 서로 겹치지 않게 1:1로 옮겨지므로, 반대 방향으로 옮기면 그대로 되돌릴 수 있습니다."));
C.push(h2("4.5 키 스케줄 — 지뢰판을 진화시켜 라운드 키 만들기"));
C.push(pk("키 없는 라운드(MineSub × 2 → MinePerm)를 **Evolve(진화)**라고 부르면, 키 스케줄은 다음과 같습니다."));
C.push(...code([
  "B(0)  = SHA-256(비밀키)의 앞 128비트                → K0",
  "B(1)  = Evolve(Evolve(B(0)))  ⊕ RC(1)              → K1",
  "B(2)  = Evolve(Evolve(B(1)))  ⊕ RC(2)              → K2",
  "  ...",
  "B(16) = Evolve(Evolve(B(15))) ⊕ RC(16)             → K16",
]));
C.push(p("비밀키로 만든 첫 지뢰판에 **데이터에 쓰는 것과 똑같은 연산**을 적용해 진행시키고, 각 단계의 판을 라운드 키로 씁니다. RC(r)은 `SHA-256(\"MineLock_RC\" ∥ r)`의 앞 128비트로 정한 라운드 상수입니다."));
C.push(bullet("**동치 키가 없음**: Evolve는 되돌릴 수 있는 연산이라, 서로 다른 첫 지뢰판이 같은 라운드 키를 만들지 않습니다."));
C.push(bullet("**부품 재사용**: 데이터 경로의 연산을 키 스케줄에도 쓰는 방식은 AES의 키 스케줄과 같은 아이디어입니다."));
C.push(bullet("**라운드 상수 RC**: 라운드마다 판을 다르게 만들어, 모든 라운드가 똑같아지는 약점(Slide 공격)을 막습니다."));
C.push(bullet(`**진화를 2번씩 하는 이유**: 1번만 하면 초기 라운드 키끼리 너무 비슷했습니다(첫 판 1비트 변경 시 K1 5.6%, K2 22.1%만 바뀜). 2번씩 하면 K1부터 평균 ${pct(RK[0].avg)}, K2부터 약 ${pct(RK[1].avg)}가 바뀝니다.`));
C.push(h2("4.6 복호화"));
C.push(p("복호화는 암호화의 단계를 **역순으로, 각 단계의 역연산**으로 수행합니다."));
C.push(...steps([
  "암호문에 K16을 XOR합니다.",
  "라운드 16부터 1까지 거꾸로, 각 라운드마다 **역 MinePerm** (열을 위로, 행을 왼쪽으로) → **역 MineSub × 2** (색 3 → 2 → 1 → 0 순서로 같은 반전 규칙, 이것을 2번) → **라운드 키 XOR**을 수행합니다.",
  "CBC를 해제하고 패딩을 제거합니다.",
]));
C.push(image("복호화 구성도_v3.png", 470, "v3 복호화 전체 구성도"));
C.push(caption("그림 3. v3 복호화 전체 구성도"));
C.push(image("역라운드 함수 구성도_v3.png", 560, "v3 역라운드 함수 구성도"));
C.push(caption("그림 4. v3 역라운드 함수 구성도"));

// ---------- 5장: HELLO 예시 ----------
const E = D.enc, KS = D.ks, DEC = D.dec;
C.push(h1("5. 실제 예시: HELLO 암호화와 복호화"));
C.push(p("평문 **HELLO**를 비밀키 **YSKL**로 암호화하고 다시 복호화하는 과정을, 그림 1과 그림 3의 상자 순서대로 따라가 봅니다."));
C.push(p("MineSub와 MinePerm은 키 스케줄과 암호화 라운드에서 계속 반복해서 쓰입니다. 그래서 **처음 등장하는 5.1절 ③(K1 만들기)에서 두 함수가 실제 값으로 어떻게 동작하는지 한 단계씩 자세히** 보여 주고, 그 뒤로는 같은 동작이므로 **결과만** 보여 줍니다. 복호화에서는 처음 나오는 역연산인 역라운드 16을 자세히 보여 줍니다."));
C.push(...table(["항목", "값"], [
  ["평문", "HELLO"],
  ["비밀키", "YSKL"],
  ["IV", `${D.iv}  (예시를 위해 고정한 값. 실제로는 암호화할 때마다 무작위로 생성)`],
], [1800, 7838], { mono: (i) => false }));

// 5.1 키 스케줄
C.push(h2("5.1 키 스케줄: 비밀키 → 라운드 키 17개 (그림 1 오른쪽 열)"));
C.push(h3("① 비밀키 → SHA-256 해시"));
C.push(pk("비밀키 YSKL(바이트 `59 53 4B 4C`)을 SHA-256으로 해시하면 32바이트가 나옵니다. 이 중 **앞 16바이트(128비트)**만 사용합니다."));
{
  const h = D.sha256.match(/../g);
  C.push(...code([`SHA-256("YSKL") = ${h.slice(0, 16).join(" ")}   ← 사용`, `                  ${h.slice(16).join(" ")}   ← 버림`]));
}
C.push(h3("② 초기 지뢰판 B(0) 생성 → K0"));
C.push(pk("앞 16바이트를 8×16 지뢰판으로 펼친 것이 **첫 지뢰판 B(0)**이고, 이 판이 그대로 **첫 라운드 키 K0**이 됩니다."));
C.push(...code([`B(0) = K0 = ${KS.B0.hex}`], true));
C.push(...board(KS.B0.grid, { labels: rowLabels(KS.B0.hex) }));
C.push(legend(LEG_MINE));
C.push(h3("③ 지뢰판 진화 → K1 (MineSub·MinePerm 자세히)"));
const DT = KS.detail;
C.push(p("K1은 B(0)에 **Evolve(MineSub → MineSub → MinePerm)를 2번** 적용한 뒤 RC(1)을 XOR해서 만듭니다. 여기가 5장에서 MineSub와 MinePerm이 처음 쓰이는 곳이므로, **진화 1회차를 한 단계씩 자세히** 따라가 봅니다."));
C.push(...code([
  "B(0) ─[MineSub 1번째]─[MineSub 2번째]─[MinePerm]─▶ 진화 1회차 결과   ← (가)~(다) 자세히",
  "     ─[MineSub 1번째]─[MineSub 2번째]─[MinePerm]─▶ 진화 2회차 결과   ← (라) 결과만",
  "     ─[⊕ RC(1)]─▶ K1                                                  ← (마)",
]));

// (가) MineSub 1번째
C.push(h4("(가) MineSub 1번째 — 입력: B(0)"));
C.push(p("MineSub는 판의 칸을 4가지 색으로 나눠 **색 0 → 1 → 2 → 3 순서로** 처리합니다. 각 단계에서는 그 색의 칸 32개만 검사하고, 다른 색 칸은 건드리지 않습니다. 각 칸에서 하는 일은 하나입니다."));
C.push(...code(["주변 8칸의 지뢰 수 c를 센다 → c가 0, 3, 4, 8 중 하나면 그 칸을 뒤집는다(0↔1), 아니면 그대로 둔다"]));
C.push(p("**[색 0 단계]** 짝수 행·짝수 열의 칸들입니다. 판의 위아래·좌우가 이어져 있으므로 (행0, 열0)의 위쪽 이웃은 행7, 왼쪽 이웃은 열F입니다. 두 칸을 예로 들면 다음과 같습니다(가운데 ■가 검사하는 칸)."));
C.push(...exampleCells(DT.examples.slice(0, 2)));
C.push(pk(`같은 방식으로 색 0의 32칸을 모두 검사하면 **${DT.sub1_steps[0].flips}칸**이 뒤집힙니다. 주황색이 이번에 뒤집힌 칸입니다.`));
C.push(...board(DT.s0_after.grid, { mark: DT.sub1_steps[0].cells }));
C.push(legend(LEG_CHANGED));
{
  const ex = DT.examples[2];
  const markedNow = (ex.marks || []).map(([a, b]) => ex.nb[a][b]);
  const cOld = ex.c - markedNow.reduce((s, v) => s + v, 0) + markedNow.reduce((s, v) => s + (1 - v), 0);
  const oldFlip = [0, 3, 4, 8].includes(cOld);
  C.push(p(`**[색 1 단계]** 짝수 행·홀수 열의 칸들입니다. 여기서 중요한 점은 **색 0 단계에서 바뀐 값을 그대로 반영해서 센다**는 것입니다. 아래 (행${ex.cell[0]}, 열${HEXCOL[ex.cell[1]]})의 주황색 이웃은 방금 색 0 단계에서 뒤집힌 칸입니다.`));
  C.push(...exampleCells([ex]));
  C.push(p(`바뀐 값으로 세면 c = ${ex.c}이므로 ${ex.flip ? "뒤집힙니다" : "그대로 둡니다"}. 만약 색 0 단계 **전** 값으로 셌다면 c = ${cOld}가 되어 ${oldFlip ? "뒤집혔을" : "그대로였을"} 것입니다. 이렇게 앞 색의 결과가 다음 색에 영향을 주기 때문에, 한 번의 MineSub 안에서도 변화가 퍼져 나갑니다.`));
}
C.push(pk(`색 1에서는 **${DT.sub1_steps[1].flips}칸**이 뒤집힙니다.`));
C.push(...board(DT.sub1_steps[1].board.grid, { mark: DT.sub1_steps[1].cells }));
C.push(legend(LEG_CHANGED));
C.push(p(`**[색 2, 색 3 단계]** 같은 방식으로 홀수 행·짝수 열(색 2), 홀수 행·홀수 열(색 3)을 차례로 처리하면 각각 ${DT.sub1_steps[2].flips}칸, ${DT.sub1_steps[3].flips}칸이 뒤집힙니다.`));
C.push(...colorTable([DT.sub1_steps], ["반전된 칸 수"]));
C.push(pk("MineSub 1번째의 최종 결과입니다. 주황색은 B(0)과 비교해 바뀐 칸 전체입니다."));
C.push(...code([`= ${DT.sub1_out.hex}`], true));
C.push(...board(DT.sub1_out.grid, { mark: DT.sub1_changed }));
C.push(legend(LEG_CHANGED));
C.push(...callout("되돌릴 수 있는 이유 (복호화 미리 보기)", [
  "색 3 단계에서 뒤집힌 칸들의 주변 8칸은 모두 색 0·1·2이고, 색 3 단계 동안에는 바뀌지 않았습니다. 그래서 색 3 단계가 끝난 판에서 같은 칸들의 주변 지뢰 수를 다시 세면 **똑같은 c**가 나오고, 같은 칸들을 한 번 더 뒤집으면 색 3 단계 전으로 돌아갑니다. 이것을 색 3 → 2 → 1 → 0 순서로 하면 MineSub 전체가 되돌려집니다.",
]));

// (나) MineSub 2번째
C.push(h4("(나) MineSub 2번째 — 입력: MineSub 1번째 결과"));
C.push(pk("규칙과 순서는 1번째와 **똑같습니다**. 다만 1번째에서 칸들이 바뀌어 주변 지뢰 수가 달라졌으므로, 이번에는 다른 칸들이 뒤집힙니다."));
C.push(...colorTable([DT.sub2.colors], ["반전된 칸 수"]));
C.push(...code([`= ${DT.sub2.after.hex}`], true));
C.push(...board(DT.sub2.after.grid, { mark: DT.sub2.changed }));
C.push(legend(LEG_CHANGED));

// (다) MinePerm
{
  const re = DT.row_example, ce = DT.col_example;
  C.push(h4("(다) MinePerm — 입력: MineSub 2번째 결과"));
  C.push(p("MinePerm은 값은 그대로 두고 **자리만** 옮깁니다. 두 단계로 이루어집니다."));
  C.push(p(`**[① 행 회전]** i번째 행을 오른쪽으로 (3i + 1)칸 돌립니다. 행 0은 1칸, 행 1은 4칸, 행 2는 7칸 … 행 7은 22 mod 16 = 6칸입니다. 오른쪽 끝을 넘어간 칸은 왼쪽 끝으로 돌아옵니다. 예를 들어 행 ${re.row}을 오른쪽으로 ${re.shift}칸 돌리면, 맨 오른쪽 ${re.shift}칸(주황색)이 맨 앞으로 옵니다.`));
  const n = re.before.length;
  C.push(...bitStrip([
    [`행 ${re.row} (돌리기 전)`, re.before, new Set(Array.from({ length: re.shift }, (_, k) => n - re.shift + k))],
    [`행 ${re.row} (오른쪽 ${re.shift}칸)`, re.after, new Set(Array.from({ length: re.shift }, (_, k) => k))],
  ], 460));
  C.push(pk("8개 행을 모두 돌린 결과입니다."));
  C.push(...board(DT.rows.grid));
  C.push(legend(LEG_MINE));
  C.push(p(`**[② 열 회전]** 각 열을 열 번호만큼 아래로 돌립니다(행이 8개이므로 열 j는 j mod 8칸). 열 0은 그대로, 열 1은 1칸 … 열 8은 다시 0칸입니다. 아래쪽 끝을 넘어간 칸은 위로 돌아옵니다. 예를 들어 열 ${ce.col}을 아래로 ${ce.shift}칸 돌리면 다음과 같습니다(가로로 눕혀서 표시, 왼쪽이 행 0).`));
  C.push(...bitStrip([
    [`열 ${ce.col} (돌리기 전)`, ce.before, new Set([4, 5, 6, 7])],
    [`열 ${ce.col} (아래로 ${ce.shift}칸)`, ce.after, new Set([0, 1, 2, 3])],
  ], 700));
  C.push(pk("16개 열을 모두 돌린 결과가 **진화 1회차 결과**입니다."));
  C.push(...code([`= ${DT.cols.hex}`], true));
  C.push(...board(DT.cols.grid));
  C.push(legend(LEG_MINE));
  C.push(pk("두 단계를 합치면 각 칸이 어디로 가는지 공식으로 쓸 수 있습니다. 실제 값으로 확인해 보면 다음과 같습니다."));
  C.push(...table(["원래 위치", "① 행 회전 후", "② 열 회전 후", "그 칸의 값"], DT.map_examples.map(([a, b, v]) => {
    const j2 = (a[1] + 3 * a[0] + 1) % 16;
    return [`(행${a[0]}, 열${HEXCOL[a[1]]})`, `(행${a[0]}, 열${HEXCOL[j2]})`, `(행${b[0]}, 열${HEXCOL[b[1]]})`, String(v)];
  }), [2400, 2400, 2400, 2438]));
}

// (라) 진화 2회차
C.push(h4("(라) 진화 2회차"));
C.push(pk("진화 1회차 결과에 (가)~(다)를 **똑같이 한 번 더** 적용합니다. 동작은 같으므로 결과만 적습니다."));
C.push(...code([`진화 2회차 결과 : ${KS.step2_out}`]));
C.push(h4("(마) 라운드 상수 XOR → K1"));
C.push(...code([`  ${KS.step2_out}   (진화 2회차 결과)`, `⊕ ${KS.RC1}   (RC1)`, `= ${KS.K1.hex}   = K1`], true));
C.push(...board(KS.K1.grid));
C.push(legend(LEG_MINE));
C.push(h3("④ 나머지 라운드 키 K2 ~ K16"));
C.push(pk("같은 과정(진화 2번 → RC XOR)을 반복합니다. 앞 판에서 다음 판이 만들어지므로 순서대로 계산해야 합니다."));
C.push(...table(["라운드 키", "값 (16바이트)", "쓰이는 곳"],
  KS.K.map((k, r) => [`K${r}`, k, r === 16 ? "최종 키 혼합" : `라운드 ${r + 1}`]),
  [1300, 6438, 1900], { size: 18, mono: (i) => i === 1 }));

// 5.2 암호화
C.push(h2("5.2 암호화 (그림 1 왼쪽 열 → 가운데 열)"));
C.push(h3("① 평문 → 바이트 변환과 패딩 (PKCS#7)"));
C.push(pk("HELLO는 `48 45 4C 4C 4F` 5바이트입니다. 16바이트를 채우려면 11바이트가 모자라므로, 값이 11인 `0B`를 11개 붙입니다."));
C.push(...code([E.padded]));
C.push(h3("② 16바이트 블록 분할"));
C.push(p("패딩 결과가 16바이트이므로 블록은 1개(P1)입니다. 평문이 길면 여기서 여러 블록으로 나뉘고, 아래 과정을 블록마다 반복합니다."));
C.push(h3("③ CBC 연결: P1 ⊕ IV"));
C.push(pk("첫 블록은 IV와 XOR합니다(두 번째 블록부터는 바로 앞 암호문 블록과 XOR). 같은 평문이라도 IV가 다르면 전혀 다른 암호문이 나오게 하는 단계입니다."));
C.push(...code([`  ${E.padded}   (P1)`, `⊕ ${D.iv}   (IV)`, `= ${E.p_xor_iv.hex}`]));
C.push(h3("④ 8×16 지뢰판으로 변환"));
C.push(pk("한 행에 2바이트씩 넣습니다. 파란 칸이 지뢰(1)입니다."));
C.push(...board(E.p_xor_iv.grid, { labels: rowLabels(E.p_xor_iv.hex) }));
C.push(legend(LEG_MINE));
C.push(h3("⑤ 라운드 1"));
C.push(p("라운드 1은 **AddRoundKey(⊕ K0) → MineSub → MineSub → MinePerm**입니다. MineSub와 MinePerm의 동작은 5.1절 ③ (가)~(다)에서 본 것과 **완전히 같고**, 입력이 키 판 대신 데이터 판이라는 점만 다릅니다. 그래서 여기서는 각 단계의 결과만 보여 줍니다."));
C.push(h4("[1] AddRoundKey: ⊕ K0"));
C.push(pk("이 단계에서 처음으로 비밀키(에서 나온 K0)가 데이터에 섞입니다."));
C.push(...code([`  ${E.p_xor_iv.hex}`, `⊕ ${KS.K[0]}   (K0)`, `= ${E.r1_xor.hex}`], true));
C.push(...board(E.r1_xor.grid));
C.push(legend(LEG_MINE));
C.push(h4("[2] MineSub × 2"));
C.push(...colorTable([E.r1_sub1.colors, E.r1_sub2.colors], ["MineSub 1번째", "MineSub 2번째"]));
{
  const g0 = E.r1_xor.grid, g2 = E.r1_sub2.after.grid;
  const changed = [];
  g0.forEach((row, i) => row.forEach((v, j) => { if (v !== g2[i][j]) changed.push([i, j]); }));
  C.push(...code([`MineSub 1번째 후 : ${E.r1_sub1.after.hex}`, `MineSub 2번째 후 : ${E.r1_sub2.after.hex}`], true));
  C.push(...board(g2, { mark: changed }));
  C.push(legend(LEG_CHANGED.slice(0, 1).concat([["F4A26B", "[1]과 비교해 바뀐 칸 (지뢰)"], ["FBD9C2", "[1]과 비교해 바뀐 칸 (빈칸)"]])));
}
C.push(h4("[3] MinePerm → 라운드 1 출력"));
C.push(...code([`= ${E.r1_perm.hex}`], true));
C.push(...board(E.r1_perm.grid));
C.push(legend(LEG_MINE));
C.push(h3("⑥ 라운드 2 ~ 16"));
C.push(pk("같은 과정(⊕ K(r-1) → MineSub × 2 → MinePerm)을 15번 더 반복합니다."));
C.push(...table(["라운드", "사용한 키", "라운드 출력"], E.rounds.map((r, i) => [`라운드 ${i + 1}`, `K${i}`, r]), [1500, 1400, 6738], { size: 18, mono: (i) => i === 2 }));
C.push(h3("⑦ 최종 키 혼합: ⊕ K16"));
C.push(...code([`  ${E.rounds[15]}   (라운드 16 출력)`, `⊕ ${KS.K[16]}   (K16)`, `= ${E.c1}   = 암호문 블록 C1`]));
C.push(h3("⑧ 암호문 출력"));
C.push(pk("복호화하는 쪽도 IV가 필요하므로, IV를 암호문 앞에 붙여서 내보냅니다(IV는 비밀이 아닙니다)."));
C.push(...code([`암호문 = IV ∥ C1`, `       = ${D.iv}`, `         ${E.c1}`]));

// 5.3 복호화
C.push(h2("5.3 복호화 (그림 3 순서)"));
C.push(p("복호화는 같은 비밀키 YSKL로 5.1절과 똑같은 라운드 키 K0 ~ K16을 만든 뒤, **역순으로** 사용합니다. 복호화 도중에 나오는 값이 암호화 때의 값과 정확히 같아지는 것을 확인해 봅니다."));
C.push(h3("① IV 분리와 블록 분할"));
C.push(...code([`IV = ${D.iv}`, `C1 = ${E.c1}`]));
C.push(h3("② 최종 키 제거: C1 ⊕ K16"));
C.push(...code([`  ${E.c1}   (C1)`, `⊕ ${KS.K[16]}   (K16)`, `= ${DEC.y}   = 암호화 라운드 16 출력과 같음`]));
C.push(h3("③ 역라운드 16 (자세히)"));
C.push(pk("암호화 라운드 16의 단계(⊕ K15 → MineSub → MineSub → MinePerm)를 **뒤에서부터** 되돌립니다."));
C.push(h4("[1] 역 MinePerm"));
C.push(pk("열을 위로, 행을 왼쪽으로 되돌려 MinePerm 직전 상태를 복원합니다. 이 값은 암호화 라운드 16에서 MineSub 2번째를 마친 직후의 판과 같습니다."));
C.push(...code([`= ${DEC.inv_perm}`], true));
C.push(...board(DEC.inv_perm_board.grid));
C.push(legend(LEG_MINE));
C.push(h4("[2] 역 MineSub (2번째 MineSub 되돌리기)"));
C.push(pk("반전 규칙을 **색 3 → 2 → 1 → 0** 순서로 적용합니다. 각 색에서 뒤집히는 칸은 암호화 때 뒤집혔던 칸과 같습니다."));
C.push(...colorTable([DEC.inv_sub2_colors], ["반전된 칸 수"]));
C.push(...code([`= ${DEC.inv_sub2}   = MineSub 1번째 직후 상태`]));
C.push(h4("[3] 역 MineSub (1번째 MineSub 되돌리기)"));
C.push(...colorTable([DEC.inv_sub1_colors], ["반전된 칸 수"]));
C.push(...code([`= ${DEC.inv_sub1}   = 라운드 16에서 ⊕ K15 직후 상태`]));
C.push(h4("[4] ⊕ K15"));
C.push(...code([`  ${DEC.inv_sub1}`, `⊕ ${KS.K[15]}   (K15)`, `= ${DEC.r15}   = 암호화 라운드 15 출력과 같음`]));
C.push(h3("④ 역라운드 15 ~ 1"));
C.push(pk("같은 방법으로 역라운드 15부터 1까지 진행합니다. 결과가 암호화 때의 값을 거꾸로 되짚어 갑니다."));
C.push(...table(["역라운드", "사용한 키", "결과", "암호화의 같은 값"],
  DEC.inv_rounds.map((v, k) => { const r = 15 - k; return [`역라운드 ${r}`, `K${r - 1}`, v, r === 1 ? "P1 ⊕ IV" : `라운드 ${r - 1} 출력`]; }),
  [1500, 1100, 5038, 2000], { size: 17, mono: (i) => i === 2 }));
C.push(h3("⑤ CBC 해제: ⊕ IV"));
C.push(...code([`  ${E.p_xor_iv.hex}`, `⊕ ${D.iv}   (IV)`, `= ${DEC.after_iv}`]));
C.push(h3("⑥ 패딩 제거 → 평문"));
C.push(p(`마지막 바이트가 \`0B\`(11)이므로 뒤의 11바이트를 지웁니다. 남은 \`48 45 4C 4C 4F\`가 **"${DEC.plaintext}"**입니다. 원래 평문이 정확히 복원됩니다.`));

// 5.4 1비트
C.push(h2("5.4 평문을 1비트만 바꾸면"));
C.push(pk(`마지막 글자를 O(4F = 0100 1111)에서 N(4E = 0100 1110)으로 바꾸면 평문이 **정확히 1비트** 달라집니다. 이 **HELLN**을 같은 키와 IV로 암호화하면, 암호문 블록 128비트 중 **${D.avalanche.diff}비트(${(D.avalanche.diff / 1.28).toFixed(0)}%)**가 바뀝니다.`));
C.push(...code([`HELLO → ${D.avalanche.ct}`, `HELLN → ${D.avalanche.ct2}`]));

// ---------- 6장 ----------
C.push(h1("6. 검증 결과"));
C.push(p("모든 수치는 `tools/measure_v3.py`로 `mines_cipher_v3.py`를 측정한 값입니다(1차 설계 값은 `mines_cipher_v2.py` 실행 결과)."));
C.push(h2("6.1 1차 설계와 v3 비교"));
C.push(...table(["항목", "1차 설계", "v3"], [
  ["구조", "Feistel 16라운드", "지뢰판 SPN 16라운드"],
  ["치환", "인접 숫자 맵 (상위 비트 선형 누출)", "MineSub × 2 (단계당 최대 편향 1/16)"],
  ["전치", "없음 (L/R 교환만)", "MinePerm (행·열 회전)"],
  ["키 스케줄", "BFS 순서 + HMAC-SHA256", "지뢰판 진화 (라운드 키마다 Evolve 2번)"],
  ["치환 출력의 선형 일치율", "99.4 ~ 100% (64비트 중 16비트)", `**${M.lin_agree.min.toFixed(1)} ~ ${M.lin_agree.max.toFixed(1)}% (128비트 전체)**`],
  ["1비트 차분 유지 확률 (라운드당)", "—", `약 2^-${T1.toFixed(1)}`],
  ["평문 1비트 변경 시 변화율 (16라운드)", "49.43%", `${AV["16"].avg.toFixed(2)}%`],
  ["키 1비트 변경 시 변화율", "54.69% (1회 측정)", `${M.keysens.avg.toFixed(2)}% (${M.keysens.n.toLocaleString()}회 평균)`],
  ["가역성 (무작위 1,000회)", "1,000 / 1,000", `${1000 - M.invert_fail} / 1,000`],
  ["속도 (Python)", "—", `블록당 ${M.block_ms.toFixed(1)} ms, 키 스케줄 ${M.ks_ms.toFixed(1)} ms`],
], [3200, 3219, 3219]));
C.push(p("선형 일치율은 1차 설계는 F 함수 출력, v3는 MineSub 한 번의 출력을 기준으로 측정했습니다. 50%에 가까울수록 출력 비트를 입력 비트로 예측할 수 없다는 뜻입니다. 키 1비트 변경은 첫 지뢰판 B(0)의 비트를 하나씩 바꿔 측정했습니다."));
C.push(h2("6.2 라운드 수에 따른 확산"));
C.push(pk("평문 1비트를 바꿨을 때 암호문이 바뀌는 비율을 라운드 수별로 측정했습니다(키 20개 × 비트 위치 128개의 평균)."));
const AVR = ["1", "2", "3", "4", "5", "6", "8", "16"];
C.push(...table(["라운드 수"].concat(AVR), [["평균 변화율"].concat(AVR.map((r) => pct(AV[r].avg)))], [1638].concat(Array(8).fill(1000))));
C.push(p(`**${[1, 2, 3, 4, 5].find((r) => AV[r].avg >= 49.5)}라운드**에서 평균 변화율이 50%에 도달합니다. 다만 이것은 확산이 빠르다는 뜻일 뿐, **몇 라운드면 안전한지에 대한 근거는 아닙니다**. 라운드 수의 근거는 6.3절의 차분·선형 분석으로 만들어야 합니다.`));
C.push(h2("6.3 알려진 약점과 남은 과제"));
C.push(p("검토 과정에서 지적된 약점과, 이를 시제품·정식 구현으로 확인하고 대응한 내용입니다. 심각한 순서로 정리했습니다."));
C.push(h3("① 여러 라운드에 걸친 차분 경로 — 일부 대응"));
C.push(p("**차분 공격**은 두 평문의 차이가 암호화를 거치며 어떤 차이로 바뀌는지, 그 확률을 이용하는 공격입니다. MineSub에서는 각 칸이 '자기 값 ⊕ h(이웃)'으로 바뀌어 자기 칸의 차이가 항상 남기 때문에, 1비트 차이가 그대로 다음 라운드로 넘어가는 경로가 있었습니다."));
C.push(...table(["설계", "라운드당 1비트 유지 확률", "16라운드", "판정 (기준 2^-128)"], [
  ["MineSub 1회 (이전 시제품)", "약 2^-6.3 (10만 쌍)", "약 2^-102", "부족"],
  ["**MineSub 2회 (v3)**", `약 2^-${T1.toFixed(1)} (${M.trail1.n.toLocaleString()}쌍 중 ${M.trail1.hits}쌍)`, `약 2^-${Math.round(T16)}`, `통과 (이 경로만 보면 ${T_NEED}라운드부터)`],
], [2800, 2900, 1500, 2438]));
C.push(p("다만 자기 칸의 차이가 통과하는 **구조 자체는 그대로**이고, 여러 비트 차이로 이어지는 다른 경로와 선형 경로는 아직 분석하지 않았습니다. 따라서 \"이 경로에 대해서는 16라운드로 충분하다\"까지만 말할 수 있습니다."));
C.push(h3("② 키 스케줄 — 일부 대응"));
C.push(p(`진화를 라운드 키마다 2번씩 하도록 바꿔서, 초기 라운드 키의 확산이 느리던 문제(K1 5.6%, K2 22.1%, K3 44.0%)를 K1 ${pct(RK[0].avg)}, K2 ${pct(RK[1].avg)}, K3 ${pct(RK[2].avg)}로 개선했습니다. 그러나 진화가 되돌릴 수 있는 연산이므로 **라운드 키 하나만 알면 나머지 라운드 키와 첫 지뢰판을 모두 복원**할 수 있다는 성질은 그대로입니다. AES-128도 같은 성질이라 단일 키 환경에서는 흔한 구조입니다.`));
C.push(h3("③ 대수 차수·적분 공격 — 미분석"));
C.push(p("반전 규칙 h를 이웃 8비트의 다항식(AND와 XOR)으로 쓰면 **대수 차수는 7**입니다(최대 8). 한 단계의 차수는 높지만, 라운드를 거치며 차수가 얼마나 빨리 늘어나는지와 적분 공격에 대한 분석은 아직 하지 않았습니다."));
C.push(h3("④ 독창성의 위치"));
C.push(p("전체 구조는 표준 SPN이고, 치환층이 **셀룰러 오토마타(CA)** 형태라는 점이 다릅니다. CA형 치환은 SHA-3(Keccak)의 χ처럼 이미 쓰인 예가 있으므로, 독창성은 **'지뢰찾기의 이웃 지뢰 수 규칙'**과 **'4색 분할로 2차원 CA를 되돌릴 수 있게 만든 방법'**에 있다고 설명하는 것이 정확합니다."));
C.push(h3("적용한 개선과 남은 과제"));
C.push(...table(["구분", "내용"], [
  ["적용: 라운드마다 MineSub 2회", `1비트 차분 유지 확률 2^-6.3 → 2^-${T1.toFixed(1)} (라운드당). 확산 50% 도달 5라운드 → ${[1, 2, 3, 4, 5].find((r) => AV[r].avg >= 49.5)}라운드`],
  ["적용: 키 스케줄 진화 2번", `K1 확산 5.6% → ${pct(RK[0].avg)}. 키 스케줄 시간 ${M.ks_ms.toFixed(1)} ms`],
  ["적용: 비트 연산 구현", `판 전체를 128비트 정수로 계산. 블록당 7.2 ms(시제품) → ${M.block_ms.toFixed(1)} ms`],
  ["남은 과제", "자동 경로 탐색 도구(MILP·SAT 등)로 n라운드 최소 활성 칸 수를 구해 라운드 수의 근거 만들기, 선형 경로 분석, 대수 차수 증가 분석"],
  ["검토할 선택지", "키에 따라 반전 규칙 선택(편향 1/16인 규칙 4개 중 하나) — 독창성은 커지지만 분석은 더 어려워짐"],
], [3000, 6638]));
C.push(...callout("주의", [
  "MineLock v3는 학습용으로 설계한 암호입니다. 위의 분석이 끝나지 않았으므로 실제 데이터 보호에 사용하면 안 됩니다.",
], "FFF4EC", ORANGE));

// ---------- 7장 ----------
C.push(h1("7. 용어 정리"));
C.push(...table(["용어", "뜻"], [
  ["블록 암호", "데이터를 일정한 크기(MineLock은 16바이트)로 잘라 암호화하는 방식"],
  ["대칭키", "암호화와 복호화에 같은 키를 쓰는 방식"],
  ["XOR (⊕)", "두 비트가 다르면 1, 같으면 0. 같은 값으로 두 번 하면 원래대로"],
  ["치환 (Substitution)", "비트의 값을 바꾸는 연산. v3에서는 MineSub"],
  ["전치 (Permutation)", "비트의 위치를 바꾸는 연산. v3에서는 MinePerm"],
  ["라운드 / 라운드 키", "반복되는 처리의 한 회차 / 그 회차에 쓰는 키"],
  ["키 스케줄", "비밀키 하나에서 라운드 키 여러 개를 만드는 과정"],
  ["Evolve (진화)", "키 없는 라운드: MineSub × 2 → MinePerm. 키 스케줄에서 지뢰판을 진행시킬 때 사용"],
  ["Feistel 구조", "블록을 반으로 나눠 한쪽으로 다른 쪽을 바꾸는 구조 (1차 설계, DES)"],
  ["SPN 구조", "치환과 전치를 블록 전체에 반복하는 구조 (v3, AES)"],
  ["패딩 (PKCS#7)", "마지막 블록을 16바이트로 채우는 규칙. 부족한 바이트 수 n을 n번 붙임"],
  ["CBC / IV", "각 블록을 이전 암호문 블록과 XOR한 뒤 암호화하는 방식 / 첫 블록에 쓰는 무작위 값"],
  ["눈사태 효과", "입력 1비트 변화로 출력의 약 절반이 바뀌는 성질"],
  ["선형 / 비선형", "출력이 입력 비트들의 XOR로 표현됨 / 표현되지 않음. 비선형이어야 안전"],
  ["선형 편향", "출력 비트를 입력 XOR로 맞힐 확률이 1/2에서 벗어난 정도. 작을수록 좋음"],
  ["라운드 상수 (RC)", "라운드마다 다르게 더하는 고정값. 라운드가 똑같아지는 것을 막음"],
  ["차분 공격", "두 입력의 차이가 출력 차이로 전달되는 확률을 이용하는 공격"],
  ["대수 차수", "출력을 입력 비트의 AND·XOR 식으로 쓸 때 최고 차수"],
  ["적분 공격", "입력 일부를 모든 값으로 바꿔 출력 합의 성질을 이용하는 공격"],
  ["셀룰러 오토마타 (CA)", "각 칸이 이웃 상태에 따라 다음 상태로 바뀌는 격자 모델"],
], [2800, 6838], { size: 19 }));

// ================= 문서 =================
const doc = new Document({
  creator: "YSKL 2조", title: "MineLock v3 설계 설명서",
  styles: {
    default: { document: { run: { font: font(KF), size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: font(KF), size: 34, bold: true, color: NAVY }, paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0, keepNext: true } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: font(KF), size: 26, bold: true, color: BLUE }, paragraph: { spacing: { before: 320, after: 140 }, outlineLevel: 1, keepNext: true } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: font(KF), size: 22, bold: true, color: NAVY }, paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: { config: numberingConfigs },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "888888" })] })] }) },
    children: C,
  }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT, buf.length); });
