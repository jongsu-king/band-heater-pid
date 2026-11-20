# /// script
# dependencies = ["manifold3d", "numpy", "matplotlib"]
# ///
# 아두이노 쪽 통: 하프 브레드보드 6개(3x2), 1602 LCD 3개, 택트 스위치 4개, 한쪽 끝면에 MAX31856 단자 4개.
# 단위 mm. 좌표: 안쪽 바닥 모서리가 원점. x = 폭, y = 길이(열전대 끝벽 안쪽 면이 0), z = 안쪽 바닥에서 위로.
# 사용: uv run tools/control_box.py <출력 폴더> <미리보기 png>
import sys, os, struct, numpy as np
import manifold3d as m

# ---------- 고칠 수 있는 치수 ----------
BB_L, BB_W, BB_H = 82.0, 55.0, 8.5   # 하프(400홀, 30줄) 브레드보드 1개. 실물이 다르면 여기만 고침
BB_MARGIN = 3.0                      # 브레드보드 묶음 둘레 여유 (84x54.5짜리도 들어가게)
T_WALL, T_FLOOR, T_LID = 2.4, 2.4, 3.0
H_IN   = 50.0                        # 안쪽 높이 (브레드보드 8.5 + 점퍼선 + LCD 뒤쪽)
TC_ZONE = 12.0                       # 끝벽 안쪽 면에서 브레드보드 가장자리까지 (모듈 단자대가 튀어나오는 자리)
FAR    = 10.0                        # 반대쪽 끝의 선 정리 자리 (USB 플러그, 220V 박스로 가는 선)
# MAX31856 (Adafruit 보드, 핀을 브레드보드에 꽂고 단자대가 가장자리 밖으로 나옴)
MOD_W, MOD_D = 28.0, 25.4            # 기판 폭(핀 줄 방향), 깊이
MOD_OVER = 9.4                       # 기판이 브레드보드 가장자리 밖으로 나오는 길이 (핀을 j열에 꽂을 때)
Z_PCB0 = BB_H + 2.5                  # 기판 아랫면 높이 (핀 헤더 플라스틱 2.5)
PCB_T  = 1.6
ROW0, ROW_P = 4.17, 2.54             # 브레드보드 끝에서 1번 줄까지, 줄 간격
TC_ROWS = (8, 23)                    # 모듈 가운데 핀이 오는 줄 번호 (4~12번 줄, 19~27번 줄에 꽂음)
WIN_W, WIN_Z0, WIN_Z1 = 18.0, Z_PCB0 - 0.5, Z_PCB0 + PCB_T + 12.5   # 끝벽의 단자대 창
REST_H = 9.2                         # 단자대 아래 받침 높이 (드라이버로 누를 때 기판이 꺾이지 않게)
# LCD 1602
LCD_HX, LCD_HY = 75.0, 31.0          # 고정 구멍 간격
LCD_WX, LCD_WY = 72.0, 25.0          # 표시창 구멍
LCD_BOSS = 5.0
# 뚜껑 글자·LCD는 통의 긴 옆면(x=0 쪽)이 아래, 열전대 끝면이 오른쪽에 오도록 읽는 방향이다. 세워 놓아도 단자가 바닥을 향하지 않는다.
LCD_CS = ((127.0, 140.0, '1 CTRL'), (85.0, 140.0, '2 TEMP'), (43.0, 140.0, '3 AC 220V'))   # 뚜껑의 LCD 3개 중심 (x, y)과 글자
# 택트 스위치 12x12
BTN_X0 = 85.0; BTN_YS = (86.0, 68.0, 50.0, 32.0)   # 버튼 줄의 x, 각 버튼의 y (SET, UP, DN, RUN)
BTN_POCKET, BTN_DEPTH, BTN_BOSS, BTN_HOLE = 12.5, 4.0, 2.0, 7.8
BAR_W, BAR_T = 7.0, 3.0
PILOT, CLEAR = 2.6, 3.4              # M3 볼트가 플라스틱에 직접 나사산을 내는 밑구멍, 통과 구멍
NUT_W, NUT_T, NUT_Z = 5.9, 2.8, 9.0  # 뚜껑 기둥의 M3 너트 홈 (폭, 높이, 기둥 윗면에서 깊이)
USB_W, USB_H = 18.0, 15.0            # USB 케이블 구멍 (USB-C 플러그가 통째로 지나감)
USB_X, WIRE_X = 45.0, 125.0
PILLAR, PILLAR_Y = 7.0, 9.0
LIP_T, LIP_H, LIP_CLR = 1.6, 3.0, 0.25
# 다듬기
R_OUT, CH_OUT = 5.0, 1.2             # 바깥 세로 모서리 둥글기, 바닥·뚜껑 윗면 가장자리 모따기
CH_WIN, CH_HOLE = 1.0, 0.6           # 창·구멍 가장자리 모따기
FOOT_D, FOOT_H, FOOT_IN = 10.4, 1.0, 16.0   # 바닥의 고무발 자리 (지름 10mm 고무발), 모서리에서 안쪽으로
# 기능 디테일
TIE_OUT, TIE_T = 6.0, 2.5            # 열전대 선을 케이블 타이로 묶는 턱: 벽에서 나온 길이, 끝 두께
TIE_Z  = WIN_Z0 - 3.0                # 턱 윗면 높이 (단자 창 아래)
VENT_N, VENT_P, VENT_W, VENT_Z = 10, 8.0, 3.0, (20.0, 40.0)   # 위쪽 옆벽의 통풍 구멍: 개수, 간격, 폭, 높이 범위
SIDE_FOOT_Y, SIDE_FOOT_Z = (32.0, 158.0), 24.0               # 세워 놓을 때 쓰는 옆벽 고무발 자리
RIB_X, RIB_W, RIB_H = (64.0, 106.0), 2.0, 4.0                # 뚜껑 안쪽 보강 리브 (LCD 사이)
LED_C, LED_D = (40.0, 59.0), 5.1     # 알람 LED(5mm) 구멍
FRAME = (24.0, 150.0, 100.0, 183.0)  # LCD 묶음 둘레 장식 홈 (x0, x1, y0, y1)

IN_W = 2*BB_L + 2*BB_MARGIN                       # 170
BB_Y0 = TC_ZONE
BB_LEN = 3*BB_W + BB_MARGIN                       # 168
IN_L = BB_Y0 + BB_LEN + FAR
TC_X = [BB_MARGIN + i*BB_L + ROW0 + (r-1)*ROW_P for i in range(2) for r in TC_ROWS]
BAR_SCREW_Y = ((BTN_YS[0]+BTN_YS[1])/2, (BTN_YS[2]+BTN_YS[3])/2)
BOSS_Y = (BTN_YS[-1]-8, BTN_YS[0]+8)
PIL = [(x0, y0) for x0 in (0, IN_W-PILLAR) for y0 in (0, IN_L-PILLAR_Y)]
PIL_C = [(x0+PILLAR/2, y0+PILLAR_Y/2) for x0, y0 in PIL]

def box(x0,x1,y0,y1,z0,z1): return m.Manifold.cube([x1-x0,y1-y0,z1-z0]).translate([x0,y0,z0])
def cyl(x,y,z0,z1,d,seg=48): return m.Manifold.cylinder(z1-z0,d/2,d/2,seg).translate([x,y,z0])
def union(ps):
    r=ps[0]
    for p in ps[1:]: r=r+p
    return r

def rrect(x0,x1,y0,y1,r):
    r = min(r, (x1-x0)/2-0.01, (y1-y0)/2-0.01)
    return m.CrossSection.square([x1-x0-2*r, y1-y0-2*r]).translate([x0+r, y0+r]).offset(r, m.JoinType.Round, 2.0, 48)
def slab(cs, z0, z1): return m.Manifold.extrude(cs, z1-z0).translate([0,0,z0])
def taper(cs_a, za, cs_b, zb):
    """za 높이의 단면 cs_a 와 zb 높이의 단면 cs_b 를 잇는 경사 입체 (모따기용)."""
    return m.Manifold.batch_hull([slab(cs_a, za, za+0.001), slab(cs_b, zb-0.001, zb)])
def shell_solid(z0, z1, ch_bottom=0.0, ch_top=0.0):
    """바깥 모양: 세로 모서리는 둥글고, 아래나 위 가장자리는 모따기."""
    x0,x1,y0,y1 = -T_WALL, IN_W+T_WALL, -T_WALL, IN_L+T_WALL
    full = rrect(x0,x1,y0,y1,R_OUT); parts = [slab(full, z0+ch_bottom, z1-ch_top)]
    if ch_bottom: parts.append(taper(rrect(x0+ch_bottom,x1-ch_bottom,y0+ch_bottom,y1-ch_bottom,R_OUT-ch_bottom), z0, full, z0+ch_bottom))
    if ch_top:    parts.append(taper(full, z1-ch_top, rrect(x0+ch_top,x1-ch_top,y0+ch_top,y1-ch_top,R_OUT-ch_top), z1))
    return union(parts)
def cut_z(cs, z0, z1, ch):
    """단면 cs 로 z0~z1 을 뚫고, 윗면(z1) 가장자리를 ch 만큼 모따기하는 칼."""
    return slab(cs, z0, z1+1) + taper(cs, z1-ch, cs.offset(ch+0.02, m.JoinType.Miter, 4.0), z1+0.02)
def cut_wall(x0, x1, z0, z1, y_in, y_out, ch):
    """끝벽(y 방향 두께)을 x0~x1, z0~z1 로 뚫고 바깥 면(y_out) 가장자리를 모따기하는 칼."""
    s_ = 1 if y_out > y_in else -1
    inner = box(x0, x1, min(y_in, y_out)-1, max(y_in, y_out)+1, z0, z1)
    a = box(x0, x1, y_out-s_*ch-0.0005, y_out-s_*ch+0.0005, z0, z1)
    b = box(x0-ch, x1+ch, y_out-0.0005+s_*0.02, y_out+0.0005+s_*0.02, z0-ch, z1+ch)
    return inner + m.Manifold.batch_hull([a, b])

def xcyl(y, z, x0, x1, d): return m.Manifold.cylinder(x1-x0, d/2, d/2, 32).rotate([0,90,0]).translate([x0, y, z])

def text3d(s, size, h):
    """글자를 xy 평면에 세운 입체. 원점은 글자 묶음의 중심."""
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    tp = TextPath((0,0), s, size=size, prop=FontProperties(family='DejaVu Sans', weight='bold'))
    polys = [np.asarray(p) for p in tp.to_polygons() if len(p) >= 4]
    cs = m.CrossSection([p[:-1].tolist() for p in polys], m.FillRule.EvenOdd)
    b = cs.bounds(); cx, cy = (b[0]+b[2])/2, (b[1]+b[3])/2
    return m.Manifold.extrude(cs.translate([-cx,-cy]), h)

# ---------- 본체 ----------
def make_base():
    body = shell_solid(-T_FLOOR, H_IN, ch_bottom=CH_OUT) - box(0, IN_W, 0, IN_L, 0, H_IN+1)
    add = [box(0, IN_W, 0, TC_ZONE-0.5, 0, REST_H)]                            # 단자대 아래 받침 겸 브레드보드 멈춤 턱
    for x0, y0 in PIL:
        add.append(box(x0, x0+PILLAR, y0, y0+PILLAR_Y, 0, H_IN))               # 뚜껑 나사 기둥
    body = union([body]+add)
    for x, y in PIL_C:
        body -= cyl(x, y, H_IN-16, H_IN+1, CLEAR)
        xa, xb = (x-NUT_W/2, PILLAR+1) if x < IN_W/2 else (IN_W-PILLAR-1, x+NUT_W/2)   # 너트를 안쪽에서 옆으로 밀어 넣는 홈
        body -= box(xa, xb, y-NUT_W/2, y+NUT_W/2, H_IN-NUT_Z-NUT_T, H_IN-NUT_Z)
    for x in TC_X:                                                             # 단자대 창
        body -= cut_wall(x-WIN_W/2, x+WIN_W/2, WIN_Z0, WIN_Z1, 0.0, -T_WALL, CH_WIN)
    body -= cut_wall(USB_X-USB_W/2, USB_X+USB_W/2, H_IN-USB_H, H_IN+3, IN_L, IN_L+T_WALL, CH_WIN)   # USB 케이블 구멍
    body -= cut_wall(WIRE_X-7, WIRE_X+7, H_IN-12, H_IN+3, IN_L, IN_L+T_WALL, CH_WIN)                # 220V 박스로 가는 선
    for fx in (-T_WALL+FOOT_IN, IN_W+T_WALL-FOOT_IN):                           # 바닥 고무발 자리
        for fy in (-T_WALL+FOOT_IN, IN_L+T_WALL-FOOT_IN):
            body -= cyl(fx, fy, -T_FLOOR-1, -T_FLOOR+FOOT_H, FOOT_D)
    body -= text3d('USB', 6.0, 0.6).rotate([90,0,180]).translate([USB_X, IN_L+T_WALL-0.6, H_IN-USB_H-7])
    for i, x in enumerate(TC_X):                                               # 끝벽 바깥에 채널 번호
        body -= text3d('TC%d' % (i+1), 6.0, 0.6).rotate([90,0,0]).translate([x, -T_WALL+0.6, WIN_Z1+6.0])
    yw = -T_WALL                                                               # 열전대 선 타이 턱 (아래는 45도 경사라 서포트 없음)
    prof = [(yw+0.01, TIE_Z), (yw-TIE_OUT, TIE_Z), (yw-TIE_OUT, TIE_Z-TIE_T), (yw+0.01, TIE_Z-TIE_T-TIE_OUT)]
    body += m.Manifold.hull_points([(x, y, z) for x in (8.0, IN_W-8.0) for y, z in prof])
    for x in TC_X:
        for dx in (-7.0, 7.0):
            body -= box(x+dx-0.9, x+dx+0.9, yw-TIE_OUT+1.0, yw-1.6, TIE_Z-TIE_T-TIE_OUT-1, TIE_Z+1)
    for k in range(VENT_N):                                                    # 통풍 구멍 (읽는 방향 기준 윗벽)
        y = IN_L/2 + (k-(VENT_N-1)/2)*VENT_P
        body -= box(IN_W-1, IN_W+T_WALL+1, y-VENT_W/2, y+VENT_W/2, VENT_Z[0], VENT_Z[1])
        for z in VENT_Z: body -= xcyl(y, z, IN_W-1, IN_W+T_WALL+1, VENT_W)
    for y in SIDE_FOOT_Y:                                                      # 세울 때 바닥이 되는 옆벽의 고무발 자리
        body -= xcyl(y, SIDE_FOOT_Z, -T_WALL-1, -T_WALL+FOOT_H, FOOT_D)
    return body

# ---------- 뚜껑 (z=0 이 뚜껑 아랫면, 조립 자세) ----------
def make_lid():
    lid = shell_solid(0, T_LID, ch_top=CH_OUT)
    c = LIP_CLR; g = c + 0.3
    ring = box(c, IN_W-c, c, IN_L-c, -LIP_H, 0) - box(c+LIP_T, IN_W-c-LIP_T, c+LIP_T, IN_L-c-LIP_T, -LIP_H-1, 1)
    for x0, y0 in PIL:
        ring -= box(x0-g, x0+PILLAR+g, y0-g, y0+PILLAR_Y+g, -LIP_H-1, 1)
    add = [ring]
    for cx, cy, _ in LCD_CS:
        for sx in (-1,1):
            for sy in (-1,1):
                add.append(cyl(cx+sx*LCD_HY/2, cy+sy*LCD_HX/2, -LCD_BOSS, 0, 7.0))
    add.append(box(BTN_X0-9, BTN_X0+9, BOSS_Y[0], BOSS_Y[1], -BTN_BOSS, 0))    # 버튼 자리 두께 보강
    for x in RIB_X:
        add.append(box(x-RIB_W/2, x+RIB_W/2, FRAME[2], FRAME[3]-3, -RIB_H, 0))    # 보강 리브
    lid = union([lid]+add)
    E = 0.6
    rtext = lambda st, size: text3d(st, size, E+0.1).rotate([0,0,-90])         # 글자가 -y 방향으로 진행 (위는 +x)
    for cx, cy, name in LCD_CS:
        lid -= cut_z(rrect(cx-LCD_WY/2, cx+LCD_WY/2, cy-LCD_WX/2, cy+LCD_WX/2, 0.6), -1, T_LID, CH_WIN)
        for sx in (-1,1):
            for sy in (-1,1):
                lid -= cyl(cx+sx*LCD_HY/2, cy+sy*LCD_HX/2, -LCD_BOSS-1, T_LID-1.0, PILOT)
        lid -= rtext(name, 4.5).translate([cx+16.5, cy, T_LID-E])
    for y, st in zip(BTN_YS, ('SET','UP','DN','RUN')):
        lid -= box(BTN_X0-BTN_POCKET/2, BTN_X0+BTN_POCKET/2, y-BTN_POCKET/2, y+BTN_POCKET/2, -BTN_BOSS-1, -BTN_BOSS+BTN_DEPTH)
        lid -= cut_z(m.CrossSection.circle(BTN_HOLE/2, 48).translate([BTN_X0, y]), -1, T_LID, CH_HOLE)
        lid -= rtext(st, 4.5).translate([BTN_X0+13.5, y, T_LID-E])
    for y in BAR_SCREW_Y:
        lid -= cyl(BTN_X0, y, -BTN_BOSS-1, T_LID-1.0, PILOT)
    for x, y in PIL_C:
        lid -= cut_z(m.CrossSection.circle(CLEAR/2, 32).translate([x, y]), -1, T_LID, 0.4)
    for i, x in enumerate(TC_X):                                               # 단자 나사를 조이는 드라이버 구멍
        lid -= cut_z(rrect(x-7.5, x+7.5, 1.5, 11.5, 3.0), -1, T_LID, CH_HOLE)
        lid -= rtext('TC%d' % (i+1), 4.5).translate([x, 19.5, T_LID-E])
    lid -= cut_z(m.CrossSection.circle(LED_D/2, 32).translate(list(LED_C)), -1, T_LID, CH_HOLE)   # 알람 LED
    lid -= rtext('ALARM', 4.0).translate([LED_C[0]+8.5, LED_C[1], T_LID-E])
    fr = rrect(FRAME[0], FRAME[1], FRAME[2], FRAME[3], 4.0)                    # LCD 묶음 둘레 홈
    lid -= slab(fr - fr.offset(-0.8, m.JoinType.Round, 2.0, 48), T_LID-0.5, T_LID+1)
    lid -= box(IN_W+T_WALL-1.6, IN_W+T_WALL+1, IN_L/2-8, IN_L/2+8, -0.01, 1.2)     # 뚜껑을 들어 올리는 손톱 홈
    return lid

# ---------- 버튼 누름 막대 (z=0 이 스위치 바닥에 닿는 면, 아래로 두께) ----------
def make_bar():
    b = box(BTN_X0-BAR_W/2, BTN_X0+BAR_W/2, BOSS_Y[0]+1, BOSS_Y[1]-1, -BAR_T, 0)
    for y in BAR_SCREW_Y:
        b -= cyl(BTN_X0, y, -BAR_T-1, 1, CLEAR)
    return b

base, lid, bar = make_base(), make_lid(), make_bar()
for nm, o in (('본체',base),('뚜껑',lid),('막대',bar)):
    assert o.status()==m.Error.NoError and o.num_vert()>0, nm
    assert len(o.decompose())==1, nm+' 덩어리가 여러 개'

# 조립 위치
lid_a  = lid.translate([0,0,H_IN])
bar_a  = bar.translate([0,0,H_IN-BTN_BOSS])

# ---------- 간섭 검사용 모형 ----------
bbs = union([box(BB_MARGIN + i*BB_L, BB_MARGIN + (i+1)*BB_L, BB_Y0 + j*BB_W, BB_Y0 + (j+1)*BB_W, 0, BB_H)
             for i in range(2) for j in range(3)])
wires = box(BB_MARGIN, IN_W-BB_MARGIN, BB_Y0+MOD_D-MOD_OVER+1, BB_Y0+3*BB_W, BB_H, BB_H+20)   # 점퍼선이 차지하는 높이 20mm
my0 = BB_Y0 - MOD_OVER
mods  = union([box(x-MOD_W/2, x+MOD_W/2, my0, my0+MOD_D, Z_PCB0, Z_PCB0+PCB_T) for x in TC_X])
terms = union([box(x-5.1, x+5.1, my0, my0+8.0, Z_PCB0+PCB_T, Z_PCB0+PCB_T+10.0) for x in TC_X])
tails = union([box(x-5.1, x+5.1, my0+1, my0+7.0, Z_PCB0-1.6, Z_PCB0) for x in TC_X])          # 단자대 납땜 끝
lcd_pcb  = union([box(cx-18, cx+18, cy-40, cy+40, H_IN-LCD_BOSS-1.6, H_IN-LCD_BOSS) for cx, cy, _ in LCD_CS])
lcd_bez  = union([box(cx-12.1, cx+12.1, cy-35.6, cy+35.6, H_IN-LCD_BOSS, H_IN-LCD_BOSS+7.6) for cx, cy, _ in LCD_CS])
lcd_back = union([box(cx-18, cx+18, cy-40, cy+40, H_IN-LCD_BOSS-1.6-14, H_IN-LCD_BOSS-1.6) for cx, cy, _ in LCD_CS])
btns = union([box(BTN_X0-6.0, BTN_X0+6.0, y-6.0, y+6.0, H_IN-BTN_BOSS, H_IN-BTN_BOSS+3.8) for y in BTN_YS])
shafts = union([cyl(BTN_X0, y, H_IN-BTN_BOSS+3.8, H_IN-BTN_BOSS+7.3, 7.0) for y in BTN_YS])
led = cyl(LED_C[0], LED_C[1], H_IN-6.0, H_IN+T_LID+1.5, 5.0)
usbplug = box(USB_X-6.5, USB_X+6.5, IN_L-25, IN_L+30, H_IN-LIP_H-8.0, H_IN-LIP_H-0.5)       # USB-C 플러그 13 x 7.5
shell = base + lid_a + bar_a
checks = [('브레드보드 6개',bbs,shell),('점퍼선 20mm',wires,shell+lcd_back),('MAX31856 기판',mods,shell),
          ('단자대',terms,shell),('단자대 납땜 끝',tails,shell),('LCD 기판',lcd_pcb,shell),('LCD 표시창 틀',lcd_bez,shell),
          ('LCD 뒤쪽(백팩)',lcd_back,shell+mods+terms),('택트 스위치',btns,shell),('스위치 축',shafts,shell),
          ('USB 플러그 통과',usbplug,shell),('알람 LED',led,shell),('뚜껑-본체',lid_a,base),('막대-뚜껑',bar_a,lid_a),('막대-LCD',bar_a,lcd_pcb+lcd_back)]
ok = True
for nm, a, b in checks:
    v = (a ^ b).volume(); bad = v > 0.01
    print('  간섭 %-16s %8.3f mm3 %s' % (nm, v, '<-- 충돌' if bad else '')); ok &= not bad
print('  스위치 축이 뚜껑 위로 나오는 길이: 전체 높이 7.3mm형 %.1f, 9mm형 %.1f, 12mm형 %.1f mm' %
      tuple(h - (BTN_BOSS + T_LID) for h in (7.3, 9.0, 12.0)))
print('  단자대 창 중심 x(안쪽 왼벽에서): ' + ', '.join('%.1f' % x for x in TC_X) + ' mm, 단자대 앞면과 벽 사이 %.1f mm' % my0)

# ---------- 출력 자세로 돌려 저장 ----------
def flat(o, flip):
    if flip: o = o.rotate([180,0,0])
    b = o.bounding_box(); return o.translate([-b[0], -b[1], -b[2]])
def write_stl(man, path, name):
    me = man.to_mesh(); V = np.asarray(me.vert_properties)[:,:3].astype(np.float32); F = np.asarray(me.tri_verts)
    N = np.cross(V[F[:,1]]-V[F[:,0]], V[F[:,2]]-V[F[:,0]]); N /= (np.linalg.norm(N,axis=1,keepdims=True)+1e-12)
    rec = np.zeros(len(F), dtype=[('n','<3f4'),('v','<9f4'),('a','<u2')])
    rec['n'] = N; rec['v'] = V[F].reshape(-1,9)
    with open(path,'wb') as f:
        f.write(name.encode().ljust(80,b' ')); f.write(struct.pack('<I',len(F))); f.write(rec.tobytes())
    from collections import Counter
    ec = Counter(tuple(sorted(e)) for t in F for e in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])))
    return V.max(0)-V.min(0), all(v==2 for v in ec.values()), len(F)
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
prints = [('box_base.stl', flat(base, False)), ('box_lid.stl', flat(lid, True)),
          ('button_bar.stl', flat(bar, False))]
for fn, o in prints:
    size, tight, nf = write_stl(o, os.path.join(out, fn), fn)
    fits = max(size[0], size[1]) <= 250
    print('  %-16s %6.1f x %6.1f x %5.1f mm  부피 %6.1f cm3  삼각형 %6d  닫힌 메시 %s  베드 256 %s' %
          (fn, *size, o.volume()/1000, nf, tight, '들어감' if fits else '안 들어감')); ok &= tight and fits

# ---------- 미리보기 (깊이 버퍼로 직접 그림) ----------
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt, matplotlib.colors
from matplotlib import font_manager as fm
fp = fm.FontProperties(fname='/System/Library/Fonts/AppleSDGothicNeo.ttc')
def render(objs, el, az, W=1400, H=1000, pad=0.05):
    el, az = np.radians(el), np.radians(az)
    fwd = np.array([np.cos(el)*np.cos(az), np.cos(el)*np.sin(az), np.sin(el)])      # 눈 쪽 방향
    right = np.cross([0,0,1], fwd); right /= np.linalg.norm(right); up = np.cross(fwd, right)
    tris, cols = [], []
    for man, color in objs:
        me = man.to_mesh(); V = np.asarray(me.vert_properties)[:,:3]; T = V[np.asarray(me.tri_verts)]
        n = np.cross(T[:,1]-T[:,0], T[:,2]-T[:,0]); n /= (np.linalg.norm(n,axis=1,keepdims=True)+1e-12)
        lit = 0.42 + 0.58*np.clip(n@np.array([0.25,-0.45,0.86]),0,1) * (0.75+0.25*np.clip(n@fwd,0,1))
        tris.append(T); cols.append(np.clip(lit[:,None]*np.array(matplotlib.colors.to_rgb(color))[None,:],0,1))
    T = np.concatenate(tris); C = np.concatenate(cols)
    P = np.stack([T@right, T@up, T@fwd], -1)
    lo, hi = P[...,:2].reshape(-1,2).min(0), P[...,:2].reshape(-1,2).max(0)
    sc = min(W*(1-2*pad)/(hi[0]-lo[0]), H*(1-2*pad)/(hi[1]-lo[1]))
    P[...,0] = (P[...,0]-(lo[0]+hi[0])/2)*sc + W/2; P[...,1] = H/2 - (P[...,1]-(lo[1]+hi[1])/2)*sc
    img = np.ones((H,W,3)); zb = np.full((H,W), -1e9)
    for t, c in zip(P, C):
        x0, x1 = int(max(np.floor(t[:,0].min()),0)), int(min(np.ceil(t[:,0].max()),W-1))
        y0, y1 = int(max(np.floor(t[:,1].min()),0)), int(min(np.ceil(t[:,1].max()),H-1))
        if x1 < x0 or y1 < y0: continue
        d = (t[1,1]-t[2,1])*(t[0,0]-t[2,0]) + (t[2,0]-t[1,0])*(t[0,1]-t[2,1])
        if abs(d) < 1e-9: continue
        xs, ys = np.meshgrid(np.arange(x0,x1+1)+0.5, np.arange(y0,y1+1)+0.5)
        w0 = ((t[1,1]-t[2,1])*(xs-t[2,0]) + (t[2,0]-t[1,0])*(ys-t[2,1]))/d
        w1 = ((t[2,1]-t[0,1])*(xs-t[2,0]) + (t[0,0]-t[2,0])*(ys-t[2,1]))/d
        w2 = 1-w0-w1; z = w0*t[0,2]+w1*t[1,2]+w2*t[2,2]
        sub = zb[y0:y1+1, x0:x1+1]; msk = (w0>=-1e-4)&(w1>=-1e-4)&(w2>=-1e-4)&(z>sub)
        sub[msk] = z[msk]; img[y0:y1+1, x0:x1+1][msk] = c
    return img
ORANGE, GREY = '#ff8a3c', '#aab2bb'
inner = [(base,GREY),(bbs,'#f3f1e8'),(mods,'#2456c8'),(terms,'#2fa84f')]
lidset = [(led,'#e02020'),(lid_a,ORANGE),(lcd_pcb,'#1d6b3a'),(lcd_bez,'#2a3fd0'),(btns,'#222222'),(shafts,'#111111'),(bar_a,ORANGE)]
lid_p = lid.rotate([180,0,0])
panels = [('조립한 모습 (읽는 방향: 열전대 단자가 오른쪽)', inner+lidset, 34, -152),
          ('뚜껑을 연 안쪽: 브레드보드 6개, 끝 줄에 꽂은 MAX31856 4개', inner, 50, -62),
          ('열전대 끝면: 창 4개로 단자대가 보임', inner+lidset, 14, -75),
          ('반대쪽 끝: USB 케이블 구멍과 선 통과 홈', inner+lidset, 28, 118),
          ('뚜껑 안쪽 (출력 자세): LCD 3개 기둥, 스위치 자리 4개', [(lid_p,ORANGE)], 52, -62),
          ('위에서 본 뚜껑 (읽는 방향 그대로)', [(lid_a,ORANGE),(lcd_bez,'#2a3fd0'),(shafts,'#111111')], 89.9, -180)]
fig, axs = plt.subplots(2, 3, figsize=(24, 12.5))
for ax, (title, objs, el, az) in zip(axs.ravel(), panels):
    ax.imshow(render(objs, el, az)); ax.set_axis_off(); ax.set_title(title, fontproperties=fp, fontsize=17)
fig.subplots_adjust(0.01,0.01,0.99,0.95,0.02,0.08); fig.savefig(sys.argv[2], dpi=75)
print('  결과:', '통과' if ok else '실패'); sys.exit(0 if ok else 1)
