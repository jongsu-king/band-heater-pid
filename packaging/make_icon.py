# /// script
# dependencies = ["pillow"]
# ///
# 응용프로그램 아이콘을 그린다: 어두운 바탕에 목표선(점선)과 올라가는 온도 곡선.
# 사용: uv run packaging/make_icon.py   → packaging/icon.png, icon.ico, icon.iconset/ (맥에서는 iconutil 로 icon.icns)
import math, os
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024; k = 4; N = S * k                                   # 4배로 그려서 줄임 (가장자리 다듬기)
im = Image.new('RGBA', (N, N), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
m = int(N * 0.098); r = int(N * 0.18)                         # 맥 아이콘 여백과 둥근 모서리
d.rounded_rectangle((m, m, N - m, N - m), r, fill=(24, 28, 32, 255))
x0, x1, y0, y1 = N * 0.23, N * 0.77, N * 0.30, N * 0.72
for i in range(1, 4):                                         # 가로 눈금
    y = y0 + (y1 - y0) * i / 4; d.line((x0, y, x1, y), fill=(48, 55, 62, 255), width=int(N * 0.004))
ysp = y0 + (y1 - y0) * 0.22                                   # 목표선
seg = (x1 - x0) / 15
for i in range(0, 15, 2): d.line((x0 + i * seg, ysp, x0 + (i + 1) * seg, ysp), fill=(138, 146, 155, 255), width=int(N * 0.012))
w = int(N * 0.030)                                            # 온도 곡선: 오르다가 살짝 넘고 가라앉음 (원을 촘촘히 찍어 매끈하게)
for i in range(4001):
    t = i / 4000; u = t * 7.5
    v = 1 - math.exp(-0.9 * u) * (math.cos(1.15 * u) + 0.78 * math.sin(1.15 * u))
    x, y = x0 + (x1 - x0) * t, y1 - (y1 - ysp) * v
    d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=(240, 138, 84, 255))
d.line((x0, y0 - N * 0.02, x0, y1, x1 + N * 0.02, y1), fill=(152, 162, 173, 255), width=int(N * 0.010), joint='curve')
im = im.resize((S, S), Image.LANCZOS); im.save(os.path.join(HERE, 'icon.png'))
im.save(os.path.join(HERE, 'icon.ico'), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
iset = os.path.join(HERE, 'icon.iconset'); os.makedirs(iset, exist_ok=True)
for n in (16, 32, 128, 256, 512):
    im.resize((n, n), Image.LANCZOS).save(os.path.join(iset, 'icon_%dx%d.png' % (n, n)))
    im.resize((n * 2, n * 2), Image.LANCZOS).save(os.path.join(iset, 'icon_%dx%d@2x.png' % (n, n)))
print('ok')
