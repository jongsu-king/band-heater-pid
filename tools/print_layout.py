# /// script
# dependencies = ["numpy", "matplotlib"]
# ///
# 플레이트별 부품 배치를 위에서 본 그림으로 그린다. 사용: uv run -q tools/print_layout.py case/print/plate_layout.png
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from print_plates import PLACE, SIZE, BED, NAMES
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Rectangle
from matplotlib import font_manager as fm
fp = fm.FontProperties(fname='/System/Library/Fonts/AppleSDGothicNeo.ttc')
def stl(path):
    d = open(path, 'rb').read(); n = int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d, dtype=np.dtype([('n','<3f4'),('v','<9f4'),('a','<u2')]), count=n, offset=84)
    return a['v'].reshape(-1, 3, 3).astype(float)
LABEL = {'box_base.stl': '본체 box_base', 'box_lid.stl': '뚜껑 box_lid (윗면이 바닥)', 'button_bar.stl': '버튼 막대'}
TIME = {1: '약 3시간 45분 · PLA 169 g', 2: '약 1시간 55분 · PLA 77 g'}
fig, axs = plt.subplots(1, 2, figsize=(15, 8.2))
for pl, ax in zip((1, 2), axs):
    ax.add_patch(Rectangle((0, 0), BED, BED, fc='#f3f4f6', ec='#111827', lw=1.6))
    for g in np.arange(32, BED, 32):
        ax.plot([g, g], [0, BED], color='#d7dbe0', lw=0.6, zorder=1); ax.plot([0, BED], [g, g], color='#d7dbe0', lw=0.6, zorder=1)
    for nm, (p, x, y) in PLACE.items():
        if p != pl: continue
        T = stl(os.path.join('case/control_box', nm)); n = np.cross(T[:,1]-T[:,0], T[:,2]-T[:,0])
        ln = np.linalg.norm(n, axis=1); keep = (n[:,2] > 1e-9) & (ln > 1e-12); T, n = T[keep], n[keep]/ln[keep,None]
        zt = T[...,2].mean(1); o = np.argsort(zt); T, n, zt = T[o], n[o], zt[o]
        lit = 0.62 + 0.38*np.clip(n @ np.array([-0.35, -0.35, 0.87]), 0, 1); dep = 0.72 + 0.28*zt/max(zt.max(), 1e-6)
        col = np.clip((lit*dep)[:,None]*np.array([1.0, 0.55, 0.16])[None,:], 0, 1)
        ax.add_collection(PolyCollection(T[:,:,:2] + np.array([x, y]), facecolors=col, edgecolors='none', antialiaseds=False, zorder=3))
        w, d = SIZE[nm]
        ax.add_patch(Rectangle((x, y), w, d, fill=False, ec='#7c2d12', lw=1.0, zorder=4))
        if w > 50:
            ax.text(x+w/2, y+d+5, '%s  %.1f × %.1f mm' % (LABEL[nm], w, d), fontproperties=fp, fontsize=10.5, ha='center', va='bottom', color='#111827', zorder=5)
            ax.text(x+w/2, y-5, '왼쪽에서 %.1f mm · 앞에서 %.1f mm' % (x, y), fontproperties=fp, fontsize=9, ha='center', va='top', color='#374151', zorder=5)
        else:
            ax.text(x+w+5, y+d/2, '%s\n%.0f × %.0f mm' % (LABEL[nm], w, d), fontproperties=fp, fontsize=9.5, ha='left', va='center', color='#111827', zorder=5)
    ax.text(BED/2, -14, '앞 (문 쪽)', fontproperties=fp, fontsize=10, ha='center', va='top', color='#374151')
    ax.set_title('플레이트 %s   ·   %s' % (NAMES[pl], TIME[pl]), fontproperties=fp, fontsize=13.5, pad=10)
    ax.set_xlim(-22, BED+22); ax.set_ylim(-28, BED+10); ax.set_aspect('equal'); ax.axis('off')
fig.suptitle('Bambu Lab P2S (256 × 256 mm) 출력 배치 — 0.20 mm, 서포트 없음', fontproperties=fp, fontsize=15, y=0.985)
fig.text(0.5, 0.012, '시간과 무게는 밤부 스튜디오 기본 설정(0.20mm Standard, 벽 2겹, 채움 15%, Bambu PLA Basic)으로 슬라이스한 추정값', fontproperties=fp, fontsize=9.5, ha='center', color='#4b5563')
fig.subplots_adjust(0.01, 0.04, 0.99, 0.91, 0.02, 0)
fig.savefig(sys.argv[1], dpi=130)
