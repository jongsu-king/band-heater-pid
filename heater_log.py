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
    uv run heater_app.py                       브라우저 대신 전용 창으로 (응용프로그램은 이것을 묶은 것)

기록은 기본으로 ~/Documents/밴드히터_기록 에 실험마다 파일 네 개로 남는다 (--out 으로 변경).
  heater_날짜_시각_이름.csv           1초마다 한 줄 (열 설명은 _meta.json 의 columns)
  heater_날짜_시각_이름_events.txt    운전·정지·알람·설정 변경·보낸 명령·표시(마커)
  heater_날짜_시각_이름_raw.log       보드가 보낸 줄 전부 (받은 시각과 함께, 가공하지 않음)
  heater_날짜_시각_이름_meta.json     실험 이름·시료·메모, 채널 이름, 펌웨어, PID 설정, 열 설명

포트를 열 때 나노가 리셋된다(아두이노의 정상 동작). 운전 중에 켜면 히터가 꺼지므로
이 프로그램을 먼저 켜고 나서 운전을 시작한다.
"""
import argparse, atexit, base64, datetime, json, os, re, secrets, signal, subprocess, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

VERSION = '1.1'
HERE = os.path.dirname(os.path.abspath(__file__))
RES = getattr(sys, '_MEIPASS', HERE)    # 응용프로그램으로 묶였을 때는 그 안의 자원 폴더
USB_VID = {0x0403, 0x1A86, 0x10C4, 0x2341, 0x2A03, 0x067B}        # FTDI, CH340, CP210x, Arduino, Prolific
KEYS = ['PV', 'SP', 'OUT', 'T1', 'T2', 'T3', 'T4']
HEAD = ['PV_degC', 'SP_degC', 'OUT_pct', 'T1_degC', 'T2_degC', 'T3_degC', 'T4_degC']
FMT = ['%.2f', '%.1f', '%.1f', '%.2f', '%.2f', '%.2f', '%.2f']
MODE_CODE = {'STOP': 0, 'RUN': 1, 'TUNE': 2, 'FAULT': 3}
MAX_ROWS = 400000                       # 화면용으로 메모리에 두는 표본 수 (1초 간격으로 약 4.6일). 파일에는 제한 없이 쓴다
CMD_OK = re.compile(r'^(?:(?:sp|kp|ki|kd|out) \d+(?:\.\d+)?|src (?:[1-4]|avg|max)|run|stop|tune|clear|show|help|log [01])$')
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
    'mode': 'STOP / RUN / TUNE(오토튜닝) / FAULT(알람). 보드에 3초마다 물어 갱신하므로 버튼으로 바꾼 직후 몇 초는 늦을 수 있음',
}


def num(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float('inf') else None      # nan, inf 는 빈 값


def clean(s, n=200):
    return re.sub(r'[\x00-\x1f\x7f]+', ' ', str(s or '')).strip()[:n]


def slug(s):
    return re.sub(r'[^\w-]+', '_', clean(s, 40)).strip('_')


def stamp_ms():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


def sim_exe(build=False):
    """가상 보드 실행 파일의 위치. 없으면 None. build=True 이면 소스가 있을 때 새로 컴파일한다."""
    packed = os.path.join(RES, 'sim', 'sim_bin')
    if os.path.exists(packed):
        return packed
    src = os.path.join(HERE, 'tools', 'sim', 'sim.cpp')
    ino = os.path.join(HERE, 'band_heater_pid', 'band_heater_pid.ino')
    exe = os.path.join(HERE, 'tools', 'sim', 'sim_bin')
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
        self.meta = dict(name=clean(name, 60), sample='', memo='', labels=['', '', '', ''])
        self.state = dict(connected=False, port='', note='보드를 찾는 중', mode='', fault='', version='',
                          sp=None, kp=None, ki=None, kd=None, outmax=None, src='',
                          relay='', ssr='', energy=None, runtime=None, csv='', sim=False)
        self.csv = self.evf = self.raw = None
        self.last_port = ''

    # ---------- 보드 연결을 고르고 바꾼다 ----------
    def start(self, sim=None, port='', new_file=True):
        """sim: 가상 보드 배속(없으면 실물 보드). port: 고른 포트('' 이면 자동). 실물 ↔ 연습을 바꾸면 새 파일로 넘어간다."""
        old, th = self.link, self.thread
        if old:
            old.stop()
        if th:
            th.join(3)
        with self.lock:
            self.scale = float(sim) if sim else 1.0
            self.want = '' if sim else (port or '')
            self.out_dir = os.path.join(self.base_dir, '연습') if sim else self.base_dir
            self.state.update(connected=False, port='', note='가상 보드를 켜는 중' if sim else '보드를 찾는 중', mode='', fault='',
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
            'board': {'port': self.last_port, 'firmware': s['version'], 'simulated': s['sim'], 'time_scale': self.scale},
            'settings_at_start': self.first_settings,
            'sample_interval_s': 1.0,
            'rows': self.nrows,
            'columns': COLUMNS,
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
        self.evf.write('%s\t%.2f\t%s\t%s\n' % (stamp_ms(), t, kind, text))

    def _settings_seen(self):
        s = self.state
        if self.first_settings is None:                            # 이 파일에서 처음 본 설정만 메타데이터에 남긴다
            self.first_settings = {k: s[k] for k in ('sp', 'kp', 'ki', 'kd', 'outmax', 'src')}
        self._event('set', '설정 SP=%g Kp=%g Ki=%g Kd=%g OUTMAX=%g SRC=%s MODE=%s' %
                    (s['sp'], s['kp'], s['ki'], s['kd'], s['outmax'], s['src'], s['mode']))

    def mark(self, text):
        with self.lock:
            n = sum(1 for e in self.events if e[1] == 'mark') + 1
            self._event('mark', clean(text, 120) or '표시 %d' % n)

    # ---------- 받은 줄 ----------
    def feed(self, line, who=None):
        line = line.rstrip('\r\n')
        kind, d = parse(line)
        with self.lock:
            if not self.csv or (who is not None and who is not self.link):
                return
            if line.strip():
                self.raw.write('%s\t%s\n' % (stamp_ms(), line))
            s = self.state
            if kind == 'data':
                t = self._now()
                vals = [d.get(k) for k in KEYS]
                self.nrows += 1
                if self.nrows % 300 == 0:
                    self._write_meta()                             # 줄 수를 5분마다 메타데이터에 반영 (끝낼 때 한 번 더 씀)
                if len(self.rows) < MAX_ROWS:
                    self.rows.append([t] + vals + [MODE_CODE.get(s['mode'])])
                self.csv.write('%s,%.2f,%s,%s\n' % (stamp_ms(), t,
                               ','.join('' if v is None else f % v for f, v in zip(FMT, vals)), s['mode']))
            elif kind == 'set':
                first = s['sp'] is None
                diff = ['%s %s → %s' % (k.upper(), s[k], d[k]) for k in ('sp', 'kp', 'ki', 'kd', 'outmax', 'src')
                        if s[k] != d[k]]
                old_mode = s['mode']
                s.update(d)
                if first:                                          # 연결 직후, 또는 보드가 리셋된 직후
                    self._settings_seen()
                    self._write_meta()
                else:
                    if diff:
                        self._event('set', '설정 변경: ' + ', '.join(diff))
                    if old_mode and old_mode != d['mode']:
                        self._event('mode', '상태 %s → %s%s' % (old_mode, d['mode'], (' (' + d['fault'] + ')') if d['fault'] else ''))
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
                elif d == 'Auto-tune start':
                    s['mode'] = 'TUNE'
                elif d == '# boot':
                    s['sp'], s['mode'] = None, ''                  # 리셋됨: 다음 설정 줄을 새로 적는다
                self._event('board', d.lstrip('# '))
                if old_mode and s['mode'] and old_mode != s['mode']:
                    self._event('mode', '상태 %s → %s%s' % (old_mode, s['mode'], (' (' + s['fault'] + ')') if s['fault'] else ''))

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
                self._write_meta()

    # ---------- 웹 화면이 읽어 가는 것 ----------
    def snapshot(self, gen, n, ne):
        with self.lock:
            if gen != self.gen:
                n = ne = 0
            return dict(gen=self.gen, rows=self.rows[n:n + 20000], total=len(self.rows), events=self.events[ne:],
                        state=dict(self.state), meta=dict(self.meta), elapsed=self._now(),
                        ports=list(self.ports), want=self.want, sim_ok=sim_exe() is not None, folder=self.out_dir)

    def save_png(self, data, tag):
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
            path = '%s_graph_%s.png' % (self.base, re.sub(r'[^0-9a-z_-]+', '', str(tag))[:30] or 'all')
            n = 1
            while os.path.exists(path):
                n += 1
                path = '%s_graph_%s_%d.png' % (self.base, re.sub(r'[^0-9a-z_-]+', '', str(tag))[:30] or 'all', n)
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
            return False, '쓸 수 없는 명령: ' + cmd
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
                    self._event('cmd', '%s 명령: %s' % (who, cmd))
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
                hub.set_conn(False, note='보드를 찾는 중 (USB를 꽂으세요)', who=self)
                self.wait(1.5)
                continue
            try:
                self.ser = serial.Serial(port, 115200, timeout=0.5)
            except Exception as e:
                why = ('다른 프로그램이 쓰는 중 (아두이노 시리얼 모니터를 닫으세요)' if 'busy' in str(e).lower()
                       else '포트가 없음' if 'No such file' in str(e) or 'FileNotFound' in str(e) else str(e)[:80])
                hub.set_conn(False, note='%s 을 열 수 없음: %s' % (port, why), who=self)
                self.wait(2)
                continue
            hub.set_conn(True, port, who=self)
            buf, last_show = b'', time.monotonic() - 0.5           # 리셋 뒤 부팅이 끝날 즈음(2.5초 뒤) 첫 show
            try:
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
                    hub.set_conn(False, note='USB가 빠졌거나 다른 프로그램이 포트를 열었음', who=self)
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
                raise RuntimeError('가상 보드 파일이 없음')
        except Exception as e:
            self.hub.set_conn(False, note='가상 보드를 켜지 못함: %s' % e, who=self)
            return
        self.p = subprocess.Popen([exe, 'board', str(self.speed)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  text=True, bufsize=1)
        self.hub.set_conn(True, '가상 보드 %g배속' % self.speed, who=self)
        threading.Thread(target=self.poll, daemon=True).start()
        for line in self.p.stdout:
            self.hub.feed(line, who=self)
        if self.alive:
            self.hub.set_conn(False, note='가상 보드가 끝남', who=self)

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
                return self.reply(200, load_page().replace('__TOKEN__', token).encode(), 'text/html; charset=utf-8')
            if u.path == '/api/data':
                q = parse_qs(u.query)
                try:
                    g, n, ev = (int(q.get(k, ['0'])[0] or 0) for k in ('gen', 'n', 'ev'))
                except ValueError:
                    return self.reply(400, {'error': 'bad query'})
                return self.reply(200, hub.snapshot(g, max(0, n), max(0, ev)))
            self.reply(404, {'error': 'not found'})

        def do_POST(self):
            # 다른 웹 페이지가 몰래 명령을 보내지 못하게, 이 화면에만 심어 둔 값(token)을 확인한다
            if not self.local() or not secrets.compare_digest(self.headers.get('X-Token', ''), token):
                return self.reply(403, {'error': 'forbidden'})
            try:
                n = int(self.headers.get('Content-Length', '0') or 0)
                limit = 16000000 if self.path == '/api/png' else 4000
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
                return self.reply(200, {'ok': True, 'msg': '표시를 남겼습니다'})
            if self.path == '/api/meta':
                hub.set_meta(body)
                return self.reply(200, {'ok': True, 'msg': '실험 정보를 저장했습니다'})
            if self.path == '/api/new':
                hub.new_file(body)
                return self.reply(200, {'ok': True, 'msg': '새 파일: ' + os.path.basename(hub.state['csv'])})
            if self.path == '/api/png':
                ok, msg = hub.save_png(body.get('data'), body.get('tag', ''))
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


def run_window(url, hub, selftest=None):
    """브라우저 대신 전용 창에 화면을 띄운다 (응용프로그램으로 실행할 때). 창을 닫으면 끝난다."""
    import webview
    w = webview.create_window('밴드 히터 PID 기록', url, width=1280, height=880, min_size=(1000, 700))
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
    ap.add_argument('--out', default=os.path.join(os.path.expanduser('~'), 'Documents', '밴드히터_기록'), help='기록 폴더')
    ap.add_argument('--name', default='', help='실험 이름 (파일 이름에 붙음)')
    ap.add_argument('--sim', type=float, nargs='?', const=1.0, metavar='배속', help='보드 없이 가상 보드로 실행')
    ap.add_argument('--http-port', type=int, default=8765)
    ap.add_argument('--no-browser', action='store_true', help='브라우저를 자동으로 열지 않음')
    ap.add_argument('--window', action='store_true', help='브라우저 대신 전용 창으로 띄움 (pywebview 필요)')
    ap.add_argument('--selftest', metavar='FILE', help=argparse.SUPPRESS)
    a, _ = ap.parse_known_args()
    if a.sim is not None and a.sim <= 0:
        ap.error('--sim 배속은 0보다 커야 합니다')
    window = window or a.window

    hub = Hub(a.out, name=a.name)
    atexit.register(hub.close)             # 어떤 길로 끝나든 파일을 닫는다 (이미 닫혔으면 아무 일도 안 함)
    hub.start(sim=a.sim, port=a.port)

    token = secrets.token_urlsafe(16)
    srv = None
    for port in range(a.http_port, a.http_port + 20):
        try:
            srv = ThreadingHTTPServer(('127.0.0.1', port), make_handler(hub, token))
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
    for sig in (signal.SIGTERM, getattr(signal, 'SIGHUP', None)):     # 터미널 창을 닫아도 파일을 정리하고 끝냄
        if sig is not None:
            signal.signal(sig, lambda *_: sys.exit(0))
    try:
        if window:
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            run_window(url, hub, a.selftest)
        else:
            print('기록 파일: %s' % hub.state['csv'])
            print('화면: %s   (끝내려면 Ctrl+C)' % url, flush=True)
            if not a.no_browser:
                threading.Timer(0.6, webbrowser.open, [url]).start()
            srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        csv = hub.state['csv']
        hub.close()
        if not window:
            print('\n끝냄. 기록 파일: %s' % csv)


if __name__ == '__main__':
    main()
