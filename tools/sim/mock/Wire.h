#pragma once
// present[주소] 가 false 면 그 주소의 I2C 장치는 응답하지 않는 것으로 흉내 낸다
struct WireMock { bool present[128]; int cur=0; WireMock(){ for(auto&b:present) b=true; }
  void begin(){} void setWireTimeout(long,bool){} void beginTransmission(int a){cur=a;} int endTransmission(){return present[cur&127]?0:2;} };
extern WireMock Wire;
