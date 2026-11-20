/*
 * =====================================================================
 *  Band Heater PID Controller  v1.3
 * ---------------------------------------------------------------------
 *  보드      : Arduino Uno / Nano (ATmega328P)
 *  온도센서  : 열전대 1~4개 + MAX31856(T형 등 모든 타입) / MAX6675(K형) / MAX31855 모듈
 *              (SCK/SO/SDI 공유, CS 개별)
 *  히터출력  : SSR 시분할(Time-proportional) 제어 → 220V 400W 밴드히터
 *  안전릴레이: D5 (High 트리거 5V 릴레이 모듈, 히터 선에 SSR과 직렬)
 *              운전·오토튜닝 중에만 ON, 정지·알람·리셋 중에는 OFF → SSR이 붙어도(단락 고장) 히터 차단
 *  표시      : 16x2 I2C LCD 1~3개 (SDA=A4, SCL=A5 공유, 주소만 다름)
 *              LCD 1 (0x27) 제어 화면 / LCD 2 (0x26) 열전대 4개 / LCD 3 (0x25) 220V 상태
 *              부팅할 때 응답하는 LCD만 쓴다. LCD 1 하나만 달면 v1.2와 같은 화면으로 동작
 *  버튼      : SET / UP / DOWN / RUN  (핀 ↔ GND, 내부 풀업 사용)
 *  시리얼    : 115200bps, 1초마다 로그 (시리얼 플로터 호환) + 명령 ("help")
 * ---------------------------------------------------------------------
 *  [조작법]
 *   RUN 1초 길게 누름 : 운전 시작
 *   RUN 짧게 누름     : 정지 / 알람 해제
 *   SET               : 메뉴 진입 → 다음 항목 → 마지막 다음엔 저장 후 나가기
 *   UP / DOWN         : 값 변경 (누르고 있으면 연속, 3초 이상이면 10배속)
 *   메인화면에서 UP    : 목표온도 설정으로 이동
 *   메인화면에서 DOWN  : LCD 3 이 없을 때만 온도 화면 ↔ 220V 상태 화면 전환
 *   메뉴 "Auto-tune"에서 UP : 오토튜닝 시작 (끝나면 게인 자동 저장 후 운전)
 *
 *  [LCD 1 제어 화면]  (LCD 2 가 있을 때)
 *   SP150.0 PV148.7     목표온도, 현재온도(제어 기준 센서)
 *   RUN  OUT 45% TC4    상태(RUN/STOP/AT n/ERR!), 출력 %, 제어 기준(TC1~4/AVG/MAX)
 *   알람 중에는 둘째 줄이 1.5초마다 고장 내용과 번갈아 나옴. 메뉴와 안내 문구도 LCD 1 에 나옴
 *
 *  [LCD 2 열전대 화면]
 *   1:148.7 2:132.1     TC1~TC4 온도(0.1도). 제어 기준 센서는 ':' 대신 '>'
 *   3:128.4 4>121.5     읽지 못하는 채널은 --.-
 *
 *  [LCD 3 220V 상태 화면]
 *   R:ON  S:ON   45%    R=안전 릴레이  S=SSR(지금 켜져 있는지)  히터 출력 %
 *   180W  123Wh 01:23   추정 소비전력, 누적 전력량, 누적 운전시간(시:분)
 *   전력·전력량은 측정값이 아니라 HEATER_W × 켜진 시간으로 계산한 추정값 (전원을 껐다 켜면 0부터)
 *
 *  [LCD 1 하나만 있을 때]  v1.2 와 같음
 *   P198.5*S200  45%    P=현재온도  *=히터 ON 중  S=목표온도  출력%/STOP/AT/ERR
 *   198<201 195 203     TC1~TC4 온도, '<' 표시 = 제어 기준 센서. DOWN 으로 220V 상태 화면 전환
 *
 *  필요 라이브러리 : "LiquidCrystal I2C" (Frank de Brabander)
 * =====================================================================
 */

#include <EEPROM.h>
#include <avr/wdt.h>
#include <stddef.h>

// ===================== 사용자 설정 =====================
// I2C LCD 주소. 백팩 뒷면 납땜 패드로 정함: 그대로 = 0x27, A0 이음 = 0x26, A1 이음 = 0x25
// (PCF8574A 백팩이면 0x3F / 0x3E / 0x3D 로 바꾸기). 달지 않은 LCD는 그냥 두면 됨
#define LCD_I2C_ADDR   0x27   // LCD 1: 제어 화면
#define LCD2_I2C_ADDR  0x26   // LCD 2: 열전대 4개 온도
#define LCD3_I2C_ADDR  0x25   // LCD 3: 220V 상태
#define USE_WATCHDOG  1       // 프로그램이 멈추면 2초 뒤 자동 리셋 (리셋 중엔 히터 OFF)

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
LiquidCrystal_I2C lcd(LCD_I2C_ADDR, 16, 2), lcd2(LCD2_I2C_ADDR, 16, 2), lcd3(LCD3_I2C_ADDR, 16, 2);
LiquidCrystal_I2C* const LCDS[3] = {&lcd, &lcd2, &lcd3};
bool lcdHere[3];                  // 부팅할 때 응답한 LCD

// ---- 열전대 ----
#ifndef TC_CHIP
#define TC_CHIP 31856         // 31856 = MAX31856 모듈(T형 등 모든 타입), 6675 = MAX6675(K형 전용), 31855 = MAX31855
#endif
#define TC_TYPE 7             // MAX31856 열전대 타입: T=7, K=3, J=2, E=1, N=4, R=5, S=6, B=0
const uint8_t NUM_TC = 4;                          // 실제 연결한 열전대 수 (1~4)
const uint8_t PIN_TC_SCK = 13;                     // 모든 모듈 공통
const uint8_t PIN_TC_SO  = 12;                     // 모든 모듈 공통 (모듈 표기 SO 또는 SDO)
const uint8_t PIN_TC_SDI = 4;                      // 모든 모듈 공통, MAX31856만 사용
const uint8_t PIN_TC_CS[4] = {10, 9, 8, 7};        // TC1 ~ TC4 각각
const float   TC_OFFSET[4] = {0.0, 0.0, 0.0, 0.0}; // 채널별 보정값(°C). 기준 온도계와 비교해서 입력

// ---- 출력 ----
const uint8_t PIN_SSR   = 6;     // SSR 입력(+). 10k 풀다운 저항 권장
const uint8_t PIN_ALARM = 11;    // 알람 LED 또는 부저 (선택)
const uint8_t PIN_RELAY = 5;     // 안전 릴레이 모듈 IN (High = ON). 10k 풀다운 저항 권장
const bool    RELAY_ON  = HIGH;  // Low 트리거 모듈이면 LOW 로 (그 경우 풀다운 대신 5V 풀업)
const unsigned long RELAY_SETTLE_MS = 200;  // 릴레이 접점이 붙은 뒤 이만큼 기다렸다가 SSR ON (무전류 투입)
const float   HEATER_W  = 400.0; // 히터 정격 소비전력(W). 220V 상태화면의 전력·전력량 추정에 사용

// ---- 버튼 (누르면 GND) ----
const uint8_t PIN_BTN_SET  = A0;
const uint8_t PIN_BTN_UP   = A1;
const uint8_t PIN_BTN_DOWN = A2;
const uint8_t PIN_BTN_RUN  = A3;

// ---- 제어 주기 ----
const unsigned long WINDOW_MS    = 2000;  // 시분할 주기. SSR: 1000~2000 / 기계식 릴레이: 10000 이상
const unsigned long MIN_PULSE_MS = 0;     // 최소 ON/OFF 시간. 기계식 릴레이면 500 정도
const unsigned long TC_READ_MS   = 250;   // 열전대 읽기 주기 (MAX6675 변환시간 220ms 이상)
const unsigned long PID_MS       = 1000;  // PID 계산 주기

// ---- 온도 범위 / 안전 ----
const float SP_MIN     = 0.0;
const float SP_MAX     = 300.0;           // 설정 가능한 최대 목표온도 (T형 열전대 기준. K형이면 400까지)
const float TEMP_LIMIT = 350.0;           // 어느 채널이든 이 온도 이상이면 즉시 차단 + 알람 (T형 측정 한계 약 350°C)
const unsigned long RUNAWAY_MS = 240000UL; // 풀파워로 이 시간 동안...
const float RUNAWAY_RISE = 2.0;            // ...최저점 대비 이만큼도 안 오르면 고장 판정
                                           // (히터 단선 / 열전대 빠짐 / SSR 고장 / 극성 반대)

// ---- 오토튜닝 (릴레이 방식) ----
const float AT_HYST = 1.0;                     // ON/OFF 전환 히스테리시스 (°C)
const uint8_t AT_CYCLES = 4;                   // 측정 사이클 수 (첫 사이클은 버리고 평균)
const unsigned long AT_TIMEOUT_MS = 7200000UL; // 2시간 안에 못 끝내면 중단

// ===================== 설정값 (EEPROM 저장) =====================
struct Settings {
  uint16_t magic;
  float sp;        // 목표온도 (°C)
  float kp;        // 비례 게인   (%/°C)
  float ki;        // 적분 게인   (%/(°C·s))
  float kd;        // 미분 게인   (%·s/°C)
  float outMax;    // 최대 출력   (%)
  uint8_t src;     // 제어 기준: 0~NUM_TC-1 = 해당 TC, NUM_TC = 평균, NUM_TC+1 = 최대값
  uint8_t sum;     // 체크섬
};
const uint16_t CFG_MAGIC = 0xB4E1;
Settings cfg;

// ===================== 상태 =====================
enum { M_STOP, M_RUN, M_TUNE, M_FAULT };
enum { F_NONE, F_SENSOR, F_OVERTEMP, F_RUNAWAY, F_TUNE };
uint8_t mode  = M_STOP;
uint8_t fault = F_NONE;

float   tcTemp[4];
bool    tcOk[4];
uint8_t tcBad[4];

float pv = 0;            // 제어에 쓰는 현재온도
bool  pvOk = false;
float output = 0;        // 히터 출력 (%)
bool  heaterOn = false;

// PID
float iTerm = 0, lastPv = 0;
bool  pidFirst = true;

// 시분할 출력
unsigned long winStart = 0, winOn = 0;

// 안전 릴레이
bool relayOn = false;
unsigned long relayOnAt = 0;

// 220V 상태 (추정): 히터가 실제로 켜져 있던 시간, 운전(RUN/TUNE) 시간
unsigned long heatOnMs = 0, runMs = 0, tAcc = 0;
uint8_t page = 0;                 // 0 = 온도 화면, 1 = 220V 상태 화면

// 폭주(온도 안 오름) 감시
bool raArmed = false;
unsigned long raStart = 0;
float raMin = 0;

// 오토튜닝
struct {
  bool heating, hasOn;
  unsigned long start, lastOn, offAt;
  float curMin, curMax, lastMin;
  uint8_t cycles;
  float sumPu, sumA;
} at;

// UI
enum { MI_SP, MI_SRC, MI_KP, MI_KI, MI_KD, MI_OUT, MI_TUNE, MI_COUNT };
const char* const MENU_NAME[MI_COUNT] = {
  "Setpoint", "Ctrl sensor", "Kp (P gain)", "Ki (I gain)", "Kd (D gain)", "Output limit", "Auto-tune"
};
int8_t menu = -1;                 // -1 = 메인화면
unsigned long menuTouched = 0;
uint8_t runPressMode = M_STOP;
char msg1[17], msg2[17];
unsigned long msgStart = 0, msgDur = 0;
char shadow[3][2][16];            // LCD마다 현재 써 있는 내용 (바뀐 글자만 다시 씀)
bool logOn = true;
char cmdBuf[32];
uint8_t cmdLen = 0;
unsigned long tTc = 0, tPid = 0, tLcd = 0, tLog = 0;

struct Btn {
  uint8_t pin;
  bool raw, down, longDone;
  unsigned long tChange, tDown, tRep;
};
Btn bSet = {PIN_BTN_SET}, bUp = {PIN_BTN_UP}, bDn = {PIN_BTN_DOWN}, bRun = {PIN_BTN_RUN};
enum { EV_PRESS = 1, EV_REPEAT = 2, EV_LONG = 4 };

// ===================== 설정 저장/불러오기 =====================
uint8_t srcCount() { return NUM_TC > 1 ? NUM_TC + 2 : 1; }

uint8_t cfgSum(const Settings& s) {
  const uint8_t* p = (const uint8_t*)&s;
  uint8_t x = 0x5A;
  for (uint8_t i = 0; i < offsetof(Settings, sum); i++) x = ((x << 1) | (x >> 7)) ^ p[i];
  return x;
}

void cfgSave() {
  cfg.sum = cfgSum(cfg);
  EEPROM.put(0, cfg);              // 바뀐 바이트만 기록됨
}

void cfgDefaults() {
  cfg.magic = CFG_MAGIC;
  cfg.sp = 150;
  cfg.kp = 3.0;
  cfg.ki = 0.01;
  cfg.kd = 30;
  cfg.outMax = 100;
  cfg.src = 0;
}

void cfgLoad() {
  EEPROM.get(0, cfg);
  bool bad = cfg.magic != CFG_MAGIC || cfg.sum != cfgSum(cfg) || cfg.src >= srcCount() ||
             isnan(cfg.sp) || isnan(cfg.kp) || isnan(cfg.ki) || isnan(cfg.kd) || isnan(cfg.outMax);
  if (bad) {
    cfgDefaults();
    cfgSave();
  }
  cfg.sp = constrain(cfg.sp, SP_MIN, SP_MAX);
  cfg.outMax = constrain(cfg.outMax, 10, 100);
}

// ===================== 열전대 (MAX31856 / MAX6675 / MAX31855) =====================
// MAX31856: SPI 모드 1 (SCK 평소 LOW, 올라갈 때 칩이 출력하고 내려갈 때 칩이 입력을 읽음)
uint8_t tcXfer(uint8_t out) {
  uint8_t in = 0;
  for (uint8_t i = 0; i < 8; i++) {
    digitalWrite(PIN_TC_SCK, HIGH);
    digitalWrite(PIN_TC_SDI, (out & 0x80) ? HIGH : LOW);
    out <<= 1;
    delayMicroseconds(2);
    in <<= 1;
    if (digitalRead(PIN_TC_SO)) in |= 1;
    digitalWrite(PIN_TC_SCK, LOW);
    delayMicroseconds(2);
  }
  return in;
}

void tc56Read(uint8_t cs, uint8_t reg, uint8_t* buf, uint8_t n) {
  digitalWrite(PIN_TC_SCK, LOW);
  digitalWrite(cs, LOW);
  tcXfer(reg & 0x7F);
  for (uint8_t i = 0; i < n; i++) buf[i] = tcXfer(0xFF);
  digitalWrite(cs, HIGH);
}

void tc56Write(uint8_t cs, uint8_t reg, uint8_t v) {
  digitalWrite(PIN_TC_SCK, LOW);
  digitalWrite(cs, LOW);
  tcXfer(reg | 0x80);
  tcXfer(v);
  digitalWrite(cs, HIGH);
}

// 칩 설정 (MAX31856만 필요): 자동 연속 변환 + 단선 감지 + 60Hz 노이즈 필터, 열전대 타입
void tcInit(uint8_t cs) {
#if TC_CHIP == 31856
  tc56Write(cs, 0x00, 0x90);
  tc56Write(cs, 0x01, TC_TYPE);
#else
  (void)cs;
#endif
}

uint32_t tcShiftIn(uint8_t cs, uint8_t bits) {
  uint32_t v = 0;
  digitalWrite(PIN_TC_SCK, LOW);
  digitalWrite(cs, LOW);
  delayMicroseconds(10);
  for (uint8_t i = 0; i < bits; i++) {
    v <<= 1;
    if (digitalRead(PIN_TC_SO)) v |= 1;
    digitalWrite(PIN_TC_SCK, HIGH);
    delayMicroseconds(5);
    digitalWrite(PIN_TC_SCK, LOW);
    delayMicroseconds(5);
  }
  digitalWrite(cs, HIGH);
  return v;
}

// 한 채널 읽기. 단선 / 모듈 응답 없음이면 false
bool tcReadOnce(uint8_t cs, float& t) {
#if TC_CHIP == 31856
  uint8_t b[4];
  tc56Read(cs, 0x0C, b, 4);                       // 온도 3바이트 + 고장 상태(SR)
  if ((b[0] & b[1] & b[2] & b[3]) == 0xFF || (b[0] | b[1] | b[2] | b[3]) == 0) return false;  // 모듈 응답 없음
  if (b[3] & 0xC3) return false;                  // SR: 단선, 과전압, 측정범위 초과
  int32_t v = (int32_t)(((uint32_t)b[0] << 24) | ((uint32_t)b[1] << 16) | ((uint32_t)b[2] << 8)) >> 13;
  t = v * 0.0078125;                              // 19비트, 0.0078°C 단위
#elif TC_CHIP == 31855
  uint32_t r = tcShiftIn(cs, 32);
  // D16 = 고장(단선/GND단락/VCC단락), 0x00000000/0xFFFFFFFF = 모듈 응답 없음
  if (r == 0 || r == 0xFFFFFFFFUL || (r & 0x10000UL)) return false;
  t = ((int16_t)(r >> 16) >> 2) * 0.25;
#else
  uint16_t r = tcShiftIn(cs, 16);
  // D2 = 열전대 단선, D15/D1 은 항상 0, 0x0000/0xFFFF = 모듈 응답 없음
  if (r == 0 || (r & 0x8006)) return false;
  t = (r >> 3) * 0.25;
#endif
  return true;
}

void readThermocouples() {
  for (uint8_t i = 0; i < NUM_TC; i++) {
    float t;
    if (!tcReadOnce(PIN_TC_CS[i], t)) {
      tcInit(PIN_TC_CS[i]);                      // MAX31856이 전원 문제로 설정을 잃었을 수 있으니 다시 설정
      if (tcBad[i] < 255) tcBad[i]++;
      if (tcBad[i] >= 3) tcOk[i] = false;      // 3번 연속 실패해야 고장 (노이즈 무시)
    } else {
      t += TC_OFFSET[i];
      if (tcOk[i]) tcTemp[i] += 0.3 * (t - tcTemp[i]);   // 저역통과 필터
      else tcTemp[i] = t;
      tcOk[i] = true;
      tcBad[i] = 0;
    }
  }
}

// 제어에 쓸 온도 계산. 쓰이는 센서가 하나라도 고장이면 false
bool calcPv(float& out) {
  if (cfg.src < NUM_TC) {
    out = tcTemp[cfg.src];
    return tcOk[cfg.src];
  }
  float sum = 0, mx = -999;
  for (uint8_t i = 0; i < NUM_TC; i++) {
    if (!tcOk[i]) return false;
    sum += tcTemp[i];
    if (tcTemp[i] > mx) mx = tcTemp[i];
  }
  out = (cfg.src == NUM_TC) ? sum / NUM_TC : mx;
  return true;
}

// ===================== 고장 처리 =====================
const char* faultText(uint8_t f) {
  switch (f) {
    case F_SENSOR:   return "SENSOR FAULT";
    case F_OVERTEMP: return "OVER TEMP!";
    case F_RUNAWAY:  return "NO TEMP RISE";
    case F_TUNE:     return "TUNE TIMEOUT";
  }
  return "";
}

// 안전 릴레이: 운전·오토튜닝 중에만 ON. 꺼질 때는 SSR을 먼저 끈 뒤에 연다
void setRelay(bool on) {
  if (on && !relayOn) relayOnAt = millis();
  relayOn = on;
  digitalWrite(PIN_RELAY, on ? RELAY_ON : !RELAY_ON);
}

void heaterOff() {
  output = 0;
  winOn = 0;
  heaterOn = false;
  digitalWrite(PIN_SSR, LOW);
  setRelay(false);
}

void trip(uint8_t f) {
  heaterOff();
  if (mode != M_FAULT) {
    mode = M_FAULT;
    fault = f;
    Serial.print(F("!! FAULT: "));
    Serial.println(faultText(f));
  }
}

void showMsg(const char* a, const char* b, unsigned long ms) {
  strncpy(msg1, a, 16); msg1[16] = 0;
  strncpy(msg2, b, 16); msg2[16] = 0;
  msgStart = millis();
  msgDur = ms;
}

// ===================== PID =====================
void pidReset() {
  iTerm = 0;
  pidFirst = true;
  raArmed = false;
}

float pidCompute(float x, float dt) {
  float err = cfg.sp - x;
  float d = pidFirst ? 0 : -(x - lastPv) / dt;    // 측정값 미분 (목표 바꿀 때 튐 방지)
  lastPv = x;
  pidFirst = false;
  float p = cfg.kp * err;
  float out = p + iTerm + cfg.kd * d;
  // anti-windup: 출력이 이미 포화인데 같은 방향으로 더 밀면 적분 중지
  if (!((out >= cfg.outMax && err > 0) || (out <= 0 && err < 0))) {
    iTerm += cfg.ki * err * dt;
    iTerm = constrain(iTerm, 0, cfg.outMax);
  }
  out = p + iTerm + cfg.kd * d;
  return constrain(out, 0, cfg.outMax);
}

// ===================== 오토튜닝 (릴레이 피드백 방식) =====================
//  목표온도 기준으로 히터를 100%/0% 로 토글 → 생기는 진동의 주기(Pu)와 진폭(a)으로
//  임계게인 Ku = 4d/(πa) 계산 → Tyreus-Luyben 규칙으로 게인 산출
void tuneFinish(float duty) {
  uint8_t n = AT_CYCLES - 1;
  float pu = at.sumPu / n;                 // 진동 주기 (s)
  float a  = at.sumA / n;                  // 진동 진폭 (°C)
  float d  = cfg.outMax / 2.0;             // 출력 진폭 (%)
  float a2 = a * a - AT_HYST * AT_HYST;
  if (a2 < 0.01) a2 = 0.01;
  float ku = 4.0 * d / (PI * sqrt(a2));
  // Tyreus-Luyben 규칙 (지연이 큰 히터에서 Ziegler-Nichols 보다 오버슈트가 훨씬 적음)
  cfg.kp = 0.45 * ku;                      // Kp = Ku/2.2
  cfg.ki = cfg.kp / (2.2 * pu);            // Ti = 2.2·Pu
  cfg.kd = cfg.kp * (pu / 6.3);            // Td = Pu/6.3
  cfgSave();

  Serial.print(F("Auto-tune done: Pu=")); Serial.print(pu, 1);
  Serial.print(F("s a=")); Serial.print(a, 2);
  Serial.print(F("C Ku=")); Serial.println(ku, 3);

  pidReset();
  iTerm = constrain(cfg.outMax * duty, 0, cfg.outMax);   // 진동 중 평균출력으로 시작 (무충격 전환)
  mode = M_RUN;
  char b[17], k[8];
  dtostrf(cfg.kp, 1, 2, k);
  snprintf(b, sizeof b, "Kp=%s", k);
  showMsg("Auto-tune done!", b, 3000);
}

float tuneStep(float x) {
  unsigned long now = millis();
  if (now - at.start > AT_TIMEOUT_MS) {
    trip(F_TUNE);
    return 0;
  }
  if (at.heating) {
    if (x < at.curMin) at.curMin = x;
    if (x > cfg.sp + AT_HYST) {                       // ON → OFF
      at.heating = false;
      at.lastMin = at.curMin;
      at.curMax = x;
      at.offAt = now;
    }
  } else {
    if (x > at.curMax) at.curMax = x;
    if (x < cfg.sp - AT_HYST) {                       // OFF → ON : 한 사이클 끝
      if (at.hasOn) {
        at.cycles++;
        if (at.cycles > 1) {                          // 첫 사이클은 버림
          at.sumPu += (now - at.lastOn) / 1000.0;
          at.sumA  += (at.curMax - at.lastMin) / 2.0;
        }
        if (at.cycles >= AT_CYCLES) {
          tuneFinish((float)(at.offAt - at.lastOn) / (now - at.lastOn));
          return 0;
        }
      }
      at.heating = true;
      at.hasOn = true;
      at.lastOn = now;
      at.curMin = x;
    }
  }
  return at.heating ? cfg.outMax : 0;
}

void tuneStart() {
  if (mode != M_STOP && mode != M_RUN) return;
  if (!pvOk) {
    showMsg("Can't tune:", "sensor error", 2500);
    return;
  }
  at.heating = pv < cfg.sp;
  at.hasOn = false;
  at.start = millis();
  at.cycles = 0;
  at.sumPu = at.sumA = 0;
  at.curMin = at.curMax = at.lastMin = pv;
  raArmed = false;
  mode = M_TUNE;
  Serial.println(F("Auto-tune start"));
}

// ===================== 제어 =====================
// 풀파워인데 온도가 안 오르면 고장 (히터 단선, 열전대 빠짐, SSR 개방 고장, 열전대 극성 반대)
void runawayCheck(float x) {
  bool full = output >= cfg.outMax - 0.5 && x < cfg.sp - 5;
  if (!full) {
    raArmed = false;
    return;
  }
  unsigned long now = millis();
  if (!raArmed) {
    raArmed = true;
    raStart = now;
    raMin = x;
    return;
  }
  if (x < raMin) raMin = x;
  if (now - raStart >= RUNAWAY_MS) {
    if (x - raMin < RUNAWAY_RISE) trip(F_RUNAWAY);
    else {
      raStart = now;
      raMin = x;
    }
  }
}

void controlStep() {
  // 절대 과열 감시: 모드와 상관없이 항상 (정지 중 SSR 단락 고장도 알람)
  for (uint8_t i = 0; i < NUM_TC; i++)
    if (tcOk[i] && tcTemp[i] >= TEMP_LIMIT) trip(F_OVERTEMP);

  float x;
  pvOk = calcPv(x);
  if (pvOk) pv = x;

  if (mode == M_RUN || mode == M_TUNE) {
    if (!pvOk) {
      trip(F_SENSOR);
      return;
    }
    output = (mode == M_RUN) ? pidCompute(pv, PID_MS / 1000.0) : tuneStep(pv);
    if (mode == M_RUN || mode == M_TUNE) runawayCheck(pv);
  } else {
    output = 0;
  }
}

void startRun() {
  if (mode != M_STOP) return;
  if (!pvOk) {
    showMsg("Can't start:", "sensor error", 2500);
    return;
  }
  pidReset();
  mode = M_RUN;
  Serial.println(F("RUN"));
}

void stopRun() {
  if (mode == M_RUN || mode == M_TUNE) {
    mode = M_STOP;
    heaterOff();
    Serial.println(F("STOP"));
  }
}

bool tryClearFault() {
  if (mode != M_FAULT) return true;
  for (uint8_t i = 0; i < NUM_TC; i++) {
    if (tcOk[i] && tcTemp[i] >= TEMP_LIMIT - 10) {
      showMsg("Still too hot!", "wait & retry", 2000);
      Serial.println(F("? still too hot"));
      return false;
    }
  }
  mode = M_STOP;
  fault = F_NONE;
  showMsg("Alarm cleared", "Hold RUN: start", 2000);
  Serial.println(F("Fault cleared"));
  return true;
}

// 시분할 출력: WINDOW_MS 마다 출력% 만큼만 SSR ON
void updateSsr() {
  unsigned long now = millis();
  if (now - winStart >= WINDOW_MS) {
    winStart = now;
    unsigned long on = (unsigned long)(output * WINDOW_MS / 100.0);
    if (on < MIN_PULSE_MS) on = 0;
    if (on + MIN_PULSE_MS > WINDOW_MS) on = WINDOW_MS;
    winOn = on;
  }
  bool active = mode == M_RUN || mode == M_TUNE;
  if (!active) digitalWrite(PIN_SSR, LOW);         // 릴레이를 열기 전에 SSR 먼저 OFF
  setRelay(active);
  // 직전 구간 동안의 상태로 누적 (전력량·운전시간 추정)
  unsigned long dt = now - tAcc;
  tAcc = now;
  if (heaterOn) heatOnMs += dt;
  if (active) runMs += dt;

  heaterOn = active && (millis() - relayOnAt >= RELAY_SETTLE_MS) && (now - winStart < winOn);
  digitalWrite(PIN_SSR, heaterOn ? HIGH : LOW);
}

void updateAlarm() {
  bool on = mode == M_FAULT && (millis() / 500) % 2;
  digitalWrite(PIN_ALARM, on ? HIGH : LOW);
}

// ===================== 버튼 / 메뉴 =====================
uint8_t pollBtn(Btn& b, unsigned long now) {
  uint8_t ev = 0;
  bool r = digitalRead(b.pin) == LOW;
  if (r != b.raw) {
    b.raw = r;
    b.tChange = now;
  }
  if (r != b.down && now - b.tChange >= 30) {        // 30ms 디바운스
    b.down = r;
    if (r) {
      b.tDown = b.tRep = now;
      b.longDone = false;
      ev |= EV_PRESS;
    }
  }
  if (b.down) {
    if (!b.longDone && now - b.tDown >= 1000) {
      b.longDone = true;
      ev |= EV_LONG;
    }
    if (now - b.tDown >= 500 && now - b.tRep >= 120) {
      b.tRep = now;
      ev |= EV_REPEAT;
    }
  }
  return ev;
}

void menuExit() {
  menu = -1;
  cfgSave();
}

void menuAdjust(int8_t dir, uint8_t mult) {
  int16_t n = dir * mult;
  switch (menu) {
    case MI_SP:  cfg.sp = constrain(cfg.sp + n * 1.0, SP_MIN, SP_MAX); break;
    case MI_SRC: cfg.src = (cfg.src + srcCount() + dir) % srcCount(); pidFirst = true; break;
    case MI_KP:  cfg.kp = constrain(cfg.kp + n * 0.1, 0, 500); break;
    case MI_KI:  cfg.ki = constrain(cfg.ki + n * 0.001, 0, 50); break;
    case MI_KD:  cfg.kd = constrain(cfg.kd + n * 1.0, 0, 5000); break;
    case MI_OUT: cfg.outMax = constrain(cfg.outMax + dir * 5.0, 10, 100); break;
    case MI_TUNE:
      if (dir > 0) {
        menuExit();
        tuneStart();
      }
      break;
  }
}

void handleButtons() {
  unsigned long now = millis();
  uint8_t eSet = pollBtn(bSet, now);
  uint8_t eUp  = pollBtn(bUp, now);
  uint8_t eDn  = pollBtn(bDn, now);
  uint8_t eRun = pollBtn(bRun, now);

  // RUN: 짧게 = 정지/알람해제, 정지 상태에서 1초 길게 = 시작
  if (eRun & EV_PRESS) {
    runPressMode = mode;
    if (mode == M_RUN || mode == M_TUNE) stopRun();
    else if (mode == M_FAULT) tryClearFault();
  }
  if ((eRun & EV_LONG) && runPressMode == M_STOP) startRun();

  if (eSet | eUp | eDn) menuTouched = now;
  if (eSet & EV_PRESS) {
    if (menu < 0) menu = 0;
    else if (++menu >= MI_COUNT) menuExit();
  }
  int8_t dir = 0;
  if (eUp & (EV_PRESS | EV_REPEAT)) dir = 1;
  if (eDn & (EV_PRESS | EV_REPEAT)) dir = -1;
  if (dir) {
    if (menu < 0) {
      if (dir > 0) menu = MI_SP;                     // 메인화면에서 UP → 목표온도 설정으로 이동
      else if ((eDn & EV_PRESS) && !lcdHere[2]) page ^= 1;   // LCD 3 이 없을 때만: DOWN → 온도 화면 ↔ 220V 상태 화면
    } else {
      Btn& b = dir > 0 ? bUp : bDn;
      menuAdjust(dir, (now - b.tDown > 3000) ? 10 : 1);
    }
  }
  if (menu >= 0 && now - menuTouched > 20000) menuExit();   // 20초간 조작 없으면 저장 후 나감
}

// ===================== LCD =====================
void lcdRow(uint8_t n, uint8_t r, const char* s) {     // n = LCD 번호(0~2), r = 줄
  if (!lcdHere[n]) return;
  uint8_t len = strlen(s);
  for (uint8_t i = 0; i < 16; i++) {
    char c = i < len ? s[i] : ' ';
    if (shadow[n][r][i] != c) {
      LCDS[n]->setCursor(i, r);
      LCDS[n]->write((uint8_t)c);
      shadow[n][r][i] = c;
    }
  }
}

void drawMenu(char* l1, char* l2) {
  char f[12];
  snprintf(l1, 17, "%-12s %d/%d", MENU_NAME[menu], menu + 1, MI_COUNT);
  switch (menu) {
    case MI_SP:
      snprintf(l2, 17, "> %d%cC", (int)(cfg.sp + 0.5), (char)223);
      break;
    case MI_SRC:
      if (cfg.src < NUM_TC) snprintf(l2, 17, "> TC%d", cfg.src + 1);
      else strcpy(l2, cfg.src == NUM_TC ? "> AVG of all" : "> MAX of all");
      break;
    case MI_KP: dtostrf(cfg.kp, 1, 2, f); snprintf(l2, 17, "> %s", f); break;
    case MI_KI: dtostrf(cfg.ki, 1, 4, f); snprintf(l2, 17, "> %s", f); break;
    case MI_KD: dtostrf(cfg.kd, 1, 1, f); snprintf(l2, 17, "> %s", f); break;
    case MI_OUT: snprintf(l2, 17, "> %d %%", (int)cfg.outMax); break;
    case MI_TUNE: strcpy(l2, mode == M_TUNE ? "> running..." : "> UP = start"); break;
  }
}

float energyWh() { return heatOnMs / 3600000.0 * HEATER_W; }

// 220V 상태화면:  R:ON  S:ON   45%  /  180W  123Wh 01:23
void drawAc(char* l1, char* l2) {
  char e[8];
  bool active = mode == M_RUN || mode == M_TUNE;
  snprintf(l1, 17, "R:%-3s S:%-3s %3d%%", relayOn ? "ON" : "OFF", heaterOn ? "ON" : "OFF", (int)(output + 0.5));
  float wh = energyWh();
  if (wh < 999.5) snprintf(e, sizeof e, "%4dWh", (int)(wh + 0.5));
  else if (wh < 9950.0) {
    dtostrf(wh / 1000.0, 3, 1, e);                            // 1.0kWh ~ 9.9kWh
    strcat(e, "kWh");
  } else snprintf(e, sizeof e, "%3dkWh", wh < 999500.0 ? (int)(wh / 1000.0 + 0.5) : 999);
  unsigned long mins = runMs / 60000UL;
  if (mins > 5999) mins = 5999;                               // 99:59 까지 표시
  snprintf(l2, 17, "%3dW%6s %02d:%02d", active ? (int)(HEATER_W * output / 100.0 + 0.5) : 0, e,
           (int)(mins / 60), (int)(mins % 60));
}

// LCD 2 열전대 화면:  1:148.7 2:132.1  /  3:128.4 4>121.5   ('>' = 제어 기준)
void drawTemps(char* l1, char* l2) {
  char f[8];
  for (uint8_t i = 0; i < 4; i++) {
    char* p = (i < 2 ? l1 : l2) + (i % 2) * 8;
    if (i >= NUM_TC) {
      strcpy(p, "        ");
      continue;
    }
    if (tcOk[i]) dtostrf(constrain(tcTemp[i], -99.9, 999.9), 5, 1, f);
    else strcpy(f, " --.-");
    snprintf(p, 9, "%d%c%s ", i + 1, cfg.src == i ? '>' : ':', f);
  }
}

void drawLcd() {
  char l1[17], l2[17], f[8], g[8], st[5];
  unsigned long now = millis();
  bool blink = mode == M_FAULT && (now / 1500) % 2;      // 알람 중 1.5초마다 고장 내용과 번갈아 표시

  if (lcdHere[1]) {                                      // LCD 2: 열전대 4개 (항상)
    drawTemps(l1, l2);
    lcdRow(1, 0, l1);
    lcdRow(1, 1, l2);
  }
  if (lcdHere[2]) {                                      // LCD 3: 220V 상태 (항상)
    drawAc(l1, l2);
    lcdRow(2, 0, l1);
    lcdRow(2, 1, l2);
  }

  // ---- LCD 1 ----
  if (now - msgStart < msgDur) {
    lcdRow(0, 0, msg1);
    lcdRow(0, 1, msg2);
    return;
  }
  if (menu >= 0) {
    drawMenu(l1, l2);
    lcdRow(0, 0, l1);
    lcdRow(0, 1, l2);
    return;
  }
  if (page == 1 && !lcdHere[2]) {                        // LCD 3 이 없으면 LCD 1 에서 DOWN 으로 넘겨 봄
    drawAc(l1, l2);
    if (blink) strcpy(l2, faultText(fault));
    lcdRow(0, 0, l1);
    lcdRow(0, 1, l2);
    return;
  }

  if (pvOk) dtostrf(pv > 999.9 ? 999.9 : pv, 5, 1, f);
  else strcpy(f, " --.-");

  if (lcdHere[1]) {
    // LCD 2 가 채널 온도를 보여주므로 LCD 1 은 제어 요약:  SP150.0 PV148.7  /  RUN  OUT 45% TC4
    dtostrf(cfg.sp, 5, 1, g);
    snprintf(l1, sizeof l1, "SP%s PV%s", g, f);
    switch (mode) {
      case M_RUN:   strcpy(st, "RUN"); break;
      case M_TUNE:  snprintf(st, sizeof st, "AT%d", at.cycles); break;
      case M_FAULT: strcpy(st, "ERR!"); break;
      default:      strcpy(st, "STOP");
    }
    if (blink) strcpy(l2, faultText(fault));
    else {
      char sn[4] = "TC1";
      if (cfg.src < NUM_TC) sn[2] = '1' + cfg.src;
      else strcpy(sn, cfg.src == NUM_TC ? "AVG" : "MAX");
      snprintf(l2, sizeof l2, "%-4s OUT%3d%% %s", st, (int)(output + 0.5), sn);
    }
    lcdRow(0, 0, l1);
    lcdRow(0, 1, l2);
    return;
  }

  // LCD 1 하나만 있을 때 (v1.2 화면).  1행: P198.5*S200  45%
  switch (mode) {
    case M_RUN:   snprintf(st, sizeof st, "%3d%%", (int)(output + 0.5)); break;
    case M_TUNE:  snprintf(st, sizeof st, "AT%d ", at.cycles); break;
    case M_FAULT: strcpy(st, "ERR!"); break;
    default:      strcpy(st, "STOP");
  }
  char tag = cfg.src < NUM_TC ? 'P' : (cfg.src == NUM_TC ? 'A' : 'M');
  snprintf(l1, sizeof l1, "%c%s%cS%-3d %s", tag, f, heaterOn ? '*' : ' ', (int)(cfg.sp + 0.5), st);

  // 2행: 채널별 온도 (고장 시 고장 내용과 번갈아 표시)
  if (blink) {
    strcpy(l2, faultText(fault));
  } else {
    for (uint8_t i = 0; i < 4; i++) {
      char* p = l2 + i * 4;
      if (i >= NUM_TC) {
        strcpy(p, "    ");
        continue;
      }
      if (!tcOk[i]) {
        strcpy(p, "--- ");
      } else {
        int t = (int)(tcTemp[i] + 0.5);
        snprintf(p, 5, "%3d ", constrain(t, -99, 999));
      }
      if (cfg.src == i) p[3] = '<';
    }
    l2[16] = 0;
  }
  lcdRow(0, 0, l1);
  lcdRow(0, 1, l2);
}

// ===================== 시리얼 =====================
void logSerial() {
  if (!logOn) return;
  Serial.print(F("PV:"));   Serial.print(pv, 2);
  Serial.print(F(",SP:"));  Serial.print(cfg.sp, 1);
  Serial.print(F(",OUT:")); Serial.print(output, 1);
  for (uint8_t i = 0; i < NUM_TC; i++) {
    if (!tcOk[i]) continue;
    Serial.print(F(",T")); Serial.print(i + 1); Serial.print(':');
    Serial.print(tcTemp[i], 2);
  }
  Serial.println();
}

void printSettings() {
  static const char* const MODE_NAME[] = {"STOP", "RUN", "TUNE", "FAULT"};
  Serial.print(F("# SP="));   Serial.print(cfg.sp, 1);
  Serial.print(F(" Kp="));    Serial.print(cfg.kp, 3);
  Serial.print(F(" Ki="));    Serial.print(cfg.ki, 5);
  Serial.print(F(" Kd="));    Serial.print(cfg.kd, 2);
  Serial.print(F(" OUTMAX="));Serial.print(cfg.outMax, 0);
  Serial.print(F(" SRC="));
  if (cfg.src < NUM_TC) { Serial.print(F("TC")); Serial.print(cfg.src + 1); }
  else Serial.print(cfg.src == NUM_TC ? F("AVG") : F("MAX"));
  Serial.print(F(" MODE="));  Serial.print(MODE_NAME[mode]);
  if (mode == M_FAULT) { Serial.print(' '); Serial.print(faultText(fault)); }
  Serial.println();
  Serial.print(F("# AC: RELAY="));  Serial.print(relayOn ? F("ON") : F("OFF"));
  Serial.print(F(" SSR="));         Serial.print(heaterOn ? F("ON") : F("OFF"));
  Serial.print(F(" E="));           Serial.print(energyWh(), 1);
  Serial.print(F("Wh RUNTIME="));   Serial.print(runMs / 60000UL);
  Serial.println(F("min (estimated)"));
}

void printHelp() {
  Serial.println(F("# commands: sp 200 | kp 3 | ki 0.01 | kd 30 | out 100 | src 1~4/avg/max"));
  Serial.println(F("#           run | stop | tune | clear | show | log 0/1 | help"));
}

void runCommand(char* s) {
  char* cmd = strtok(s, " =");
  char* arg = strtok(NULL, " =");
  if (!cmd) return;
  float v = arg ? atof(arg) : 0;
  bool changed = true;

  if      (!strcmp(cmd, "sp")  && arg) cfg.sp = constrain(v, SP_MIN, SP_MAX);
  else if (!strcmp(cmd, "kp")  && arg) cfg.kp = v < 0 ? 0 : v;
  else if (!strcmp(cmd, "ki")  && arg) cfg.ki = v < 0 ? 0 : v;
  else if (!strcmp(cmd, "kd")  && arg) cfg.kd = v < 0 ? 0 : v;
  else if (!strcmp(cmd, "out") && arg) cfg.outMax = constrain(v, 10, 100);
  else if (!strcmp(cmd, "src") && arg) {
    if (!strcmp(arg, "avg") && NUM_TC > 1) cfg.src = NUM_TC;
    else if (!strcmp(arg, "max") && NUM_TC > 1) cfg.src = NUM_TC + 1;
    else if (v >= 1 && v <= NUM_TC) cfg.src = (uint8_t)v - 1;
    else { Serial.println(F("? bad src")); return; }
    pidFirst = true;
  } else {
    changed = false;
    if      (!strcmp(cmd, "run"))   { if (mode == M_FAULT) Serial.println(F("? fault: send 'clear' first")); else startRun(); }
    else if (!strcmp(cmd, "stop"))  stopRun();
    else if (!strcmp(cmd, "tune"))  tuneStart();
    else if (!strcmp(cmd, "clear")) tryClearFault();
    else if (!strcmp(cmd, "log") && arg) logOn = v != 0;
    else if (!strcmp(cmd, "show"))  ;
    else { printHelp(); return; }
  }
  if (changed) cfgSave();
  printSettings();
}

void handleSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdLen) {
        cmdBuf[cmdLen] = 0;
        runCommand(cmdBuf);
        cmdLen = 0;
      }
    } else if (cmdLen < sizeof(cmdBuf) - 1) {
      cmdBuf[cmdLen++] = tolower(c);
    }
  }
}

// ===================== setup / loop =====================
void setup() {
#if USE_WATCHDOG
  MCUSR = 0;
  wdt_disable();
#endif
  digitalWrite(PIN_SSR, LOW);                // 가장 먼저 히터 OFF
  pinMode(PIN_SSR, OUTPUT);
  digitalWrite(PIN_RELAY, !RELAY_ON);        // 안전 릴레이도 OFF
  pinMode(PIN_RELAY, OUTPUT);
  pinMode(PIN_ALARM, OUTPUT);
  digitalWrite(PIN_ALARM, LOW);

  pinMode(PIN_TC_SCK, OUTPUT);
  digitalWrite(PIN_TC_SCK, LOW);
  pinMode(PIN_TC_SO, INPUT_PULLUP);          // 모듈 없으면 0xFFFF → 고장으로 인식
#if TC_CHIP == 31856
  pinMode(PIN_TC_SDI, OUTPUT);
#endif
  for (uint8_t i = 0; i < NUM_TC; i++) {
    digitalWrite(PIN_TC_CS[i], HIGH);
    pinMode(PIN_TC_CS[i], OUTPUT);
  }
  for (uint8_t i = 0; i < NUM_TC; i++) tcInit(PIN_TC_CS[i]);
  pinMode(PIN_BTN_SET, INPUT_PULLUP);
  pinMode(PIN_BTN_UP, INPUT_PULLUP);
  pinMode(PIN_BTN_DOWN, INPUT_PULLUP);
  pinMode(PIN_BTN_RUN, INPUT_PULLUP);

  Serial.begin(115200);
  Serial.println(F("# boot"));
  Wire.begin();
  Wire.setWireTimeout(3000, true);           // LCD 배선 문제로 I2C가 막혀도 프로그램이 멈추지 않게 (AVR 코어 1.8.3+)
  const uint8_t lcdAddr[3] = {LCD_I2C_ADDR, LCD2_I2C_ADDR, LCD3_I2C_ADDR};
  for (uint8_t i = 0; i < 3; i++) {          // 응답하는 LCD만 쓴다
    Wire.beginTransmission(lcdAddr[i]);
    lcdHere[i] = Wire.endTransmission() == 0;
    Serial.print(F("# LCD"));
    Serial.print(i + 1);
    Serial.println(lcdHere[i] ? F(" ok") : F(" not found"));
    if (lcdHere[i]) {
      LCDS[i]->init();
      LCDS[i]->backlight();
      LCDS[i]->clear();
    }
  }
  if (!lcdHere[0]) Serial.println(F("# LCD1 not found: check SDA=A4, SCL=A5, 5V, GND, address pads"));

  cfgLoad();

  char b[17];
  snprintf(b, sizeof b, "v1.3   TC x%d", NUM_TC);
  lcdRow(0, 0, "Band Heater PID");
  lcdRow(0, 1, b);
  delay(1500);                               // MAX6675 첫 변환 대기 겸 스플래시

  readThermocouples();
  pvOk = calcPv(pv);
  Serial.println(F("# Band Heater PID v1.3"));
  printHelp();
  printSettings();

#if USE_WATCHDOG
  wdt_enable(WDTO_2S);
#endif
  tTc = tPid = tLcd = tLog = tAcc = millis();
}

void loop() {
#if USE_WATCHDOG
  wdt_reset();
#endif
  unsigned long now = millis();

  handleSerial();
  handleButtons();
  if (now - tTc >= TC_READ_MS) { tTc = now; readThermocouples(); }
  if (now - tPid >= PID_MS)    { tPid = now; controlStep(); }
  updateSsr();
  updateAlarm();
  if (now - tLcd >= 250)  { tLcd = now; drawLcd(); }
  if (now - tLog >= 1000) { tLog = now; logSerial(); }
}
