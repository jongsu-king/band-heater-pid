# 밤부 스튜디오가 자동 배치한 프로젝트(3mf)의 부품 위치를 정해 둔 배치로 바꾼다.
#   플레이트 1: 본체 (가운데)
#   플레이트 2: 뚜껑(윗면이 바닥) + 버튼 누름 막대
# 사용: python3 tools/print_plates.py <자동배치.3mf> <결과.3mf>
import sys, re, zipfile
BED = 256.0; PLATE_STEP = BED * 1.2          # 밤부 스튜디오는 플레이트를 1.2배 간격으로 나란히 둠
SIZE = {'box_base.stl': (174.8, 200.8), 'box_lid.stl': (174.8, 194.8), 'button_bar.stl': (7.0, 68.0)}
GAP = 10.0
def centered(w, d): return ((BED - w) / 2, (BED - d) / 2)
bw, bd = SIZE['box_base.stl']; lw, ld = SIZE['box_lid.stl']; rw, rd = SIZE['button_bar.stl']
x0 = (BED - (lw + GAP + rw)) / 2
PLACE = {  # 이름: (플레이트 번호, x, y)  — 플레이트 왼쪽 앞 모서리 기준, 부품의 왼쪽 앞 모서리 위치
    'box_base.stl':   (1, *centered(bw, bd)),
    'box_lid.stl':    (2, x0, (BED - ld) / 2),
    'button_bar.stl': (2, x0 + lw + GAP, (BED - rd) / 2),
}
NAMES = {1: '1 본체', 2: '2 뚜껑 + 버튼 막대'}
def main(src, dst):
    zi = zipfile.ZipFile(src)
    ms = zi.read('Metadata/model_settings.config').decode()
    model = zi.read('3D/3dmodel.model').decode()
    ids = {}                                      # 이름 -> object id
    for oid, body in re.findall(r'<object id="(\d+)">(.*?)</object>', ms, re.S):
        ids[re.search(r'key="name" value="([^"]+)"', body).group(1)] = oid
    assert set(ids) == set(PLACE), ids
    for nm, (pl, x, y) in PLACE.items():
        wx = x + (pl - 1) * PLATE_STEP
        pat = r'(<item objectid="%s"[^>]*transform="1 0 0 0 1 0 0 0 1 )[-\d.e]+ [-\d.e]+ ([-\d.e]+")' % ids[nm]
        model, n = re.subn(pat, lambda m: '%s%.4f %.4f %s' % (m.group(1), wx, y, m.group(2)), model); assert n == 1, nm
    inst = {}                                     # object id -> model_instance 블록
    for blk in re.findall(r'    <model_instance>.*?</model_instance>\n', ms, re.S):
        inst[re.search(r'key="object_id" value="(\d+)"', blk).group(1)] = blk
    ms = re.sub(r'    <model_instance>.*?</model_instance>\n', '', ms, flags=re.S)
    def fill(m):
        pid = int(m.group(2)); body = m.group(1) + m.group(2) + m.group(3)
        body = body.replace('key="plater_name" value=""', 'key="plater_name" value="%s"' % NAMES[pid])
        return body + ''.join(inst[ids[nm]] for nm, (pl, _, _) in PLACE.items() if pl == pid) + '  </plate>'
    ms, n = re.subn(r'(  <plate>\s*<metadata key="plater_id" value=")(\d+)(".*?)  </plate>', fill, ms, flags=re.S); assert n == 2
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zo:
        for it in zi.infolist():
            data = {'Metadata/model_settings.config': ms.encode(), '3D/3dmodel.model': model.encode()}.get(it.filename, zi.read(it.filename))
            zo.writestr(it, data)
    for nm, (pl, x, y) in PLACE.items():
        w, d = SIZE[nm]; print('  플레이트 %d  %-15s x %.1f~%.1f  y %.1f~%.1f  (가장자리 여유 %.1f mm)' % (pl, nm, x, x+w, y, y+d, min(x, y, BED-x-w, BED-y-d)))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
