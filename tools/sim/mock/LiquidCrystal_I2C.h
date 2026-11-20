#pragma once
#include <cstdint>
struct LiquidCrystal_I2C { char scr[2][17]; int cx=0,cy=0; LiquidCrystal_I2C(int,int,int){clear();}
  void init(){} void backlight(){} void clear(){for(auto&r:scr){for(int i=0;i<16;i++)r[i]=' ';r[16]=0;}} void setCursor(int x,int y){cx=x;cy=y;} void write(uint8_t c){if(cx<16)scr[cy][cx++]=(c==223?'o':c);} };
