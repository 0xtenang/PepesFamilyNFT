import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from mc import Skin, rect, FACES, PARTS, H
def sh(c,k): return tuple(max(0,min(255,int(x*k))) for x in c)
SIDES=['right','left','back']
# ---------------- palettes ----------------
SKINS={'Classic Green':('6aa04a',400),'Forest':('4e8a3a',150),'Lime':('9acd32',120),'Swamp':('7a8f4a',100),
       'Blue':('4a8fc0',80),'Pink':('e58fb0',60),'Gold':('e8b923',40),'Ghost':('d9e3e8',30),'Diamond':('5fe3e0',10)}
IRIS={'Blue':'1a478b','Teal':'16adb8','Brown':'5a3a28','Grey':'3d4353','Purple':'6b2fa0','Green':'2f7d32'}
HAIRC={'Brown':('5c3a28',),'Black':('22222a',),'Purple':('6b3873',),'Pink':('e06aa0',),'Blonde':('e8c35a',),
       'Green':('149157',),'Blue':('2a62d8',),'Red':('b8242c',),'White':('e6e8ee',)}
BGS={'Mint':('c8f0d8',120),'Peach':('ffd8c2',120),'Sky':('cfe6ff',120),'Lavender':('e2d6ff',110),'Butter':('fff2b3',110),
     'Blush':('ffd6e3',100),'Cloud':('eef0f3',100),'Sage':('d5e3c8',90),'Sand':('eedfc6',90),'Night':('2b2f45',40)}
def skinpal(name):
    c=H(SKINS[name][0]); return {'c':c,'s':sh(c,.72),'l':sh(c,1.18),'o':sh(c,.32)}
# ---------------- base frog ----------------
def base(s,sk):
    for p in PARTS: s.fill(p,sk['c'])
    s.px('head','right',4,4,sk['s']); s.px('head','left',3,4,sk['s'])
EYES={ # rows 2,3,4 for each 3-wide eye ; weight
 'Smug':(['ooo','lll','wik'],300),'Side Eye':(['ooo','www','wwk'],180),'Wide':(['ooo','www','wkw'],150),
 'Sad':(['ooo','lll','kww'],120),'Crying':(['ooo','lll','kww'],80),'Sleepy':(['ggg','ooo','lll'],100),
 'Angry':(['oog','lll','wik'],70),'Laser':(['ooo','rrr','RRR'],25)}
def eyes(s,sk,name,iris):
    rows=EYES[name][0]
    pal={'o':sk['o'],'l':sk['l'],'w':H('f7faff'),'i':H(IRIS[iris]),
         'k':H('111111'),'g':sk['c'],'r':H('ff2a2a'),'R':H('ffb0a0')}
    for i,row in enumerate(rows):
        for j,ch in enumerate(row):
            s.px('head','front',1+j,2+i,pal[ch],j=3)
            rc=row[::-1][j] if name=='Angry' else ch
            s.px('head','front',5+j,2+i,pal[rc],j=3)
    if name=='Crying':
        for x in(1,5): s.px('head','front',x,5,H('5ab8f0')); 
        s.px('head','front',1,6,H('5ab8f0'))
MOUTHS={'Classic Lips':300,'Orange Lips':150,'Smile':120,'Frown':100,'Shocked':70,'Tongue Out':80,'Bubblegum':50}
def mouth(s,sk,name):
    L1,L2=(H('e8622a'),H('f08a4b')) if name=='Orange Lips' else (H('8e3b35'),H('c0625a'))
    f=lambda x,y,c: s.px('head','front',x,y,c,j=3)
    if name in('Classic Lips','Orange Lips','Tongue Out','Bubblegum'):
        for x in range(1,7): f(x,6,L1)
        for x in range(2,6): f(x,7,L2)
        if name=='Tongue Out': f(4,7,H('ff7aa0')); f(5,7,H('ff7aa0'))
        if name=='Bubblegum':
            s.grid('head','front',['...pp...','..pqpp..','...pp...'],{'p':H('ff8ac4'),'q':H('ffd0e8')},1,y0=5)
    elif name=='Smile':
        f(1,5,L1); f(6,5,L1)
        for x in range(2,6): f(x,6,L1)
    elif name=='Frown':
        for x in range(2,6): f(x,6,L1)
        f(1,7,L1); f(6,7,L1)
    elif name=='Shocked':
        f(3,6,L1); f(4,6,L1); f(3,7,H('2a0d0d')); f(4,7,H('2a0d0d')); f(2,7,L1); f(5,7,L1)
# ---------------- hair (base layer) ----------------
HAIRS={'Bald':200,'Bob':180,'Messy':180,'Bun':110,'Wild':110,'Mohawk':80,'Long Rainbow':40}
def hair(s,sk,name,col):
    if name=='Bald': return
    if name=='Long Rainbow':
        RB=[H(c) for c in('ff0a09','ffab0a','fefe08','3dff0a','1ad2de','8a10ff','ff09f6','93058f')]
        s.fill('head',RB[2],faces=['top'])
        for x in range(8):
            for y in range(8): s.px('head','top',x,y,RB[(x+y)%8],j=5)
        for f in SIDES:
            u,v,w,h=rect('head',f)
            for x in range(w):
                for y in range(8): s.px('head',f,x,y,RB[x%8],j=6)
        s.grid('head','front',['yyoorrpp','y.......'],{'y':RB[2],'o':RB[1],'r':RB[0],'p':RB[6]})
        for x in range(8):
            for y in range(10): s.px('body','back',x,y,RB[x%8],1,j=5)
        s.grid('body','front',['y......p','g......m','y......p'],{'y':RB[2],'g':RB[3],'p':RB[5],'m':RB[6]},1)
        return
    c=H(HAIRC[col][0]); d,l=sh(c,.62),sh(c,1.3)
    stripe=lambda x,y:[c,d,c,l][(x+y)%4]
    if name=='Mohawk':
        for y in range(8):
            for x in(3,4): s.px('head','top',x,y,stripe(x,y),j=4)
        for y in range(6):
            for x in(3,4): s.px('head','back',x,y,stripe(x,y),j=4)
        s.grid('head','front',['...hh...','...dd...'],{'h':c,'d':d})
        for y in range(8): s.px('head','top',3,y,l,1); s.px('head','top',4,y,c,1)
        return
    for x in range(8):
        for y in range(8): s.px('head','top',x,y,stripe(x,y),j=5)
    bottom={'Bob':7,'Messy':5,'Bun':8,'Wild':7}[name]
    for f in SIDES:
        u,v,w,h=rect('head',f)
        for x in range(w):
            for y in range(bottom if f!='back' else 8): s.px('head',f,x,y,stripe(x,y),j=5)
    fr={'Bob':['hdhhdhhd','d.......','h.......','d.......'],
        'Messy':['hdhlhdhl','dh.hd.hd','h...h...'],
        'Bun':['ddhddhld','hd.dd.dh','d.......'],
        'Wild':['hdhkhdhk','kh.hk.dh']}[name]
    s.grid('head','front',fr,{'h':c,'d':d,'l':l,'k':sh(c,.4)})
    if name=='Bun':
        s.grid('head','top',['..dddd..','.dlllld.','.dlddld.','.dlllld.','..dddd..'],{'d':d,'l':l},1)
        s.grid('head','right',['......','.p....','..p...','...p..'],{'p':H('c8508a')},1)
    if name=='Wild':
        for f in('right','left'):
            for y in range(0,7,2): s.px('head',f,(y*3)%8,y,d,1)
# ---------------- hats (overlay) ----------------
HATS={'None':320,'Bucket Hat':90,'W Cap':110,'Beanie':100,'Goggles Beanie':50,'Straw Hat':60,'Headphones':80,
      'Bandana':70,'Headband':60,'Crown':20}
HATC={'Red':'c62f2f','Black':'1b2531','Blue':'2a62d8','Maroon':'95313b','Pink':'f4a6c0','Orange':'f07b2a','Purple':'7d3fb8','White':'e6e8ee','Yellow':'f2c94c'}
def band(s,fn,rows=3):
    for f in FACES:
        if f=='bottom': continue
        u,v,w,h=rect('head',f,1)
        for x in range(w):
            for y in range(h):
                if f!='top' and y>=rows: continue
                c=fn(f,x,y)
                if c: s.px('head',f,x,y,c,1,j=4)
def hat(s,name,col):
    if name=='None': return
    c=H(HATC.get(col,'c62f2f')); d,l=sh(c,.6),sh(c,1.25)
    if name=='Bucket Hat':
        P=H('fde0e3')
        band(s,lambda f,x,y: d if (f!='top' and y==2) else ((c if (x+y)%2 else d) if (f=='right' or (f in('front','top') and x<4) or (f=='back' and x>=4)) else P))
        s.grid('head','front',['.....m.m','......m.'],{'m':c},1)
    elif name=='W Cap':
        band(s,lambda f,x,y: d if (f!='top' and y==2) else (d if f=='top' and y>=6 else c))
        s.grid('head','front',['..w.w.w.','...w.w..'],{'w':H('e6e6e6') if col!='White' else H('1b2531')},1)
    elif name in('Beanie','Goggles Beanie'):
        band(s,lambda f,x,y: (l if y==2 else (c if x%2 else d)) if f!='top' else (c if (x+y)%2 else d))
        if name=='Goggles Beanie':
            band(s,lambda f,x,y: None if f=='top' or y!=2 else H('b9bcc4'))
            s.grid('head','front',['........','........','.gg..gg.'],{'g':H('6fd3ff')},1)
    elif name=='Straw Hat':
        S,Sd,Rb=H('e8bb6a'),H('c99a4c'),H('d23a3a')
        band(s,lambda f,x,y: Rb if (f!='top' and y==1) else (S if (x+y)%3 else Sd))
    elif name=='Headphones':
        K=H('1c1c1f')
        for y in range(8):
            for x in(3,4): s.px('head','top',x,y,K,1)
        for f in('right','left'):
            for y in range(3,7):
                for x in range(2,6):
                    s.px('head',f,x,y,K if (y in(3,6) or x in(2,5)) else c,1)
        for y in range(0,3):
            for f in('right','left'): s.px('head',f,3,y,K,1); s.px('head',f,4,y,K,1)
    elif name=='Bandana':
        band(s,lambda f,x,y: H('ffffff') if (x*3+y*5)%7==0 and f!='top' else c)
        s.grid('head','back',['........','...cc...','..c..c..'],{'c':d},1)
    elif name=='Headband':
        band(s,lambda f,x,y: None if f=='top' or y!=1 else (H('ffffff') if x%4==0 else c))
    elif name=='Crown':
        G1,G2=H('f2c14e'),H('c88a1e')
        band(s,lambda f,x,y: None if f=='top' and 0<x<7 and 0<y<7 else (G2 if y==2 else (G1 if (y==1 or x%2==0) else None)),rows=3)
        s.grid('head','front',['........','.r.b.r..'],{'r':H('d6283a'),'b':H('3b7bd8')},1)
EYEWEAR={'None':700,'Sunglasses':120,'3D Glasses':60,'Nerd Glasses':80,'VR Headset':25}
def eyewear(s,name):
    if name=='None': return
    if name=='Sunglasses':
        s.grid('head','front',['','','','kkkkkkkk','.kkk.kkk'],{'k':H('121216')},1)
        s.px('head','front',1,3,H('5a5a66'),1); s.px('head','front',5,3,H('5a5a66'),1)
        for x in range(4,8): s.px('head','right',x,3,H('121216'),1)
        for x in range(0,4): s.px('head','left',x,3,H('121216'),1)
    elif name=='3D Glasses':
        s.grid('head','front',['','','','wwwwwwww','wrrrwccc'],{'w':H('f2f2f2'),'r':H('e53935'),'c':H('29b6f6')},1)
        for x in range(4,8): s.px('head','right',x,3,H('f2f2f2'),1)
        for x in range(0,4): s.px('head','left',x,3,H('f2f2f2'),1)
    elif name=='Nerd Glasses':
        s.grid('head','front',['','','kkkkkkkk','k...k...','kkkkkkkk'],{'k':H('2a1a12')},1)
        for y in(2,3,4): s.px('head','front',7,y,H('2a1a12'),1)
        s.grid('head','front',['','','','.....','.www.www'],{'w':H('f7faff')},0)
    elif name=='VR Headset':
        s.grid('head','front',['','','wwwwwwww','wbbbbbbw','wwwwwwww'],{'w':H('e9ebef'),'b':H('3a7bff')},1)
        for f in('right','left'):
            for x in range(8): s.px('head',f,x,3,H('2a2a30'),1)
# ---------------- outfits ----------------
OUTFITS={'Coral Jacket':100,'Sweater':130,'Pinafore':90,'Joker Suit':40,'Detective Coat':80,'Royal Robe':25,
         'Pirate Vest':60,'Frog Hoodie':120,'Buff':50,'Star Tee':100,'Tuxedo':60,'Hawaiian Shirt':80,'Tracksuit':100}
OUTC={'Coral Jacket':['Coral'],'Sweater':['Navy','Maroon','Olive','Grey'],'Pinafore':['Maroon','Blue','Black'],'Joker Suit':['Purple'],
      'Detective Coat':['Brown','Beige'],'Royal Robe':['Red','Blue'],'Pirate Vest':['Red'],'Frog Hoodie':['Brown','Grey','Black','Pink'],
      'Buff':['Black Shorts'],'Star Tee':['Black'],'Tuxedo':['Black'],'Hawaiian Shirt':['Teal','Orange'],'Tracksuit':['Red','Blue','Green','Black']}
CC={'Coral':'ff5a68','Navy':'222b3a','Maroon':'77304f','Olive':'5b6b2e','Grey':'6d717a','Blue':'2a52b8','Black':'1d1d22','Purple':'8c2fb4',
    'Brown':'9b6a45','Beige':'cbb48a','Red':'c41f2f','Pink':'e993b5','Teal':'1ea5a0','Orange':'f08a3a','Green':'2e8b3e'}
def limbs(s,sk,coat,pants,shoe,cuff=9,leg_skin_from=None):
    for a in('rarm','larm'):
        s.fill(a,coat)
        s.fill(a,sh(coat,.6),rows=(cuff,cuff),faces=['front','back','left','right'])
        s.fill(a,sk['c'],rows=(cuff+1,11),faces=['front','back','left','right']); s.fill(a,sk['c'],faces=['bottom'])
    for l in('rleg','lleg'):
        s.fill(l,pants)
        if leg_skin_from is not None: s.fill(l,sk['c'],rows=(leg_skin_from,9),faces=['front','back','left','right'])
        s.fill(l,shoe,rows=(10,11),faces=['front','back','left','right']); s.fill(l,shoe,faces=['bottom'])
def front(s,rows,pal,layer=0,part='body'): s.grid(part,'front',rows,pal,layer)
def outfit(s,sk,name,col):
    c=H(CC[col]) if col in CC else None
    if name=='Coral Jacket':
        C,D=H('ff5a68'),H('22252e'); s.fill('body',C)
        front(s,['ccdddcc'[:0]+'ccddddcc']*12,{'c':C,'d':D}); 
        for y in(3,6,9): s.px('body','front',1,y,sh(C,.6)); s.px('body','front',6,y,sh(C,.6))
        limbs(s,sk,C,D,H('3b2020'))
    elif name=='Sweater':
        s.fill('body',c); front(s,['.wwwwww.','..wwww..','...ww...'],{'w':H('d1d9e6')})
        for y in range(4,12): s.px('body','front',2,y,sh(c,.55)); s.px('body','front',5,y,sh(c,.55))
        limbs(s,sk,c,H('15171d'),H('8a8f99'))
    elif name=='Pinafore':
        Wt=H('dfe2ea'); s.fill('body',Wt); s.fill('body',c,faces=['front','back','left','right'],rows=(3,11))
        front(s,['.a....a.','.a....a.','.a....a.'],{'a':c})
        for y in range(3,12): s.px('body','front',1,y,sh(c,.55)); s.px('body','front',6,y,sh(c,.55))
        limbs(s,sk,Wt,sk['c'],H('3e1530'),cuff=4)
        for l in('rleg','lleg'): s.fill(l,c,rows=(0,3),faces=['front','back','left','right'])
    elif name=='Joker Suit':
        Pp,Pd,Gv,Gd,Or=H('8c2fb4'),H('531966'),H('369c2a'),H('215e19'),H('eb9500')
        s.fill('body',Pp); front(s,['pdgGGgdp']*2+['pdgOOgdp']*8+['pppOOppp']*2,{'p':Pp,'d':Pd,'g':Gv,'G':Gd,'O':Or})
        limbs(s,sk,Pp,Pp,H('1b1220'))
    elif name=='Detective Coat':
        s.fill('body',c); front(s,['cdwtwdc.'[:0]+'cdwttwdc']*12,{'c':c,'d':sh(c,.7),'w':H('f2f4f8'),'t':H('6b3a1f')})
        s.grid('body','front',['','','','','','','','','kkkkkkkk'],{'k':sh(c,.45)})
        limbs(s,sk,c,sh(c,.75),H('2a2a2e'))
    elif name=='Royal Robe':
        Gd=H('f2c14e'); s.fill('body',c)
        front(s,['cgwwwwgc']*12,{'c':c,'g':Gd,'w':H('f7f7f7')})
        limbs(s,sk,c,sh(c,.45),H('2a1010'))
        for a in('rarm','larm'): s.fill(a,Gd,rows=(0,0),faces=['front','back','left','right'])
    elif name=='Pirate Vest':
        R,Y=H('c41f2f'),H('f2d03a'); s.fill('body',R)
        front(s,['rrssssrr','rrsysssrr'[:8],'rrssssrr','rrsysssr','rrssssrr','rrssssrr','rrssssrr','rrssssrr','rrssssrr','rrssssrr'],{'r':R,'s':sk['c'],'y':Y})
        s.fill('body',Y,rows=(10,11),faces=['front','back','left','right'])
        limbs(s,sk,R,H('2a52b8'),H('6b4423'),cuff=5)
        for l in('rleg','lleg'): s.fill(l,H('f2f2f2'),rows=(6,6),faces=['front','back','left','right']); s.fill(l,sk['c'],rows=(7,9),faces=['front','back','left','right'])
    elif name=='Frog Hoodie':
        s.fill('body',c); front(s,['.dddddd.'],{'d':sh(c,.7)})
        front(s,['','','..gggg..','..wkwk..','..gggg..','..mmmm..'],{'g':sk['c'],'w':H('f7faff'),'k':H('111111'),'m':H('8e3b35')})
        front(s,['']*8+['.dddddd.','.d....d.','.dddddd.'],{'d':sh(c,.75)})
        limbs(s,sk,c,H('5a7cae'),H('f2f2f2'))
    elif name=='Buff':
        s.fill('body',sk['c'])
        front(s,['........','.ss..ss.','..s..s..','........','...ss...','..s..s..','...ss...','..s..s..','...ss...','........'],{'s':sk['s']})
        s.fill('body',H('1d1d22'),rows=(10,11),faces=['front','back','left','right'])
        for a in('rarm','larm'): s.fill(a,sk['c']); s.fill(a,sk['s'],rows=(3,3),faces=['front','back','left','right'])
        for l in('rleg','lleg'):
            s.fill(l,sk['c']); s.fill(l,H('1d1d22'),rows=(0,4),faces=['front','back','left','right'])
            s.fill(l,H('8a8f99'),rows=(10,11),faces=['front','back','left','right']); s.fill(l,H('8a8f99'),faces=['bottom'])
    elif name=='Star Tee':
        K,R,Y=H('1d1d22'),H('c62f2f'),H('f6c434'); s.fill('body',K)
        front(s,['','...yy...','..yyyy..','...yy...','..y..y..'],{'y':Y})
        limbs(s,sk,R,H('2b3a55'),H('f2f2f2'))
    elif name=='Tuxedo':
        K,Wt,R=H('17171c'),H('f4f6fa'),H('c41f2f'); s.fill('body',K)
        front(s,['kkwrrwkk','kkwrrwkk','kkkwwkkk','kkkwwkkk','kkkkkkkk','kkkwwkkk'[:0]+'kkkbkkkk','kkkkkkkk','kkkbkkkk'],{'k':K,'w':Wt,'r':R,'b':H('3a3a44')})
        limbs(s,sk,K,K,H('0c0c0e'))
    elif name=='Hawaiian Shirt':
        s.fill('body',c)
        for f in('front','back','left','right'):
            u,v,w,h=rect('body',f)
            for x in range(w):
                for y in range(h):
                    k=(x*7+y*5+len(f))%9
                    if k==0: s.px('body',f,x,y,H('ff6fae'))
                    elif k==4: s.px('body',f,x,y,H('fff27a'))
        for y in range(12): s.px('body','front',4,y,sh(c,.6))
        limbs(s,sk,c,H('d9c08c'),H('7a4a22'),cuff=4,leg_skin_from=5)
    elif name=='Tracksuit':
        Wt=H('f4f4f4'); s.fill('body',c); front(s,['...ww...']+['....w...']*11,{'w':Wt})
        limbs(s,sk,c,c,Wt)
        for a,f in(('rarm','right'),('larm','left')):
            for y in range(9): s.px(a,f,1,y,Wt); s.px(a,f,2,y,Wt)
        for l,f in(('rleg','right'),('lleg','left')):
            for y in range(10): s.px(l,f,2,y,Wt)
ACCS={'None':550,'Gold Chain':120,'Silver Chain':90,'Diamond Chain':25,'Earring':80,'Scarf':60}
def accessory(s,name):
    if name=='None': return
    if name in('Gold Chain','Silver Chain','Diamond Chain'):
        a,b={'Gold Chain':('f2b40a','ffe33f'),'Silver Chain':('a9b0bb','e9edf2'),'Diamond Chain':('5fe3e0','e8ffff')}[name]
        s.grid('body','front',['.a....a.','.bab bab'.replace(' ','') [:0]+'..a..a..','...bb...'],{'a':H(a),'b':H(b)},1)
    elif name=='Earring':
        s.px('head','right',5,6,H('f2c14e'),1)
    elif name=='Scarf':
        R=H('d23a3a')
        for f in('front','back','left','right'):
            u,v,w,h=rect('body',f,1)
            for x in range(w): s.px('body',f,x,0,R if x%2 else sh(R,.7),1)
        s.grid('body','front',['','.rr.....','.rr.....','.r......'],{'r':R},1)
