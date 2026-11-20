# 회로도에 LCD 2개(DS2 0x26, DS3 0x25)를 추가한다. DS1 묶음(심볼, 전원 심볼, 선, 라벨)을 복사해 아래쪽 빈자리에 놓는다.
import sys,re,uuid; sys.path.insert(0,'tools'); from sx import *
P='kicad/coil_heater_pid.kicad_sch'
s=open(P).read(); t=parse(s)
assert '"DS2"' not in s, '이미 추가됨'
num=r'-?\d+(?:\.\d+)?'
def fmt(v): return ('%.4f'%round(v,4)).rstrip('0').rstrip('.')
def shift(txt,dx,dy):
    return re.sub(r'\((at|xy) (%s) (%s)'%(num,num),lambda m:'(%s %s %s'%(m.group(1),fmt(float(m.group(2))+dx),fmt(float(m.group(3))+dy)),txt)
def newuuid(txt): return re.sub(r'\(uuid "[^"]+"\)',lambda m:'(uuid "%s")'%uuid.uuid4(),txt)
def pos(c):
    if c[0]=='wire': return [(float(p[1]),float(p[2])) for p in find(one(c,'pts'),'xy')]
    a=one(c,'at'); return [(float(a[1]),float(a[2]))]
def ref(c): return [p[2] for p in find(c,'property') if p[1]=='"Reference"'][0].strip('"')
T=lambda c: s[c.span[0]:c.span[1]]
group=[c for c in t if isinstance(c,list) and c[0] in('symbol','wire','label') and all(283<=x<=325 and 90<=y<=110 for x,y in pos(c))]
kinds=sorted((c[0],ref(c) if c[0]=='symbol' else c[1] if c[0]=='label' else '') for c in group); print(kinds)
assert [k for k in kinds if k[0]=='symbol']==[('symbol','#PWR13'),('symbol','#PWR14'),('symbol','DS1')] and len(group)==9, len(group)
head=[c for c in t if isinstance(c,list) and c[0]=='text' and c[1]=='"LCD 16x2 (I2C 0x27)"'][0]
new=[]; pw=23
for (dx,dy),ds,val in [((-81.28,137.16),'DS2','LCD 2 (0x26): TC1~TC4 온도'),((-30.48,137.16),'DS3','LCD 3 (0x25): 220V 상태')]:
    for c in group:
        x=newuuid(shift(T(c),dx,dy))
        if c[0]=='symbol':
            r=ref(c); nr=ds if r=='DS1' else '#PWR%d'%pw
            if r!='DS1': pw+=1
            assert x.count('"%s"'%r)==2,(r,x.count('"%s"'%r)); x=x.replace('"%s"'%r,'"%s"'%nr)
            if r=='DS1': assert x.count('"LCD 16x2 + I2C backpack"')==1; x=x.replace('"LCD 16x2 + I2C backpack"','"%s"'%val)
        new.append(x)
def text(st,x,y,size):
    x_=newuuid(T(head)).replace('"LCD 16x2 (I2C 0x27)"','"%s"'%st).replace('(at 266.7 87.63 0)','(at %s %s 0)'%(fmt(x),fmt(y)))
    if size!=2: x_=x_.replace('(size 2 2)','(size %s %s)'%(size,size)).replace('\n\t\t\t\t(bold yes)','')
    return x_
new.append(text('LCD 2, 3 추가 (SDA / SCL은 세 개 모두 A4 / A5에 같이 연결)',187.96,227.33,2))
new.append(text('I2C 주소는 백팩 뒷면 납땜 패드로 정함\\nDS1 0x27: 패드 그대로 · DS2 0x26: A0 패드 이음 · DS3 0x25: A1 패드 이음\\n(PCF8574A 백팩이면 0x3F / 0x3E / 0x3D)\\n코드 v1.2는 DS1(0x27)만 구동. 3화면 표시는 펌웨어 수정 필요',187.96,264.5,1.4))
si=one(t,'sheet_instances').span[0]
out=s[:si]+''.join(x+'\n\t' for x in new)+s[si:]
def rep(a,b):
    global out
    assert out.count(a)==1,(a,out.count(a)); out=out.replace(a,b)
rep('(text "LCD 16x2 (I2C 0x27)"','(text "LCD 1: 제어 화면 (I2C 0x27)"')
rep('"LCD 16x2 + I2C backpack"','"LCD 1 (0x27): 설정·현재 온도·출력"')
rep('(text "I2C 0x27"','(text "I2C"')
rep('(rev "1.1")','(rev "1.2")')
rep('Arduino Nano + 4x MAX31856 (T-type) + SSR + safety relay','Arduino Nano + 4x MAX31856 (T-type) + 3x I2C LCD + SSR + safety relay')
parse(out); open(P,'w').write(out); print('ok', len(new))
