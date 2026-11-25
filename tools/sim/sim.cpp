// band_heater_pid.ino 를 PC에서 그대로 컴파일해 MAX31856 4개 + 히터 열 모델과 함께 돌리는 모의 시험
#include "Arduino.h"
#include <cassert>
#include <vector>
SerialMock Serial; int MCUSR; unsigned long wdtLast=0;
#include "EEPROM.h"
#include "Wire.h"
EEPROMMock EEPROM; WireMock Wire;
static unsigned long clk=0; unsigned long millis(){return clk;}
static void plant(unsigned long ms);
void delay(unsigned long ms){ plant(ms); clk+=ms; }
char* dtostrf(double v,int w,int p,char* b){ sprintf(b,"%*.*f",w,p,v); return b; }
// ---- 핀 상태 ----
static int pinv[20], pinm[20]; static bool btn[20];
static int fails=0, checks=0;
#define CHECK(c,msg) do{checks++; if(!(c)){fails++; printf("  [FAIL] %s  (t=%.1fs)\n",msg,clk/1000.0);} else printf("  [ok]   %s\n",msg);}while(0)
// ---- MAX31856 4개 (CS: D10,D9,D8,D7) ----
struct Chip { int cs; uint8_t reg[16]; double temp; bool open, present; int bit; uint8_t sh_in, addr; bool gotAddr, wr; uint8_t sh_out; } chip[4];
static long violRelay=0, violBus=0, ssrOnWhileRelayOff=0; static unsigned long relayRise=0, ssrFirst=0; static bool waitSsr=false; static long minGap=1<<30;
static int so=1;
static Chip* sel(){ Chip* s=nullptr; int n=0; for(auto&c:chip) if(pinm[c.cs]==OUTPUT && pinv[c.cs]==LOW){s=&c;n++;} if(n>1) violBus++; return s; }
static uint8_t rd(Chip& c,uint8_t a){
  a&=0x0F; bool run=c.reg[0]&0x80;
  if(a>=0x0C&&a<=0x0E){ if(!run||c.open) return (a==0x0C&&c.open)?0x7F:(c.open?0xFF:0); int32_t v=(int32_t)lround(c.temp*128.0)<<5; return (v>>(8*(0x0E - a)))&0xFF; }
  if(a==0x0F) return c.open && (c.reg[0]&0x30) ? 0x01 : 0;
  return c.reg[a];
}
void pinMode(uint8_t p,uint8_t m){ pinm[p]=m; if(m==INPUT_PULLUP) pinv[p]=HIGH; }
void digitalWrite(uint8_t p,uint8_t v){
  int old=pinv[p]; pinv[p]=v;
  if(p==5){ if(v&&!old){relayRise=clk; waitSsr=true;} }
  if(p==6 && v && !old){ if(!pinv[5]) ssrOnWhileRelayOff++; if(waitSsr){ long g=clk-relayRise; if(g<minGap)minGap=g; waitSsr=false; } }
  if(p==5 && !v && old && pinv[6]) violRelay++;          // 릴레이가 SSR보다 먼저 열림
  for(auto&c:chip) if(p==c.cs){ if(!v&&old){c.bit=0;c.gotAddr=false;c.sh_in=0;} }
  if(p==13 && v!=old){ Chip* c=sel(); if(!c||!c->present){so=1;return;}
    if(v){ // 상승: 칩이 출력
      if(c->gotAddr && !c->wr){ if(c->bit%8==0) c->sh_out=rd(*c,c->addr); so=(c->sh_out&0x80)?1:0; c->sh_out<<=1; } else so=1;
    } else { // 하강: 칩이 SDI 샘플
      c->sh_in=(c->sh_in<<1)|(pinv[4]?1:0); c->bit++;
      if(c->bit%8==0){ if(!c->gotAddr){c->gotAddr=true;c->wr=c->sh_in&0x80;c->addr=c->sh_in&0x7F;} else { if(c->wr) c->reg[c->addr&0x0F]=c->sh_in; c->addr++; } c->sh_in=0; }
    } }
}
int digitalRead(uint8_t p){ if(p==12) return so; if(p>=A0&&p<=A3) return btn[p]?LOW:HIGH; return pinv[p]; }
// ---- 히터 열 모델: 400W 밴드히터 + 금속 블록 (2차 지연) ----
static double Th=25, Tb=25; static double ofs[4]={0,-6,+4,-10}; static bool forceT=false; static long heatMs=0;
static void plant(unsigned long ms){
  for(unsigned long i=0;i<ms;i++){ bool on=pinv[6]&&pinv[5]; if(on) heatMs++;
    double dt=0.001; Th+=dt*((on?400.0:0)/60.0 - (Th-Tb)/8.0); Tb+=dt*((Th-Tb)/20.0 - (Tb-25)/400.0); }
  if(!forceT) for(int i=0;i<4;i++) chip[i].temp=Tb+ofs[i];
}
#include "band_heater_pid.ino"
static void run(unsigned long ms){ for(unsigned long i=0;i<ms;i++){ loop(); plant(1); clk++; assert(clk-wdtLast<2000); } }
static void cmd(const char* s){ for(;*s;s++) Serial.in.push_back(*s); Serial.in.push_back('\n'); run(50); }
static void show(const char* tag){ printf("  %-16s mode=%d fault=%d PV=%.1f out=%.0f%% T=[%.1f %.1f %.1f %.1f] ok=[%d%d%d%d] relay=%d ssr=%d | LCD \"%s\" / \"%s\"\n",tag,mode,fault,pv,output,tcTemp[0],tcTemp[1],tcTemp[2],tcTemp[3],tcOk[0],tcOk[1],tcOk[2],tcOk[3],pinv[5],pinv[6],lcd.scr[0],lcd.scr[1]); }
// ---- LCD 3개가 모두 달린 경우 ----
static int three(){
  printf("A) 부팅: LCD 3개 응답\n"); setup(); run(2000); show("boot");
  CHECK(lcdHere[0]&&lcdHere[1]&&lcdHere[2],"LCD 3개 모두 인식");
  printf("         LCD1 \"%s\" / \"%s\"\n         LCD2 \"%s\" / \"%s\"\n         LCD3 \"%s\" / \"%s\"\n",lcd.scr[0],lcd.scr[1],lcd2.scr[0],lcd2.scr[1],lcd3.scr[0],lcd3.scr[1]);
  CHECK(!strncmp(lcd.scr[0],"SP",2)&&strstr(lcd.scr[0]," PV")&&!strncmp(lcd.scr[1],"STOP OUT  0% TC1",16),"LCD1: SP/PV 와 STOP, 출력 0%, 제어 기준 TC1");
  { char e1[17],e2[17]; snprintf(e1,17,"1>%5.1f 2:%5.1f ",tcTemp[0],tcTemp[1]); snprintf(e2,17,"3:%5.1f 4:%5.1f ",tcTemp[2],tcTemp[3]);
    CHECK(!strcmp(lcd2.scr[0],e1)&&!strcmp(lcd2.scr[1],e2),"LCD2: 네 채널 온도가 0.1도 단위로, 제어 기준에 '>' 표시"); }
  CHECK(!strncmp(lcd3.scr[0],"R:OFF S:OFF   0%",16),"LCD3: 릴레이 OFF, SSR OFF, 0%");
  printf("B) 운전 (목표 100도, 30분)\n"); cmd("sp 100"); cmd("run"); run(1000);
  for(int k=0;k<1800;k++) run(1000); show("run");
  printf("         LCD1 \"%s\" / \"%s\"\n         LCD2 \"%s\" / \"%s\"\n         LCD3 \"%s\" / \"%s\"\n",lcd.scr[0],lcd.scr[1],lcd2.scr[0],lcd2.scr[1],lcd3.scr[0],lcd3.scr[1]);
  CHECK(mode==M_RUN&&fabs(pv-100)<3.0,"30분 운전 뒤 PV가 목표의 ±3도 안");
  CHECK(!strncmp(lcd.scr[0],"SP100.0 PV",10)&&!strncmp(lcd.scr[1],"RUN  OUT",8)&&!strcmp(lcd.scr[1]+12," TC1"),"LCD1: SP100.0, RUN, 출력 %, TC1");
  CHECK(!strncmp(lcd3.scr[0],"R:ON ",5)&&strlen(lcd3.scr[1])==16&&strstr(lcd3.scr[1],"00:30"),"LCD3: 릴레이 ON, 운전시간 00:30");
  for(int n=0;n<3;n++){ auto&L=n==0?lcd:n==1?lcd2:lcd3; CHECK(strlen(L.scr[0])==16&&strlen(L.scr[1])==16,n==0?"LCD1 두 줄 모두 16자":n==1?"LCD2 두 줄 모두 16자":"LCD3 두 줄 모두 16자"); }
  printf("C) 버튼\n"); btn[A2]=true; run(100); btn[A2]=false; run(400);
  CHECK(page==0&&!strncmp(lcd.scr[0],"SP",2),"LCD3이 있으면 DOWN 을 눌러도 LCD1 화면이 안 바뀜");
  btn[A1]=true; run(100); btn[A1]=false; run(300); CHECK(menu==MI_SP&&!strncmp(lcd2.scr[0],"1>",2)&&!strncmp(lcd3.scr[0],"R:ON",4),"UP 으로 메뉴에 들어가도 LCD2·LCD3 은 계속 표시");
  for(int i=0;i<MI_COUNT;i++){btn[A0]=true; run(100); btn[A0]=false; run(100);} CHECK(menu<0,"SET 으로 메뉴에서 나옴");
  printf("D) 제어 기준 바꾸기, 단선\n"); cmd("src 4"); run(600);
  CHECK(lcd2.scr[1][9]=='>'&&lcd2.scr[0][1]==':'&&!strcmp(lcd.scr[1]+12," TC4"),"src 4: LCD2 의 '>' 가 4번으로, LCD1 끝이 TC4");
  chip[2].open=true; run(3000); CHECK(mode==M_RUN&&!strncmp(lcd2.scr[1],"3: --.-",7),"TC3 단선: LCD2 에 --.- 표시, 운전은 계속"); chip[2].open=false; run(2000);
  chip[3].open=true; run(3000); bool sawFault=false, sawStat=false; for(int k=0;k<40;k++){ run(100); if(strstr(lcd.scr[1],"SENSOR")) sawFault=true; if(!strncmp(lcd.scr[1],"ERR!",4)) sawStat=true; }
  printf("         LCD1 \"%s\" / \"%s\"\n",lcd.scr[0],lcd.scr[1]);
  CHECK(mode==M_FAULT&&!pinv[5]&&!pinv[6]&&sawFault&&sawStat,"TC4(제어 기준) 단선: 차단, LCD1 둘째 줄이 ERR! 와 고장 내용을 번갈아 표시");
  CHECK(!strncmp(lcd3.scr[0],"R:OFF S:OFF",11),"LCD3: 차단 뒤 릴레이 OFF, SSR OFF");
  CHECK(violBus==0&&ssrOnWhileRelayOff==0&&violRelay==0,"SPI 충돌 없음, 릴레이·SSR 순서 위반 없음");
  printf("\n결과: %d개 중 %d개 통과, %d개 실패\n",checks,checks-fails,fails); return fails?1:0;
}
// ---- 가상 보드: 펌웨어를 그대로 돌리면서 표준입력을 시리얼 입력으로, 시리얼 출력을 표준출력으로 잇는다 ----
//   사용: sim_bin board [배속]   (heater_log.py --sim 이 이 방식으로 실행함)
#ifdef _WIN32
// 윈도우: 표준입력(파이프)에 와 있는 만큼만 읽는다. windows.h 는 Arduino.h 의 INPUT, boolean 과 이름이 겹쳐서
// 쓰는 함수 다섯 개만 직접 선언한다.
#include <chrono>
struct _OVERLAPPED;
extern "C" {
  __declspec(dllimport) void* __stdcall GetStdHandle(unsigned long);
  __declspec(dllimport) unsigned long __stdcall GetFileType(void*);
  __declspec(dllimport) int __stdcall PeekNamedPipe(void*,void*,unsigned long,unsigned long*,unsigned long*,unsigned long*);
  __declspec(dllimport) int __stdcall ReadFile(void*,void*,unsigned long,unsigned long*,struct _OVERLAPPED*);
  __declspec(dllimport) void __stdcall Sleep(unsigned long);
}
static int board(double speed){
  if(speed<=0) speed=1;
  void* in=GetStdHandle((unsigned long)-10);             // STD_INPUT_HANDLE
  bool piped=GetFileType(in)==3;                         // FILE_TYPE_PIPE. 콘솔에서 직접 켜면 입력 없이 돈다
  setup();
  auto t0=std::chrono::steady_clock::now(); double simMs=0;
  for(;;){
    if(piped){
      unsigned long avail=0,n=0; char buf[256];
      if(!PeekNamedPipe(in,0,0,0,&avail,0)) return 0;    // 입력이 닫히면(기록 프로그램 종료) 끝냄
      while(avail>0){
        if(!ReadFile(in,buf,avail<sizeof buf?avail:(unsigned long)sizeof buf,&n,0)||n==0) return 0;
        for(unsigned long i=0;i<n;i++) Serial.in.push_back(buf[i]);
        avail-=n;
      }
    }
    run(100); simMs+=100;
    if(!Serial.out.empty()){ fputs(Serial.out.c_str(),stdout); fflush(stdout); Serial.out.clear(); }
    // Sleep 은 15 ms 단위로 길어질 수 있어서, 정해진 만큼 쉬지 않고 실제 시간보다 앞선 만큼만 쉰다
    double ahead=simMs/speed-std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t0).count();
    if(ahead>=1) Sleep((unsigned long)ahead);
    else if(ahead<-1000){ t0=std::chrono::steady_clock::now(); simMs=0; }   // 크게 밀렸으면 몰아서 따라잡지 않고 다시 맞춤
  }
}
#else
#include <unistd.h>
#include <fcntl.h>
static int board(double speed){
  if(speed<=0) speed=1;
  fcntl(0,F_SETFL,fcntl(0,F_GETFL)|O_NONBLOCK);
  setup();
  for(;;){
    char buf[256]; ssize_t n;
    while((n=read(0,buf,sizeof buf))>0) for(ssize_t i=0;i<n;i++) Serial.in.push_back(buf[i]);
    if(n==0) return 0;                                   // 입력이 닫히면(기록 프로그램 종료) 끝냄
    run(100);
    if(!Serial.out.empty()){ fputs(Serial.out.c_str(),stdout); fflush(stdout); Serial.out.clear(); }
    usleep((useconds_t)(100000.0/speed));
  }
}
#endif
int main(int argc,char** argv){
  int csp[4]={10,9,8,7}; for(int i=0;i<4;i++){ chip[i]=Chip(); chip[i].cs=csp[i]; chip[i].present=true; chip[i].temp=25+ofs[i]; }
  if(argc>1 && !strcmp(argv[1],"board")){ Wire.present[LCD2_I2C_ADDR]=Wire.present[LCD3_I2C_ADDR]=true; return board(argc>2?atof(argv[2]):1.0); }
  bool all=argc>1; Wire.present[LCD2_I2C_ADDR]=Wire.present[LCD3_I2C_ADDR]=all;   // 인자가 있으면 LCD 3개, 없으면 LCD 1 하나만
  if(all) return three();
  printf("1) 부팅 (LCD 1 하나만 응답)\n"); setup(); run(2000); show("boot");
  CHECK(lcdHere[0]&&!lcdHere[1]&&!lcdHere[2],"LCD1 만 인식, LCD2·LCD3 은 없는 것으로 처리");
  CHECK(NUM_TC==4,"NUM_TC = 4");
  bool map=true; for(int i=0;i<4;i++) map&=fabs(tcTemp[i]-(Tb+ofs[i]))<0.3 && tcOk[i];
  CHECK(map,"4채널이 CS 핀(D10,D9,D8,D7) 순서대로 각자 온도를 읽음");
  bool cfgok=true; for(auto&c:chip) cfgok&=(c.reg[0]==0x90&&c.reg[1]==7); CHECK(cfgok,"칩 4개 모두 CR0=0x90(연속 변환, 단선 감지, 60Hz), CR1=7(T형)로 설정됨");
  CHECK(mode==M_STOP&&!pinv[5]&&!pinv[6],"정지 상태: 릴레이 OFF, SSR OFF");
  printf("1-1) 저장하지 않는 목표 변경 (spt)\n");
  { long n0=EEPROM.puts; cmd("spt 120"); CHECK(fabs(cfg.sp-120)<1e-6&&EEPROM.puts==n0,"spt 120: 목표는 120으로 바뀌고 EEPROM에는 쓰지 않음");
    cmd("spt 999"); CHECK(fabs(cfg.sp-SP_MAX)<1e-6&&EEPROM.puts==n0,"spt 999: 상한(SP_MAX)으로 잘림, 여전히 쓰지 않음");
    cmd("sp 130"); CHECK(fabs(cfg.sp-130)<1e-6&&EEPROM.puts==n0+1,"sp 130: 저장함 (쓰기 1회)"); }
  printf("2) 운전 (목표 100도, 30분)\n"); cmd("sp 100"); cmd("run"); run(1000);
  CHECK(mode==M_RUN&&pinv[5],"run 명령 후 릴레이 ON");
  double mx=0; for(int k=0;k<1800;k++){ run(1000); if(pv>mx)mx=pv; if(k%300==299) show("run"); }
  CHECK(minGap>=200&&minGap<5000,"릴레이 ON 뒤 200ms 이상 지나서 SSR 첫 ON"); printf("         (측정된 간격 %ld ms)\n",minGap);
  CHECK(mode==M_RUN,"30분 동안 고장 없이 운전 유지");
  CHECK(fabs(pv-100)<3.0,"30분 뒤 PV가 목표 100도의 ±3도 안"); printf("         (최종 %.1f도, 최고 %.1f도; 임의로 정한 열 모델 기준)\n",pv,mx);
  printf("2-1) 220V 상태 화면 (메인화면에서 DOWN)\n");
  btn[A2]=true; run(100); btn[A2]=false; run(400); show("AC page");
  CHECK(page==1&&!strncmp(lcd.scr[0],"R:ON ",5),"DOWN 한 번에 220V 상태 화면으로 전환, 릴레이 ON 표시");
  { double trueWh=heatMs/3600000.0*400.0; double e=energyWh(); printf("         (추정 %.1f Wh, 열 모델이 실제로 받은 %.1f Wh, 운전시간 %lu분)\n",e,trueWh,runMs/60000UL);
    CHECK(fabs(e-trueWh)<trueWh*0.02+0.5,"누적 전력량 추정이 실제 히터 ON 시간과 2% 안에서 일치");
    CHECK(runMs/60000UL==30,"운전시간 30분 표시"); CHECK(strlen(lcd.scr[1])==16&&strstr(lcd.scr[1],"00:30"),"둘째 줄 16자 안에 W, Wh, 시간 표시"); }
  btn[A2]=true; run(100); btn[A2]=false; run(400); CHECK(page==0&&lcd.scr[0][0]=='P',"DOWN 한 번 더 누르면 온도 화면으로 복귀");
  btn[A1]=true; run(100); btn[A1]=false; run(100); CHECK(menu==MI_SP,"UP 은 그대로 목표온도 설정으로 이동"); for(int i=0;i<MI_COUNT;i++){btn[A0]=true; run(100); btn[A0]=false; run(100);} CHECK(menu<0&&fabs(cfg.sp-100)<0.01,"SET 으로 메뉴를 빠져나오고 목표온도는 그대로");
  printf("3) 표시용 열전대(TC3) 단선: 제어는 계속\n"); chip[2].open=true; run(3000); show("TC3 open");
  CHECK(mode==M_RUN&&!tcOk[2],"TC3은 고장 표시, 운전은 계속 (제어 기준은 TC1)"); chip[2].open=false; run(2000); CHECK(tcOk[2],"TC3 복구 후 다시 읽힘");
  printf("4) 정지\n"); cmd("stop"); run(100); CHECK(mode==M_STOP&&!pinv[5]&&!pinv[6],"stop 후 릴레이 OFF, SSR OFF");
  printf("5) RUN 버튼 1초 길게 → 운전, 짧게 → 정지\n"); btn[A3]=true; run(1200); btn[A3]=false; run(300); CHECK(mode==M_RUN&&pinv[5],"RUN 길게 누르면 운전 + 릴레이 ON");
  btn[A3]=true; run(100); btn[A3]=false; run(100); CHECK(mode==M_STOP&&!pinv[5],"RUN 짧게 누르면 정지 + 릴레이 OFF");
  printf("6) 제어 기준 열전대(TC1) 단선 → 센서 고장\n"); cmd("run"); run(2000); chip[0].open=true; run(3000); show("TC1 open");
  CHECK(mode==M_FAULT&&fault==F_SENSOR&&!pinv[5]&&!pinv[6],"SENSOR FAULT, 릴레이 OFF, SSR OFF"); chip[0].open=false; run(2000); cmd("clear"); CHECK(mode==M_STOP,"clear 로 알람 해제");
  printf("7) 모듈 빠짐(TC2 응답 없음, SO 전부 1)\n"); chip[1].present=false; run(2000); CHECK(!tcOk[1],"응답 없는 모듈은 고장 처리"); chip[1].present=true; chip[1].reg[0]=0; chip[1].reg[1]=0; run(2000); CHECK(tcOk[1]&&chip[1].reg[0]==0x90,"모듈이 리셋돼 설정을 잃어도 자동 재설정 후 복구");
  printf("8) 정지 중 표시용 열전대(TC4) 과열 → 차단\n"); forceT=true; chip[3].temp=360; run(4000); show("TC4 360C");
  CHECK(mode==M_FAULT&&fault==F_OVERTEMP&&!pinv[5],"OVER TEMP, 릴레이 OFF"); cmd("run"); CHECK(mode==M_FAULT,"알람 중에는 run 거부"); cmd("clear"); CHECK(mode==M_FAULT,"아직 뜨거우면 clear 거부");
  chip[3].temp=100; forceT=false; run(8000); cmd("clear"); CHECK(mode==M_STOP,"식은 뒤 clear 로 해제");
  printf("9) 전체 구간 불변 조건\n");
  CHECK(violBus==0,"CS가 동시에 두 개 LOW가 된 적 없음 (SPI 버스 충돌 없음)");
  CHECK(ssrOnWhileRelayOff==0,"릴레이가 꺼진 상태에서 SSR이 켜진 적 없음");
  CHECK(violRelay==0,"SSR이 켜진 채 릴레이가 열린 적 없음 (항상 SSR 먼저 OFF)");
  printf("\n결과: %d개 중 %d개 통과, %d개 실패\n",checks,checks-fails,fails); return fails?1:0;
}
