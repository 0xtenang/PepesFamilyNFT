import math, random
from PIL import Image, ImageDraw, ImageFilter
H=lambda s: tuple(int(s[i:i+2],16) for i in (0,2,4))
# ---------- skin layout (classic 64x64) ----------
PARTS={ # name: (base uv, overlay uv, w,h,d)
 'head':((0,0),(32,0),8,8,8), 'body':((16,16),(16,32),8,12,4),
 'rarm':((40,16),(40,32),4,12,4), 'larm':((32,48),(48,48),4,12,4),
 'rleg':((0,16),(0,32),4,12,4), 'lleg':((16,48),(0,48),4,12,4)}
def rect(part,face,layer=0):
    (bu,ou,w,h,d)=PARTS[part]; u,v=(bu if layer==0 else ou)
    return {'top':(u+d,v,w,d),'bottom':(u+d+w,v,w,d),'right':(u,v+d,d,h),
            'front':(u+d,v+d,w,h),'left':(u+d+w,v+d,d,h),'back':(u+2*d+w,v+d,w,h)}[face]
FACES=['top','bottom','right','front','left','back']
class Skin:
    def __init__(s): s.im=Image.new('RGBA',(64,64),(0,0,0,0)); s.rng=random.Random(7)
    def jit(s,c,j=7):
        return tuple(max(0,min(255,x+s.rng.randint(-j,j))) for x in c)+(255,)
    def px(s,part,face,x,y,c,layer=0,j=0):
        u,v,w,h=rect(part,face,layer)
        if 0<=x<w and 0<=y<h: s.im.putpixel((u+x,v+y),s.jit(c,j) if c else (0,0,0,0))
    def fill(s,part,c,faces=FACES,layer=0,rows=None,j=7):
        for f in faces:
            u,v,w,h=rect(part,f,layer)
            for y in range(h):
                if rows and not (rows[0]<=y<=rows[1]): continue
                if f in('top','bottom') and rows: continue
                for x in range(w): s.im.putpixel((u+x,v+y),s.jit(c,j))
    def grid(s,part,face,rows,pal,layer=0,j=4,y0=0):
        for y,row in enumerate(rows):
            for x,ch in enumerate(row):
                if ch!='.': s.px(part,face,x,y0+y,pal[ch],layer,j)
# ---------- frog basics ----------
G,GS,GL,O,W=H('6aa04a'),H('4a7a34'),H('85b85c'),H('1f3519'),H('f7faff')
L1,L2=H('8e3b35'),H('c0625a')
def frog_base(s, iris, lips=(L1,L2), extra=None):
    for p in PARTS: s.fill(p,G)
    pal={'g':G,'s':GS,'l':GL,'o':O,'w':W,'i':iris,'m':lips[0],'n':lips[1],'k':H('111111')}
    if extra: pal.update(extra)
    s.grid('head','front',[
        'gggggggg',
        'gggggggg',
        'gooogooo',
        'glllglll',
        'gwikgwik',
        'gggggggg',
        'gmmmmmmg',
        'ggnnnngg'],pal)
    s.px('head','right',4,4,GS); s.px('head','left',3,4,GS)   # ear holes
    return pal
def limbs(s,coat,coat_d,pants,shoe,hand=G,sleeve_rows=(0,10)):
    for a in('rarm','larm'):
        s.fill(a,coat); s.fill(a,hand,rows=(sleeve_rows[1]+1,11),faces=['front','back','left','right']); s.fill(a,hand,faces=['bottom'])
        s.fill(a,coat_d,rows=(sleeve_rows[1],sleeve_rows[1]),faces=['front','back','left','right'])
    for l in('rleg','lleg'):
        s.fill(l,pants); s.fill(l,shoe,rows=(10,11),faces=['front','back','left','right']); s.fill(l,shoe,faces=['bottom'])
# ---------- characters ----------
def rainbow():
    s=Skin(); frog_base(s,H('16adb8'))
    RB=[H(c) for c in('ff0a09','ffab0a','fefe08','3dff0a','1ad2de','8a10ff','ff09f6','93058f')]
    for f in('right','left','back'):
        u,v,w,h=rect('head',f)
        for x in range(w):
            for y in range(2,8): s.px('head',f,x,y,RB[x%8],j=6)
    for y in range(2,8): s.px('head','front',0,y,H('fefe08'),j=6)
    # bucket hat (overlay): maroon checker left / pink smiley right, dark brim
    M,Md,P,B=H('95313b'),H('5e1c25'),H('fde0e3'),H('2e1012')
    for f in FACES:
        if f=='bottom': continue
        u,v,w,h=rect('head',f,1)
        for x in range(w):
            for y in range(h):
                if f!='top' and y>2: continue
                if f!='top' and y==2: c=B
                elif f=='right' or (f in('front','top') and x<4) or f=='back' and x>=4: c=M if (x+y)%2 else Md
                else: c=P
                s.px('head',f,x,y,c,1,j=4)
    s.grid('head','front',['.....m.m','......m.'],{'m':M},1)
    # coral jacket, dark shirt, rainbow collar
    C,Cd,D=H('ff5a68'),H('8e4249'),H('22252e')
    s.fill('body',C); s.fill('body',D,faces=['front'],rows=(0,11)); 
    for y in range(12):
        for x in (0,1,6,7): s.px('body','front',x,y,C,j=6)
        if y in(3,6,9): s.px('body','front',1,y,Cd); s.px('body','front',6,y,Cd)
    s.grid('body','front',['ky....pv','gk....pm','.k....k.'],{'k':D,'g':H('3dff0a'),'y':H('fefe08'),'p':H('8a10ff'),'v':H('ff09f6'),'m':H('93058f')},1)
    for x in range(8): 
        for y in range(10): s.px('body','back',x,y,RB[x%8],1,j=5)
    limbs(s,C,Cd,D,H('3b2020'))
    return s
def wcap():
    s=Skin(); frog_base(s,H('1a478b'))
    Pu,Pd,Pl=H('6b3873'),H('421f49'),H('b05fc0')
    for f in('right','left','back'):
        u,v,w,h=rect('head',f)
        for x in range(w):
            for y in range(2,8): s.px('head',f,x,y,[Pu,Pd,Pu,Pl][x%4] if y<7 else Pd,j=5)
    for y in range(3,7): s.px('head','front',0,y,Pu,j=5)
    K,Kd,Wc=H('1b2531'),H('0d1017'),H('d2d2d2')
    for f in FACES:
        if f=='bottom': continue
        u,v,w,h=rect('head',f,1)
        for x in range(w):
            for y in range(h):
                if f!='top' and y>2: continue
                s.px('head',f,x,y,Kd if (f!='top' and y==2) else K,1,j=4)
    s.grid('head','front',['..w.w.w.','...w.w..'],{'w':Wc},1)
    s.grid('head','top',['........','........','........','........','........','........','kkkkkkkk','kkkkkkkk'],{'k':Kd},1)
    N,Nd=H('222b3a'),H('08090d')
    s.fill('body',N); s.grid('body','front',['.cccccc.','..cccc..','...cc...'],{'c':H('d1d9e6')})
    for y in range(4,12): s.px('body','front',2,y,Nd); s.px('body','front',5,y,Nd)
    limbs(s,N,Nd,H('15171d'),H('8a8f99'))
    return s
def bun():
    s=Skin(); frog_base(s,H('3d4353'))
    Br,Bd,Bl,Pk=H('5c2221'),H('301212'),H('8c3232'),H('c8508a')
    s.fill('head',Br,faces=['top'])
    s.grid('head','top',['..bbbb..','.bllllb.','.blbblb.','.bllllb.','..bbbb..','........','........','........'],{'b':Bd,'l':Bl})
    for f in('right','left','back'):
        u,v,w,h=rect('head',f)
        for x in range(w):
            for y in range(0,8): s.px('head',f,x,y,[Br,Bd,Bl,Br][(x+y)%4],j=5)
    s.grid('head','front',['bbrbbrlb','rb.bb.br','b.......'],{'b':Bd,'r':Br,'l':Bl})
    s.grid('head','right',['......','.p....','..p...','...p..'],{'p':Pk},1,y0=0)
    Wt,Wd,Mr,Md,Au,Ay=H('dfe2ea'),H('aab0bc'),H('77304f'),H('3e1530'),H('fbb40a'),H('ffe33f')
    s.fill('body',Wt); s.fill('body',Mr,faces=['front','back','left','right'],rows=(3,11))
    s.grid('body','front',['.a....a.','.yawway.','..ayya..'],{'a':Au,'y':Ay,'w':Wd})
    for y in range(3,12): s.px('body','front',1,y,Md); s.px('body','front',6,y,Md)
    limbs(s,Wt,Wd,G,H('3e1530'),sleeve_rows=(0,4))
    s.fill('rleg',Mr,rows=(0,3),faces=['front','back','left','right']); s.fill('lleg',Mr,rows=(0,3),faces=['front','back','left','right'])
    return s
def joker():
    s=Skin()
    frog_base(s,H('422924'),lips=(H('bd0100'),H('810100')))
    s.grid('head','front',['.bb..bb.','........','........','........','........','.bb..bb.'],{'b':H('229dd6')})
    Hg,Hd,Hk=H('149157'),H('0b5b36'),H('043821')
    s.fill('head',Hg,faces=['top'])
    for f in('right','left','back','top'):
        u,v,w,h=rect('head',f)
        for x in range(w):
            for y in range(h if f in('top','back') else 7): s.px('head',f,x,y,[Hg,Hd,Hg,Hk,Hg][(x*3+y)%5],j=5)
    s.grid('head','front',['hdhghdhg','gh.hg.dh'],{'h':Hg,'d':Hd,'g':Hk})
    Pp,Pd,Gv,Gd,Or=H('8c2fb4'),H('531966'),H('369c2a'),H('215e19'),H('eb9500')
    s.fill('body',Pp)
    s.grid('body','front',['pdgGGgdp','pdgGGgdp','pdgOOgdp','pdgOOgdp','pdgOOgdp','pdgOOgdp','pdgOOgdp','pdgOOgdp','pdgOOgdp','pdgOOgdp','pppOOppp','pppOOppp'],
           {'p':Pp,'d':Pd,'g':Gv,'G':Gd,'O':Or})
    limbs(s,Pp,Pd,Pp,H('1b1220'))
    return s
CHARS={'rainbow':rainbow,'wcap':wcap,'bun':bun,'joker':joker}
