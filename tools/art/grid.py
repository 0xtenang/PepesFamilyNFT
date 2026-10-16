from PIL import Image
import sys
C=1280/24
def grid(p):
    im=Image.open(p).convert('RGB')
    return [[im.getpixel((int(c*C+C/2),int(r*C+C/2))) for c in range(24)] for r in range(24)]
if __name__=='__main__':
    g=grid(sys.argv[1])
    for r in range(7,18):
        print(r,' '.join('%02x%02x%02x'%p for p in g[r][4:19]))
