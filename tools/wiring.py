# /// script
# dependencies = ["matplotlib"]
# ///
# 실체 배선도 (band_heater_pid v1.3, MAX31856 x4, LCD x3, 안전 릴레이 D5)
import sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle, Polygon, Ellipse
from matplotlib import font_manager as fm
import matplotlib.patheffects as pe
fp=fm.FontProperties(fname='/System/Library/Fonts/AppleSDGothicNeo.ttc')
fb=fm.FontProperties(fname='/System/Library/Fonts/AppleSDGothicNeo.ttc',weight='bold')
W,H=1800,1318
fig=plt.figure(figsize=(W/100,H/100)); ax=fig.add_axes([0,0,1,1]); ax.set_xlim(0,W); ax.set_ylim(H,0); ax.axis('off')
fig.patch.set_facecolor('#ffffff')
def T(x,y,s,size=9,color='#222',ha='center',va='center',rot=0,bold=False,z=30,bg=None):
    return ax.text(x,y,s,fontsize=size,color=color,ha=ha,va=va,rotation=rot,fontproperties=fb if bold else fp,zorder=z,bbox=dict(fc=bg,ec='none',pad=1.5,alpha=0.92) if bg else None)
def box(x,y,w,h,fc,ec='#222',r=6,lw=1.2,z=5,**k):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0,rounding_size=%g'%r,fc=fc,ec=ec,lw=lw,zorder=z,**k))
def rect(x,y,w,h,fc,ec='none',lw=1,z=6): ax.add_patch(Rectangle((x,y),w,h,fc=fc,ec=ec,lw=lw,zorder=z))
def pin(x,y,z=8): ax.add_patch(Rectangle((x-5,y-5),10,10,fc='#d9b23c',ec='#6b5510',lw=0.8,zorder=z)); ax.add_patch(Circle((x,y),2,fc='#3a2e08',ec='none',zorder=z+1))
def screw(x,y,z=8): ax.add_patch(Circle((x,y),7,fc='#c9ccd1',ec='#555',lw=1,zorder=z)); ax.plot([x-4,x+4],[y-4,y+4],color='#555',lw=1.2,zorder=z+1)
C=dict(v5='#e02020',gnd='#1c1c1c',sck='#f2b600',sdo='#17a34a',sdi='#2563eb',cs1='#f97316',cs2='#a855f7',cs3='#06b6d4',cs4='#ec4899',
       sda='#0d9488',scl='#7c3aed',btn='#64748b',alarm='#e11d48',ssr='#ea580c',rly='#9333ea',L='#8b4513',N='#1d4ed8',PE='#65a30d',tcp='#b45309',tcn='#dc2626')
def wire(pts,c,lw=3.2,z=20,dots=()):
    xs,ys=zip(*pts)
    ax.plot(xs,ys,color=c,lw=lw,solid_joinstyle='round',solid_capstyle='round',zorder=z,path_effects=[pe.Stroke(linewidth=lw+1.6,foreground='#00000055'),pe.Normal()])
    for d in dots: ax.add_patch(Circle(d,5.5,fc=c,ec='#000',lw=0.8,zorder=z+1))
def resistor(x1,y1,x2,y2,label,lx=0,ly=0):
    import math
    ax.plot([x1,x2],[y1,y2],color='#777',lw=2,zorder=21)
    mx,my=(x1+x2)/2,(y1+y2)/2; L=math.hypot(x2-x1,y2-y1); ang=math.degrees(math.atan2(y2-y1,x2-x1))
    bl=min(34,L*0.6)
    t=matplotlib.transforms.Affine2D().rotate_deg_around(mx,my,ang)+ax.transData
    ax.add_patch(FancyBboxPatch((mx-bl/2,my-6),bl,12,boxstyle='round,pad=0,rounding_size=5',fc='#e8cf9a',ec='#7a5c1e',lw=1,zorder=22,transform=t))
    for k,col in enumerate(('#a00','#a00','#111')): ax.add_patch(Rectangle((mx-bl/2+6+k*7,my-6),3.5,12,fc=col,ec='none',zorder=23,transform=t))
    T(mx+lx,my+ly,label,7.5,'#444')

# ---------- 제목 ----------
T(40,36,'밴드 히터 PID 컨트롤러 배선도',15,'#111','left',bold=True)
T(40,62,'rev 1.2   2026-11-20',9,'#555','left')

# ---------- 구역 ----------
box(1205,84,570,1214,'#ffffff','#555',r=3,lw=1.0,z=1,ls=(0,(6,4)))
T(1225,106,'AC 220V',11,'#333','left',bold=True)
box(22,84,1168,1214,'#ffffff','#888',r=3,lw=1.0,z=1)
T(40,102,'DC 5V',11,'#333','left',bold=True)

# ---------- 레일 ----------
def rail(y,c,label,x0=100,x1=1170):
    ax.plot([x0,x1],[y,y],color=c,lw=6,solid_capstyle='round',zorder=18,alpha=0.95)
    T(x0-8,y,label,8.5,c,'right',bold=True)
rail(330,C['v5'],'+5V',100,1150); rail(350,C['gnd'],'GND',100,1170)
rail(700,C['v5'],'+5V',100,1150); rail(720,C['gnd'],'GND',100,1170)
wire([(1150,330),(1150,700)],C['v5'],5,18); wire([(1170,350),(1170,720)],C['gnd'],5,18)

# ---------- MAX31856 모듈 4개 ----------
MC=[165,415,665,915]; names=['VIN','GND','SCK','SDO','SDI','CS']
cs_c=[C['cs1'],C['cs2'],C['cs3'],C['cs4']]
for n,c in enumerate(MC):
    x0=c-78; y0=180
    box(x0,y0,156,112,'#5b2a86','#2c1245',r=8)
    T(c,y0+62,'MAX31856',9.5,'#fff',bold=True); T(c,y0+78,'TC%d 모듈'%(n+1),8,'#e3d4f5')
    rect(c-16,y0+30,32,20,'#1b1b1b','#000'); 
    # 열전대 단자대
    box(c-34,y0-12,68,30,'#2e9e4f','#14532d',r=3,z=7); screw(c-16,y0+3); screw(c+16,y0+3)
    T(c-16,y0+25,'T+',6.5,'#fff'); T(c+16,y0+25,'T-',6.5,'#fff')
    # 열전대 프로브
    wire([(c-16,y0+3),(c-16,138),(c-6,124)],C['tcp'],2.6,9); wire([(c+16,y0+3),(c+16,138),(c+6,124)],C['tcn'],2.6,9)
    box(c-9,102,18,24,'#444','#111',r=3,z=10)
    ax.add_patch(FancyBboxPatch((c-4,104),88,8,boxstyle='round,pad=0,rounding_size=4',fc='#cfd4da',ec='#666',lw=1,zorder=9))
    T(c-22,112,'TC%d'%(n+1),9.5,'#7c2d12','right',bold=True)
    for i,nm in enumerate(names):
        px=c-50+20*i; pin(px,292); T(px,275,nm,6.3,'#fff',rot=90)
    px=lambda i:c-50+20*i
    wire([(px(0),292),(px(0),330)],C['v5'],dots=[(px(0),330)])
    wire([(px(1),292),(px(1),350)],C['gnd'],dots=[(px(1),350)])
    wire([(px(2),292),(px(2),380)],C['sck'],dots=[(px(2),380)])
    wire([(px(3),292),(px(3),400)],C['sdo'],dots=[(px(3),400)])
    wire([(px(4),292),(px(4),420)],C['sdi'],dots=[(px(4),420)])

# ---------- 나노 ----------
NX=lambda i:420+30*i; NT,NB=572,648
box(372,548,500,124,'#0f6f7d','#063a42',r=8)
rect(350,588,46,44,'#c9ccd1','#666',z=7); T(373,610,'USB',7,'#333')
rect(600,596,44,28,'#1b1b1b','#000',z=7); T(622,610,'328P',6.5,'#bbb')
T(520,610,'Arduino Nano',11,'#d8f3f7',bold=True)
top=['D12','D11','D10','D9','D8','D7','D6','D5','D4','D3','D2','GND','RST','RX0','TX1']
bot=['D13','3V3','AREF','A0','A1','A2','A3','A4','A5','A6','A7','5V','RST','GND','VIN']
used_t={'D12','D11','D10','D9','D8','D7','D6','D5','D4','GND'}; used_b={'D13','A0','A1','A2','A3','A4','A5','5V','GND'}
for i,(a,b) in enumerate(zip(top,bot)):
    pin(NX(i),NT); pin(NX(i),NB)
    T(NX(i),NT+17,a,6.3,'#fff' if a in used_t else '#7fb4bc',rot=90,bold=a in used_t)
    T(NX(i),NB-17,b,6.3,'#fff' if b in used_b else '#7fb4bc',rot=90,bold=b in used_b)

# SPI 버스
wire([(60,380),(MC[3]-10,380)],C['sck']); wire([(60,380),(60,684),(NX(0),684),(NX(0),NB)],C['sck'])
wire([(MC[0]+10,400),(MC[3]+10,400)],C['sdo']); wire([(NX(0),400),(NX(0),NT)],C['sdo'],dots=[(NX(0),400)])
wire([(MC[0]+30,420),(MC[3]+30,420)],C['sdi']); wire([(NX(8),420),(NX(8),NT)],C['sdi'],dots=[(NX(8),420)])
T(1000,380,'SCK → D13',8,C['sck'],'left',bold=True); T(1000,400,'SDO → D12',8,C['sdo'],'left',bold=True); T(1000,420,'SDI → D4',8,C['sdi'],'left',bold=True)
# CS 4개
for n,(c,ny,ni) in enumerate(zip(MC,[450,466,482,498],[2,3,4,5])):
    wire([(c+50,292),(c+50,ny),(NX(ni),ny),(NX(ni),NT)],cs_c[n])
    lx=(c+50+NX(ni))/2 if n!=1 else c+50-4
T(300,450,'CS1 → D10',8,C['cs1'],bold=True,bg='#fff'); T(480,466,'CS2 → D9',8,C['cs2'],bold=True,bg='#fff')
T(620,482,'CS3 → D8',8,C['cs3'],bold=True,bg='#fff'); T(860,498,'CS4 → D7',8,C['cs4'],bold=True,bg='#fff')
# 나노 전원
wire([(NX(11),NT),(NX(11),350)],C['gnd'],dots=[(NX(11),350)])
wire([(NX(11),NB),(NX(11),700)],C['v5'],dots=[(NX(11),700)])
wire([(NX(13),NB),(NX(13),720)],C['gnd'],dots=[(NX(13),720)])

# ---------- 알람 LED ----------
wire([(NX(1),NT),(NX(1),530),(292,530)],C['alarm']); resistor(292,530,222,530,'220Ω',0,-15)
wire([(222,530),(196,530)],C['alarm'])
ax.add_patch(Ellipse((180,530),30,30,fc='#ff3b3b',ec='#8b0000',lw=1.2,zorder=22)); ax.add_patch(Ellipse((175,524),9,7,fc='#ffb3b3',ec='none',zorder=23))
wire([(164,530),(135,530),(135,350)],C['gnd'],dots=[(135,350)])
T(180,558,'알람 LED (D11)',8.5,'#9f1239',bold=True)

# ---------- 버튼 4개 ----------
BC=[170,280,390,500]; bn=['SET','UP','DOWN','RUN']
wire([(100,720),(100,900),(BC[3]+16,900)],C['gnd'],dots=[(100,720)])
for k,c in enumerate(BC):
    box(c-26,812,52,52,'#cbd5e1','#475569',r=5); ax.add_patch(Circle((c,838),15,fc='#1f2937',ec='#000',zorder=7)); ax.add_patch(Circle((c-4,834),5,fc='#4b5563',ec='none',zorder=8))
    pin(c-16,812); pin(c+16,864)
    T(c+6,881,bn[k],9,'#111','right',bold=True)
    wire([(NX(3+k),NB),(NX(3+k),745+13*k),(c-16,745+13*k),(c-16,812)],C['btn'])
    wire([(c+16,864),(c+16,900)],C['gnd'],dots=[(c+16,900)] if k<3 else [])
T(335,925,'A0 SET / A1 UP / A2 DOWN / A3 RUN',8.5,'#334155')

# ---------- LCD 3개 (I2C 버스 공유, 주소만 다름) ----------
LY=985; BUS=[946,956,966,976]; BC_=[C['gnd'],C['v5'],C['sda'],C['scl']]
LCDS=[(60,'SP150.0 PV148.7','RUN  OUT 45% TC4','LCD 1 (0x27)'),
      (430,'1:148.7 2:132.1','3:128.4 4>121.5','LCD 2 (0x26, A0)'),
      (800,'R:ON  S:ON   45%','180W  123Wh 01:23','LCD 3 (0x25, A1)')]
# 나노·전원 레일에서 버스까지
wire([(850,720),(850,BUS[0])],C['gnd'],dots=[(850,720)])
wire([(875,700),(875,BUS[1])],C['v5'],dots=[(875,700)])
wire([(NX(7),NB),(NX(7),760),(900,760),(900,BUS[2])],C['sda'])
wire([(NX(8),NB),(NX(8),778),(925,778),(925,BUS[3])],C['scl'])
for j in range(4): wire([(60+50+25*j,BUS[j]),(800+50+25*j,BUS[j])],BC_[j])
for x0,l1,l2,cap in LCDS:
    box(x0,LY,330,130,'#1f7a3a','#0b3d1a',r=6); box(x0+28,LY+28,274,74,'#1e40af','#0b1d5c',r=4,z=7)
    ax.text(x0+40,LY+52,l1,fontsize=11,color='#e8f0ff',family='monospace',zorder=9,va='center')
    ax.text(x0+40,LY+80,l2,fontsize=11,color='#e8f0ff',family='monospace',zorder=9,va='center')
    T(x0+165,LY+116,cap,8.5,'#e6f5ea',bold=True)
    for j,nm in enumerate(['GND','VCC','SDA','SCL']):
        x=x0+50+25*j; pin(x,LY); T(x,LY+14,nm,6.3,'#fff')
        wire([(x,BUS[j]),(x,LY)],BC_[j],dots=[(x,BUS[j])] if x0<800 else [])
T(770,760,'SDA ← A4',8,C['sda'],bold=True,bg='#fff'); T(770,778,'SCL ← A5',8,C['scl'],bold=True,bg='#fff')

# ---------- AC 220V ----------
XL,XN,XPE=1600,1700,1650
box(1575,122,150,44,'#e5e7eb','#374151',r=8); T(1650,144,'220V 플러그',9.5,'#111',bold=True)
wire([(XPE,166),(XPE,196)],C['PE'],4.5); T(XPE,206,'PE 접지',7.5,'#3f6212',bold=True); T(XPE,220,'→ 함체·노즐',7,'#3f6212')
box(1572,232,156,58,'#f8fafc','#111',r=5); T(1650,252,'누전차단기 ELCB',9,'#111',bold=True); T(1650,272,'2P 30mA',8,'#444')
wire([(XL,166),(XL,232)],C['L'],4.5); wire([(XN,166),(XN,232)],C['N'],4.5)
wire([(XL,290),(XL,318)],C['L'],4.5)
box(XL-13,318,26,46,'#fff7ed','#7c2d12',r=5,z=22); T(XL,341,'F1',7.5,'#7c2d12',bold=True,z=31); T(XL-22,341,'퓨즈 3.15A',8,'#7c2d12','right')
wire([(XL,364),(XL,392)],C['L'],4.5); wire([(XN,290),(XN,392)],C['N'],4.5)
box(1572,392,156,46,'#111827','#000',r=5); T(1650,415,'메인 스위치 2P',9,'#fff',bold=True)
# L, N 본선
wire([(XN,438),(XN,1078),(XL+56,1078)],C['N'],4.5)
T(XN+10,620,'N (파랑)',8,C['N'],'left',bold=True); T(XL+10,462,'L',8,C['L'],'left',bold=True)
# HLK-PM01
box(1300,452,150,80,'#1f2937','#000',r=6); T(1375,484,'HLK-PM01',10,'#fff',bold=True); T(1375,503,'220V → 5V',8,'#cbd5e1')
for (x,y,nm,ha) in [(1300,472,'+5V','left'),(1300,512,'GND','left'),(1450,472,'L','right'),(1450,512,'N','right')]:
    pin(x,y); T(x+(10 if ha=='left' else -10),y,nm,6.5,'#fff',ha)
wire([(XL,438),(XL,472)],C['L'],4.5)
wire([(XL,472),(1548,472)],C['L'],3.2,dots=[(XL,472)]); box(1500,462,48,20,'#fff7ed','#7c2d12',r=5,z=22); T(1524,472,'F2 0.5A',7,'#7c2d12',bold=True,z=31); wire([(1500,472),(1450,472)],C['L'],3.2)
wire([(XN,512),(1450,512)],C['N'],3.2,dots=[(XN,512)])
wire([(1300,472),(1150,472)],C['v5'],dots=[(1150,472)]); wire([(1300,512),(1170,512)],C['gnd'],dots=[(1170,512)])
# MOV
wire([(XL,556),(1632,556)],C['L'],2.6,dots=[(XL,556)]); wire([(1668,556),(XN,556)],C['N'],2.6,dots=[(XN,556)])
ax.add_patch(Circle((1650,556),18,fc='#2563eb',ec='#1e3a8a',lw=1.2,zorder=22)); T(1650,556,'MOV',6.5,'#fff',bold=True,z=31); T(1650,584,'14D471K',7,'#1e3a8a')
# E-stop
wire([(XL,472),(XL,612)],C['L'],4.5)
box(XL-32,612,64,44,'#fde047','#854d0e',r=6,z=22); ax.add_patch(Circle((XL,634),15,fc='#dc2626',ec='#7f1d1d',lw=1.2,zorder=23)); T(XL-42,634,'비상정지',8.5,'#854d0e','right',bold=True)
# 릴레이 모듈 K1
box(1330,690,190,110,'#1d4ed8','#0b1f66',r=6); box(1395,708,78,74,'#3b82f6','#0b1f66',r=4,z=7); T(1434,738,'RELAY',9,'#fff',bold=True); T(1434,756,'5V',8,'#dbeafe')
T(1425,816,'K1 안전 릴레이 (D5, High 트리거)',8.5,'#1e3a8a',bold=True)
for y,nm in zip([712,745,778],['VCC','IN','GND']): pin(1330,y); T(1342,y,nm,6.5,'#fff','left')
for y,nm in zip([720,770],['COM','NO']): screw(1520,y); T(1506,y,nm,6.5,'#fff','right')
wire([(XL,656),(XL,720),(1520,720)],C['L'],4.5)
wire([(1520,770),(XL,770),(XL,912),(1520,912)],C['L'],4.5)
# SSR U3
box(1330,850,190,110,'#1f2937','#000',r=6); T(1425,872,'Autonics',8.5,'#f97316',bold=True); T(1425,888,'SRH1-1210',9,'#fff',bold=True)
T(1425,976,'U3 SSR · 방열판 일체형 · 입력 4-30VDC (D6)',8.5,'#374151',bold=True)
for y,nm in zip([912,942],['3/A1+','4/A2-']): screw(1330,y); T(1343,y,nm,7,'#fff','left',bold=True)
for y,nm in zip([912,942],['2/L1','1/T1']): screw(1520,y); T(1507,y,nm,7,'#fff','right',bold=True)
wire([(1520,942),(1560,942),(1560,1007),(XL-24,1007)],C['L'],4.5)
# 서모스탯 + 히터
box(XL-24,990,48,34,'#fef3c7','#92400e',r=6,z=22); T(XL,1007,'TS1',7.5,'#92400e',bold=True,z=31); T(XL+32,1000,'과열 서모스탯',8,'#92400e','left'); T(XL+32,1014,'(NC, 수동복귀)',7,'#92400e','left')
wire([(XL,1024),(XL,1078),(XL+8,1078)],C['L'],4.5)
box(XL+8,1062,48,32,'#fb923c','#9a3412',r=6,z=22)
for k in range(5): ax.plot([XL+14+k*9,XL+14+k*9],[1064,1092],color='#7c2d12',lw=1.5,zorder=23)
T(XL+32,1112,'밴드 히터 220V 400W',9,'#9a3412',bold=True)
# 제어선 D6, D5
wire([(NX(6),NT),(NX(6),514),(1222,514),(1222,912),(1330,912)],C['ssr'])
wire([(NX(7),NT),(NX(7),534),(1240,534),(1240,745),(1330,745)],C['rly'])
T(1060,514,'D6 → SSR 3/A1+',8,C['ssr'],bold=True,bg='#fff'); T(1060,534,'D5 → 릴레이 IN',8,C['rly'],bold=True,bg='#fff')
wire([(1150,700),(1150,712),(1330,712)],C['v5'])
wire([(1170,720),(1262,720),(1262,778),(1330,778)],C['gnd'])
wire([(1262,778),(1262,942),(1330,942)],C['gnd'],dots=[(1262,778)])
resistor(1302,745,1310,778,'',0,0); T(1282,761,'10k',6.5,'#444',z=32,bg='#ffffff')
ax.add_patch(Circle((1302,745),4.5,fc=C['rly'],ec='#000',lw=0.7,zorder=24)); ax.add_patch(Circle((1302,778),4.5,fc=C['gnd'],ec='#000',lw=0.7,zorder=24))
resistor(1302,912,1310,942,'',0,0); T(1282,927,'10k',6.5,'#444',z=32,bg='#ffffff')
ax.add_patch(Circle((1302,912),4.5,fc=C['ssr'],ec='#000',lw=0.7,zorder=24)); ax.add_patch(Circle((1302,942),4.5,fc=C['gnd'],ec='#000',lw=0.7,zorder=24))

# ---------- 범례 ----------
box(42,1172,1130,114,'#ffffff','#999',r=2,lw=0.8,z=2)
T(60,1194,'전선 색',9.5,'#111','left',bold=True)
leg=[('v5','+5V'),('gnd','GND'),('sck','SCK (D13)'),('sdo','SDO (D12)'),('sdi','SDI (D4)'),('cs1','CS1 (D10)'),('cs2','CS2 (D9)'),('cs3','CS3 (D8)'),('cs4','CS4 (D7)'),
     ('sda','SDA (A4)'),('scl','SCL (A5)'),('btn','버튼 (A0~A3)'),('alarm','알람 LED (D11)'),('ssr','SSR (D6)'),('rly','릴레이 (D5)'),('L','AC L 활선'),('N','AC N 중성선'),('PE','PE 접지')]
for i,(k,nm) in enumerate(leg):
    x=60+(i%6)*185; y=1220+(i//6)*24
    ax.plot([x,x+34],[y,y],color=C[k],lw=5,solid_capstyle='round',zorder=30); T(x+44,y,nm,8.5,'#222','left')
fig.savefig(sys.argv[1],dpi=160,facecolor=fig.get_facecolor())
