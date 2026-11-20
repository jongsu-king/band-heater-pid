#pragma once
#define WDTO_2S 7
extern int MCUSR; extern unsigned long wdtLast; unsigned long millis();
inline void wdt_disable(){} inline void wdt_enable(int){wdtLast=millis();} inline void wdt_reset(){wdtLast=millis();}
