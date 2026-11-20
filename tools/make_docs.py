# /// script
# dependencies = ["matplotlib", "pillow"]
# ///
# 핀맵 + 배선도 + 회로도 + 통 치수 도면을 한 PDF(A4 가로)와 쪽별 PNG로 만든다.
# 통 치수는 tools/control_box.py 의 치수 블록을 그대로 읽어 쓴다 (따로 적지 않음).
# 사용: uv run tools/make_docs.py docs
import sys, os
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import font_manager as fm
from PIL import Image

src = open('tools/control_box.py').read()
exec(src[src.index('# ---------- 고칠 수 있는 치수 ----------'):src.index('def box(')])
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
FONT = '/System/Library/Fonts/AppleSDGothicNeo.ttc'
fp = fm.FontProperties(fname=FONT); fb = fm.FontProperties(fname=FONT, weight='bold')
PW, PH = 297.0, 210.0
DATE, REV = '2026-11-20', 'rev 1.2'
pages = []

def page(title, sub=''):
    fig = plt.figure(figsize=(PW/25.4, PH/25.4)); ax = fig.add_axes([0,0,1,1]); ax.set_xlim(0,PW); ax.set_ylim(0,PH); ax.axis('off')
    ax.add_patch(Rectangle((8,8), PW-16, PH-16, fc='none', ec='#333', lw=0.8))
    T(ax, 14, PH-17, title, 15, bold=True); T(ax, 14, PH-24, sub, 8.5, '#555')
    T(ax, 14, 11.5, '밴드 히터 PID 컨트롤러', 6.5, '#444'); T(ax, PW-14, 11.5, '%s    %s    %d / 7' % (REV, DATE, len(pages)+1), 6.5, '#444', ha='right')
    pages.append(fig); return ax
def T(ax, x, y, s, size=8, color='#111', ha='left', va='center', bold=False, rot=0):
    ax.text(x, y, s, fontsize=size, color=color, ha=ha, va=va, rotation=rot, fontproperties=fb if bold else fp, rotation_mode='anchor')
def table(ax, x, ytop, colw, header, rows, rh=5.6, size=7.4, hcol='#e4e4e4', swatch=None):
    """swatch: 색 견본을 그릴 열 번호. 그 열의 값은 (색, 글자)."""
    W = sum(colw)
    ax.add_patch(Rectangle((x, ytop-rh), W, rh, fc=hcol, ec='#222', lw=0.4))
    cx = x
    for w, h in zip(colw, header): T(ax, cx+1.5, ytop-rh/2, h, size, '#111', bold=True); cx += w
    y = ytop - rh
    for i, r in enumerate(rows):
        sec = isinstance(r, str)
        ax.add_patch(Rectangle((x, y-rh), W, rh, fc='#f2f2f2' if sec else '#ffffff', ec='#222', lw=0.4))
        if sec: T(ax, x+1.5, y-rh/2, r, size, '#111', bold=True)
        else:
            cx = x
            for j, (w, c) in enumerate(zip(colw, r)):
                if swatch == j and c:
                    ax.plot([cx+1.5, cx+7.5], [y-rh/2]*2, color=c[0], lw=3.2, solid_capstyle='round'); T(ax, cx+9.5, y-rh/2, c[1], size)
                else: T(ax, cx+1.5, y-rh/2, c, size, bold=(j == 0))
                cx += w
        y -= rh
    cx = x; ys = ytop; yy = ytop - rh            # 세로 칸 선: 구분 줄(글자만 있는 줄)은 건너뜀
    segs = [(ytop, ytop-rh)]
    for r in rows:
        if not isinstance(r, str): segs.append((yy, yy-rh))
        yy -= rh
    for w in colw[:-1]:
        cx += w
        for a, b in segs: ax.plot([cx, cx], [a, b], color='#222', lw=0.25)
    return y

C = dict(v5=('#e02020','빨강'), gnd=('#1c1c1c','검정'), sck=('#f2b600','노랑'), sdo=('#17a34a','초록'), sdi=('#2563eb','파랑'),
         cs1=('#f97316','주황'), cs2=('#a855f7','보라'), cs3=('#06b6d4','하늘'), cs4=('#ec4899','분홍'), sda=('#0d9488','청록'), scl=('#7c3aed','남보라'),
         btn=('#64748b','회색'), alarm=('#e11d48','진홍'), ssr=('#ea580c','주황빨강'), rly=('#9333ea','자주'), L=('#8b4513','갈색'), N=('#1d4ed8','파랑'), PE=('#65a30d','녹황'))

# ================= 1쪽: 나노 핀맵 =================
ax = page('1. 아두이노 나노 핀맵', '')
rows = [
 '디지털 핀',
 ('D0 (RX), D1 (TX)', 'USB 시리얼', '비움 (USB 통신)', '', ''),
 ('D2, D3', '-', '-', '', ''),
 ('D4', 'MAX31856 SDI', 'TC1~TC4 SDI', C['sdi'], '출력'),
 ('D5', '안전 릴레이 K1', '릴레이 모듈 IN, R2 10kΩ 풀다운', C['rly'], '출력'),
 ('D6', 'SSR', 'SRH1-1210 3/A1+, R1 10kΩ 풀다운', C['ssr'], '출력'),
 ('D7', 'MAX31856 CS4', 'TC4 CS', C['cs4'], '출력'),
 ('D8', 'MAX31856 CS3', 'TC3 CS', C['cs3'], '출력'),
 ('D9', 'MAX31856 CS2', 'TC2 CS', C['cs2'], '출력'),
 ('D10', 'MAX31856 CS1', 'TC1 CS', C['cs1'], '출력'),
 ('D11', '알람 LED', 'R3 220Ω → LED(+) → LED(-) → GND', C['alarm'], '출력'),
 ('D12', 'MAX31856 SDO', 'TC1~TC4 SDO', C['sdo'], '입력'),
 ('D13', 'MAX31856 SCK', 'TC1~TC4 SCK', C['sck'], '출력'),
 '아날로그 핀',
 ('A0', '버튼 SET', '택트 스위치 → GND (내부 풀업)', C['btn'], '입력'),
 ('A1', '버튼 UP', '택트 스위치 → GND', C['btn'], '입력'),
 ('A2', '버튼 DOWN', '택트 스위치 → GND', C['btn'], '입력'),
 ('A3', '버튼 RUN', '택트 스위치 → GND', C['btn'], '입력'),
 ('A4', 'I2C SDA', 'LCD 1, 2, 3 SDA', C['sda'], '양방향'),
 ('A5', 'I2C SCL', 'LCD 1, 2, 3 SCL', C['scl'], '출력'),
 ('A6, A7', '-', '-', '', ''),
 '전원 핀',
 ('5V', '5V', 'HLK-PM01 +Vo, MAX31856 VIN, LCD VCC, 릴레이 VCC', C['v5'], ''),
 ('GND', 'GND', 'HLK-PM01 -Vo, 모듈 GND, 버튼, LED, SSR 4/A2-, R1, R2', C['gnd'], ''),
 ('VIN, 3V3, RST, AREF', '-', '-', '', ''),
]
table(ax, 14, PH-30, [38, 44, 128, 34, 22], ['나노 핀', '기능', '연결되는 곳', '전선 색', '방향'], rows, rh=5.75, swatch=3)

# ================= 2쪽: 모듈별 핀맵 =================
ax = page('2. 모듈별 핀맵', '')
y = table(ax, 14, PH-30, [26, 30, 30, 30, 30], ['MAX31856 핀', 'TC1 모듈', 'TC2 모듈', 'TC3 모듈', 'TC4 모듈'], [
 ('VIN', '5V', '5V', '5V', '5V'), ('3Vo', '연결 안 함', '연결 안 함', '연결 안 함', '연결 안 함'), ('GND', 'GND', 'GND', 'GND', 'GND'),
 ('SCK', 'D13', 'D13', 'D13', 'D13'), ('SDO', 'D12', 'D12', 'D12', 'D12'), ('SDI', 'D4', 'D4', 'D4', 'D4'),
 ('CS', 'D10', 'D9', 'D8', 'D7'), ('FLT, DRDY', '연결 안 함', '연결 안 함', '연결 안 함', '연결 안 함'),
 ('단자대 T+ / T-', 'T형 + / -', 'T형 + / -', 'T형 + / -', 'T형 + / -')], rh=5.3, size=7.2)
T(ax, 14, y-3.5, 'T형: + 선이 구리색. 제어 기준 TC4', 6.6, '#444')
y = table(ax, 14, y-8, [26, 40, 40, 40], ['LCD 백팩 핀', 'LCD 1', 'LCD 2', 'LCD 3'], [
 ('GND', 'GND', 'GND', 'GND'), ('VCC', '5V', '5V', '5V'), ('SDA', 'A4', 'A4', 'A4'), ('SCL', 'A5', 'A5', 'A5'),
 ('I2C 주소', '0x27', '0x26', '0x25'), ('납땜 패드', '-', 'A0', 'A1')], rh=5.3, size=7.2)
T(ax, 14, y-3.5, 'PCF8574A 백팩: 0x3F / 0x3E / 0x3D', 6.6, '#444')
y = table(ax, 14, y-8, [30, 38, 78], ['버튼·LED', '한쪽', '다른 쪽'], [
 ('SET', 'A0', 'GND'), ('UP', 'A1', 'GND'), ('DOWN', 'A2', 'GND'), ('RUN', 'A3', 'GND'),
 ('알람 LED', 'D11 → R3 220Ω → LED(+)', 'LED(-) → GND')], rh=5.3, size=7.2)
T(ax, 14, y-3.5, '택트 스위치: 대각선 다리 2개 사용', 6.6, '#444')
X2 = 168
y = table(ax, X2, PH-30, [34, 81], ['SSR SRH1-1210', '연결'], [
 ('3/A1+ (입력 +)', 'D6, R1 10kΩ 풀다운'), ('4/A2- (입력 -)', 'GND'),
 ('2/L1 (부하)', '릴레이 K1의 NO (전원 쪽)'), ('1/T1 (부하)', '과열 서모스탯 TS1 (히터 쪽)')], rh=5.3, size=7.2)
y = table(ax, X2, y-4, [34, 81], ['안전 릴레이 K1', '연결'], [
 ('VCC', '5V'), ('GND', 'GND'), ('IN', 'D5 (High 트리거), R2 10kΩ 풀다운'),
 ('COM', '비상정지 스위치 (L 쪽)'), ('NO', 'SSR 2/L1'), ('NC', '연결 안 함')], rh=5.3, size=7.2)
y = table(ax, X2, y-4, [34, 81], ['HLK-PM01', '연결'], [
 ('AC (L)', 'F2 0.5A → L (메인 스위치 뒤)'), ('AC (N)', 'N (메인 스위치 뒤)'),
 ('+Vo', '5V 레일 (나노 5V 핀)'), ('-Vo', 'GND 레일')], rh=5.3, size=7.2)
y = table(ax, X2, y-4, [10, 105], ['순서', '220V 히터 경로 (L)'], [
 ('1', '220V 플러그 L → 누전차단기 2P 30mA'), ('2', 'F1 3.15A 속단 세라믹 5×20'), ('3', '메인 스위치 2P (L, N 동시 차단)'),
 ('4', '분기: MOV 14D471K (L-N), F2 → HLK-PM01'), ('5', '비상정지 (NC)'), ('6', '릴레이 K1 COM → NO'),
 ('7', 'SSR 2/L1 → 1/T1'), ('8', '과열 서모스탯 KSD301 NC'), ('9', '밴드 히터 220V 400W → N'),
 ('PE', '히터 금속 몸체')], rh=5.3, size=7.2)
T(ax, X2, y-3.5, '220V 배선 0.75mm² 이상, 5V 신호선 26AWG', 6.6, '#444')

# ================= 3·4쪽: 그림 =================
def image_page(title, sub, path):
    ax = page(title, sub); im = Image.open(path).convert('RGB'); w, h = im.size
    bw, bh = PW-28, PH-30-16; s = min(bw/w, bh/h); x0 = 14+(bw-w*s)/2; y0 = 16+(bh-h*s)/2
    ax.imshow(im, extent=(x0, x0+w*s, y0, y0+h*s), aspect='auto', zorder=1, interpolation='lanczos'); ax.set_xlim(0,PW); ax.set_ylim(0,PH)
image_page('3. 배선도', '', 'wiring_diagram.png')
image_page('4. 회로도', '', 'kicad/coil_heater_pid_rev1.2.png')

# ================= 도면 도우미 =================
class View:
    """모형 좌표(a, b) → 쪽 좌표. 배율 s (1 미만이면 축소)."""
    def __init__(s_, ax, ox, oy, s): s_.ax, s_.ox, s_.oy, s_.s = ax, ox, oy, s
    def P(s_, a, b): return (s_.ox + a*s_.s, s_.oy + b*s_.s)
    def rect(s_, a0, b0, a1, b1, r=0, **k):
        x0, y0 = s_.P(min(a0,a1), min(b0,b1)); w, h = abs(a1-a0)*s_.s, abs(b1-b0)*s_.s
        k.setdefault('fc', 'none'); k.setdefault('ec', '#111'); k.setdefault('lw', 0.8)
        if r: s_.ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle='round,pad=0,rounding_size=%g' % (r*s_.s), **k))
        else: s_.ax.add_patch(Rectangle((x0, y0), w, h, **k))
    def circ(s_, a, b, d, **k):
        k.setdefault('fc', 'none'); k.setdefault('ec', '#111'); k.setdefault('lw', 0.8)
        s_.ax.add_patch(Circle(s_.P(a, b), d/2*s_.s, **k))
    def line(s_, pts, **k):
        k.setdefault('color', '#111'); k.setdefault('lw', 0.8)
        xs, ys = zip(*[s_.P(a, b) for a, b in pts]); s_.ax.plot(xs, ys, **k)
    def tag(s_, a, b, n, dx=0, dy=0):
        x, y = s_.P(a, b); x += dx; y += dy
        s_.ax.add_patch(Circle((x, y), 2.3, fc='#fff7d6', ec='#b45309', lw=0.6, zorder=20)); s_.ax.text(x, y, str(n), fontsize=6.2, color='#7c2d12', ha='center', va='center', fontproperties=fb, zorder=21)
    def hdim(s_, a0, a1, b, off, txt=None, size=6.8):
        (x0, y), (x1, _) = s_.P(a0, b), s_.P(a1, b); yy = y + off
        for x in (x0, x1): s_.ax.plot([x, x], [y, yy + (1.2 if off > 0 else -1.2)], color='#0b5cad', lw=0.35)
        s_.ax.annotate('', (x1, yy), (x0, yy), arrowprops=dict(arrowstyle='<|-|>', color='#0b5cad', lw=0.5, mutation_scale=5, shrinkA=0, shrinkB=0))
        T(s_.ax, (x0+x1)/2, yy+1.6, txt or ('%g' % round(abs(a1-a0), 1)), size, '#0b5cad', ha='center')
    def vdim(s_, b0, b1, a, off, txt=None, size=6.8):
        (x, y0), (_, y1) = s_.P(a, b0), s_.P(a, b1); xx = x + off
        for y in (y0, y1): s_.ax.plot([x, xx + (1.2 if off > 0 else -1.2)], [y, y], color='#0b5cad', lw=0.35)
        s_.ax.annotate('', (xx, y1), (xx, y0), arrowprops=dict(arrowstyle='<|-|>', color='#0b5cad', lw=0.5, mutation_scale=5, shrinkA=0, shrinkB=0))
        T(s_.ax, xx-1.6, (y0+y1)/2, txt or ('%g' % round(abs(b1-b0), 1)), size, '#0b5cad', ha='center', rot=90)

# 읽는 방향 좌표: U = 오른쪽(열전대 끝 쪽), V = 위. 원점은 바깥 왼쪽 아래 모서리.
LEN, WID = IN_L + 2*T_WALL, IN_W + 2*T_WALL
U = lambda y: (IN_L + T_WALL) - y
V = lambda x: x + T_WALL
f1 = lambda v: '%.1f' % v

# ================= 5쪽: 뚜껑 =================
ax = page('5. 통 뚜껑 치수 (위에서 본 모습, LCD를 읽는 방향)', '단위 mm, 원점: 바깥 왼쪽 아래 모서리, 두께 %g, 턱 깊이 %g' % (T_LID, LIP_H))
v = View(ax, 26, 31, 0.80)
v.rect(0, 0, LEN, WID, r=R_OUT, lw=1.2, fc='#fff4ea')
items = []; n = 0
for cx, cy, name in LCD_CS:
    n += 1; u, w = U(cy), V(cx); v.rect(u-LCD_WX/2, w-LCD_WY/2, u+LCD_WX/2, w+LCD_WY/2, r=0.6, fc='#dbe6ff')
    for su in (-1, 1):
        for sw in (-1, 1): v.circ(u+su*LCD_HX/2, w+sw*LCD_HY/2, PILOT, ec='#666', ls=(0, (2, 1.5)), lw=0.5)
    v.tag(u, w, n); T(ax, *v.P(u, w-5), name, 6.5, '#334', ha='center')
    items.append((n, 'LCD 창 ' + name, f1(u), f1(w), '%g × %g' % (LCD_WX, LCD_WY)))
n += 1; items.append((n, 'LCD 고정 구멍 (안쪽, 창마다 4개)', '창 중심 ±%g' % (LCD_HX/2), '±%g' % (LCD_HY/2), 'Ø%g 밑구멍, 기둥 높이 %g' % (PILOT, LCD_BOSS)))
cx0, cy0, _ = LCD_CS[0]; v.tag(U(cy0)-LCD_HX/2, V(cx0)+LCD_HY/2, n, dx=-3.4, dy=1.5)
for y, st in zip(BTN_YS, ('SET', 'UP', 'DN', 'RUN')):
    n += 1; v.circ(U(y), V(BTN_X0), BTN_HOLE, fc='#e5e7eb'); v.tag(U(y), V(BTN_X0), n, dy=-6.5); T(ax, *v.P(U(y), V(BTN_X0)+9.5), st, 6.2, '#334', ha='center')
    items.append((n, '버튼 구멍 ' + st, f1(U(y)), f1(V(BTN_X0)), 'Ø%g (안쪽 자리 %g 각)' % (BTN_HOLE, BTN_POCKET)))
n += 1
for y in BAR_SCREW_Y: v.circ(U(y), V(BTN_X0), PILOT, ec='#666', ls=(0, (2, 1.5)), lw=0.5)
v.tag(U(BAR_SCREW_Y[0]), V(BTN_X0), n, dy=4.5)
items.append((n, '버튼 막대 나사 구멍 (안쪽, 2개)', ' / '.join(f1(U(y)) for y in BAR_SCREW_Y), f1(V(BTN_X0)), 'Ø%g 밑구멍' % PILOT))
n += 1; v.circ(U(LED_C[1]), V(LED_C[0]), LED_D, fc='#fecaca'); v.tag(U(LED_C[1]), V(LED_C[0]), n, dx=5)
items.append((n, '알람 LED 구멍', f1(U(LED_C[1])), f1(V(LED_C[0])), 'Ø%g' % LED_D))
for i, x in enumerate(TC_X):
    n += 1; v.rect(U(11.5), V(x)-7.5, U(1.5), V(x)+7.5, r=3, fc='#e5e7eb'); v.tag(U(6.5), V(x), n, dx=-9.5)
    items.append((n, '드라이버 구멍 TC%d' % (i+1), f1(U(6.5)), f1(V(x)), '10 × 15 (둥근 네모)'))
n += 1
for x, y in PIL_C: v.circ(U(y), V(x), CLEAR)
v.tag(U(PIL_C[1][1]), V(PIL_C[1][0]), n, dx=5.5, dy=-2)
items.append((n, '뚜껑 볼트 구멍 (4개)', ' / '.join(sorted({f1(U(y)) for x, y in PIL_C}, key=float)), ' / '.join(sorted({f1(V(x)) for x, y in PIL_C}, key=float)), 'Ø%g, M3' % CLEAR))
for x in RIB_X: v.line([(U(FRAME[2]), V(x)), (U(FRAME[3]-3), V(x))], color='#888', lw=0.6, ls=(0, (4, 2)))
v.hdim(0, LEN, 0, -9); v.vdim(0, WID, 0, -9)
v.hdim(0, U(LCD_CS[0][1]), WID, 3.5, f1(U(LCD_CS[0][1]))); v.hdim(U(LCD_CS[0][1])-LCD_WX/2, U(LCD_CS[0][1])+LCD_WX/2, WID, 8.5)
v.vdim(V(LCD_CS[2][0]), V(LCD_CS[1][0]), LEN, 6); v.vdim(V(LCD_CS[1][0]), V(LCD_CS[0][0]), LEN, 6)
v.hdim(U(BTN_YS[0]), U(BTN_YS[1]), V(BTN_X0)-12, -3)
T(ax, 26, 15.5, '점선: 안쪽 면의 밑구멍·보강 리브. 가장자리 모따기 %g, 바깥 모서리 R%g. 글자는 깊이 0.6 음각.' % (CH_OUT, R_OUT), 6.6, '#444')
table(ax, 194, PH-30, [8, 46, 22, 14], ['번호', '항목', 'U (가로)', 'V (세로)'], [(str(a), b, c, d) for a, b, c, d, e in items], rh=4.9, size=6.3)
yy = PH-30-4.9*(len(items)+1)-5
T(ax, 194, yy, '크기', 7, '#1f3a5f', bold=True)
sizes = [('1~3', '%g × %g, 가장자리 모따기 %g' % (LCD_WX, LCD_WY, CH_WIN)), ('4', 'Ø%g 밑구멍, 기둥 높이 %g' % (PILOT, LCD_BOSS)), ('5~8', 'Ø%g, 안쪽 자리 %g 각 × 깊이 %g' % (BTN_HOLE, BTN_POCKET, BTN_DEPTH)),
         ('9', 'Ø%g 밑구멍' % PILOT), ('10', 'Ø%g' % LED_D), ('11~14', '15 × 10 둥근 네모'), ('15', 'Ø%g (M3 통과)' % CLEAR)]
for k, (a, b) in enumerate(sizes): T(ax, 194, yy-5-4.6*k, '%s: %s' % (a, b), 6.4, '#222')

# ================= 6쪽: 본체 평면 =================
ax = page('6. 통 본체 치수 (뚜껑을 열고 위에서 본 모습)', '단위 mm, 점선: 브레드보드 82 × 55, MAX31856 보드')
v = View(ax, 30, 32, 0.80)
v.rect(0, 0, LEN, WID, r=R_OUT, lw=1.2, fc='#eef1f4')
v.rect(T_WALL, T_WALL, LEN-T_WALL, WID-T_WALL, fc='#ffffff')
v.rect(LEN, V(8.0), LEN+TIE_OUT, V(IN_W-8.0), fc='#dfe3e8')                                   # 타이 턱
for x in TC_X:
    for dx in (-7.0, 7.0): v.rect(LEN+1.6, V(x+dx)-0.9, LEN+TIE_OUT-1.0, V(x+dx)+0.9, fc='#fff', lw=0.4)
v.rect(U(TC_ZONE-0.5), V(0), U(0), V(IN_W), fc='#e6e9ee', lw=0.5)                             # 받침 턱
for x0, y0 in PIL: v.rect(U(y0+PILLAR_Y), V(x0), U(y0), V(x0+PILLAR), fc='#c9d0d8', lw=0.5)
for x, y in PIL_C: v.circ(U(y), V(x), CLEAR, lw=0.5)
for i in range(2):
    for j in range(3):
        v.rect(U(BB_Y0+(j+1)*BB_W), V(BB_MARGIN+i*BB_L), U(BB_Y0+j*BB_W), V(BB_MARGIN+(i+1)*BB_L), ec='#b08a00', ls=(0, (4, 2)), lw=0.6, fc='#fffbe6')
for i, x in enumerate(TC_X):
    my0 = BB_Y0 - MOD_OVER
    v.rect(U(my0+MOD_D), V(x)-MOD_W/2, U(my0), V(x)+MOD_W/2, ec='#1d4ed8', ls=(0, (3, 1.5)), lw=0.6, fc='#dbe6ff')
    v.rect(U(my0+8), V(x)-5.1, U(my0), V(x)+5.1, ec='#15803d', lw=0.5, fc='#bbf7d0'); T(ax, *v.P(U(my0+16), V(x)), 'TC%d' % (i+1), 6, '#1e3a8a', ha='center')
for xc, wd in ((USB_X, USB_W), (WIRE_X, 14.0)): v.rect(0, V(xc)-wd/2, T_WALL, V(xc)+wd/2, fc='#fff', ec='#c00', lw=0.8)
T(ax, *v.P(-2.5, V(USB_X)), 'USB', 6.5, '#c00', ha='right'); T(ax, *v.P(-2.5, V(WIRE_X)), '선', 6.5, '#c00', ha='right')
for k in range(VENT_N):
    y = IN_L/2 + (k-(VENT_N-1)/2)*VENT_P; v.rect(U(y)-VENT_W/2, WID-T_WALL, U(y)+VENT_W/2, WID, fc='#fff', lw=0.4)
T(ax, *v.P(U(BB_Y0+1.5*BB_W), V(IN_W*0.72)), '브레드보드 6개 (3 × 2)', 8, '#7c5a00', ha='center')
v.hdim(0, LEN, 0, -8); v.hdim(0, LEN+TIE_OUT, 0, -15, '%g (타이 턱 포함)' % (LEN+TIE_OUT)); v.vdim(0, WID, 0, -9)
v.hdim(T_WALL, LEN-T_WALL, WID, 5, '안쪽 %g' % IN_L); v.vdim(T_WALL, WID-T_WALL, LEN+TIE_OUT, 7, '안쪽 %g' % IN_W)
v.hdim(U(BB_Y0), U(0), V(40), 0.01, '%g' % TC_ZONE); v.hdim(U(BB_Y0+3*BB_W), U(BB_Y0), V(88), 0.01, '%g (55 × 3)' % (3*BB_W))
v.hdim(T_WALL, U(BB_Y0+3*BB_W), V(40), 0.01, '%g' % (IN_L-BB_Y0-3*BB_W))
rows = [('바깥 크기', '%g × %g × %g (뚜껑 포함 높이 %g)' % (LEN, WID, H_IN+T_FLOOR, H_IN+T_FLOOR+T_LID)), ('타이 턱 포함 길이', '%g' % (LEN+TIE_OUT)),
        ('안쪽 크기', '%g × %g × 높이 %g' % (IN_L, IN_W, H_IN)), ('벽 / 바닥 두께', '%g / %g' % (T_WALL, T_FLOOR)),
        ('브레드보드 자리', '%g × %g (둘레 여유 %g)' % (3*BB_W+BB_MARGIN, IN_W, BB_MARGIN)), ('단자 쪽 받침 턱', '깊이 %g, 높이 %g' % (TC_ZONE-0.5, REST_H)),
        ('USB 끝 여유', '%g' % (IN_L-BB_Y0-3*BB_W)), ('뚜껑 기둥 (모서리 4개)', '%g × %g, Ø%g 구멍 + M3 너트 홈' % (PILLAR, PILLAR_Y, CLEAR)),
        ('너트 홈', '폭 %g × 높이 %g, 기둥 윗면에서 %g 아래' % (NUT_W, NUT_T, NUT_Z)), ('모듈 꽂는 줄', 'j열, 4~12번 줄과 19~27번 줄'),
        ('모듈 단자 중심 (V)', ' / '.join(f1(V(x)) for x in TC_X)), ('바닥 고무발 자리', 'Ø%g × 깊이 %g, 모서리에서 %g' % (FOOT_D, FOOT_H, FOOT_IN)),
        ('바깥 모서리', 'R%g, 바닥 모따기 %g' % (R_OUT, CH_OUT))]
table(ax, 205, PH-30, [34, 46], ['항목', '치수 (mm)'], rows, rh=5.6, size=6.4)

# ================= 7쪽: 옆면 =================
ax = page('7. 통 옆면 치수', '단위 mm, 바깥에서 본 모습, 높이는 바닥면 기준')
ZB = lambda z: z + T_FLOOR; HT = H_IN + T_FLOOR + T_LID
def elev(ox, oy, width, title, toff=14):
    vv = View(ax, ox, oy, 0.62); vv.rect(0, 0, width, ZB(H_IN), fc='#eef1f4', lw=1.0); vv.rect(0, ZB(H_IN), width, HT, fc='#fff4ea', lw=1.0)
    T(ax, ox, oy + HT*0.62 + toff, title, 8.5, '#1f3a5f', bold=True); return vv
# (가) 열전대 끝면: 가로 = x
vv = elev(22, 122, WID, '(가) 열전대 끝면 (읽는 방향 기준 오른쪽 옆면)', 25)
vv.rect(V(8.0), ZB(TIE_Z-TIE_T-TIE_OUT), V(IN_W-8.0), ZB(TIE_Z), fc='#dfe3e8', lw=0.6)
for i, x in enumerate(TC_X):
    vv.rect(V(x)-WIN_W/2, ZB(WIN_Z0), V(x)+WIN_W/2, ZB(WIN_Z1), fc='#fff'); T(ax, *vv.P(V(x), ZB((WIN_Z0+WIN_Z1)/2)), 'TC%d' % (i+1), 6.2, '#334', ha='center')
    for dx in (-7.0, 7.0): vv.rect(V(x+dx)-0.9, ZB(TIE_Z-TIE_T), V(x+dx)+0.9, ZB(TIE_Z), fc='#fff', lw=0.3)
    vv.hdim(0, V(x), HT, 4+4.6*i, f1(V(x)), size=6.2)
vv.hdim(V(TC_X[0])-WIN_W/2, V(TC_X[0])+WIN_W/2, ZB(WIN_Z1), 2.5, '%g' % WIN_W, size=6.2)
vv.vdim(0, ZB(WIN_Z0), WID, 5, f1(ZB(WIN_Z0)), size=6.2); vv.vdim(ZB(WIN_Z0), ZB(WIN_Z1), WID, 11, f1(WIN_Z1-WIN_Z0), size=6.2); vv.vdim(0, HT, 0, -6, f1(HT), size=6.2)
vv.hdim(0, WID, 0, -6, f1(WID), size=6.2)
# (나) USB 끝면: 바깥에서 보면 x가 뒤집힘
MX = lambda x: WID - V(x)
vv = elev(160, 122, WID, '(나) USB 끝면 (읽는 방향 기준 왼쪽 옆면)', 25)
vv.rect(MX(USB_X)-USB_W/2, ZB(H_IN-USB_H), MX(USB_X)+USB_W/2, ZB(H_IN-LIP_H), fc='#fff'); T(ax, *vv.P(MX(USB_X)+USB_W/2+3, ZB(H_IN-9)), 'USB', 6.5, '#334')
vv.rect(MX(WIRE_X)-7, ZB(H_IN-12), MX(WIRE_X)+7, ZB(H_IN-LIP_H), fc='#fff'); T(ax, *vv.P(MX(WIRE_X)+7+3, ZB(H_IN-8)), '220V 박스로 가는 선', 6.5, '#334')
vv.hdim(0, MX(WIRE_X), HT, 4, f1(MX(WIRE_X)), size=6.2); vv.hdim(0, MX(USB_X), HT, 8.6, f1(MX(USB_X)), size=6.2)
vv.hdim(MX(USB_X)-USB_W/2, MX(USB_X)+USB_W/2, ZB(H_IN-USB_H), -11, '%g' % USB_W, size=6.2); vv.hdim(MX(WIRE_X)-7, MX(WIRE_X)+7, ZB(H_IN-12), -11, '14', size=6.2)
vv.vdim(0, ZB(H_IN-USB_H), WID, 5, f1(ZB(H_IN-USB_H)), size=6.2); vv.vdim(ZB(H_IN-USB_H), ZB(H_IN-LIP_H), WID, 11, f1(USB_H-LIP_H), size=6.2)
# (다) 윗벽: 통풍 구멍. 가로 = y
vv = elev(22, 50, LEN, '(다) 통풍 구멍이 있는 긴 옆면 (읽는 방향 기준 위쪽)')
for k in range(VENT_N):
    y = IN_L/2 + (k-(VENT_N-1)/2)*VENT_P + T_WALL; vv.rect(y-VENT_W/2, ZB(VENT_Z[0])-VENT_W/2, y+VENT_W/2, ZB(VENT_Z[1])+VENT_W/2, r=VENT_W/2-0.01, fc='#fff', lw=0.6)
y0 = IN_L/2 - (VENT_N-1)/2*VENT_P + T_WALL
vv.hdim(0, y0, HT, 4, f1(y0), size=6.2); vv.hdim(y0, y0+VENT_P, ZB(VENT_Z[0])-VENT_W/2, -5, '%g' % VENT_P, size=6.2)
T(ax, *vv.P(y0+VENT_P*(VENT_N-1)+8, ZB(30)), '구멍 %g × %g\n간격 %g, %d개' % (VENT_W, VENT_Z[1]-VENT_Z[0]+VENT_W, VENT_P, VENT_N), 6.3, '#334')
vv.vdim(ZB(VENT_Z[0])-VENT_W/2, ZB(VENT_Z[1])+VENT_W/2, LEN, 5, f1(VENT_Z[1]-VENT_Z[0]+VENT_W), size=6.2); vv.vdim(0, ZB(VENT_Z[0])-VENT_W/2, LEN, 11, f1(ZB(VENT_Z[0])-VENT_W/2), size=6.2)
vv.hdim(0, LEN, 0, -6, f1(LEN), size=6.2)
# (라) 아랫벽: 세울 때 바닥. 가로 = U
vv = elev(160, 50, LEN, '(라) 세울 때 바닥이 되는 긴 옆면 (읽는 방향 기준 아래쪽)')
for y in SIDE_FOOT_Y: vv.circ(U(y), ZB(SIDE_FOOT_Z), FOOT_D, fc='#fff'); vv.hdim(0, U(y), HT, 4 if y == SIDE_FOOT_Y[1] else 8.6, f1(U(y)), size=6.2)
vv.vdim(0, ZB(SIDE_FOOT_Z), LEN, 5, f1(ZB(SIDE_FOOT_Z)), size=6.2); vv.hdim(0, LEN, 0, -6, f1(LEN), size=6.2)
T(ax, *vv.P(U(SIDE_FOOT_Y[1])+9, ZB(SIDE_FOOT_Z)), '고무발 자리 Ø%g × 깊이 %g' % (FOOT_D, FOOT_H), 6.3, '#334')
table(ax, 22, 38, [44, 30, 22, 157], ['볼트 (전부 M3)', '길이', '개수', '방식'], [
 ('뚜껑 모서리', 'M3 × 12 (16까지)', '4', '기둥 옆 홈에 M3 너트를 밀어 넣고 위에서 조임'),
 ('LCD 고정', 'M3 × 6~8', '12', '뚜껑 안쪽 기둥의 Ø%g 구멍에 직접 나사산을 냄' % PILOT),
 ('버튼 누름 막대', 'M3 × 6', '2', '위와 같음. 8mm는 바닥에 닿음')], rh=4.6, size=6.4)

# ================= 저장 =================
pdf = os.path.join(OUT, '핀맵_배선_치수도면.pdf')
with PdfPages(pdf) as pp:
    for i, fig in enumerate(pages):
        pp.savefig(fig, dpi=300); fig.savefig(os.path.join(OUT, 'page%d.png' % (i+1)), dpi=170)
print('saved', pdf, len(pages), 'pages')
