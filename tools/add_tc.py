import sys,re,uuid; sys.path.insert(0,'tools'); from sx import *
P='kicad/coil_heater_pid.kicad_sch'
s=open(P).read(); t=parse(s)
num=r'-?\d+(?:\.\d+)?'
def fmt(v):
    v=round(v,4); r=('%.4f'%v).rstrip('0').rstrip('.'); return r
def shift(txt,dx,dy):
    def f(m): return '(%s %s %s'%(m.group(1),fmt(float(m.group(2))+dx),fmt(float(m.group(3))+dy))
    return re.sub(r'\((at|xy) (%s) (%s)'%(num,num),f,txt)
def newuuid(txt): return re.sub(r'\(uuid "[^"]+"\)',lambda m:'(uuid "%s")'%uuid.uuid4(),txt)
def pos(c):
    if c[0]=='wire': return [(float(p[1]),float(p[2])) for p in find(one(c,'pts'),'xy')]
    a=one(c,'at'); return [(float(a[1]),float(a[2]))]
def ref(c): return [p[2] for p in find(c,'property') if p[1]=='"Reference"'][0].strip('"')
inbox=lambda c: all(283<=x<=330 and 54<=y<=70 for x,y in pos(c))
group=[];remove=[]
for c in t:
    if not isinstance(c,list): continue
    k=c[0]
    if k in('symbol','wire','label') and inbox(c): group.append(c); remove.append(c)
    elif k=='text' and (c[1].startswith('"T형:') or c[1].startswith('"D9 / D8')): remove.append(c)
    elif k=='no_connect' and pos(c)[0][0]==203.2 and pos(c)[0][1] in(142.24,144.78,147.32): remove.append(c)
print('group',[(c[0],ref(c) if c[0]=='symbol' else c[1] if c[0]=='label' else '') for c in group])
assert len([c for c in group if c[0]=='symbol'])==4 and len([c for c in group if c[0]=='wire'])==8, len(group)
# template for nano label+wire
cs1w=[c for c in t if isinstance(c,list) and c[0]=='wire' and pos(c)==[(203.2,149.86),(193.04,149.86)]]
cs1l=[c for c in t if isinstance(c,list) and c[0]=='label' and c[1]=='"TC_CS1"' and pos(c)[0]==(193.04,149.86)]
assert len(cs1w)==1 and len(cs1l)==1
T=lambda c: s[c.span[0]:c.span[1]]
new=[]
# (dx,dy), U ref, TC ref, n
cells=[((-88.9,-27.94),'U2',1),((0,-27.94),'U4',2),((-88.9,5.08),'U5',3),((0,5.08),'U6',4)]
pw=17
for (dx,dy),u,n in cells:
    for c in group:
        x=shift(T(c),dx,dy); x=newuuid(x)
        if c[0]=='symbol':
            r=ref(c)
            if r=='U2': nr=u
            elif r=='TC1': nr='TC%d'%n; x=x.replace('T-type TC (Ø2.3x100, SUS316)','T-type TC Ø2.3x100')
            else:
                if n==1: nr=r
                else: nr='#PWR%d'%pw; pw+=1
            assert x.count('"%s"'%r)==2,(r,x.count('"%s"'%r))
            x=x.replace('"%s"'%r,'"%s"'%nr)
        elif c[0]=='label': x=x.replace('"TC_CS1"','"TC_CS%d"'%n)
        new.append(x)
for n,y in((2,147.32),(3,144.78),(4,142.24)):
    dy=y-149.86
    new.append(newuuid(shift(T(cs1w[0]),0,dy)))
    new.append(newuuid(shift(T(cs1l[0]),0,dy)).replace('"TC_CS1"','"TC_CS%d"'%n))
# apply: delete removed spans (from back), insert new before sheet_instances
si=one(t,'sheet_instances').span[0]
out=s[:si]+''.join(x+'\n\t' for x in new)+s[si:]
for c in sorted(remove,key=lambda c:-c.span[0]):
    a,b=c.span
    while out[a-1] in ' \t': a-=1
    if out[a-1]=='\n': a-=1
    out=out[:a]+out[b:]
def rep(a,b):
    global out
    assert out.count(a)==1,(a,out.count(a)); out=out.replace(a,b)
rep('"온도 측정: T형 열전대 + MAX31856"','"온도 측정: T형 열전대 4개 + MAX31856 4개 (SCK / SDO / SDI 공유, CS 개별: D10 / D9 / D8 / D7)"')
rep('U2: MAX31856 5V 호환 모듈 (예: Adafruit 3263), 코드 TC_CHIP 31856 / TC_TYPE 7 (T형)','U2/U4/U5/U6: MAX31856 5V 호환 모듈 4개 (예: Adafruit 3263), 코드 NUM_TC 4 / TC_CHIP 31856 / TC_TYPE 7 (T형)\\nTC1~TC4: T형 Ø2.3x100 SUS316, + 선 속심이 구리색. 열전대 선은 220V 배선과 떨어뜨려 배선')
rep('Arduino Nano + MAX31856 (T-type)','Arduino Nano + 4x MAX31856 (T-type)')
rep('(rev "1.0")','(rev "1.1")'); rep('(date "2026-10-30")','(date "2026-11-19")')
# move heading
m=re.search(r'\(text "온도 측정[^\n]*\n(?:[^\n]*\n){0,3}?\s*\(at 266\.7 43\.18 0\)',out); assert m
out=out[:m.start()]+m.group(0).replace('(at 266.7 43.18 0)','(at 177.8 17.78 0)')+out[m.end():]
parse(out)
open(P,'w').write(out)
