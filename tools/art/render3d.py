import math, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image, ImageDraw, ImageFilter
from mc import PARTS, rect, CHARS
# 3D placement: (x0,y0,z0) min corner, pivot, rotation about x (deg)
PLACE={'head':((-4,24,-4),None,0),'body':((-4,12,-2),None,0),
 'rarm':((-8,12,-2),(-6,22,0),-22),'larm':((4,12,-2),(6,22,0),18),
 'rleg':((-4,0,-2),(-2,12,0),16),'lleg':((0,0,-2),(2,12,0),-14)}
def sub(a,b): return [a[i]-b[i] for i in range(3)]
def add(a,b): return [a[i]+b[i] for i in range(3)]
def mul(a,k): return [x*k for x in a]
def dot(a,b): return sum(a[i]*b[i] for i in range(3))
def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def norm(a): l=math.sqrt(dot(a,a)); return mul(a,1/l)
yaw,el=math.radians(32),math.radians(14)
C=norm([-math.sin(yaw)*math.cos(el),math.sin(el),math.cos(yaw)*math.cos(el)])
R=norm(cross([0,1,0],C)); U=cross(C,R)
LIGHT=norm([-0.5,0.9,0.7])
def face_frame(f,o,w,h,d):
    x0,y0,z0=o; x1,y1,z1=x0+w,y0+h,z0+d
    # origin (texel 0,0 corner), u-axis, v-axis (per texel), normal
    return {'front':([x0,y1,z1],[1,0,0],[0,-1,0],[0,0,1]),
            'back':([x1,y1,z0],[-1,0,0],[0,-1,0],[0,0,-1]),
            'right':([x0,y1,z0],[0,0,1],[0,-1,0],[-1,0,0]),
            'left':([x1,y1,z1],[0,0,-1],[0,-1,0],[1,0,0]),
            'top':([x0,y1,z0],[1,0,0],[0,0,1],[0,1,0]),
            'bottom':([x0,y0,z1],[1,0,0],[0,0,-1],[0,-1,0])}[f]
def render(skin,out,S=30,size=(900,1200),bg=(255,255,255),cyf=0.90):
    im=skin.im; quads=[]
    for part,(bu,ou,w,h,d) in PARTS.items():
        (o,piv,ang)=PLACE[part]; a=math.radians(ang)
        def rot(p,vec=False):
            if piv is None: return p
            q=p if vec else sub(p,piv)
            y=q[1]*math.cos(a)-q[2]*math.sin(a); z=q[1]*math.sin(a)+q[2]*math.cos(a)
            r=[q[0],y,z]; return r if vec else add(r,piv)
        for layer,inf in((0,0),(1,0.5 if part=='head' else 0.25)):
            oo=[o[0]-inf,o[1]-inf,o[2]-inf]; k=[(w+2*inf)/w,(h+2*inf)/h,(d+2*inf)/d]
            for f in('top','bottom','right','front','left','back'):
                org,uu,vv,n=face_frame(f,o,w,h,d)
                rn=rot(n,True)
                if dot(rn,C)<=0.01: continue
                shade=0.62+0.38*max(0,dot(rn,LIGHT))
                u0,v0,tw,th=rect(part,f,layer)
                for ty in range(th):
                    for tx in range(tw):
                        c=im.getpixel((u0+tx,v0+ty))
                        if c[3]==0: continue
                        e=0.03
                        pts=[]
                        for (a1,b1) in((tx-e,ty-e),(tx+1+e,ty-e),(tx+1+e,ty+1+e),(tx-e,ty+1+e)):
                            p=add(add(org,mul(uu,a1)),mul(vv,b1))
                            p=[o[i]-inf+(p[i]-o[i])*k[i] for i in range(3)]
                            pts.append(rot(p))
                        cen=mul(add(add(pts[0],pts[1]),add(pts[2],pts[3])),.25)
                        col=tuple(int(min(255,x*shade)) for x in c[:3])
                        quads.append((dot(cen,C)+layer*0.01,[(dot(p,R),dot(p,U)) for p in pts],col))
    quads.sort(key=lambda q:q[0])
    SS=3; W_,H_=size; cx,cy=W_/2,H_*cyf
    canvas=Image.new('RGBA',(W_*SS,H_*SS),(0,0,0,0)); d=ImageDraw.Draw(canvas)
    for _,pts,col in quads:
        d.polygon([((cx+x*S)*SS,(cy-y*S)*SS) for x,y in pts],fill=col)
    fig=canvas.resize(size,Image.LANCZOS)
    # soft drop shadow like the reference cards
    a=fig.split()[3]; sh=Image.new('RGBA',size,(0,0,0,0)); sh.putalpha(a.point(lambda v:int(v*0.28)))
    sh=sh.filter(ImageFilter.GaussianBlur(22))
    bgc=bg; bg=Image.new('RGBA',size,tuple(bgc)+(255,))
    bg.alpha_composite(sh,(-26,18)); bg.alpha_composite(fig)
    bg.convert('RGB').save(out)
if __name__=='__main__':
    od='/home/user/pepe/minecraft'
    for n,fn in CHARS.items():
        s=fn(); s.im.save(f'{od}/skin_{n}.png'); render(s,f'{od}/render_{n}.png')
    ims=[Image.open(f'{od}/render_{n}.png') for n in CHARS]
    sheet=Image.new('RGB',(900*4,1300),'white')
    for i,m in enumerate(ims): sheet.paste(m,(i*900,0))
    sheet.resize((1800,650),Image.LANCZOS).save(f'{od}/all_renders.png')
