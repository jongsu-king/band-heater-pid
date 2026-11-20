// MAX31856 배선 진단: SDI 핀 후보(D4, D11)와 CS 핀(D10,D9,D8,D7)별로 레지스터를 읽어 출력한다.
// D5(릴레이), D6(SSR)는 건드리지 않고 LOW 로 둔다.
const uint8_t SCKP = 13, SOP = 12;
uint8_t SDIP = 4;
uint8_t xfer(uint8_t out) {
  uint8_t in = 0;
  for (uint8_t i = 0; i < 8; i++) {
    digitalWrite(SCKP, HIGH); digitalWrite(SDIP, (out & 0x80) ? HIGH : LOW); out <<= 1; delayMicroseconds(5);
    in <<= 1; if (digitalRead(SOP)) in |= 1;
    digitalWrite(SCKP, LOW); delayMicroseconds(5);
  }
  return in;
}
void rd(uint8_t cs, uint8_t reg, uint8_t* b, uint8_t n) { digitalWrite(cs, LOW); delayMicroseconds(5); xfer(reg & 0x7F); for (uint8_t i = 0; i < n; i++) b[i] = xfer(0xFF); digitalWrite(cs, HIGH); }
void wr(uint8_t cs, uint8_t reg, uint8_t v) { digitalWrite(cs, LOW); delayMicroseconds(5); xfer(reg | 0x80); xfer(v); digitalWrite(cs, HIGH); }
void hex(uint8_t v) { if (v < 16) Serial.print('0'); Serial.print(v, HEX); Serial.print(' '); }
const uint8_t CS[4] = {10, 9, 8, 7};
void setup() {
  digitalWrite(5, LOW); pinMode(5, OUTPUT); digitalWrite(6, LOW); pinMode(6, OUTPUT);
  Serial.begin(115200);
  pinMode(SCKP, OUTPUT); digitalWrite(SCKP, LOW);
  for (uint8_t i = 0; i < 4; i++) { digitalWrite(CS[i], HIGH); pinMode(CS[i], OUTPUT); }
}
bool inited = false;
void loop() {
  pinMode(SOP, INPUT_PULLUP); pinMode(SDIP, OUTPUT);
  if (!inited) { for (uint8_t i = 0; i < 4; i++) { wr(CS[i], 0x00, 0x00); delay(5); wr(CS[i], 0x02, 0xFF); wr(CS[i], 0x00, 0x92); wr(CS[i], 0x01, 0x07); wr(CS[i], 0x00, 0x90); } inited = true; Serial.println(F("=== init done (fault clear + CR0=90 CR1=07) ===")); }
  delay(1000);
  for (uint8_t i = 0; i < 4; i++) {
    uint8_t b[16]; rd(CS[i], 0x00, b, 16);
    int32_t v = (int32_t)(((uint32_t)b[12] << 24) | ((uint32_t)b[13] << 16) | ((uint32_t)b[14] << 8)) >> 13;
    int16_t cj = (int16_t)((b[10] << 8) | b[11]);
    Serial.print(F("TC")); Serial.print(i + 1); Serial.print(F(" CR0=")); hex(b[0]); Serial.print(F("CR1=")); hex(b[1]);
    Serial.print(F("CJ=")); Serial.print(cj / 256.0, 2); Serial.print(F(" TC=")); Serial.print(v * 0.0078125, 2); Serial.print(F(" SR=")); hex(b[15]); Serial.print(F("| "));
  }
  Serial.println();
}
