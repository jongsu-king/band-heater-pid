#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyserial>=3.5"]
# ///
"""밴드 히터 PID 컨트롤러 기록 프로그램.

나노가 USB 시리얼(115200)로 1초마다 내보내는 줄을 받아 파일로 저장하고,
브라우저에 실시간 그래프와 통계를 띄운다. 펌웨어는 고치지 않는다.

    uv run heater_log.py                       보드를 찾아 연결
    uv run heater_log.py --port /dev/cu.usbserial-XXXX
    uv run heater_log.py --name "Cu블록 150도"   실험 이름을 미리 정함
    uv run heater_log.py --sim 30              보드 없이 가상 보드로 연습 (30배속)
    uv run heater_log.py --lang en             영어 화면 (화면의 툴바에서도 바꿀 수 있음)
    uv run heater_app.py                       브라우저 대신 전용 창으로 (응용프로그램은 이것을 묶은 것)

기록은 기본으로 ~/Documents/밴드히터_기록 에 실험마다 파일 네 개로 남는다 (--out 으로 변경).
  heater_날짜_시각_이름.csv           1초마다 한 줄 (열 설명은 _meta.json 의 columns)
  heater_날짜_시각_이름_events.txt    운전·정지·경보·설정 변경·보낸 명령·마커
  heater_날짜_시각_이름_raw.log       보드가 보낸 줄 전부 (받은 시각과 함께, 가공하지 않음)
  heater_날짜_시각_이름_meta.json     실험 이름·시료·메모, 채널 이름, 펌웨어, PID 설정, 열 설명

포트를 열 때 나노가 리셋된다(아두이노의 정상 동작). 운전 중에 켜면 히터가 꺼지므로
이 프로그램을 먼저 켜고 나서 운전을 시작한다.
"""
import argparse, atexit, base64, datetime, glob, html, json, os, re, secrets, signal, subprocess, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

VERSION = '1.5'
HERE = os.path.dirname(os.path.abspath(__file__))
RES = getattr(sys, '_MEIPASS', HERE)    # 응용프로그램으로 묶였을 때는 그 안의 자원 폴더
USB_VID = {0x0403, 0x1A86, 0x10C4, 0x2341, 0x2A03, 0x067B}        # FTDI, CH340, CP210x, Arduino, Prolific
KEYS = ['PV', 'SP', 'OUT', 'T1', 'T2', 'T3', 'T4']
HEAD = ['PV_degC', 'SP_degC', 'OUT_pct', 'T1_degC', 'T2_degC', 'T3_degC', 'T4_degC']
FMT = ['%.2f', '%.1f', '%.1f', '%.2f', '%.2f', '%.2f', '%.2f']
MODE_CODE = {'STOP': 0, 'RUN': 1, 'TUNE': 2, 'FAULT': 3}
MAX_ROWS = 400000                       # 화면용으로 메모리에 두는 표본 수 (1초 간격으로 약 4.6일). 파일에는 제한 없이 쓴다
CMD_OK = re.compile(r'^(?:(?:sp|spt|kp|ki|kd|out) \d+(?:\.\d+)?|src (?:[1-4]|avg|max)|run|stop|tune|clear|show|help|log [01])$')
RE_SET = re.compile(r'^# SP=(\S+) Kp=(\S+) Ki=(\S+) Kd=(\S+) OUTMAX=(\S+) SRC=(\S+) MODE=(\S+)(?: (.*))?$')
RE_AC = re.compile(r'^# AC: RELAY=(ON|OFF) SSR=(ON|OFF) E=([\d.]+)Wh RUNTIME=(\d+)min')
RE_VER = re.compile(r'^# Band Heater PID (\S+)')
COLUMNS = {
    'time': '컴퓨터 시각 (현지 시각, 밀리초까지)',
    'elapsed_s': '이 파일의 기록을 시작한 뒤 지난 시간 [s]',
    'PV_degC': '제어에 쓰는 온도 (제어 기준 채널, 또는 평균·최대) [°C]',
    'SP_degC': '목표 온도 [°C]',
    'OUT_pct': 'PID 출력 = SSR 시분할 켜짐 비율 [%]',
    'T1_degC': '열전대 채널 1 [°C] (읽히지 않으면 빈칸)', 'T2_degC': '열전대 채널 2 [°C]',
    'T3_degC': '열전대 채널 3 [°C]', 'T4_degC': '열전대 채널 4 [°C]',
    'mode': 'STOP / RUN / TUNE(오토튜닝) / FAULT(경보). 보드에 3초마다 물어 갱신하므로 버튼으로 바꾼 직후 몇 초는 늦을 수 있음',
}


# 영어판: 화면·사건 기록·알림으로 나가는 문구를 내보내는 자리에서 바꾼다. 맞는 규칙이 없으면 원문 그대로.
EN_EXACT = {
    '보드를 찾는 중입니다 (USB를 연결하세요)': 'Looking for the board (plug in the USB cable)', '보드를 찾는 중입니다': 'Looking for the board',
    '가상 보드를 켜는 중입니다': 'Starting the virtual board', '가상 보드가 종료됨': 'Virtual board ended', '가상 보드 파일이 없습니다': 'virtual board file is missing',
    'USB가 빠졌거나 다른 프로그램이 포트를 사용 중입니다': 'USB unplugged, or the port is in use by another program',
    '다른 프로그램이 사용 중 (아두이노 시리얼 모니터를 닫으세요)': 'in use by another program (close the Arduino serial monitor)', '포트를 찾을 수 없음': 'port not found',
    '연결 끊김': 'Disconnected', 'PC 경보 확인': 'PC alarm acknowledged', '보드가 연결돼 있지 않습니다': 'The board is not connected',
    '마커를 추가했습니다': 'Marker added', '실험 정보를 저장했습니다': 'Experiment info saved', '저장했습니다': 'Saved', '경보를 확인했습니다': 'Alarm acknowledged',
    '그림 형식이 아닙니다': 'Not an image', '그림을 읽지 못했습니다': 'Could not read the image', '기록 폴더를 열었습니다': 'Record folder opened',
    '이 컴퓨터에는 가상 보드가 없습니다': 'No virtual board on this computer', '연습 모드를 켰습니다 (실제 히터는 켜지지 않음)': 'Practice mode on (the real heater stays off)',
    '실물 보드로 돌아왔습니다': 'Back to the real board', '목록에 없는 포트입니다': 'That port is not in the list', '포트: 자동': 'Port: auto',
    '이미 프로그램 운전 중입니다': 'A program is already running', '보드 경보 상태입니다. 먼저 경보를 해제하세요': 'The board is in alarm. Clear the alarm first',
    '오토튜닝 중입니다': 'Auto-tune is running', '단계가 없습니다': 'The program has no steps', '현재 온도를 읽지 못했습니다': 'No temperature reading',
    '프로그램 운전 시작': 'Program started', '프로그램 운전 중이 아닙니다': 'No program is running', '프로그램 중지, 히터 정지': 'Program stopped, heater off',
    '구간이 올바르지 않습니다': 'Invalid range', '기록 파일이 없습니다': 'No record file', '저장할 통계가 없습니다': 'No statistics to save',
    '차트 그림이 없습니다': 'No chart image', '차트 그림이 올바르지 않습니다': 'Bad chart image', '기록을 찾지 못했습니다': 'Record not found',
    '보드 연결이 끊겼습니다': 'Board disconnected', '밴드 히터': 'Band heater',
    '기록 파일: %s': 'Record file: %s', '화면: %s   (끝내려면 Ctrl+C)': 'Page: %s   (Ctrl+C to quit)', '종료. 기록 파일: %s': 'Stopped. Record file: %s',
    '프로그램 중지': 'Program stopped', '프로그램 끝: 히터 정지': 'Program finished: heater off', '프로그램 끝: 마지막 목표 유지': 'Program finished: holding the last setpoint',
    '프로그램 중단': 'Program aborted', '프로그램 중단: 연결 끊김': 'Program aborted: disconnected', '프로그램 중단: 보드가 정지됨': 'Program aborted: the board was stopped',
    '프로그램 중단: 운전 시작 실패': 'Program aborted: could not start', '프로그램 중단: 온도 값 없음': 'Program aborted: no temperature reading',
    # 보고서
    '실험': 'Experiment', '이름': 'Name', '시료': 'Sample', '메모': 'Notes', '기록 시작': 'Record started', '보고서 작성': 'Report written', '구간': 'Range',
    '기록 줄 수': 'Rows recorded', '보드와 설정': 'Board and settings', '포트': 'Port', '펌웨어': 'Firmware', '가상 보드': 'Virtual board', '예': 'yes', '아니오': 'no',
    '출력 한계 (%)': 'Output limit (%)', '제어 기준': 'Control sensor', '목표 SP (°C)': 'Setpoint SP (°C)', 'PC 경보 상한 T1~T4 (°C)': 'PC alarm limits T1–T4 (°C)',
    'PC 경보 채널 간 차이 (°C)': 'PC alarm channel spread (°C)', '히터 정격 (W), 전력 추정용': 'Heater rating (W), for the power estimate', '차트': 'Chart',
    '이벤트 기록': 'Event log', '경과 (s)': 'Elapsed (s)', '종류': 'Kind', '내용': 'Text', '파일': 'Files', '데이터': 'Data', '이벤트': 'Events', '원본 로그': 'Raw log', '메타데이터': 'Metadata',
}
_al = lambda t: t.replace('채널 간 차이', 'channel spread').replace('상한', 'limit')
EN_RX = [(re.compile(a), b) for a, b in [
    (r'^연결됨: 가상 보드 (\S+)배속$', r'Connected: virtual board ×\1'), (r'^가상 보드 (\S+)배속$', r'Virtual board ×\1'), (r'^연결됨: (.*)$', r'Connected: \1'),
    (r'^연결 끊김: (.*)$', lambda m: 'Disconnected: ' + to_en(m[1])), (r'^(\S+) 포트를 열 수 없습니다: (.*)$', lambda m: 'Cannot open %s: %s' % (m[1], to_en(m[2]))),
    (r'^가상 보드를 켜지 못했습니다: (.*)$', lambda m: 'Could not start the virtual board: ' + to_en(m[1])),
    (r'^변경: (.*)$', r'Changed: \1'),
    (r'^프로그램: (.*)$', r'Program: \1'), (r'^경보: (.*)$', r'Alarm: \1'),
    (r'^PC 경보: 상한 (\S+), 채널 차이 (\S+), 경보 시 정지 (켬|끔)$', lambda m: 'PC alarm: limits %s, channel spread %s, stop on alarm %s' % (m[1], m[2], 'on' if m[3] == '켬' else 'off')),
    (r'^PC 경보: (.*)$', lambda m: 'PC alarm: ' + _al(m[1])), (r'^(T\d .*상한.*|채널 간 차이.*)$', lambda m: _al(m[1])),
    (r'^안정: (PV .*) \(목표 (\S+), 최근 (\S+)분\)$', r'Stable: \1 (setpoint \2, last \3 min)'),
    (r'^프로그램 시작: (\d+)단계 × (\d+)회, 목표 변경 명령 (\w+)( .*)?$', lambda m: 'Program started: %s steps × %s cycles, setpoint command %s%s' % (m[1], m[2], m[3], ' (firmware older than v1.4: 1 °C steps, saved to the board on every change)' if m[4] else '')),
    (r'^(?:(\d+)회째 )?(\d+)단계: (.*) °C, (.*), 유지 (\S+)분$', lambda m: '%sStep %s: %s °C, %s, hold %s min' % ('Cycle %s, ' % m[1] if m[1] else '', m[2], m[3], 'at once' if m[4] == '즉시' else m[4].replace('°C/분', '°C/min'), m[5])),
    (r'^(\d+)단계 도달: (.*)$', r'Step \1 reached: \2'), (r'^프로그램 중단: 보드 경보 \((.*)\)$', r'Program aborted: board alarm (\1)'),
    (r'^연결 직후 수신한 (\d+)바이트 무시 .*$', r'Ignored \1 bytes received right after connecting (stale data from before the board booted)'),
    (r'^비정상적으로 빠르게 수신된 데이터 (\d+)줄 무시$', r'Ignored \1 data lines that arrived abnormally fast'),
    (r'^마커 (\d+)$', r'Marker \1'), (r'^표시 (\d+)$', r'Marker \1'), (r'^상태 (\S+ → .*)$', r'\1'), (r'^설정 (SP=.*)$', r'\1'),
    (r'^설정 변경: (.*)$', r'Changed: \1'), (r'^(PC|프로그램|경보) 명령: (.*)$', lambda m: {'PC': 'PC', '프로그램': 'Program', '경보': 'Alarm'}[m[1]] + ': ' + m[2]), (r'^사용할 수 없는 명령: (.*)$', r'Command not allowed: \1'), (r'^새 파일: (.*)$', r'New file: \1'),
    (r'^그림 저장: (.*)$', r'Image saved: \1'), (r'^포트: (.*)$', r'Port: \1'), (r'^구간 저장: (.*) \((\d+)줄\)$', r'Range saved: \1 (\2 rows)'),
    (r'^통계 저장: (.*)$', r'Statistics saved: \1'), (r'^보고서 저장: (.*)$', r'Report saved: \1'), (r'^보드 경보: (.*)$', r'Board alarm: \1'),
    (r'^보고서 (.*)$', r'Report \1'), (r'^(T\d) 위치$', r'\1 position'),
]]


def to_en(text):
    if not isinstance(text, str) or not text:
        return text
    if text in EN_EXACT:
        return EN_EXACT[text]
    for rx, rep in EN_RX:
        m = rx.match(text)
        if m:
            return rep(m) if callable(rep) else m.expand(rep)
    return text


COLUMNS_EN = {
    'time': 'computer clock (local time, to the millisecond)', 'elapsed_s': 'time since this record file was started [s]',
    'PV_degC': 'temperature used for control (the control channel, or average / maximum) [°C]', 'SP_degC': 'setpoint [°C]',
    'OUT_pct': 'PID output = SSR on-time share in each window [%]', 'T1_degC': 'thermocouple channel 1 [°C] (empty when unreadable)',
    'T2_degC': 'thermocouple channel 2 [°C]', 'T3_degC': 'thermocouple channel 3 [°C]', 'T4_degC': 'thermocouple channel 4 [°C]',
    'mode': 'STOP / RUN / TUNE (auto-tune) / FAULT (alarm). Refreshed from the board every 3 s, so it can lag a few seconds after a button press',
}


def num(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float('inf') else None      # nan, inf 는 빈 값


def fw_tuple(v):
    m = re.match(r'v?(\d+)\.(\d+)', v or '')
    return (int(m[1]), int(m[2])) if m else (0, 0)


def clean(s, n=200):
    return re.sub(r'[\x00-\x1f\x7f]+', ' ', str(s or '')).strip()[:n]


def slug(s):
    return re.sub(r'[^\w-]+', '_', clean(s, 40)).strip('_')


def stamp_ms():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


SIM_BIN = 'sim_bin.exe' if os.name == 'nt' else 'sim_bin'


def docs_dir():
    """문서 폴더. 윈도우에서는 OneDrive 등으로 옮겨져 있을 수 있어서 시스템에 물어본다."""
    if os.name == 'nt':
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(260)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:      # 5 = CSIDL_PERSONAL (문서)
                return buf.value
        except Exception:
            pass
    return os.path.join(os.path.expanduser('~'), 'Documents')


def sim_exe(build=False):
    """가상 보드 실행 파일의 위치. 없으면 None. build=True 이면 소스가 있을 때 새로 컴파일한다."""
    packed = os.path.join(RES, 'sim', SIM_BIN)
    if os.path.exists(packed):
        return packed
    src = os.path.join(HERE, 'tools', 'sim', 'sim.cpp')
    ino = os.path.join(HERE, 'band_heater_pid', 'band_heater_pid.ino')
    exe = os.path.join(HERE, 'tools', 'sim', SIM_BIN)
    if build and os.path.exists(src) and os.path.exists(ino) and (
            not os.path.exists(exe) or os.path.getmtime(exe) < max(os.path.getmtime(src), os.path.getmtime(ino))):
        subprocess.run(['c++', '-std=c++17', '-w', '-x', 'c++', '-I', os.path.join(HERE, 'tools', 'sim', 'mock'),
                        '-I', os.path.join(HERE, 'band_heater_pid'), src, '-o', exe], check=True)
    return exe if os.path.exists(exe) else None


def parse(line):
    """펌웨어가 내보낸 한 줄 → (종류, 내용). 알 수 없는 줄은 (None, None)."""
    line = line.strip()
    if line.startswith('PV:'):
        d = {}
        for part in line.split(','):
            k, sep, v = part.partition(':')
            if not sep:
                return None, None
            d[k.strip().upper()] = num(v)
        if d.get('SP') is None or d.get('OUT') is None:
            return None, None                                    # 중간이 잘린 줄
        return 'data', d
    m = RE_SET.match(line)
    if m:
        return 'set', dict(sp=num(m[1]), kp=num(m[2]), ki=num(m[3]), kd=num(m[4]), outmax=num(m[5]),
                           src=m[6], mode=m[7], fault=m[8] or '')
    m = RE_AC.match(line)
    if m:
        return 'ac', dict(relay=m[1], ssr=m[2], energy=num(m[3]), runtime=int(m[4]))
    if line.startswith('# commands') or line.startswith('#   '):
        return None, None                                        # 도움말 줄
    if line.startswith(('!! ', 'Auto-tune', '? ', '# ')) or line in ('RUN', 'STOP', 'Fault cleared'):
        return 'text', line
    return None, None


class Hub:
    """받은 값을 모아 두고 파일에 쓴다. 웹 화면과 시리얼 쓰레드가 같이 쓴다."""

    def __init__(self, out_dir, name=''):
        self.lock = threading.RLock()
        self.base_dir = self.out_dir = out_dir
        self.scale, self.link, self.thread = 1.0, None, None
        self.ports, self.want = [], ''
        self.gen = 0
        self.meta = dict(name=clean(name, 60), sample='', memo='', labels=['', '', '', ''], pos=[None, None, None, None])
        self.state = dict(connected=False, port='', note='보드를 찾는 중입니다', mode='', fault='', version='',
                          sp=None, kp=None, ki=None, kd=None, outmax=None, src='',
                          relay='', ssr='', energy=None, runtime=None, csv='', sim=False)
        self.csv = self.evf = self.raw = None
        self.last_port = ''
        # PC 쪽 설정: 온도 프로그램(승온·유지 단계)과 PC 경보. 기록 폴더의 설정.json 에 남는다
        self.cfg = dict(steps=[dict(target=80.0, rate=5.0, hold=10.0)], cycles=1, tol=1.0, end_stop=True,
                        hi=[None, None, None, None], spread=None, auto_stop=True, heater_w=400.0, presets={},
                        stab_tol=1.0, stab_rate=0.2, stab_min=3.0, notify=False, rod_d=None, rod_k=398.0, lang='ko')
        self.prog = dict(on=False, step=0, n=0, phase='', sp=None, target=None, left=None)
        self.alarm = dict(active=[], latched='', n=0)
        self._pstop = threading.Event()
        self._tok, self._tok_at, self._dropped, self._drop_at = 10.0, time.monotonic(), 0, 0.0
        self._tok2, self._tok2_at = 50.0, time.monotonic()
        self.stable = dict(on=False, since=None, mean=None, std=None)
        try:
            with open(os.path.join(self.base_dir, '설정.json'), encoding='utf-8') as f:
                self._merge_cfg(json.load(f))
        except (OSError, ValueError):
            pass

    def L(self, text):
        """지금 고른 언어의 문구. 영어를 골랐을 때만 바꾼다."""
        return to_en(text) if self.cfg.get('lang') == 'en' else text

    # ---------- PC 쪽 설정 ----------
    def _merge_cfg(self, d):
        c = self.cfg

        def f(x, lo, hi):
            x = num(x)
            return None if x is None else min(hi, max(lo, x))
        if not isinstance(d, dict):
            return
        def steps_of(v):
            out = []
            for st in (v if isinstance(v, list) else [])[:20]:
                if isinstance(st, dict) and f(st.get('target'), 0, 300) is not None:
                    out.append(dict(target=f(st.get('target'), 0, 300), rate=f(st.get('rate'), 0, 60) or 0.0,
                                    hold=f(st.get('hold'), 0, 6000) or 0.0))
            return out
        if isinstance(d.get('steps'), list):
            c['steps'] = steps_of(d['steps'])
        if 'cycles' in d:
            c['cycles'] = int(f(d['cycles'], 1, 100) or 1)
        if 'heater_w' in d:
            c['heater_w'] = f(d['heater_w'], 1, 10000) or 400.0
        for k, lo, hi, dflt in (('stab_tol', 0.05, 50, 1.0), ('stab_rate', 0.01, 50, 0.2), ('stab_min', 0.5, 120, 3.0), ('rod_k', 0.01, 5000, 398.0)):
            if k in d:
                c[k] = f(d[k], lo, hi) or dflt
        if 'rod_d' in d:
            c['rod_d'] = f(d['rod_d'], 0.1, 1000)
        if 'notify' in d:
            c['notify'] = bool(d['notify'])
        if d.get('lang') in ('ko', 'en'):
            c['lang'] = d['lang']
        if isinstance(d.get('presets'), dict):                     # 이름 붙인 프로그램 묶음. 통째로 바꿔 넣는다
            pre = {}
            for k, v in list(d['presets'].items())[:30]:
                if isinstance(v, dict) and clean(k, 30):
                    pre[clean(k, 30)] = dict(steps=steps_of(v.get('steps')), cycles=int(f(v.get('cycles'), 1, 100) or 1),
                                             tol=f(v.get('tol'), 0.1, 20) or 1.0, end_stop=bool(v.get('end_stop', True)))
            c['presets'] = pre
        if 'tol' in d:
            c['tol'] = f(d['tol'], 0.1, 20) or 1.0
        if 'end_stop' in d:
            c['end_stop'] = bool(d['end_stop'])
        if isinstance(d.get('hi'), list):
            c['hi'] = [f(x, -200, 400) for x in (d['hi'] + [None] * 4)[:4]]
        if 'spread' in d:
            c['spread'] = f(d['spread'], 0.1, 400)
        if 'auto_stop' in d:
            c['auto_stop'] = bool(d['auto_stop'])

    def set_cfg(self, d):
        with self.lock:
            before = json.dumps([self.cfg['hi'], self.cfg['spread'], self.cfg['auto_stop']])
            self._merge_cfg(d)
            c = self.cfg
            os.makedirs(self.base_dir, exist_ok=True)
            tmp = os.path.join(self.base_dir, '설정.json.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(c, f, ensure_ascii=False, indent=1)
            os.replace(tmp, os.path.join(self.base_dir, '설정.json'))
            if self.csv and before != json.dumps([c['hi'], c['spread'], c['auto_stop']]):
                self._event('set', 'PC 경보: 상한 %s, 채널 차이 %s, 경보 시 정지 %s' % (
                    '/'.join('-' if v is None else '%g' % v for v in c['hi']),
                    '-' if c['spread'] is None else '%g' % c['spread'], '켬' if c['auto_stop'] else '끔'))

    # ---------- 알림 (맥의 알림 센터). 켜 둔 경우에만 ----------
    def _notify(self, text):
        if not self.cfg.get('notify') or sys.platform != 'darwin':
            return
        q = lambda x: str(x).replace('\\', ' ').replace('"', "'")[:180]
        text = self.L(text)
        title = self.L('밴드 히터') + (' · ' + self.meta['name'] if self.meta['name'] else '')
        try:
            subprocess.Popen(['osascript', '-e', 'display notification "%s" with title "%s"' % (q(text), q(title))],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    # ---------- 안정 판정: 운전 중에 PV가 목표 ±tol 안에 있고 기울기가 작게 stab_min 분 동안 이어지면 안정 ----------
    def _check_stable(self, row):
        c, st = self.cfg, self.stable
        t, pv, sp, mode = row[0], row[1], row[2], row[8]
        W = c['stab_min'] * 60.0
        ok = False
        if mode == 1 and pv is not None and sp is not None and abs(pv - sp) <= c['stab_tol']:
            R = self.rows
            i = len(R) - 1
            n = sx = sy = sxx = sxy = syy = 0.0
            broke = False
            while i >= 0 and R[i][0] >= t - W:
                r = R[i]
                if r[8] != 1 or r[1] is None or r[2] != sp or abs(r[1] - sp) > c['stab_tol']:
                    broke = True
                    break
                x, y = r[0] - t, r[1] - sp
                n += 1; sx += x; sy += y; sxx += x * x; sxy += x * y; syy += y * y
                i -= 1
            covered = not broke and i >= 0                         # 창보다 앞선 줄이 있어야 창 전체를 본 것
            if covered and n >= 10:
                den = sxx - sx * sx / n
                slope = (sxy - sx * sy / n) / den * 60.0 if den > 1e-9 else 0.0
                if abs(slope) <= c['stab_rate']:
                    ok = True
                    st.update(mean=sp + sy / n, std=(max(0.0, (syy - sy * sy / n) / (n - 1))) ** 0.5)
        if ok and not st['on']:
            st.update(on=True, since=t)
            txt = '안정: PV %.2f ± %.2f °C (목표 %.1f, 최근 %g분)' % (st['mean'], st['std'], sp, c['stab_min'])
            self._event('stable', txt)
            self._notify(txt)
        elif not ok and st['on']:
            st.update(on=False, since=None)

    # ---------- PC 경보: 채널 상한, 채널 간 차이 ----------
    def _alarm_conditions(self, row):
        c, out = self.cfg, []
        if not row:
            return out
        vals = row[4:8]
        for i, v in enumerate(vals):
            hi = c['hi'][i]
            if hi is not None and v is not None and v > hi:
                out.append('T%d %.1f °C > 상한 %g' % (i + 1, v, hi))
        ok = [v for v in vals if v is not None]
        if c['spread'] is not None and len(ok) >= 2 and max(ok) - min(ok) > c['spread']:
            out.append('채널 간 차이 %.1f °C > %g' % (max(ok) - min(ok), c['spread']))
        return out

    def _check_alarm(self, row):
        a = self.alarm
        cond = self._alarm_conditions(row)
        a['active'] = cond
        a['n'] = a['n'] + 1 if cond else 0
        if cond and a['n'] == 2 and not a['latched']:              # 두 번 연속일 때만 (한 번 튄 값은 넘김)
            a['latched'] = cond[0]
            self._event('alarm', 'PC 경보: ' + '; '.join(cond))
            self._notify('PC 경보: ' + cond[0])
            if self.cfg['auto_stop'] and self.state['mode'] in ('RUN', 'TUNE'):
                self._pstop.set()
                self.send('stop', who='경보')

    def alarm_ack(self):
        with self.lock:
            if self.alarm['latched'] and self.csv:
                self._event('alarm', 'PC 경보 확인')
            self.alarm.update(latched='', n=0)

    # ---------- 온도 프로그램: 단계마다 승온 속도로 목표를 올리고, 도달하면 유지 시간만큼 머문다 ----------
    def _last_pv(self):
        return self.rows[-1][1] if self.rows else None

    def prog_start(self):
        with self.lock:
            s = self.state
            if self.prog['on']:
                return False, '이미 프로그램 운전 중입니다'
            if not s['connected']:
                return False, '보드가 연결돼 있지 않습니다'
            if s['mode'] == 'FAULT':
                return False, '보드 경보 상태입니다. 먼저 경보를 해제하세요'
            if s['mode'] == 'TUNE':
                return False, '오토튜닝 중입니다'
            steps = [dict(x) for x in self.cfg['steps']]
            cycles = self.cfg['cycles']
            if not steps:
                return False, '단계가 없습니다'
            if self._last_pv() is None:
                return False, '현재 온도를 읽지 못했습니다'
            self._pstop = threading.Event()
            self.prog.update(on=True, step=0, n=len(steps), cycle=1, cycles=cycles, phase='start', sp=None, target=None, left=None)
            args = (steps, cycles, self.link, self._pstop, self.cfg['tol'], self.cfg['end_stop'])
        threading.Thread(target=self._prog_run, args=args, daemon=True).start()
        return True, '프로그램 운전 시작'

    def prog_stop(self):
        if not self.prog['on']:
            return False, '프로그램 운전 중이 아닙니다'
        self._pstop.set()
        self.send('stop', who='프로그램')
        return True, '프로그램 중지, 히터 정지'

    def _prog_run(self, steps, cycles, link, stop, tol, end_stop):
        volatile = fw_tuple(self.state['version']) >= (1, 4)       # v1.4부터 spt: EEPROM에 쓰지 않고 목표를 바꿈
        cmd, q = ('spt', 0.1) if volatile else ('sp', 1.0)
        t0 = time.monotonic()
        clock = lambda: (time.monotonic() - t0) * self.scale
        tick = max(0.05, 0.5 / self.scale)
        sent, why = [None], ['']

        def pv():
            with self.lock:
                return self._last_pv()

        def setsp(v):
            v = round(round(v / q) * q, 1)
            if sent[0] != v:
                self.send('%s %.1f' % (cmd, v), who='')
                sent[0] = v

        def ok(need_run=True):
            s = self.state
            if stop.is_set():
                why[0] = why[0] or '중지'
            elif self.link is not link or not s['connected']:
                why[0] = '중단: 연결 끊김'
            elif s['mode'] == 'FAULT':
                why[0] = '중단: 보드 경보 (%s)' % s['fault']
            elif need_run and s['mode'] == 'STOP':
                why[0] = '중단: 보드가 정지됨'
            else:
                return True
            return False

        def status(**k):
            with self.lock:
                self.prog.update(k)

        def ev(text):
            with self.lock:
                if self.csv:
                    self._event('prog', text)
        try:
            ev('프로그램 시작: %d단계 × %d회, 목표 변경 명령 %s%s' % (len(steps), cycles, cmd, '' if volatile else ' (펌웨어 v1.4 미만: 1 °C 단위, 바꿀 때마다 보드에 저장됨)'))
            cur = pv()
            if cur is None:
                why[0] = '중단: 온도 값 없음'
                return
            if self.state['mode'] != 'RUN':
                setsp(cur)
                self.send('run', who='프로그램')
                end = time.monotonic() + 6
                while self.state['mode'] != 'RUN' and time.monotonic() < end and ok(False):
                    stop.wait(0.05)
                if self.state['mode'] != 'RUN':
                    why[0] = why[0] or '중단: 운전 시작 실패'
                    return
            for cyc, i, st in [(c, i, st) for c in range(1, cycles + 1) for i, st in enumerate(steps, 1)]:
                target, rate, hold = st['target'], st['rate'], st['hold']
                status(cycle=cyc)
                ev('%s%d단계: %.1f → %.1f °C, %s, 유지 %g분' % ('%d회째 ' % cyc if cycles > 1 else '', i, cur, target, ('%g °C/분' % rate) if rate > 0 else '즉시', hold))
                ts = clock()
                if rate > 0 and abs(target - cur) > 1e-6:
                    dur, sign = abs(target - cur) / rate * 60.0, (1 if target > cur else -1)
                    while True:
                        if not ok():
                            return
                        el = clock() - ts
                        spv = target if el >= dur else cur + sign * rate * el / 60.0
                        setsp(spv)
                        status(step=i, phase='ramp', sp=round(spv, 1), target=target, left=round(max(0.0, dur - el)))
                        if el >= dur:
                            break
                        stop.wait(tick)
                cur = target
                setsp(target)
                status(step=i, phase='wait', sp=target, target=target, left=None)
                while True:
                    if not ok():
                        return
                    p = pv()
                    if p is not None and abs(p - target) <= tol:
                        break
                    stop.wait(tick)
                ev('%d단계 도달: PV %.2f °C' % (i, p))
                th = clock()
                while True:
                    if not ok():
                        return
                    left = hold * 60.0 - (clock() - th)
                    status(step=i, phase='hold', left=round(max(0.0, left)))
                    if left <= 0:
                        break
                    stop.wait(tick)
            if end_stop:
                self.send('stop', who='프로그램')
                why[0] = '끝: 히터 정지'
            else:
                why[0] = '끝: 마지막 목표 유지'
        finally:
            ev('프로그램 ' + (why[0] or '중단'))
            self._notify('프로그램 ' + (why[0] or '중단'))
            status(on=False, phase='', left=None)

    # ---------- 구간 내보내기, 통계 저장 ----------
    def export_part(self, t0, t1, rid=None):
        t0, t1 = num(t0), num(t1)
        if t0 is None or t1 is None or t1 <= t0:
            return False, '구간이 올바르지 않습니다'
        with self.lock:
            if not self.csv:
                return False, '기록 파일이 없습니다'
            base = self._base_for(rid)
            src, dst = base + '.csv', '%s_part_%d-%ds.csv' % (base, round(t0), round(t1))
        n = 0
        with open(src, encoding='utf-8') as f, open(dst, 'w', encoding='utf-8', newline='') as g:
            g.write(f.readline())
            for line in f:
                try:
                    t = float(line.split(',', 2)[1])
                except (IndexError, ValueError):
                    continue
                if t0 <= t <= t1:
                    g.write(line)
                    n += 1
        return True, '구간 저장: %s (%d줄)' % (os.path.basename(dst), n)

    def save_stats(self, d):
        rows, t0, t1 = d.get('rows'), num(d.get('t0')), num(d.get('t1'))
        if not isinstance(rows, list) or t0 is None or t1 is None:
            return False, '저장할 통계가 없습니다'
        with self.lock:
            if not self.csv:
                return False, '기록 파일이 없습니다'
            path = self._base_for(d.get('rid')) + '_stats.tsv'
            new = not os.path.exists(path)
            with open(path, 'a', encoding='utf-8') as f:
                if new:
                    f.write('saved_at\tt0_s\tt1_s\tchannel\tn\tmean\tstd\tmin\tmax\tslope_per_min\n')
                for r in rows[:10]:
                    if isinstance(r, dict):
                        vals = [num(r.get(k)) for k in ('n', 'mean', 'std', 'min', 'max', 'slope')]
                        f.write('%s\t%.2f\t%.2f\t%s\t%s\n' % (stamp_ms(), t0, t1, clean(r.get('ch'), 30),
                                '\t'.join('' if v is None else '%.6g' % v for v in vals)))
        return True, '통계 저장: ' + os.path.basename(path)

    # ---------- 지난 기록 ----------
    def records(self):
        out = []
        with self.lock:
            cur, folder = self.base, self.out_dir
        for m in sorted(glob.glob(os.path.join(folder, 'heater_*_meta.json')), reverse=True)[:300]:
            try:
                with open(m, encoding='utf-8') as f:
                    j = json.load(f)
            except (OSError, ValueError):
                continue
            base = m[:-len('_meta.json')]
            e = j.get('experiment') or {}
            out.append(dict(id=os.path.basename(base), started=j.get('started'), ended=j.get('ended'), rows=j.get('rows'),
                            name=e.get('name', ''), sample=e.get('sample', ''), current=base == cur,
                            fw=(j.get('board') or {}).get('firmware', '')))
        return out

    def load_record(self, rid):
        if not re.fullmatch(r'heater_[\w-]+', rid or ''):         # 폴더 밖 파일은 열지 않는다
            return None
        with self.lock:
            base = os.path.join(self.out_dir, rid)
            if base == self.base and self.csv:
                self.csv.flush()
        if not os.path.exists(base + '.csv'):
            return None
        rows, events, meta = [], [], dict(name='', sample='', memo='', labels=['', '', '', ''], pos=[None, None, None, None])
        with open(base + '.csv', encoding='utf-8') as f:
            next(f, None)
            for line in f:
                p = line.rstrip('\n').split(',')
                t = num(p[1]) if len(p) >= 10 else None
                if t is not None and len(rows) < MAX_ROWS:
                    rows.append([t] + [num(x) for x in p[2:9]] + [MODE_CODE.get(p[9])])
        try:
            with open(base + '_events.txt', encoding='utf-8') as f:
                for line in f:
                    p = line.rstrip('\n').split('\t', 3)
                    if len(p) == 4 and not line.startswith('#') and num(p[1]) is not None:
                        events.append([num(p[1]), p[2], p[3]])
        except OSError:
            pass
        try:
            with open(base + '_meta.json', encoding='utf-8') as f:
                j = json.load(f)
            e, ch = j.get('experiment') or {}, j.get('channels') or {}
            ps = j.get('positions_mm') or {}
            meta = dict(name=e.get('name', ''), sample=e.get('sample', ''), memo=e.get('memo', ''),
                        labels=[ch.get('T%d' % i, '') for i in range(1, 5)], pos=[num(ps.get('T%d' % i)) for i in range(1, 5)])
            started = j.get('started')
        except (OSError, ValueError):
            started = None
        return dict(id=rid, rows=rows, events=self._ev_out(events), meta=meta, started=started)

    # ---------- 보고서: 실험 정보, 설정, 차트 그림, 화면이 계산한 표를 한 HTML 파일로 ----------
    def save_report(self, d):
        png = d.get('png')
        if not isinstance(png, str) or not png.startswith('data:image/png;base64,'):
            return False, '차트 그림이 없습니다'
        try:
            if base64.b64decode(png[22:], validate=True)[:8] != b'\x89PNG\r\n\x1a\n':
                return False, '차트 그림이 올바르지 않습니다'
        except ValueError:
            return False, '차트 그림이 올바르지 않습니다'
        E = lambda x: html.escape('' if x is None else str(x))
        with self.lock:
            if not self.csv:
                return False, '기록 파일이 없습니다'
            s, m, c, base = dict(self.state), dict(self.meta), json.loads(json.dumps(self.cfg)), self.base
            started, events, nrows, port = self.started, list(self.events), self.nrows, self.last_port
        tag = re.sub(r'[^0-9a-z_-]+', '', str(d.get('tag', '')))[:30] or 'all'

        T = self.L

        def table(title, head, rows):
            title, head = T(title), [T(x) for x in head] if head else head
            if not head:
                rows = [[T(r[0])] + list(r[1:]) for r in rows]
            h = '<h2>%s</h2><table>' % E(title)
            if head:
                h += '<tr>' + ''.join('<th>%s</th>' % E(x) for x in head) + '</tr>'
            for r in rows:
                h += '<tr>' + ''.join('<td>%s</td>' % E(x) for x in r) + '</tr>'
            return h + '</table>'
        g = lambda v: '-' if v is None else '%g' % v
        parts = [table('실험', None, [['이름', m['name']], ['시료', m['sample']], ['메모', m['memo']],
                                     ['기록 시작', started.strftime('%Y-%m-%d %H:%M:%S')], ['보고서 작성', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                                     ['구간', d.get('range', '')], ['기록 줄 수', nrows]] +
                       [['T%d 위치' % (i + 1), m['labels'][i]] for i in range(4) if m['labels'][i]]),
                 table('보드와 설정', None, [['포트', T(port)], ['펌웨어', s['version']], ['가상 보드', T('예' if s['sim'] else '아니오')],
                                          ['Kp / Ki / Kd', '%s / %s / %s' % (g(s['kp']), g(s['ki']), g(s['kd']))],
                                          ['출력 한계 (%)', g(s['outmax'])], ['제어 기준', s['src']], ['목표 SP (°C)', g(s['sp'])],
                                          ['PC 경보 상한 T1~T4 (°C)', ' / '.join(g(v) for v in c['hi'])], ['PC 경보 채널 간 차이 (°C)', g(c['spread'])],
                                          ['히터 정격 (W), 전력 추정용', g(c['heater_w'])]]),
                 '<h2>%s</h2><img alt="" src="%s">' % (T('차트'), png)]
        for t in (d.get('tables') or [])[:8]:
            if isinstance(t, dict) and isinstance(t.get('rows'), list):
                parts.append(table(clean(t.get('title'), 60), [clean(x, 40) for x in (t.get('head') or [])][:12],
                                   [[clean(x, 80) for x in r][:12] for r in t['rows'][:60] if isinstance(r, list)]))
        parts.append(table('이벤트 기록', ['경과 (s)', '종류', '내용'], [['%.1f' % e[0], e[1], self._ev_text(e[1], e[2])] for e in events[-300:]]))
        parts.append(table('파일', None, [['데이터', os.path.basename(base) + '.csv'], ['이벤트', os.path.basename(base) + '_events.txt'],
                                          ['원본 로그', os.path.basename(base) + '_raw.log'], ['메타데이터', os.path.basename(base) + '_meta.json']]))
        doc = ('<!doctype html><html lang="' + self.cfg.get('lang', 'ko') + '"><meta charset="utf-8"><title>%s</title><style>'
               'body{font:12px/1.4 "Apple SD Gothic Neo","Malgun Gothic",sans-serif;color:#000;max-width:900px;margin:24px auto;padding:0 16px}'
               'h1{font-size:18px;border-bottom:2px solid #000;padding-bottom:4px}h2{font-size:13px;margin:18px 0 4px}'
               'table{border-collapse:collapse;width:100%%}td,th{border:1px solid #888;padding:2px 6px;text-align:left;font-variant-numeric:tabular-nums}'
               'th{background:#e6e6e6;font-weight:400}img{max-width:100%%;border:1px solid #888}@media print{body{margin:0}}'
               '</style><h1>%s</h1>%s</html>') % (E(T('보고서 ' + (m['name'] or os.path.basename(base)))), E(m['name'] or os.path.basename(base)), ''.join(parts))
        path, n = '%s_report_%s.html' % (base, tag), 1
        while os.path.exists(path):
            n += 1
            path = '%s_report_%s_%d.html' % (base, tag, n)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(doc)
        return True, '보고서 저장: ' + os.path.basename(path)

    # ---------- 보드 연결을 고르고 바꾼다 ----------
    def start(self, sim=None, port='', new_file=True):
        """sim: 가상 보드 배속(없으면 실물 보드). port: 고른 포트('' 이면 자동). 실물 ↔ 연습을 바꾸면 새 파일로 넘어간다."""
        old, th = self.link, self.thread
        self._pstop.set()
        if old:
            old.stop()
        if th:
            th.join(3)
        with self.lock:
            self.scale = float(sim) if sim else 1.0
            self.want = '' if sim else (port or '')
            self.out_dir = os.path.join(self.base_dir, '연습') if sim else self.base_dir
            self.state.update(connected=False, port='', note='가상 보드를 켜는 중입니다' if sim else '보드를 찾는 중입니다', mode='', fault='',
                              version='', sp=None, kp=None, ki=None, kd=None, outmax=None, src='',
                              relay='', ssr='', energy=None, runtime=None, sim=bool(sim))
            if new_file or not self.csv:
                self.last_port = ''
                self.new_file()
            self.link = SimLink(self, float(sim)) if sim else SerialLink(self, self.want)
            self.thread = threading.Thread(target=self.link.run, daemon=True)
            self.thread.start()

    # ---------- 파일 ----------
    def new_file(self, meta=None):
        with self.lock:
            self.close()
            if meta:
                self._apply_meta(meta)
            os.makedirs(self.out_dir, exist_ok=True)
            self.started = datetime.datetime.now().astimezone()
            self.ended = None
            name = slug(self.meta['name'])
            stem = 'heater_' + self.started.strftime('%Y%m%d_%H%M%S') + ('_' + name if name else '')
            base, n = os.path.join(self.out_dir, stem), 1
            while os.path.exists(base + '.csv'):
                n += 1
                base = os.path.join(self.out_dir, '%s_%d' % (stem, n))
            self.base = base
            self.csv = open(base + '.csv', 'w', buffering=1, newline='', encoding='utf-8')
            self.csv.write('time,elapsed_s,' + ','.join(HEAD) + ',mode\n')
            self.evf = open(base + '_events.txt', 'w', buffering=1, encoding='utf-8')
            self.evf.write('# time\telapsed_s\tkind\ttext\n')
            self.raw = open(base + '_raw.log', 'w', buffering=1, encoding='utf-8')
            self.t0 = time.monotonic()
            self.rows, self.events, self.nrows = [], [], 0
            if hasattr(self, 'stable'):
                self.stable.update(on=False, since=None)
            self.gen += 1
            s = self.state
            s['csv'] = base + '.csv'
            self.first_settings = None
            if s['sp'] is not None:
                self._settings_seen()
            self._write_meta()

    def close(self):
        with self.lock:
            if not self.csv:
                return
            self.ended = datetime.datetime.now().astimezone()
            self._write_meta()
            for f in (self.csv, self.evf, self.raw):
                f.close()
            self.csv = self.evf = self.raw = None
            if self.nrows == 0 and not any(e[1] == 'mark' for e in self.events):
                for ext in ('.csv', '_events.txt', '_raw.log', '_meta.json'):    # 값이 한 줄도 없는 기록은 남기지 않는다
                    try:
                        os.remove(self.base + ext)
                    except OSError:
                        pass

    def _apply_meta(self, d):
        m = self.meta
        for k, n in (('name', 60), ('sample', 100), ('memo', 500)):
            if k in d:
                m[k] = clean(d[k], n)
        if isinstance(d.get('labels'), list):
            m['labels'] = [clean(x, 24) for x in (d['labels'] + ['', '', '', ''])[:4]]
        if isinstance(d.get('pos'), list):                         # 열전대 위치 (mm). 비우면 없음
            m['pos'] = [num(x) for x in (d['pos'] + [None] * 4)[:4]]

    def set_meta(self, d):
        with self.lock:
            self._apply_meta(d)
            self._write_meta()

    def _write_meta(self):
        s, b = self.state, os.path.basename(self.base)
        doc = {
            'program': 'heater_log.py ' + VERSION,
            'started': self.started.isoformat(timespec='seconds'),
            'ended': self.ended.isoformat(timespec='seconds') if self.ended else None,    # null 이면 기록 중이거나 강제로 꺼진 것 (CSV는 줄마다 저장됨)
            'experiment': {k: self.meta[k] for k in ('name', 'sample', 'memo')},
            'channels': {'T%d' % (i + 1): self.meta['labels'][i] for i in range(4)},
            'positions_mm': {'T%d' % (i + 1): self.meta['pos'][i] for i in range(4)},
            'board': {'port': self.last_port, 'firmware': s['version'], 'simulated': s['sim'], 'time_scale': self.scale},
            'settings_at_start': self.first_settings,
            'sample_interval_s': 1.0,
            'rows': self.nrows,
            'columns': COLUMNS_EN if self.cfg.get('lang') == 'en' else COLUMNS,
            'files': {'data': b + '.csv', 'events': b + '_events.txt', 'raw': b + '_raw.log'},
        }
        tmp = self.base + '_meta.json.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.base + '_meta.json')

    def _now(self):
        return round((time.monotonic() - self.t0) * self.scale, 2)

    def _event(self, kind, text):
        t = self._now()
        self.events.append([t, kind, text])
        self.evf.write('%s\t%.2f\t%s\t%s\n' % (stamp_ms(), t, kind, self._ev_text(kind, text)))

    def _ev_text(self, kind, text):
        if kind == 'board' or (kind == 'mark' and not re.fullmatch(r'(마커|표시) \d+', text)):
            return text                                            # 보드가 보낸 줄과 사용자가 적은 마커는 원문 그대로
        return self.L(text)

    def _ev_out(self, events):
        if self.cfg.get('lang') != 'en':
            return events
        return [[e[0], e[1], self._ev_text(e[1], e[2])] for e in events]

    def _settings_seen(self):
        s = self.state
        if self.first_settings is None:                            # 이 파일에서 처음 본 설정만 메타데이터에 남긴다
            self.first_settings = {k: s[k] for k in ('sp', 'kp', 'ki', 'kd', 'outmax', 'src')}
        self._event('set', 'SP=%g Kp=%g Ki=%g Kd=%g OUTMAX=%g SRC=%s MODE=%s' %
                    (s['sp'], s['kp'], s['ki'], s['kd'], s['outmax'], s['src'], s['mode']))

    def note(self, kind, text):
        with self.lock:
            if self.csv:
                self._event(kind, text)

    def mark(self, text):
        with self.lock:
            n = sum(1 for e in self.events if e[1] == 'mark') + 1
            self._event('mark', clean(text, 120) or '마커 %d' % n)

    # ---------- 받은 줄 ----------
    def feed(self, line, who=None):
        line = line.rstrip('\r\n')
        kind, d = parse(line)
        with self.lock:
            if not self.csv or (who is not None and who is not self.link):
                return
            s = self.state
            if kind == 'data' and not s['sim']:                    # 보드는 1초에 한 줄을 보낸다. 잠깐 몰려 오는 것(10줄)은 받고, 계속 쏟아지면 버린다
                now = time.monotonic()
                self._tok = min(10.0, self._tok + (now - self._tok_at) * 3.0)
                self._tok_at = now
                if self._tok < 1.0:
                    self._dropped += 1
                    self._drop_at = now
                    return
                self._tok -= 1.0
                if self._dropped and now - self._drop_at > 2.0:    # 쏟아짐이 끝난 뒤 한 번만 적는다
                    self._event('conn', '비정상적으로 빠르게 수신된 데이터 %d줄 무시' % self._dropped)
                    self._dropped = 0
            if kind is None and not s['sim']:                      # 알 수 없는 줄도 쏟아지면 원본 로그에 다 쓰지 않는다 (몰려 온 50줄까지, 그 뒤 초당 20줄)
                now = time.monotonic()
                self._tok2 = min(50.0, self._tok2 + (now - self._tok2_at) * 20.0)
                self._tok2_at = now
                if self._tok2 < 1.0:
                    return
                self._tok2 -= 1.0
            if line.strip():
                self.raw.write('%s\t%s\n' % (stamp_ms(), line))
            if kind == 'data':
                t = self._now()
                vals = [d.get(k) for k in KEYS]
                self.nrows += 1
                if self.nrows % 300 == 0:
                    self._write_meta()                             # 줄 수를 5분마다 메타데이터에 반영 (끝낼 때 한 번 더 씀)
                row = [t] + vals + [MODE_CODE.get(s['mode'])]
                if len(self.rows) < MAX_ROWS:
                    self.rows.append(row)
                self.csv.write('%s,%.2f,%s,%s\n' % (stamp_ms(), t,
                               ','.join('' if v is None else f % v for f, v in zip(FMT, vals)), s['mode']))
                self._check_alarm(row)
                self._check_stable(row)
            elif kind == 'set':
                first = s['sp'] is None
                diff = ['%s %s → %s' % (k.upper(), s[k], d[k]) for k in ('sp', 'kp', 'ki', 'kd', 'outmax', 'src')
                        if s[k] != d[k]]
                if self.prog['on']:                                # 프로그램이 목표를 계속 바꾸는 동안은 SP 변경을 줄줄이 적지 않는다 (CSV의 SP 열에 남음)
                    diff = [x for x in diff if not x.startswith('SP ')]
                old_mode = s['mode']
                s.update(d)
                if first:                                          # 연결 직후, 또는 보드가 리셋된 직후
                    self._settings_seen()
                    self._write_meta()
                else:
                    if diff:
                        self._event('set', '변경: ' + ', '.join(diff))
                    if old_mode and old_mode != d['mode']:
                        self._event('mode', '%s → %s%s' % (old_mode, d['mode'], (' (' + d['fault'] + ')') if d['fault'] else ''))
            elif kind == 'ac':
                s.update(d)
            elif kind == 'text':
                m = RE_VER.match(d)
                if m:
                    s['version'] = m[1]
                    self._write_meta()
                old_mode = s['mode']
                if d == 'RUN':
                    s['mode'] = 'RUN'
                elif d in ('STOP', 'Fault cleared'):
                    s['mode'], s['fault'] = 'STOP', ''
                elif d.startswith('!! FAULT: '):
                    s['mode'], s['fault'] = 'FAULT', d[10:]
                    self._notify('보드 경보: ' + d[10:])
                elif d == 'Auto-tune start':
                    s['mode'] = 'TUNE'
                elif d == '# boot':
                    s['sp'], s['mode'] = None, ''                  # 리셋됨: 다음 설정 줄을 새로 적는다
                self._event('board', d.lstrip('# '))
                if old_mode and s['mode'] and old_mode != s['mode']:
                    self._event('mode', '%s → %s%s' % (old_mode, s['mode'], (' (' + s['fault'] + ')') if s['fault'] else ''))

    def set_conn(self, ok, port='', note='', who=None):
        with self.lock:
            if who is not None and who is not self.link:           # 이미 바꿔 끼운 예전 연결이 보낸 것은 버린다
                return
            changed = self.state['connected'] != ok
            self.state.update(connected=ok, port=port, note=note)
            if ok:
                self.last_port = port
            else:                                                  # 끊긴 동안에는 보드 상태를 알 수 없음
                self.state.update(mode='', fault='', relay='', ssr='')
            if changed and self.csv:
                self._event('conn', ('연결됨: ' + port) if ok else ('연결 끊김' + (': ' + note if note else '')))
                if not ok:
                    self.stable.update(on=False, since=None)
                    self._notify('보드 연결이 끊겼습니다')
                self._write_meta()

    # ---------- 웹 화면이 읽어 가는 것 ----------
    def snapshot(self, gen, n, ne):
        with self.lock:
            if gen != self.gen:
                n = ne = 0
            st = dict(self.state)
            st['note'], st['port'] = self.L(st['note']), self.L(st['port'])
            home = os.path.expanduser('~')
            st['csv_show'] = ('~' + st['csv'][len(home):]) if st['csv'].startswith(home + os.sep) else st['csv']    # 화면에는 홈 폴더를 ~ 로 줄여 보임
            return dict(gen=self.gen, rows=self.rows[n:n + 20000], total=len(self.rows), events=self._ev_out(self.events[ne:]),
                        state=st, meta=dict(self.meta), elapsed=self._now(),
                        ports=list(self.ports), want=self.want, sim_ok=sim_exe() is not None, folder=self.out_dir,
                        cfg=json.loads(json.dumps(self.cfg)), prog=dict(self.prog),
                        alarm=dict(active=[self.L(x) for x in self.alarm['active']], latched=self.L(self.alarm['latched'])), stable=dict(self.stable),
                        spcmd='spt' if fw_tuple(self.state['version']) >= (1, 4) else 'sp', ver=VERSION)

    def _base_for(self, rid):
        """rid 가 있으면 그 지난 기록의 파일 이름 머리, 없으면 지금 기록."""
        if rid and re.fullmatch(r'heater_[\w-]+', str(rid)) and os.path.exists(os.path.join(self.out_dir, rid + '.csv')):
            return os.path.join(self.out_dir, rid)
        return self.base

    def save_png(self, data, tag, rid=None):
        """화면이 보낸 그래프 그림(PNG)을 기록 파일 옆에 저장한다."""
        if not isinstance(data, str) or not data.startswith('data:image/png;base64,'):
            return False, '그림 형식이 아닙니다'
        try:
            raw = base64.b64decode(data[22:], validate=True)
        except ValueError:
            return False, '그림을 읽지 못했습니다'
        if raw[:8] != b'\x89PNG\r\n\x1a\n':
            return False, '그림 형식이 아닙니다'
        with self.lock:
            base = self._base_for(rid)
            path = '%s_graph_%s.png' % (base, re.sub(r'[^0-9a-z_-]+', '', str(tag))[:30] or 'all')
            n = 1
            while os.path.exists(path):
                n += 1
                path = '%s_graph_%s_%d.png' % (base, re.sub(r'[^0-9a-z_-]+', '', str(tag))[:30] or 'all', n)
        with open(path, 'wb') as f:
            f.write(raw)
        return True, '그림 저장: ' + os.path.basename(path)

    def open_folder(self):
        d = self.out_dir
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(['open', d])
            elif os.name == 'nt':
                os.startfile(d)
            else:
                subprocess.Popen(['xdg-open', d])
        except OSError as e:
            return False, str(e)
        return True, '기록 폴더를 열었습니다'

    def send(self, cmd, who='PC'):
        cmd = ' '.join(clean(cmd, 40).lower().replace('=', ' ').split())
        if not CMD_OK.match(cmd):
            return False, '사용할 수 없는 명령: ' + cmd
        link = self.link
        if not link or not self.state['connected']:
            return False, '보드가 연결돼 있지 않습니다'
        try:
            link.write(cmd)
        except Exception as e:                                     # 포트가 막 끊긴 경우
            return False, str(e)
        if who:
            with self.lock:
                if self.csv:
                    self._event('cmd', '%s: %s' % (who, cmd))
        return True, cmd


# ===================== 보드와의 연결 =====================
class SerialLink:
    def __init__(self, hub, port):
        self.hub, self.want, self.ser, self.wl, self.alive = hub, port, None, threading.Lock(), True

    def stop(self):
        self.alive = False
        try:
            self.ser.close()
        except Exception:
            pass

    def find(self):
        from serial.tools import list_ports
        ports = [p for p in list_ports.comports() if not re.search(r'Bluetooth|debug-console', p.device)]
        self.hub.ports = [{'device': p.device, 'desc': (p.description or '') if p.description != 'n/a' else ''} for p in ports]
        if self.want:
            return self.want
        usb = sorted(p.device for p in ports if p.vid in USB_VID)
        named = sorted(p.device for p in ports if re.search(r'usbserial|wchusbserial|usbmodem|SLAB|ttyUSB|ttyACM', p.device))
        cand = usb or named
        return cand[0] if cand else None

    def write(self, cmd):
        with self.wl:
            self.ser.write((cmd + '\n').encode())

    def wait(self, sec):
        end = time.monotonic() + sec
        while self.alive and time.monotonic() < end:
            time.sleep(0.1)

    def run(self):
        import serial
        hub = self.hub
        while self.alive:
            port = self.find()
            if not port:
                hub.set_conn(False, note='보드를 찾는 중입니다 (USB를 연결하세요)', who=self)
                self.wait(1.5)
                continue
            try:
                self.ser = serial.Serial(port, 115200, timeout=0.5)
            except Exception as e:
                why = ('다른 프로그램이 사용 중 (아두이노 시리얼 모니터를 닫으세요)' if 'busy' in str(e).lower() or 'PermissionError' in str(e)
                       else '포트를 찾을 수 없음' if 'No such file' in str(e) or 'FileNotFound' in str(e) else str(e)[:80])
                hub.set_conn(False, note='%s 포트를 열 수 없습니다: %s' % (port, why), who=self)
                self.wait(2)
                continue
            hub.set_conn(True, port, who=self)
            buf, last_show = b'', time.monotonic() + 0.7           # 리셋 뒤 부팅이 끝날 즈음 첫 show
            try:
                # 포트를 열면 나노가 리셋되고, 부트로더가 끝난 뒤 "# boot" 를 보낸다. 그 전에 들어오는 것은 열기 전에
                # 드라이버에 남아 있던 찌꺼기다. 실제로 같은 두 줄이 2초 동안 1만 7천 번 되풀이돼 들어와 기록에 섞인 적이
                # 있어서(2026-11-20), "# boot" 가 보일 때까지(길어도 3초) 들어온 것은 버린다.
                got, end = 0, time.monotonic() + 3.0
                try:
                    self.ser.reset_input_buffer()
                except Exception:
                    pass
                while self.alive and time.monotonic() < end:
                    chunk = self.ser.read(4096)
                    got += len(chunk)
                    buf = (buf + chunk)[-8192:]
                    i = buf.find(b'# boot')
                    if i >= 0:
                        buf = buf[i:]
                        break
                else:
                    buf = b''                                      # 자동 리셋이 없는 보드: 3초 뒤부터 그냥 받는다
                if got - len(buf) > 0:
                    hub.note('conn', '연결 직후 수신한 %d바이트 무시 (보드 부팅 전 잔여 데이터)' % (got - len(buf)))
                while b'\n' in buf:                                # 기다리는 동안 받은 부팅 줄을 바로 넘긴다
                    line, buf = buf.split(b'\n', 1)
                    hub.feed(line.decode('ascii', 'replace'), who=self)
                while self.alive:
                    chunk = self.ser.read(256)
                    if chunk:
                        buf += chunk
                        while b'\n' in buf:
                            line, buf = buf.split(b'\n', 1)
                            hub.feed(line.decode('ascii', 'replace'), who=self)
                        if len(buf) > 2000:
                            buf = b''
                    if time.monotonic() - last_show >= 3.0:
                        last_show = time.monotonic()
                        self.write('show')                         # 상태·설정·릴레이를 주기적으로 물어봄 (EEPROM에는 쓰지 않는 명령)
            except Exception:
                if self.alive:
                    hub.set_conn(False, note='USB가 빠졌거나 다른 프로그램이 포트를 사용 중입니다', who=self)
            try:
                self.ser.close()
            except Exception:
                pass
            self.wait(1.5)


class SimLink:
    """보드 대신 가상 보드(펌웨어를 PC에서 그대로 컴파일한 것)를 쓴다."""

    def __init__(self, hub, speed):
        self.hub, self.speed, self.p, self.wl, self.alive = hub, speed, None, threading.Lock(), True

    def stop(self):
        self.alive = False
        try:
            self.p.kill()
        except Exception:
            pass

    def write(self, cmd):
        with self.wl:
            self.p.stdin.write(cmd + '\n')
            self.p.stdin.flush()

    def run(self):
        try:
            exe = sim_exe(build=True)
            if not exe:
                raise RuntimeError('가상 보드 파일이 없습니다')
        except Exception as e:
            self.hub.set_conn(False, note='가상 보드를 켜지 못했습니다: %s' % e, who=self)
            return
        self.p = subprocess.Popen([exe, 'board', str(self.speed)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  text=True, bufsize=1, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))    # 윈도우에서 콘솔 창이 뜨지 않게
        self.hub.set_conn(True, '가상 보드 %g배속' % self.speed, who=self)
        threading.Thread(target=self.poll, daemon=True).start()
        for line in self.p.stdout:
            self.hub.feed(line, who=self)
        if self.alive:
            self.hub.set_conn(False, note='가상 보드가 종료됨', who=self)

    def poll(self):
        while self.alive and self.p.poll() is None:
            time.sleep(max(0.3, 3.0 / self.speed))
            try:
                self.write('show')
            except Exception:
                return


# ===================== 웹 화면 =====================
def load_page():
    with open(os.path.join(RES, 'heater_log.html'), encoding='utf-8') as f:
        return f.read()


def make_handler(hub, token):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def local(self):                   # 이 컴퓨터의 브라우저에서 온 요청만 받는다
            return self.headers.get('Host', '').rsplit(':', 1)[0] in ('127.0.0.1', 'localhost')

        def reply(self, code, body, ctype='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                if isinstance(body, dict) and isinstance(body.get('msg'), str):
                    body = dict(body, msg=hub.L(body['msg']))
                body = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode()
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.local():
                return self.reply(403, {'error': 'forbidden'})
            u = urlparse(self.path)
            if u.path == '/':
                return self.reply(200, load_page().replace('__TOKEN__', token).replace('<html lang="ko">', '<html lang="%s">' % hub.cfg.get('lang', 'ko'), 1).encode(), 'text/html; charset=utf-8')
            if u.path == '/api/data':
                q = parse_qs(u.query)
                try:
                    g, n, ev = (int(q.get(k, ['0'])[0] or 0) for k in ('gen', 'n', 'ev'))
                except ValueError:
                    return self.reply(400, {'error': 'bad query'})
                return self.reply(200, hub.snapshot(g, max(0, n), max(0, ev)))
            if u.path == '/api/records':
                return self.reply(200, {'records': hub.records(), 'folder': hub.out_dir})
            if u.path == '/api/record':
                rec = hub.load_record(parse_qs(u.query).get('id', [''])[0])
                return self.reply(200, rec) if rec else self.reply(404, {'error': '기록을 찾지 못했습니다'})
            self.reply(404, {'error': 'not found'})

        def do_POST(self):
            # 다른 웹 페이지가 몰래 명령을 보내지 못하게, 이 화면에만 심어 둔 값(token)을 확인한다
            if not self.local() or not secrets.compare_digest(self.headers.get('X-Token', ''), token):
                return self.reply(403, {'error': 'forbidden'})
            try:
                n = int(self.headers.get('Content-Length', '0') or 0)
                limit = 16000000 if self.path in ('/api/png', '/api/report') else 20000
                body = json.loads(self.rfile.read(n) or b'{}') if 0 <= n <= limit else None
            except ValueError:
                body = None
            if not isinstance(body, dict):
                return self.reply(400, {'error': 'bad request'})
            if self.path == '/api/cmd':
                ok, msg = hub.send(str(body.get('cmd', '')))
                return self.reply(200, {'ok': ok, 'msg': msg})
            if self.path == '/api/mark':
                hub.mark(body.get('text', ''))
                return self.reply(200, {'ok': True, 'msg': '마커를 추가했습니다'})
            if self.path == '/api/meta':
                hub.set_meta(body)
                return self.reply(200, {'ok': True, 'msg': '실험 정보를 저장했습니다'})
            if self.path == '/api/new':
                hub.new_file(body)
                return self.reply(200, {'ok': True, 'msg': '새 파일: ' + os.path.basename(hub.state['csv'])})
            if self.path == '/api/png':
                ok, msg = hub.save_png(body.get('data'), body.get('tag', ''), body.get('rid'))
                return self.reply(200, {'ok': ok, 'msg': msg})
            if self.path == '/api/cfg':
                hub.set_cfg(body)
                return self.reply(200, {'ok': True, 'msg': '저장했습니다'})
            if self.path == '/api/prog':
                ok, msg = hub.prog_start() if body.get('on') else hub.prog_stop()
                return self.reply(200, {'ok': ok, 'msg': msg})
            if self.path == '/api/ack':
                hub.alarm_ack()
                return self.reply(200, {'ok': True, 'msg': '경보를 확인했습니다'})
            if self.path == '/api/export':
                ok, msg = hub.export_part(body.get('t0'), body.get('t1'), body.get('rid'))
                return self.reply(200, {'ok': ok, 'msg': msg})
            if self.path == '/api/stats':
                ok, msg = hub.save_stats(body)
                return self.reply(200, {'ok': ok, 'msg': msg})
            if self.path == '/api/report':
                ok, msg = hub.save_report(body)
                return self.reply(200, {'ok': ok, 'msg': msg})
            if self.path == '/api/open':
                ok, msg = hub.open_folder()
                return self.reply(200, {'ok': ok, 'msg': msg})
            if self.path == '/api/sim':                            # 연습(가상 보드) ↔ 실물 보드
                on = bool(body.get('on'))
                if on and sim_exe() is None:
                    return self.reply(200, {'ok': False, 'msg': '이 컴퓨터에는 가상 보드가 없습니다'})
                hub.start(sim=30.0 if on else None)
                return self.reply(200, {'ok': True, 'msg': '연습 모드를 켰습니다 (실제 히터는 켜지지 않음)' if on else '실물 보드로 돌아왔습니다'})
            if self.path == '/api/port':
                port = str(body.get('port', ''))
                if port and port not in [x['device'] for x in hub.ports]:
                    return self.reply(200, {'ok': False, 'msg': '목록에 없는 포트입니다'})
                hub.start(port=port, new_file=False)
                return self.reply(200, {'ok': True, 'msg': '포트: ' + (port or '자동')})
            self.reply(404, {'error': 'not found'})
    return H


class Server(ThreadingHTTPServer):
    allow_reuse_address = os.name != 'nt'      # 윈도우에서는 이 옵션이 다른 프로그램이 쓰는 포트에도 붙게 해서, 두 번 켜면 화면이 섞인다


def run_window(url, hub, selftest=None):
    """브라우저 대신 전용 창에 화면을 띄운다 (응용프로그램으로 실행할 때). 창을 닫으면 끝난다."""
    import webview
    w = webview.create_window('Band Heater PID Logger' if hub.cfg.get('lang') == 'en' else '밴드 히터 PID 기록', url, width=1280, height=880, min_size=(1000, 700))
    w.events.closed += hub.close

    def probe():                           # 빌드 확인용: 창 안의 화면을 실제로 조작해 보고 결과를 파일에 적은 뒤 닫는다
        read = ("JSON.stringify({status: document.getElementById('status').textContent, rows: rows.length, "
                "leds: document.querySelectorAll('.led').length, ledsOn: document.querySelectorAll('.led.on').length, canvas: document.getElementById('cv').width, "
                "mode: state.mode, sp: state.sp, dialog: document.getElementById('dlg').open, "
                "pv: rows.length ? rows[rows.length - 1][1] : null})")
        out = {}
        try:
            time.sleep(7)
            out['loaded'] = json.loads(w.evaluate_js(read))
            w.evaluate_js("send('sp 60')")
            time.sleep(1.5)
            w.evaluate_js("document.getElementById('brun').click()")            # 운전 → 확인 창이 떠야 함
            time.sleep(0.8)
            out['asked'] = json.loads(w.evaluate_js(read))
            w.evaluate_js("document.getElementById('dlgyes').click()")
            time.sleep(4)
            out['running'] = json.loads(w.evaluate_js(read))
            w.evaluate_js("document.getElementById('bstop').click()")
            time.sleep(1.5)
            out['stopped'] = json.loads(w.evaluate_js(read))
        except Exception as e:
            out['error'] = repr(e)
        with open(selftest, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        w.destroy()
    if selftest:
        webview.start(probe)
    else:
        webview.start()


def main(window=False):
    ap = argparse.ArgumentParser(description='밴드 히터 PID 컨트롤러 기록 프로그램')
    ap.add_argument('--port', default='', help='시리얼 포트 (생략하면 자동으로 찾음)')
    ap.add_argument('--out', default=os.path.join(docs_dir(), '밴드히터_기록'), help='기록 폴더')
    ap.add_argument('--name', default='', help='실험 이름 (파일 이름에 붙음)')
    ap.add_argument('--sim', type=float, nargs='?', const=1.0, metavar='배속', help='보드 없이 가상 보드로 실행')
    ap.add_argument('--http-port', type=int, default=8765)
    ap.add_argument('--no-browser', action='store_true', help='브라우저를 자동으로 열지 않음')
    ap.add_argument('--window', action='store_true', help='브라우저 대신 전용 창으로 띄움 (pywebview 필요)')
    ap.add_argument('--lang', choices=('ko', 'en'), help='화면 언어 (생략하면 지난번에 고른 것)')
    ap.add_argument('--selftest', metavar='FILE', help=argparse.SUPPRESS)
    a, _ = ap.parse_known_args()
    if a.sim is not None and a.sim <= 0:
        ap.error('--sim 배속은 0보다 커야 합니다')
    window = window or a.window
    if a.sim is None:
        a.selftest = None                  # 자동 점검은 운전 단추를 누르므로 가상 보드에서만 한다. 실물 보드에서는 절대 돌리지 않는다

    hub = Hub(a.out, name=a.name)
    if a.lang:
        hub.cfg['lang'] = a.lang
    atexit.register(hub.close)             # 어떤 길로 끝나든 파일을 닫는다 (이미 닫혔으면 아무 일도 안 함)
    hub.start(sim=a.sim, port=a.port)

    token = secrets.token_urlsafe(16)
    srv = None
    for port in range(a.http_port, a.http_port + 20):
        try:
            srv = Server(('127.0.0.1', port), make_handler(hub, token))
            break
        except OSError:
            continue
    if not srv:
        sys.exit('웹 화면용 포트를 열 수 없습니다')
    srv.daemon_threads = True
    url = 'http://127.0.0.1:%d/' % srv.server_address[1]
    if sys.platform == 'darwin':           # 기록하는 동안 맥이 자동으로 잠들지 않게 함 (프로그램을 끄면 원래대로)
        try:
            subprocess.Popen(['caffeinate', '-i', '-w', str(os.getpid())])
        except OSError:
            pass
    elif os.name == 'nt':                  # 윈도우도 같게: 이 스레드가 살아 있는 동안 절전으로 들어가지 않음
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)      # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        except Exception:
            pass
    for sig in (signal.SIGTERM, getattr(signal, 'SIGHUP', None)):     # 터미널 창을 닫아도 파일을 정리하고 끝냄
        if sig is not None:
            signal.signal(sig, lambda *_: sys.exit(0))
    try:
        if window:
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            run_window(url, hub, a.selftest)
        else:
            print(hub.L('기록 파일: %s') % hub.state['csv'])
            print(hub.L('화면: %s   (끝내려면 Ctrl+C)') % url, flush=True)
            if not a.no_browser:
                threading.Timer(0.6, webbrowser.open, [url]).start()
            srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        csv = hub.state['csv']
        hub.close()
        if not window:
            print('\n' + hub.L('종료. 기록 파일: %s') % csv)


if __name__ == '__main__':
    main()
