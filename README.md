# 밴드 히터 PID 컨트롤러

아두이노 나노로 220V 400W 밴드(코일) 히터를 PID 제어한다.

- 온도: T형 열전대 4개, MAX31856 4개 (SPI 공유, CS만 따로)
- 출력: SSR(Autonics SRH1-1210) 시분할, 2초 주기
- 보호: 안전 릴레이, 과열 차단, 센서 고장 감지, 가열 무반응 감지, 워치독
- 표시: 1602 I2C LCD 3개 (0x27 제어, 0x26 열전대 4개, 0x25 220V 상태), 버튼 4개
- PC: 시리얼 기록 프로그램 (CSV 저장, 실시간 차트, 구간 통계, 응답 지표)

## 상태

| 항목 | 상태 |
|---|---|
| 펌웨어 v1.3 | 나노용 컴파일, PC 모의 시험 통과. 실물 LCD 3개와 히터로는 미확인 |
| 회로도 rev 1.2 | 자체 연결 검사 통과. KiCad ERC 미실행 |
| 통(3D 출력) | 모형 간섭 검사 통과. 출력과 끼움 미확인 |
| 기록 프로그램 | 가상 보드로 검증. 실물 보드 미확인 |

## 폴더

| 경로 | 내용 |
|---|---|
| `band_heater_pid/` | 펌웨어 (아두이노 스케치) |
| `build/band_heater_pid.hex` | 올릴 수 있게 컴파일한 펌웨어 |
| `kicad/` | 회로도 원본과 그림 |
| `wiring_diagram.png` | 부품 모양으로 그린 배선도 |
| `docs/` | 핀맵, 배선, 통 치수도면 (PDF 7쪽) |
| `case/` | 통 STL, 밤부 스튜디오 프로젝트 |
| `heater_log.py`, `heater_log.html` | PC 기록 프로그램 |
| `heater_app.py`, `packaging/` | 기록 프로그램을 응용프로그램으로 묶는 것 |
| `tools/` | 그림·문서·모형을 만드는 스크립트, PC 모의 시험 |
| `band_heater_guide.html` | 조립과 사용 안내서 |

## 핀

| 기능 | 나노 핀 |
|---|---|
| MAX31856 SCK / SDO / SDI | D13 / D12 / D4 |
| MAX31856 CS (TC1~TC4) | D10 / D9 / D8 / D7 |
| SSR | D6 |
| 안전 릴레이 | D5 |
| 알람 LED | D11 |
| 버튼 SET / UP / DOWN / RUN | A0 / A1 / A2 / A3 |
| LCD SDA / SCL | A4 / A5 |

## 펌웨어

아두이노 IDE에서 `band_heater_pid/band_heater_pid.ino`를 열고 보드를 Arduino Nano (ATmega328P, Old Bootloader)로 골라 올린다.
라이브러리는 LiquidCrystal I2C가 필요하다. 자동 리셋이 안 되는 보드는 `upload_manual_reset.sh`를 쓴다.

시리얼(115200) 명령: `sp 150`, `kp 3`, `ki 0.01`, `kd 30`, `out 100`, `src 1~4/avg/max`, `run`, `stop`, `tune`, `clear`, `show`.

## PC 모의 시험

펌웨어를 PC에서 그대로 컴파일해 가상 MAX31856 4개와 열 모델에 물려 돌린다.

```sh
c++ -std=c++17 -w -x c++ -I tools/sim/mock -I band_heater_pid tools/sim/sim.cpp -o tools/sim/sim_bin
./tools/sim/sim_bin        # LCD 1개
./tools/sim/sim_bin 3      # LCD 3개
```

## 기록 프로그램

[uv](https://docs.astral.sh/uv/)가 있으면 따로 설치할 것이 없다.

```sh
uv run heater_log.py             # 브라우저에 화면
uv run heater_app.py             # 전용 창
uv run heater_log.py --sim 30    # 보드 없이 가상 보드로 연습
packaging/build_mac.sh           # 맥용 응용프로그램 (dist/)
```

기록은 `~/Documents/밴드히터_기록`에 실험마다 네 파일로 남는다: `.csv`(1초마다 한 줄), `_events.txt`, `_raw.log`, `_meta.json`.
포트를 열면 나노가 리셋되므로 프로그램을 먼저 켜고 운전을 시작한다.

윈도우용 exe는 윈도우 PC에서 `build_windows.bat`으로 만든다. 이 스크립트는 실행해 보지 않았다.

## 주의

220V를 다룬다. 누전차단기, 퓨즈, 접지, 과열 서모스탯을 빼지 않는다. 배선은 전원을 뽑은 상태에서 한다.
