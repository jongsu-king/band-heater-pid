# /// script
# dependencies = ["matplotlib"]
# ///
import sys,math; sys.path.insert(0,'tools'); from sx import *
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Circle,Polygon,Arc
from matplotlib import font_manager as fm
src,dst=sys.argv[1],sys.argv[2]
VIEW='--view' in sys.argv   # 보기용: 여백 잘라내기, 구역 상자, 굵은 선, 큰 글자
fp=fm.FontProperties(fname='/System/Library/Fonts/AppleSDGothicNeo.ttc')
s=open(src).read(); t=parse(s)
f=float; q=lambda x:x.strip('"').replace('\\n','\n').replace('\\"','"')
W,H=420,297
X0,Y0,X1,Y1=(10,8,360,272) if VIEW else (0,0,W,H)
FS=1.5 if VIEW else 1.25; LW=1.5 if VIEW else 1.0
fig=plt.figure(figsize=((X1-X0)/25.4,(Y1-Y0)/25.4)); ax=fig.add_axes([0,0,1,1]); ax.set_xlim(X0,X1); ax.set_ylim(Y1,Y0); ax.axis('off')
fig.patch.set_facecolor('#ffffff' if VIEW else '#f5f4ef')
GRN='#008a00'; RED='#8b1a1a'; BLU='#0d0dc0'; TEAL='#006e6e'
PT=72/25.4
def text(x,y,sx,size=1.27,color=TEAL,ha='left',va='bottom',rot=0):
    ax.text(x,y,sx,fontsize=size*PT*FS,color=color,ha=ha,va=va,rotation=rot,fontproperties=fp,rotation_mode='anchor',linespacing=1.3)
def just(e,dh='center',dv='center'):
    j=one(e,'justify') if e else None
    h,v=dh,dv
    if j:
        for a in j[1:]:
            if a in('left','right'): h=a
            if a in('top','bottom'): v=a
    return h,v
def size(e):
    try: return f(one(one(e,'font'),'size')[1])
    except Exception: return 1.27
def hidden(c):
    h=one(c,'hide'); 
    if h and h[1]=='yes': return True
    e=one(c,'effects'); h=one(e,'hide') if e else None
    return bool(h and h[1]=='yes')
libs={c[1]:c for c in find(one(t,'lib_symbols'),'symbol')}
def tf(a,mir):
    m={0:(1,0,0,-1),90:(0,-1,-1,0),180:(-1,0,0,1),270:(0,1,1,0)}[a]
    def g(x,y):
        X=m[0]*x+m[1]*y; Y=m[2]*x+m[3]*y
        if 'y' in mir: X=-X
        if 'x' in mir: Y=-Y
        return X,Y
    return g
pins=[]
for c in find(t,'symbol'):
    lib=libs[one(c,'lib_id')[1]]; at=one(c,'at'); ox,oy,a=f(at[1]),f(at[2]),int(f(at[3]))
    mir=[m[1] for m in find(c,'mirror')]; g=tf(a,mir); P=lambda x,y:(ox+g(x,y)[0],oy+g(x,y)[1])
    unit=one(c,'unit')[1]
    pn=one(lib,'pin_names'); pnum=one(lib,'pin_numbers')
    hide_names=bool(pn and hidden(pn)); hide_nums=bool(pnum and hidden(pnum))
    off=f(one(pn,'offset')[1]) if pn and one(pn,'offset') else 0.508
    power=bool(one(lib,'power'))
    for sub in find(lib,'symbol'):
        u=sub[1].strip('"').split('_')[-2]
        if u not in('0',unit): continue
        for d in sub[2:]:
            k=d[0]
            fill=one(d,'fill'); ft=one(fill,'type')[1] if fill else 'none'
            fc={'background':'#ffffc2','outline':RED}.get(ft,'none')
            if k=='rectangle':
                p1=P(f(one(d,'start')[1]),f(one(d,'start')[2])); p2=P(f(one(d,'end')[1]),f(one(d,'end')[2]))
                ax.add_patch(Rectangle((min(p1[0],p2[0]),min(p1[1],p2[1])),abs(p1[0]-p2[0]),abs(p1[1]-p2[1]),ec=RED,fc=fc,lw=0.9*LW,zorder=2))
            elif k=='polyline':
                pts=[P(f(p[1]),f(p[2])) for p in find(one(d,'pts'),'xy')]
                if fc!='none' and len(pts)>2: ax.add_patch(Polygon(pts,closed=True,ec=RED,fc=fc,lw=0.7,zorder=2))
                else: ax.plot(*zip(*pts),color=RED,lw=0.7,zorder=3)
            elif k=='circle':
                ce=one(d,'center'); ax.add_patch(Circle(P(f(ce[1]),f(ce[2])),f(one(d,'radius')[1]),ec=RED,fc=fc,lw=0.7,zorder=3))
            elif k=='arc':
                pts=[P(f(one(d,n)[1]),f(one(d,n)[2])) for n in('start','mid','end')]
                (x1,y1),(x2,y2),(x3,y3)=pts
                D=2*(x1*(y2-y3)+x2*(y3-y1)+x3*(y1-y2))
                if abs(D)<1e-9: ax.plot(*zip(*pts),color=RED,lw=0.7); continue
                ux=((x1*x1+y1*y1)*(y2-y3)+(x2*x2+y2*y2)*(y3-y1)+(x3*x3+y3*y3)*(y1-y2))/D
                uy=((x1*x1+y1*y1)*(x3-x2)+(x2*x2+y2*y2)*(x1-x3)+(x3*x3+y3*y3)*(x2-x1))/D
                r=math.hypot(x1-ux,y1-uy); an=[math.atan2(y-uy,x-ux) for x,y in pts]
                a0,a1,a2=an
                def between(a,b,m,ccw):
                    tw=2*math.pi; d=((b-a)%tw) if ccw else ((a-b)%tw); dm=((m-a)%tw) if ccw else ((a-m)%tw); return dm<=d
                ccw=between(a0,a2,a1,True)
                tw=2*math.pi; sp=((a2-a0)%tw) if ccw else -((a0-a2)%tw)
                th=[a0+sp*i/24 for i in range(25)]
                ax.plot([ux+r*math.cos(x) for x in th],[uy+r*math.sin(x) for x in th],color=RED,lw=0.7,zorder=3)
            elif k=='text':
                a_=one(d,'at'); x,y=P(f(a_[1]),f(a_[2])); text(x,y,q(d[1]),size(one(d,'effects')),RED,'center','center')
            elif k=='pin':
                if hidden(d): 
                    a_=one(d,'at'); pins.append(P(f(a_[1]),f(a_[2]))); continue
                a_=one(d,'at'); px,py,pa=f(a_[1]),f(a_[2]),int(f(a_[3])); L=f(one(d,'length')[1])
                ex,ey=px+L*math.cos(math.radians(pa)),py+L*math.sin(math.radians(pa))
                p0=P(px,py); p1=P(ex,ey); pins.append(p0)
                ax.plot([p0[0],p1[0]],[p0[1],p1[1]],color=RED,lw=0.7,zorder=3)
                dx,dy=p1[0]-p0[0],p1[1]-p0[1]; n=math.hypot(dx,dy) or 1; dx/=n; dy/=n
                if L==0: dx=dy=0
                name=q(one(d,'name')[1]); number=q(one(d,'number')[1])
                horiz=abs(dx)>=abs(dy)
                if name and name!='~' and not hide_names and not power:
                    if off>0:
                        x,y=p1[0]+dx*off,p1[1]+dy*off
                        if horiz: text(x,y,name,1.27,TEAL,'left' if dx>0 else 'right','center')
                        else: text(x,y,name,1.27,TEAL,'right' if dy>0 else 'left','center',90)
                    else:
                        mx,my=(p0[0]+p1[0])/2,(p0[1]+p1[1])/2
                        if horiz: text(mx,my-0.4,name,1.0,TEAL,'center','bottom')
                        else: text(mx-0.4,my,name,1.0,TEAL,'center','bottom',90)
                if number and not hide_nums and not power and L>0:
                    mx,my=(p0[0]+p1[0])/2,(p0[1]+p1[1])/2
                    if horiz: text(mx,my-0.3,number,1.0,RED,'center','bottom')
                    else: text(mx-0.3,my,number,1.0,RED,'center','bottom',90)
    for p in find(c,'property'):
        if hidden(p) or not q(p[2]): continue
        if p[1] in('"Reference"','"Value"'):
            if p[1]=='"Reference"' and q(p[2]).startswith('#'): continue
            a_=one(p,'at'); e=one(p,'effects'); h,v=just(e)
            rot=(int(f(a_[3]))+a)%180
            if 'y' in mir and rot==0: h={'left':'right','right':'left'}.get(h,h)
            if a in (180,270) and not mir: h={'left':'right','right':'left'}.get(h,h)   # KiCad는 뒤집힌 심볼의 글자를 읽는 방향으로 돌리며 정렬도 뒤집음
            text(f(a_[1]),f(a_[2]),q(p[2]),size(e),TEAL,h,v,rot)
ends=[]
for c in find(t,'wire'):
    pts=[(f(p[1]),f(p[2])) for p in find(one(c,'pts'),'xy')]; ends+=pts
    ax.plot(*zip(*pts),color=GRN,lw=0.8*LW,zorder=4)
for c in find(t,'junction'):
    a_=one(c,'at'); ax.add_patch(Circle((f(a_[1]),f(a_[2])),0.45,fc=GRN,ec=GRN,zorder=5))
ncs=[]
for c in find(t,'no_connect'):
    a_=one(c,'at'); x,y=f(a_[1]),f(a_[2]); ncs.append((x,y)); d=0.6
    ax.plot([x-d,x+d],[y-d,y+d],color=BLU,lw=0.7); ax.plot([x-d,x+d],[y+d,y-d],color=BLU,lw=0.7)
labs=[]
for c in find(t,'label'):
    a_=one(c,'at'); x,y,r=f(a_[1]),f(a_[2]),int(f(a_[3])); labs.append((x,y,q(c[1])))
    text(x+(-0.4 if r==180 else 0.4),y-0.3,q(c[1]),1.27,'#2a2a2a','right' if r==180 else 'left','bottom')
for c in find(t,'text'):
    a_=one(c,'at'); e=one(c,'effects'); h,v=just(e,'left','bottom'); text(f(a_[1]),f(a_[2]),q(c[1]),size(e),BLU,h,v)
# frame + title block
tb=one(t,'title_block')
if VIEW:
    from matplotlib.patches import FancyBboxPatch
    for (x0,y0,x1,y1),col in [((14,12,151,234),'#fbe9e7'),((176,12,356,83.2),'#e8f1fb'),((176,95,260,187),'#eef7e9'),
                              ((263,83.2,356,113.5),'#fff6dc'),((263,113.5,356,166.8),'#f3ecfa'),((263,166.8,356,187),'#fdeaf1'),((150,190,260,219),'#f0f0ee'),((181,221,300,269),'#fff6dc')]:
        ax.add_patch(Rectangle((x0+0.6,y0+0.6),x1-x0-1.2,y1-y0-1.2,fc='none',ec='#777',lw=0.6,ls=(0,(5,4)),zorder=0))
    bx,by=263,190
else:
    ax.add_patch(Rectangle((10,10),W-20,H-20,ec=RED,fc='none',lw=0.8)); ax.add_patch(Rectangle((12,12),W-24,H-24,ec=RED,fc='none',lw=0.5))
    bx,by=W-12-108,H-12-32
ax.add_patch(Rectangle((bx,by),93 if VIEW else 108,29 if VIEW else 32,ec=RED,fc='#ffffff',lw=0.6,zorder=6))
cm={c[1]:q(c[2]) for c in find(tb,'comment')}
for i,(sz,line) in enumerate([(1.3,cm.get('2','')),(1.3,cm.get('1','')),(2.0,'Title: '+q(one(tb,'title')[1])),(1.3,'Date: %s    Rev: %s'%(q(one(tb,'date')[1]),q(one(tb,'rev')[1])))]):
    ax.text(bx+2,by+[4,8.5,17,25][i],line,fontsize=sz*PT*1.2,color=RED,va='center',fontproperties=fp,zorder=7,weight='bold' if sz>1.5 else 'normal')
fig.savefig(dst,dpi=200 if dst.endswith('png') else None,facecolor=fig.get_facecolor())
# connectivity check
R=lambda p:(round(p[0],2),round(p[1],2))
E={R(p) for p in ends}|{R(p) for p in ncs}
from collections import Counter
pc=Counter(R(p) for p in pins)
bad=[p for p in pc if p not in E and pc[p]<2]
print('pins',len(pins),'unconnected pin ends:',bad)
pe={R(p) for p in pins}
segs=[[(f(p[1]),f(p[2])) for p in find(one(c,'pts'),'xy')] for c in find(t,'wire')]
def onseg(p):
    n=0
    for a,b in segs:
        if abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))<1e-6 and min(a[0],b[0])-1e-6<=p[0]<=max(a[0],b[0])+1e-6 and min(a[1],b[1])-1e-6<=p[1]<=max(a[1],b[1])+1e-6: n+=1
    return n
ec=Counter(R(p) for p in ends)
print('dangling wire ends:',[p for p in ec if p not in pe and onseg(p)<2 and p not in {(x,y) for x,y,_ in map(lambda l:(round(l[0],2),round(l[1],2),0),labs)}])
print('labels off-wire:',[l for l in labs if onseg(l[:2])<1])
print('label counts:',sorted(Counter(l[2] for l in labs).items()))
