#pragma once
#include <cstring>
struct EEPROMMock { unsigned char d[1024]; long puts=0; EEPROMMock(){memset(d,0xFF,sizeof d);}
  template<class T> T& get(int a,T& t){memcpy(&t,d+a,sizeof t);return t;} template<class T> void put(int a,const T& t){memcpy(d+a,&t,sizeof t);puts++;} };
extern EEPROMMock EEPROM;
