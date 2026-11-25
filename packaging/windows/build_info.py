"""빌드한 설치 파일의 세부 정보를 모아 dist/BUILD-INFO.txt 와 dist/build-info.json 으로 적는다.

    uv run --with pyinstaller --with "pywebview>=5" --with "pyserial>=3.5" python packaging/windows/build_info.py

build_windows.bat 과 같은 --with 로 돌려야 묶인 패키지의 버전이 그대로 나온다. 윈도우 러너에서 돌리는 것을
전제로 하지만, 다른 곳에서도 구할 수 없는 값만 비워 두고 끝까지 돈다.
"""
import datetime, hashlib, importlib.metadata, json, os, platform, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST = os.path.join(ROOT, 'dist')
APP = os.path.join(DIST, 'HeaterLog')
sys.path.insert(0, ROOT)
import heater_log


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def first_line(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip().splitlines()
        return out[0].strip() if out else ''
    except Exception:
        return ''


def webview2_version():
    """이 컴퓨터에 깔린 WebView2 런타임의 버전 (설치 스크립트가 보는 것과 같은 레지스트리 값)."""
    try:
        import winreg
    except ImportError:
        return ''
    key = r'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    for root, path in ((winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\' + key), (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\' + key),
                       (winreg.HKEY_CURRENT_USER, 'Software\\' + key)):
        try:
            with winreg.OpenKey(root, path) as k:
                v = winreg.QueryValueEx(k, 'pv')[0]
                if v and v != '0.0.0.0':
                    return v
        except OSError:
            pass
    return ''


def inno_version(iscc):
    """Inno Setup 의 버전. 설치 등록 정보에서 읽고, 없으면 빈 스크립트를 컴파일해 컴파일러가 찍는 줄에서 읽는다."""
    try:
        import winreg
        for root, path in ((winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1'),
                           (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1'),
                           (winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1')):
            try:
                with winreg.OpenKey(root, path) as k:
                    v = str(winreg.QueryValueEx(k, 'DisplayVersion')[0]).strip()
                    if v and v != '0.0.0.0':
                        return v
            except OSError:
                pass
    except ImportError:
        return ''
    if not os.path.exists(iscc):
        return ''
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            iss = os.path.join(tmp, 'v.iss')
            with open(iss, 'w', encoding='ascii') as f:
                f.write('[Setup]\nAppName=v\nAppVersion=1\nDefaultDirName={tmp}\\v\nOutputDir=%s\n' % tmp)
            out = subprocess.run([iscc, iss], capture_output=True, text=True, timeout=120).stdout
        m = re.search(r'Compiler engine version: Inno Setup ([\d.]+)', out)
        return m.group(1) if m else ''
    except Exception:
        return ''


def main():
    ver = heater_log.VERSION
    setup = os.path.join(DIST, 'Band-Heater-Logger-%s-windows-x64-setup.exe' % ver)
    files = []
    for folder, _, names in os.walk(APP):
        for n in names:
            p = os.path.join(folder, n)
            files.append((os.path.relpath(p, APP).replace(os.sep, '/'), os.path.getsize(p)))
    files.sort()
    with open(os.path.join(ROOT, 'band_heater_pid', 'band_heater_pid.ino'), encoding='utf-8') as f:
        fw = re.search(r'# Band Heater PID (v[\d.]+)', f.read())
    iscc = os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Inno Setup 6', 'ISCC.exe')
    pkgs = sorted({(d.metadata['Name'] or '').lower(): d.version for d in importlib.metadata.distributions() if d.metadata['Name']}.items())
    env = os.environ.get
    info = {
        'version': ver,
        'firmware_in_source': fw.group(1) if fw else '',
        'built_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
        'commit': env('GITHUB_SHA', first_line(['git', '-C', ROOT, 'rev-parse', 'HEAD'])),
        'ref': env('GITHUB_REF_NAME', ''),
        'run_url': ('%s/%s/actions/runs/%s' % (env('GITHUB_SERVER_URL'), env('GITHUB_REPOSITORY'), env('GITHUB_RUN_ID'))) if env('GITHUB_RUN_ID') else '',
        'runner_image': ' '.join(x for x in (env('ImageOS', ''), env('ImageVersion', '')) if x),
        'os': platform.platform(),
        'python': platform.python_version() + ' ' + platform.architecture()[0],
        'gxx': first_line(['g++', '--version']),
        'inno_setup': inno_version(iscc),
        'webview2_on_build_machine': webview2_version(),
        'packages': pkgs,
        'installer': {'name': os.path.basename(setup), 'bytes': os.path.getsize(setup), 'sha256': sha256(setup)} if os.path.exists(setup) else None,
        'program': {'files': len(files), 'bytes': sum(s for _, s in files),
                    'exe_sha256': sha256(os.path.join(APP, 'HeaterLog.exe')) if os.path.exists(os.path.join(APP, 'HeaterLog.exe')) else '',
                    'virtual_board': any(n == '_internal/sim/sim_bin.exe' for n, _ in files)},
        'file_list': files,
    }
    os.makedirs(DIST, exist_ok=True)
    with open(os.path.join(DIST, 'build-info.json'), 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=1)

    L = []
    add = L.append
    add('Band Heater PID Logger %s - Windows installer build details' % ver)
    add('=' * 72)
    for k, label in (('built_utc', 'Built'), ('commit', 'Commit'), ('ref', 'Branch or tag'), ('run_url', 'Build run'), ('runner_image', 'Runner image'),
                     ('os', 'Build OS'), ('python', 'Python'), ('gxx', 'C++ compiler (virtual board)'), ('inno_setup', 'Inno Setup'),
                     ('webview2_on_build_machine', 'WebView2 Runtime on the build machine'), ('firmware_in_source', 'Firmware in this source tree')):
        add('%-40s %s' % (label + ':', info[k] or '-'))
    add('')
    if info['installer']:
        add('Installer')
        add('  %s' % info['installer']['name'])
        add('  size     %d bytes (%.1f MiB)' % (info['installer']['bytes'], info['installer']['bytes'] / 2 ** 20))
        add('  SHA-256  %s' % info['installer']['sha256'])
        add('')
    add('Installed program folder: %d files, %d bytes (%.1f MiB)' % (info['program']['files'], info['program']['bytes'], info['program']['bytes'] / 2 ** 20))
    add('  HeaterLog.exe SHA-256  %s' % (info['program']['exe_sha256'] or '-'))
    add('  virtual board bundled  %s' % ('yes' if info['program']['virtual_board'] else 'no'))
    add('')
    add('Python packages in the build environment (pywebview, pyserial and what they need go into the program;')
    add('PyInstaller and its helpers build it; the rest belongs to the build machine and is not part of the program)')
    for name, v in pkgs:
        add('  %-28s %s' % (name, v))
    add('')
    add('Files installed (path under the install folder, bytes)')
    for name, size in files:
        add('  %10d  %s' % (size, name))
    with open(os.path.join(DIST, 'BUILD-INFO.txt'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(L) + '\n')
    print('\n'.join(L[:24]))
    print('... %d files listed in dist/BUILD-INFO.txt' % len(files))


if __name__ == '__main__':
    main()
