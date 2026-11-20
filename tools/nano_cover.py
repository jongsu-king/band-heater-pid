# /// script
# dependencies = ["manifold3d", "numpy", "matplotlib"]
# ///
# 브레드보드에 꽂은 Arduino Nano 위에 씌우는 덮개. 단위 mm.
# 좌표: x = 길이(USB 쪽 기판 끝이 0), y = 폭(가운데 0), z = 브레드보드 윗면에서 위로.
import sys, struct, numpy as np
import manifold3d as m
L, WD   = 43.2, 17.8          # 나노 기판 길이, 폭 (기판만, USB 단자 제외). 실물이 다르면 여기만 고치면 됨
HW      = WD/2
Z_BOT, Z_TOP = 2.5, 4.1       # 기판 아랫면/윗면 높이 (핀 헤더 플라스틱 2.5 + 기판 1.6)
H_IN    = 9.8                 # 기판 윗면에서 지붕 안쪽까지 (ICSP 핀 높이 약 8.5 + 여유)
T_ROOF, T_END, T_SKIRT, T_LEG = 1.6, 1.6, 1.0, 1.6
CLR     = 0.2                 # 기판 끝과 벽 사이 틈
INSET   = 0.3                 # 지붕·옆벽을 기판 가장자리보다 안으로 (옆 구멍에 꽂는 점퍼선과 안 닿게)
SIDE_GAP= 2.0                 # 옆벽 아래 끝과 기판 사이 (핀 납땜 자리 피함)
USB_W, USB_TOP = 12.5, 11.5   # USB 플러그가 지나가는 구멍 폭, 윗변 높이
LEG_X0, LEG_X1 = -1.0, 2.1    # 다리의 x 범위 (첫 핀 옆 구멍을 막지 않는 범위)
BUMP    = 0.45                # 기판 아래로 걸리는 턱 깊이
ZR = Z_TOP + H_IN; ZT = ZR + T_ROOF; YR = HW - INSET; YL = HW + 0.15
def box(x0,x1,y0,y1,z0,z1): return m.Manifold.cube([x1-x0,y1-y0,z1-z0]).translate([x0,y0,z0])
def sym(f):  # y 대칭
    return f(1) + f(-1)
def ybox(s,x0,x1,ya,yb,z0,z1): 
    y0,y1 = sorted((s*ya,s*yb)); return box(x0,x1,y0,y1,z0,z1)
X0, X1 = -CLR-T_END, L+CLR+T_END
parts = [box(X0,X1,-YR,YR,ZR,ZT)]                                             # 지붕
for xa,xb in ((LEG_X0,LEG_X1),(L-LEG_X1,L-LEG_X0)):
    parts.append(box(xa,xb,-(YL+T_LEG),YL+T_LEG,ZR,ZT))                       # 다리가 붙는 귀
    for s in (1,-1):
        parts.append(ybox(s,xa,xb,YL,YL+T_LEG,0.4,ZR))                        # 다리
        y0=s*YL                                                               # 걸림 턱 (아래는 밀어 넣는 경사, 위는 45도)
        pts=[(x,y,z) for x in (xa,xb) for (y,z) in ((y0,0.6),(y0-s*BUMP,1.3),(y0-s*BUMP,Z_BOT-0.25),(y0,Z_BOT+0.2),(y0+s*0.2,0.6),(y0+s*0.2,Z_BOT+0.2))]
        parts.append(m.Manifold.hull_points(pts))
for s in (1,-1):
    parts.append(ybox(s,X0,X1,YR-T_SKIRT,YR,Z_TOP+SIDE_GAP,ZR))               # 옆벽 (기판 위 2mm 까지)
    for xa,xb in ((0.3,LEG_X1),(L-LEG_X1,L-0.3)):
        parts.append(ybox(s,xa,xb,6.4,YR,Z_TOP+0.15,ZR))                      # 모서리 기둥: 기판 윗면에 얹혀 높이를 정함
    parts.append(ybox(s,X0,-CLR,USB_W/2,HW-0.6,1.0,ZR))                       # USB 쪽 끝벽 (플러그 양옆 기둥)
parts.append(box(X0,-CLR,-USB_W/2,USB_W/2,USB_TOP,ZR))                        # USB 구멍 위 가로대
parts.append(box(L+CLR,X1,-(HW-0.6),HW-0.6,1.0,ZR))                           # 반대쪽 끝벽
body = parts[0]
for p in parts[1:]: body = body + p
for xc in (27.0,29.6,32.2,34.8):                                              # LED 보이는 창살, 리셋 버튼은 이쑤시개로
    body = body - box(xc-0.8,xc+0.8,-5.5,5.5,ZR-1,ZT+1)
assert body.status()==m.Error.NoError and body.num_vert()>0

# ---- 간섭 검사용 모형: 나노, 핀 헤더, USB, ICSP, 옆 구멍의 점퍼선 ----
pcb   = box(0,L,-HW,HW,Z_BOT,Z_TOP)
hdr   = sym(lambda s: ybox(s,2.54,L-2.54,7.62-1.27,7.62+1.27,0,Z_BOT))
tips  = sym(lambda s: ybox(s,2.9,L-2.9,6.7,8.5,Z_TOP,Z_TOP+1.9))
usb   = box(-1.8,7.4,-3.9,3.9,Z_TOP,Z_TOP+4.0)
plug  = box(-30,-0.3,-5.6,5.6,Z_TOP+2.0-4.2,Z_TOP+2.0+4.2)
icsp  = box(L-7.4,L-1.3,-2.6,2.6,Z_TOP,Z_TOP+8.6)
dup   = sym(lambda s: ybox(s,3.81-1.25,L-3.81+1.25,10.16-1.25,10.16+1.25,0,30))
board = sym(lambda s: ybox(s,-10,L+10,0,30,-5,0))
checks=[('기판',pcb),('핀 헤더 플라스틱',hdr),('핀 납땜 끝',tips),('USB 단자',usb),('USB 플러그',plug),('ICSP 헤더',icsp),('옆 구멍 점퍼선(듀폰)',dup),('브레드보드',board)]
ok=True
for nm,o in checks:
    v=(body^o).volume()
    lim = 2.0 if nm=='기판' else 0.001      # 기판은 걸림 턱이 살짝 물리는 것만 허용
    print('  간섭 %-22s %.3f mm3 %s'%(nm,v,'(걸림 턱 접촉)' if nm=='기판' and v>0 else '' if v<=lim else '<-- 충돌')); ok&= v<=lim
bb=body.bounding_box(); print('  크기 %.1f x %.1f x %.1f mm, 부피 %.2f cm3, 덩어리 %d개'%(bb[3]-bb[0],bb[4]-bb[1],bb[5]-bb[2],body.volume()/1000,len(body.decompose())))

# ---- 출력 방향: 지붕이 바닥에 닿게 뒤집음 ----
pr = body.rotate([180,0,0]).translate([-X0,0,ZT]); bb=pr.bounding_box(); pr=pr.translate([0,-bb[1],-bb[2]])
def write_stl(man,path):
    me=man.to_mesh(); V=np.asarray(me.vert_properties)[:,:3].astype(np.float32); F=np.asarray(me.tri_verts)
    with open(path,'wb') as f:
        f.write(b'nano breadboard cover'.ljust(80,b' ')); f.write(struct.pack('<I',len(F)))
        for a,b,c in F:
            n=np.cross(V[b]-V[a],V[c]-V[a]); n=n/(np.linalg.norm(n) or 1)
            f.write(struct.pack('<12fH',*n,*V[a],*V[b],*V[c],0))
    return V,F
V,F=write_stl(pr,sys.argv[1]); print('  STL 삼각형 %d개, 출력 자세 크기 %.1f x %.1f x %.1f'%(len(F),*(V.max(0)-V.min(0))))
# 닫힌 면 검사: 모든 모서리가 정확히 두 삼각형에 속함
from collections import Counter
ec=Counter(tuple(sorted(e)) for t in F for e in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])))
print('  물샐틈없는 메시:', all(v==2 for v in ec.values())); ok&=all(v==2 for v in ec.values())

# ---- 미리보기 ----
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; import matplotlib.colors
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib import font_manager as fm
fp=fm.FontProperties(fname='/System/Library/Fonts/AppleSDGothicNeo.ttc')
def tri(man):
    me=man.to_mesh(); V=np.asarray(me.vert_properties)[:,:3]; return V[np.asarray(me.tri_verts)]
def shaded(ax,man,color,alpha=1.0):
    T=tri(man); n=np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]); n/= (np.linalg.norm(n,axis=1,keepdims=True)+1e-12)
    lit=0.55+0.45*np.clip(n@np.array([0.35,-0.45,0.82]),-1,1)
    c=np.array(matplotlib.colors.to_rgb(color)); fc=np.clip(lit[:,None]*c[None,:],0,1); fc=np.concatenate([fc,np.full((len(fc),1),alpha)],1)
    ax.add_collection3d(Poly3DCollection(T,facecolors=fc,edgecolor='none',linewidths=0))
fig=plt.figure(figsize=(18,7))
views=[(24,-62,'씌운 모습 (USB 쪽, 나노·점퍼선과 함께)',True),(24,118,'반대쪽에서 본 모습',True),(30,-60,'출력 자세 (지붕이 바닥, 서포트 없음)',False)]
for i,(el,az,title,asm) in enumerate(views):
    ax=fig.add_subplot(1,3,i+1,projection='3d',computed_zorder=False)
    if asm:
        for o,c in ((hdr,'#2a2a2a'),(pcb,'#0f6f7d'),(usb,'#c9ccd1'),(icsp,'#3a3a3a')): shaded(ax,o,c)
        if i==0:
            for k in (2,5,8,11):
                for sgn in (1,-1): shaded(ax,ybox(sgn,3.81+2.54*k-1.25,3.81+2.54*k+1.25,8.91,11.41,0,14),'#e0a020')
        shaded(ax,body,'#ff7f2a',0.78)
        c0=np.array([L/2,0,7]); r=27
    else:
        shaded(ax,pr,'#ff7f2a'); bb=pr.bounding_box(); c0=np.array([(bb[0]+bb[3])/2,(bb[1]+bb[4])/2,8]); r=27
    ax.set_xlim(c0[0]-r,c0[0]+r); ax.set_ylim(c0[1]-r,c0[1]+r); ax.set_zlim(c0[2]-r,c0[2]+r)
    ax.view_init(el,az); ax.set_box_aspect((1,1,1),zoom=1.55); ax.set_axis_off(); ax.set_title(title,fontproperties=fp,fontsize=14,y=0.93)
fig.subplots_adjust(0,0,1,0.94,0,0); fig.savefig(sys.argv[2],dpi=130)
sys.exit(0 if ok else 1)
