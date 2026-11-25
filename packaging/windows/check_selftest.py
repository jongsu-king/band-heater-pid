"""--selftest 가 남긴 결과 파일을 확인한다 (빌드 확인용, 가상 보드에서만).

    python packaging/windows/check_selftest.py dist/selftest-windows.json

프로그램이 창 안의 화면을 직접 조작한 기록이다: 화면이 뜨고 가상 보드의 값이 들어오는지,
운전 단추가 확인 창을 띄우는지, 운전·정지가 되는지를 본다. 하나라도 어긋나면 0 이 아닌 값으로 끝난다.
"""
import json, sys

bad = 0
for path in sys.argv[1:]:
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    print(path)
    print(json.dumps(d, ensure_ascii=False))
    checks = [
        ('no error while driving the window', 'error' not in d),
        ('page loaded and board data reached the chart', d.get('loaded', {}).get('rows', 0) > 0 and d['loaded'].get('pv') is not None),
        ('chart canvas has a size', d.get('loaded', {}).get('canvas', 0) > 0),
        ('idle before RUN', d.get('loaded', {}).get('mode') == 'STOP'),
        ('setpoint command applied (sp 60)', d.get('asked', {}).get('sp') == 60),
        ('RUN asks for confirmation', d.get('asked', {}).get('dialog') is True and d['asked'].get('mode') == 'STOP'),
        ('running after confirming', d.get('running', {}).get('mode') == 'RUN'),
        ('data keeps arriving', d.get('running', {}).get('rows', 0) > d.get('loaded', {}).get('rows', 0)),
        ('stopped by the STOP button', d.get('stopped', {}).get('mode') == 'STOP'),
    ]
    for name, ok in checks:
        print('  %s  %s' % ('ok  ' if ok else 'FAIL', name))
        bad += not ok
if len(sys.argv) < 2:
    sys.exit('usage: check_selftest.py FILE...')
sys.exit(1 if bad else 0)
