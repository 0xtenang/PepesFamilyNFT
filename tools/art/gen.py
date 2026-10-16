import sys, os, json, random
sys.path.insert(0, os.path.dirname(__file__))
from multiprocessing import Pool
import traits as T
from mc import Skin, CHARS, H
from render3d import render
# ---------------- config: edit these ----------------
NAME='Frog Craft'
DESC='3,333 blocky frogs, each with a wearable Minecraft skin.'
IMAGE_BASE='ipfs://REPLACE_WITH_IMAGES_CID'
SKIN_BASE='ipfs://REPLACE_WITH_SKINS_CID'
SUPPLY=3333; SEED=3333
OUT=sys.argv[1] if len(sys.argv)>1 else '/home/user/pepe/collection'
GENESIS=[('rainbow','Genesis Rainbow','Peach'),('wcap','Genesis W Cap','Lavender'),('bun','Genesis Bun','Mint'),('joker','Genesis Joker','Night')]
def pick(rng,d):
    ks=list(d); ws=[v[1] if isinstance(v,tuple) else v for v in d.values()]
    return rng.choices(ks,ws)[0]
def make_spec(rng):
    sp={'Background':pick(rng,T.BGS),'Skin':pick(rng,T.SKINS),'Eyes':pick(rng,T.EYES),'Eye Color':rng.choice(list(T.IRIS)),
        'Mouth':pick(rng,T.MOUTHS),'Hair':pick(rng,T.HAIRS),'Hat':pick(rng,T.HATS),'Eyewear':pick(rng,T.EYEWEAR),
        'Outfit':pick(rng,T.OUTFITS),'Accessory':pick(rng,T.ACCS)}
    sp['Hair Color']=rng.choice(list(T.HAIRC)) if sp['Hair'] not in('Bald','Long Rainbow') else '-'
    sp['Hat Color']=rng.choice(list(T.HATC)) if sp['Hat'] in('Bucket Hat','W Cap','Beanie','Goggles Beanie','Headphones','Bandana','Headband') else '-'
    sp['Outfit Color']=rng.choice(T.OUTC[sp['Outfit']])
    # rules
    if sp['Eyes']=='Laser' and sp['Eyewear']!='None': sp['Eyewear']='None'
    if sp['Mouth']=='Bubblegum' and sp['Accessory']=='Scarf': sp['Accessory']='None'
    return sp
def build(sp):
    s=Skin(); sk=T.skinpal(sp['Skin'])
    T.base(s,sk); T.outfit(s,sk,sp['Outfit'],sp['Outfit Color'])
    T.eyes(s,sk,sp['Eyes'],sp['Eye Color']); T.mouth(s,sk,sp['Mouth'])
    T.hair(s,sk,sp['Hair'],sp['Hair Color']); T.hat(s,sp['Hat'],sp['Hat Color'])
    T.eyewear(s,sp['Eyewear']); T.accessory(s,sp['Accessory'])
    return s
def attrs(sp):
    out=[]
    for k in('Background','Skin','Eyes','Eye Color','Mouth','Hair','Hair Color','Hat','Hat Color','Eyewear','Outfit','Outfit Color','Accessory'):
        if sp.get(k,'-')!='-': out.append({'trait_type':k,'value':sp[k]})
    return out
def job(args):
    tid,sp=args
    if 'Genesis' in sp: s=CHARS[sp['Genesis']]()
    else: s=build(sp)
    s.im.save(f'{OUT}/skins/{tid}.png')
    render(s,f'{OUT}/images/{tid}.png',S=27,size=(1000,1000),bg=H(T.BGS[sp['Background']][0]),cyf=0.95)
    return tid
if __name__=='__main__':
    for d in('images','skins','metadata'): os.makedirs(f'{OUT}/{d}',exist_ok=True)
    rng=random.Random(SEED); specs={}; seen=set()
    for i,(k,label,bg) in enumerate(GENESIS,1):
        specs[i]={'Genesis':k,'Label':label,'Background':bg}
    tid=len(GENESIS)+1
    while tid<=SUPPLY:
        sp=make_spec(rng); dna=json.dumps(sp,sort_keys=True)
        if dna in seen: continue
        seen.add(dna); specs[tid]=sp; tid+=1
    # shuffle non-genesis order so rare traits aren't clustered (already random) ; write metadata
    allmeta=[]
    for tid,sp in specs.items():
        if 'Genesis' in sp: at=[{'trait_type':'Background','value':sp['Background']},{'trait_type':'1/1','value':sp['Label']}]
        else: at=attrs(sp)
        m={'name':f'{NAME} #{tid}','description':DESC,'image':f'{IMAGE_BASE}/{tid}.png','minecraft_skin':f'{SKIN_BASE}/{tid}.png','edition':tid,'attributes':at}
        json.dump(m,open(f'{OUT}/metadata/{tid}.json','w'),indent=2); allmeta.append(m)
    json.dump(allmeta,open(f'{OUT}/_metadata.json','w'))
    if '--meta-only' in sys.argv: sys.exit()
    todo=[(t,specs[t]) for t in specs if '--only' not in sys.argv or t<=int(sys.argv[sys.argv.index('--only')+1])]
    with Pool(4) as p:
        for n,_ in enumerate(p.imap_unordered(job,todo,chunksize=8),1):
            if n%250==0: print(n,flush=True)
    print('done',len(todo))
