#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <cctype>
#include <string>
#include <deque>
typedef bool boolean; typedef uint8_t byte;
#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#define PI 3.14159265358979
#define F(x) x
enum { A0=14, A1, A2, A3, A4, A5 };
#define constrain(x,a,b) ((x)<(a)?(a):((x)>(b)?(b):(x)))
using std::isnan;
unsigned long millis(); void delay(unsigned long); inline void delayMicroseconds(unsigned) {}
void pinMode(uint8_t,uint8_t); void digitalWrite(uint8_t,uint8_t); int digitalRead(uint8_t);
char* dtostrf(double v,int w,int p,char* b);
struct SerialMock {
  std::deque<char> in; std::string out;
  void begin(long){} int available(){return in.size();} int read(){char c=in.front();in.pop_front();return c;}
  void print(const char* s){out+=s;} void print(char c){out+=c;} void print(int v){out+=std::to_string(v);}
  void print(unsigned v){out+=std::to_string(v);} void print(unsigned long v){out+=std::to_string(v);} void print(long v){out+=std::to_string(v);} void print(double v,int d=2){char b[32];snprintf(b,32,"%.*f",d,v);out+=b;}
  void println(){out+="\n";} template<class T> void println(T v){print(v);out+="\n";} void println(double v,int d){print(v,d);out+="\n";}
};
extern SerialMock Serial;
