"""릴리스 노트를 만든다: 손으로 쓴 docs/release-notes/<버전>.md 에 이번 빌드의 값을 채워 dist/RELEASE-NOTES.md 로 적는다.

    python packaging/release_notes.py

채우는 자리 (각각 _KO, _EN 두 가지):
    {{FILES_KO}}   받을 파일 표 (이름, 크기, SHA-256)
    {{BUILD_KO}}   빌드 정보 표 (커밋, 러너, 도구와 패키지 버전, 설치 폴더 크기)
    {{TESTS_KO}}   자동 점검 결과 표 (dist/selftest-*.json)
값은 packaging/windows/build_info.py 가 적은 dist/build-info.json 에서 읽는다.
"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, 'dist')
sys.path.insert(0, ROOT)
import heater_log

REPO = os.environ.get('GITHUB_REPOSITORY', 'jongsu-king/band-heater-pid')
SHOWN = ('pyinstaller', 'pywebview', 'pyserial', 'pythonnet', 'clr-loader', 'clr_loader', 'cffi', 'bottle', 'proxy-tools', 'proxy_tools',
         'typing-extensions', 'typing_extensions', 'pyinstaller-hooks-contrib', 'pefile', 'pywin32-ctypes', 'altgraph', 'pycparser')


def mib(n):
    return '%.1f MiB' % (n / 2 ** 20)


def files_table(info, ko):
    tag = 'v' + info['version']
    base = 'https://github.com/%s/releases/download/%s/' % (REPO, tag)
    rows = []
    ins = info.get('installer')
    if ins:
        rows.append(('[`%s`](%s%s)' % (ins['name'], base, ins['name']), '%s (%s B)' % (mib(ins['bytes']), format(ins['bytes'], ',')),
                     '윈도우 10·11 64비트 설치 파일' if ko else 'Installer for 64-bit Windows 10 and 11', '`%s`' % ins['sha256']))
    rows.append(('[`SHA256SUMS.txt`](%sSHA256SUMS.txt)' % base, '', '설치 파일의 SHA-256 (확인용)' if ko else 'SHA-256 of the installer, for checking the download', ''))
    rows.append(('[`BUILD-INFO.txt`](%sBUILD-INFO.txt)' % base, '', '빌드 환경과 설치되는 파일 전체 목록' if ko else 'Build environment and the full list of installed files', ''))
    head = '| 파일 | 크기 | 내용 | SHA-256 |' if ko else '| File | Size | What it is | SHA-256 |'
    return '\n'.join([head, '|---|---|---|---|'] + ['| %s | %s | %s | %s |' % r for r in rows])


def build_table(info, ko):
    p = info['program']
    pk = dict((k.replace('_', '-'), v) for k, v in info.get('packages', []))
    shown = []
    for name in SHOWN:
        n = name.replace('_', '-')
        if n in pk and n not in [s[0] for s in shown]:
            shown.append((n, pk[n]))
    commit = info.get('commit') or ''
    rows = [
        ('프로그램 버전' if ko else 'Program version', info['version']),
        ('소스의 펌웨어' if ko else 'Firmware in the source', info.get('firmware_in_source') or '-'),
        ('커밋' if ko else 'Commit', '[`%s`](https://github.com/%s/commit/%s)' % (commit[:7], REPO, commit) if commit else '-'),
        ('빌드 실행' if ko else 'Build run', info.get('run_url') or '-'),
        ('빌드 시각' if ko else 'Built', info.get('built_utc') or '-'),
        ('빌드 러너' if ko else 'Build runner', ' / '.join(x for x in (info.get('runner_image'), info.get('os')) if x) or '-'),
        ('Python', info.get('python') or '-'),
        ('묶인 패키지' if ko else 'Bundled packages', ', '.join('%s %s' % s for s in shown) or '-'),
        ('가상 보드 컴파일러' if ko else 'Compiler for the virtual board', info.get('gxx') or '-'),
        ('Inno Setup', info.get('inno_setup') or '-'),
        ('러너의 WebView2 런타임' if ko else 'WebView2 Runtime on the runner', info.get('webview2_on_build_machine') or '-'),
        ('설치되는 폴더' if ko else 'Installed folder', ('파일 %d개, %s (%s B)' if ko else '%d files, %s (%s B)') % (p['files'], mib(p['bytes']), format(p['bytes'], ','))),
        ('`HeaterLog.exe` SHA-256', '`%s`' % p['exe_sha256'] if p.get('exe_sha256') else '-'),
        ('가상 보드(연습 모드)' if ko else 'Virtual board (practice mode)', ('들어 있음' if ko else 'included') if p.get('virtual_board') else ('없음' if ko else 'not included')),
    ]
    head = '| 항목 | 값 |' if ko else '| Item | Value |'
    return '\n'.join([head, '|---|---|'] + ['| %s | %s |' % r for r in rows])


def tests_table(ko):
    names = {'selftest-windows.json': '빌드한 프로그램' if ko else 'Built program',
             'selftest-windows-installed.json': '설치한 프로그램' if ko else 'Installed copy'}
    head = ('| 대상 | 화면이 뜬 뒤 받은 줄 수 | 목표 변경 | 운전 확인 창 | 운전 중 상태·PV | 정지 뒤 상태 | 오류 |' if ko else
            '| Target | Rows received when the page was up | Setpoint change | RUN confirmation | State and PV while running | State after STOP | Error |')
    out = [head, '|---|---|---|---|---|---|---|']
    for path in sorted(glob.glob(os.path.join(DIST, 'selftest-*.json')), key=len):      # 빌드한 것 먼저, 설치한 것 다음
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
        g = lambda a, b: d.get(a, {}).get(b)
        out.append('| %s | %s | %s → %s | %s | %s, %s °C | %s | %s |' % (
            names.get(os.path.basename(path), os.path.basename(path)), g('loaded', 'rows'), g('loaded', 'sp'), g('asked', 'sp'),
            ('떴음' if ko else 'shown') if g('asked', 'dialog') else ('안 뜸' if ko else 'not shown'),
            g('running', 'mode'), g('running', 'pv'), g('stopped', 'mode'), d.get('error', '없음' if ko else 'none')))
    return '\n'.join(out) if len(out) > 2 else ('(자동 점검 결과 파일이 없음)' if ko else '(no self-test reports)')


def main():
    with open(os.path.join(DIST, 'build-info.json'), encoding='utf-8') as f:
        info = json.load(f)
    src = os.path.join(ROOT, 'docs', 'release-notes', info['version'] + '.md')
    if os.path.exists(src):
        with open(src, encoding='utf-8') as f:
            text = f.read()
    elif os.environ.get('GITHUB_REF', '').startswith('refs/tags/'):
        sys.exit('docs/release-notes/%s.md 가 없습니다. 릴리스 노트를 먼저 쓰세요.' % info['version'])
    else:
        text = '# Band Heater PID Logger %s\n\n{{FILES_EN}}\n\n{{BUILD_EN}}\n\n{{TESTS_EN}}\n' % info['version']
    fill = {'FILES_KO': files_table(info, True), 'FILES_EN': files_table(info, False), 'BUILD_KO': build_table(info, True),
            'BUILD_EN': build_table(info, False), 'TESTS_KO': tests_table(True), 'TESTS_EN': tests_table(False)}
    for k, v in fill.items():
        text = text.replace('{{%s}}' % k, v)
    left = re.findall(r'\{\{[A-Z_]+\}\}', text)
    if left:
        sys.exit('채우지 못한 자리: %s' % ', '.join(sorted(set(left))))
    with open(os.path.join(DIST, 'RELEASE-NOTES.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print('dist/RELEASE-NOTES.md: %d chars' % len(text))
    if len(text) > 120000:
        sys.exit('릴리스 노트가 GitHub 한도(125000자)에 가깝습니다')


if __name__ == '__main__':
    main()
