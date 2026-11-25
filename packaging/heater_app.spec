# PyInstaller 설정: 맥용 응용프로그램(.app)과 윈도우용 프로그램 폴더를 같은 파일로 만든다.
#   맥:     packaging/build_mac.sh
#   윈도우: build_windows.bat  (dist/HeaterLog/ 를 만들고, 이어서 packaging/windows/installer.iss 로 설치 파일을 만든다)
import os, re, sys
ROOT = os.path.dirname(SPECPATH)
mac = sys.platform == 'darwin'
win = sys.platform == 'win32'
with open(os.path.join(ROOT, 'heater_log.py'), encoding='utf-8') as f:
    VER = re.search(r"^VERSION = '([^']+)'", f.read(), re.M).group(1)
datas = [(os.path.join(ROOT, 'heater_log.html'), '.')]
binaries = []
sim = os.path.join(ROOT, 'tools', 'sim', 'sim_bin.exe' if win else 'sim_bin')
if (mac or win) and os.path.exists(sim):
    binaries.append((sim, 'sim'))                              # 연습 모드용 가상 보드 (있을 때만 넣음)

a = Analysis([os.path.join(ROOT, 'heater_app.py')], pathex=[ROOT], datas=datas, binaries=binaries,
             hiddenimports=['serial.tools.list_ports'], excludes=['tkinter', 'numpy', 'matplotlib', 'PIL'])
pyz = PYZ(a.pure)
if mac:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='HeaterLog', console=False,
              icon=os.path.join(SPECPATH, 'icon.icns'))
    coll = COLLECT(exe, a.binaries, a.datas, name='HeaterLog')
    app = BUNDLE(coll, name='밴드히터 기록.app', icon=os.path.join(SPECPATH, 'icon.icns'),
                 bundle_identifier='local.bandheater.log', version='1.1',
                 info_plist={'CFBundleDisplayName': '밴드히터 기록', 'CFBundleName': '밴드히터 기록',
                             'NSHighResolutionCapable': True, 'LSMinimumSystemVersion': '11.0',
                             'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True}})
elif win:
    # 폴더로 묶는다(설치 파일이 이 폴더를 설치함). 파일 속성에 보이는 버전은 heater_log.py 의 VERSION 이고,
    # 설치 스크립트도 이 값을 읽어 쓴다.
    from PyInstaller.utils.win32.versioninfo import (VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable,
                                                     StringStruct, VarFileInfo, VarStruct)
    num = tuple(int(x) for x in (re.findall(r'\d+', VER) + ['0', '0', '0'])[:4])
    info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=num, prodvers=num),
        kids=[StringFileInfo([StringTable('040904B0', [
                  StringStruct('CompanyName', 'jongsu-king'),
                  StringStruct('FileDescription', 'Band Heater PID Logger'),
                  StringStruct('FileVersion', VER),
                  StringStruct('InternalName', 'HeaterLog'),
                  StringStruct('LegalCopyright', 'MIT License'),
                  StringStruct('OriginalFilename', 'HeaterLog.exe'),
                  StringStruct('ProductName', 'Band Heater PID Logger'),
                  StringStruct('ProductVersion', VER)])]),
              VarFileInfo([VarStruct('Translation', [1033, 1200])])])
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='HeaterLog', console=False,
              icon=os.path.join(SPECPATH, 'icon.ico'), version=info)
    coll = COLLECT(exe, a.binaries, a.datas, name='HeaterLog')
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='HeaterLog', console=False,
              icon=os.path.join(SPECPATH, 'icon.ico'))
