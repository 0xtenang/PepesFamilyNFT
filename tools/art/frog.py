import sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from grid import grid
from PIL import Image, ImageDraw
H=lambda s: tuple(int(s[i:i+2],16) for i in (0,2,4))
G,GS,GL,O,W=H('6aa04a'),H('4a7a34'),H('85b85c'),H('1f3519'),H('f7faff')
L1,L2=H('8e3b35'),H('c0625a')
def near(a,b,t=40): return sum(abs(x-y) for x,y in zip(a,b))<t
SKIN=[H('ffcead')]; SHADE=[H('d08c7f'),H('96bbcd'),H('8197a4')]; BLUSH=[H('ff9190')]
def frog(g, joker=False):
    skin=SKIN+([H('cfe3ec')] if joker else [])
    # pupil colour: darkest non-black iris colour from original eye rows
    iris=[g[11][10],g[12][10]]
    iris=min(iris,key=sum)
    for r in range(8,20):
        for c in range(5,19):
            p=g[r][c]
            if any(near(p,s) for s in skin): g[r][c]=G
            elif any(near(p,s) for s in SHADE): g[r][c]=GS
            elif any(near(p,s) for s in BLUSH): g[r][c]=G
    for cols,pup in (((9,10,11,12),(10,11)),((15,16,17),(15,16))):
        for c in cols:
            g[10][c]=O          # top of bulging eye (was brow)
            g[11][c]=GL         # heavy droopy lid
            g[12][c]=W          # eye white
            g[13][c]=O if c in (cols[0],cols[-1]) or True else W
        g[12][pup[0]]=iris; g[12][pup[1]]=O
        g[11][cols[0]]=O if cols[0]==9 else GL
    g[11][17]=GL
    if not joker:
        # wide pepe lips
        for c in range(10,16): g[15][c]=L1
        for c in range(11,15): g[16][c]=L2
        g[14][10]=GS; g[14][15]=GS
    return g
def render(g,out):
    C=1280/24; im=Image.new('RGB',(1280,1280)); d=ImageDraw.Draw(im)
    for r in range(24):
        for c in range(24):
            d.rectangle([round(c*C),round(r*C),round((c+1)*C)-1,round((r+1)*C)-1],fill=g[r][c])
    im.save(out)
if __name__=="__main__":
  for i in range(1,5):
    g=frog(grid(f'images/{i}.jpg'), joker=(i==4))
    render(g,f'pepe_{i}.png')
