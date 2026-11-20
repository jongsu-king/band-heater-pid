#!/bin/zsh
# 통 부품 3개를 Bambu Lab P2S용 밤부 스튜디오 프로젝트(플레이트 2장)로 만든다.
# 사용: tools/make_print_project.sh   (세션 폴더에서 실행)
set -e
B="/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"
P="/Applications/BambuStudio.app/Contents/Resources/profiles/BBL"
T=$(mktemp -d); mkdir -p "$T/presets" "$T/data" "$T/a" "$T/b" case/print
python3 tools/bbs_flatten.py "$P" "$T/presets" > /dev/null          # 명령줄은 프리셋 상속을 풀지 못해서 미리 합침
H=$PWD
(cd "$T/a" && "$B" --datadir "$T/data" --debug 1 --load-settings "$T/presets/machine.json;$T/presets/process.json" \
   --load-filaments "$T/presets/filament_pla.json" --arrange 1 --export-3mf arranged.3mf --outputdir "$T/a" \
   "$H/case/control_box/box_base.stl" "$H/case/control_box/box_lid.stl" "$H/case/control_box/button_bar.stl" > /dev/null 2>&1)
python3 tools/print_plates.py "$T/a/arranged.3mf" "$T/b/edited.3mf"
(cd "$T/b" && "$B" --datadir "$T/data" --debug 1 --export-3mf control_box_P2S.3mf --outputdir "$T/b" edited.3mf > /dev/null 2>&1)
cp "$T/b/control_box_P2S.3mf" case/print/control_box_P2S.3mf
(cd "$T/b" && "$B" --datadir "$T/data" --debug 1 --slice 0 --outputdir "$T/b" control_box_P2S.3mf > /dev/null 2>&1)   # 검증용 슬라이스 (결과 G코드는 버림)
python3 - "$T/b/result.json" <<'PY'
import json, sys
j = json.load(open(sys.argv[1])); print('  슬라이스 검증:', j.get('return_code'), j.get('error_string'))
for p in j.get('sliced_plates', []):
    t = p['main_predication']
    print('  플레이트 %d  약 %d시간 %02d분  PLA %.0f g  %s  경고: %r' % (p['id'], t//3600, t%3600//60, sum(f['total_used_g'] for f in p['filaments']), [o['name'] for o in p['objects']], p.get('warning_message')))
PY
rm -rf "$T"
