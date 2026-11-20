# PyInstaller 설정: 맥용 응용프로그램(.app)과 윈도우용 exe 를 같은 파일로 만든다.
#   맥:     packaging/build_mac.sh
#   윈도우: build_windows.bat
import os, sys
ROOT = os.path.dirname(SPECPATH)
mac = sys.platform == 'darwin'
datas = [(os.path.join(ROOT, 'heater_log.html'), '.')]
binaries = []
sim = os.path.join(ROOT, 'tools', 'sim', 'sim_bin')
if mac and os.path.exists(sim):
    binaries.append((sim, 'sim'))                              # 연습 모드용 가상 보드 (맥에서만 넣음)

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
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='HeaterLog', console=False,
              icon=os.path.join(SPECPATH, 'icon.ico'))
