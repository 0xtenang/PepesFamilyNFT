# Generates src/FrogCraftArt.sol and src/FrogCraftSpecs.sol from the Python trait art in tools/art/ (traits.py,
# mc.py) and the 3,333 trait sets gen.py draws (seed 3333): every layer becomes packed rectangles on the 64 x 64 skin,
# every trait set 6 bytes. Also writes build/expected/ (skins and option tables) for the tests.
#
#   python3 tools/gen_art.py            # writes the contracts
#   python3 tools/gen_art.py --check    # fails if they're out of date
#
# The skin painter (_paint), the card renderer (_card, FACES) and _name are I'M DEGEN's CrafterArt
# (github.com/AdamNakamoto/MineWorld, contracts/src/CrafterArt.sol), copied as they are: the card is the same isometric
# view, written byte for byte as web/degen-skin.js cardOf() writes it.
import sys, os, json, re, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'art'))
import mc, traits as T, gen as G

# On chain every colour is flat: no per-pixel noise.
mc.Skin.jit = lambda s, c, j=7: tuple(c[:3]) + (255,)

DEGEN_ART = os.environ.get('DEGEN_ART', '/home/user/adamnakamoto/mineworld/contracts/src/CrafterArt.sol')

SKIN_NAMES = list(T.SKINS)
BG_NAMES = list(T.BGS)
SKIN_A, SKIN_B = T.skinpal(SKIN_NAMES[0]), T.skinpal('Blue')
SKIN_KEYS = ['c', 's', 'l', 'o', 'l']  # the painter's skin codes 9-13 (S s l d B)


def skin_cols(sk):
    return [sk[k] for k in SKIN_KEYS]


# ---------------------------------------------------------------- options: what each trait paints, and its names

def pixmap(paint):
    """Paint on an empty skin twice (two frog colours): pixels that differ follow the frog's colour (skin codes)."""
    maps = []
    for sk in (SKIN_A, SKIN_B):
        s = mc.Skin()
        paint(s, sk)
        maps.append(list(s.im.getdata()))
    out = {}
    for i, (a, b) in enumerate(zip(*maps)):
        if a[3] == 0 and b[3] == 0:
            continue
        if a != b:
            ca = skin_cols(SKIN_A)
            if a[:3] not in ca or b[:3] != skin_cols(SKIN_B)[ca.index(a[:3])]:
                raise ValueError(f'pixel {i} follows the skin in an unknown way: {a} {b}')
            out[i] = ('skin', ca.index(a[:3]))
        else:
            out[i] = ('rgb', a[:3])
    return out


SILENT = {'paint': None, 'names': []}  # a slot a 1/1 doesn't use: paints nothing, lists nothing


def opt(paint, names):
    return {'paint': paint, 'names': names}


SLOTS = {}  # slot -> list of options (local index = position)
SLOTS['background'] = [opt(None, [('Background', n)]) for n in BG_NAMES] + [SILENT]
SLOTS['skin'] = [opt(None, [('Skin', n)]) for n in SKIN_NAMES] + [SILENT]
SLOTS['outfit'] = []
OUTFIT_KEYS = []
for o in T.OUTFITS:
    for c in T.OUTC[o]:
        SLOTS['outfit'].append(opt(lambda s, sk, o=o, c=c: T.outfit(s, sk, o, c), [('Outfit', o), ('Outfit Color', c)]))
        OUTFIT_KEYS.append((o, c))
for k, label, _bg in G.GENESIS:
    def genesis(s, sk, k=k):
        src = mc.CHARS[k]()
        s.im = src.im.copy()
    SLOTS['outfit'].append(opt(genesis, [('1/1', label)]))
    OUTFIT_KEYS.append(('Genesis', k))
SLOTS['eyes'] = []
EYE_KEYS = []
for e in T.EYES:
    for ic in T.IRIS:
        SLOTS['eyes'].append(opt(lambda s, sk, e=e, ic=ic: T.eyes(s, sk, e, ic), [('Eyes', e), ('Eye Color', ic)]))
        EYE_KEYS.append((e, ic))
SLOTS['eyes'].append(SILENT)
SLOTS['mouth'] = [opt(lambda s, sk, m=m: T.mouth(s, sk, m), [('Mouth', m)]) for m in T.MOUTHS] + [SILENT]
SLOTS['hair'] = []
HAIR_KEYS = []
for h in T.HAIRS:
    for c in (['-'] if h in ('Bald', 'Long Rainbow') else list(T.HAIRC)):
        names = [('Hair', h)] + ([('Hair Color', c)] if c != '-' else [])
        SLOTS['hair'].append(opt(lambda s, sk, h=h, c=c: T.hair(s, sk, h, c), names))
        HAIR_KEYS.append((h, c))
SLOTS['hair'].append(SILENT)
COLOURED_HATS = ('Bucket Hat', 'W Cap', 'Beanie', 'Goggles Beanie', 'Headphones', 'Bandana', 'Headband')
SLOTS['hat'] = []
HAT_KEYS = []
for h in T.HATS:
    for c in (list(T.HATC) if h in COLOURED_HATS else ['-']):
        names = [('Hat', h)] + ([('Hat Color', c)] if c != '-' else [])
        SLOTS['hat'].append(opt(lambda s, sk, h=h, c=c: T.hat(s, h, c), names))
        HAT_KEYS.append((h, c))
SLOTS['hat'].append(SILENT)
SLOTS['eyewear'] = [opt(lambda s, sk, e=e: T.eyewear(s, e), [('Eyewear', e)]) for e in T.EYEWEAR] + [SILENT]
SLOTS['accessory'] = [opt(lambda s, sk, a=a: T.accessory(s, a), [('Accessory', a)]) for a in T.ACCS] + [SILENT]
FROG = opt(lambda s, sk: T.base(s, sk), [])

# The packed trait set: these fields, lowest bits first.
FIELDS = ['background', 'skin', 'outfit', 'eyes', 'mouth', 'hair', 'hat', 'eyewear', 'accessory']
PAINT_ORDER = ['outfit', 'eyes', 'mouth', 'hair', 'hat', 'eyewear', 'accessory']
ATTR_ORDER = ['background', 'skin', 'eyes', 'mouth', 'hair', 'hat', 'eyewear', 'outfit', 'accessory']
WIDTH = {f: max(1, (len(SLOTS[f]) - 1).bit_length()) for f in FIELDS}
SHIFT = {}
_b = 0
for f in FIELDS:
    SHIFT[f] = _b
    _b += WIDTH[f]
assert _b <= 48, _b


def silent(f):
    return len(SLOTS[f]) - 1


def pack(sp):
    """A trait set (gen.py's spec) as its 48-bit word."""
    if 'Genesis' in sp:
        loc = {f: silent(f) for f in FIELDS}
        loc['background'] = BG_NAMES.index(sp['Background'])
        loc['skin'] = silent('skin')
        loc['outfit'] = OUTFIT_KEYS.index(('Genesis', sp['Genesis']))
    else:
        loc = {
            'background': BG_NAMES.index(sp['Background']), 'skin': SKIN_NAMES.index(sp['Skin']),
            'outfit': OUTFIT_KEYS.index((sp['Outfit'], sp['Outfit Color'])),
            'eyes': EYE_KEYS.index((sp['Eyes'], sp['Eye Color'])), 'mouth': list(T.MOUTHS).index(sp['Mouth']),
            'hair': HAIR_KEYS.index((sp['Hair'], sp['Hair Color'])), 'hat': HAT_KEYS.index((sp['Hat'], sp['Hat Color'])),
            'eyewear': list(T.EYEWEAR).index(sp['Eyewear']), 'accessory': list(T.ACCS).index(sp['Accessory']),
        }
    v = 0
    for f in FIELDS:
        assert loc[f] < (1 << WIDTH[f])
        v |= loc[f] << SHIFT[f]
    return v


def unpack(v):
    return {f: (v >> SHIFT[f]) & ((1 << WIDTH[f]) - 1) for f in FIELDS}


# ---------------------------------------------------------------- the reference skin (what the contract must paint)

def skin_of(v):
    """The skin, as 4,096 colours (-1: empty), painted the way the contract paints it."""
    u = unpack(v)
    sk = T.skinpal(SKIN_NAMES[min(u['skin'], len(SKIN_NAMES) - 1)])
    s = mc.Skin()
    FROG['paint'](s, sk)
    for f in PAINT_ORDER:
        o = SLOTS[f][u[f]]
        if o['paint']:
            o['paint'](s, sk)
    return [-1 if p[3] == 0 else (p[0] << 16 | p[1] << 8 | p[2]) for p in s.im.getdata()]


# ---------------------------------------------------------------- encoding

def rects_of(pixels):
    """Greedy rectangles (width <= 64, height <= 16) covering {index: code} exactly, each of one code."""
    seen = set()
    out = []
    for y in range(64):
        for x in range(64):
            i = y * 64 + x
            if i not in pixels or i in seen:
                continue
            c = pixels[i]
            w = 1
            while x + w < 64 and (i + w) in pixels and pixels[i + w] == c and (i + w) not in seen:
                w += 1
            h = 1
            while h < 16 and y + h < 64 and all(
                    ((y + h) * 64 + x + k) in pixels and pixels[(y + h) * 64 + x + k] == c
                    and ((y + h) * 64 + x + k) not in seen for k in range(w)):
                h += 1
            for dy in range(h):
                for k in range(w):
                    seen.add((y + dy) * 64 + x + k)
            out.append((x, y, w, h, c))
    return out


class Builder:
    def __init__(self):
        self.layers = []      # tuples of rects
        self.layer_ix = {}
        self.palettes = []    # tuples of colours
        self.pal_ix = {}

    def layer(self, rects):
        key = tuple(rects)
        if key not in self.layer_ix:
            self.layer_ix[key] = len(self.layers)
            self.layers.append(key)
        return self.layer_ix[key]

    def palette(self, cols):
        key = tuple(cols)
        if key not in self.pal_ix:
            self.pal_ix[key] = len(self.palettes)
            self.palettes.append(key)
        return self.pal_ix[key]

    def option(self, o):
        """An option's sub-layers: (layer, palette) pairs, at most 9 own colours each."""
        if not o['paint']:
            return []
        px = pixmap(o['paint'])
        lits = []
        for v in px.values():
            if v[0] == 'rgb' and v[1] not in lits:
                lits.append(v[1])
        groups = [lits[k:k + 9] for k in range(0, len(lits), 9)] or [[]]
        subs = []
        for g, cols in enumerate(groups):
            pix = {}
            for i, v in px.items():
                if v[0] == 'skin' and g == 0:
                    pix[i] = 9 + v[1]
                elif v[0] == 'rgb' and v[1] in cols:
                    pix[i] = cols.index(v[1])
            if pix:
                subs.append((self.layer(rects_of(pix)), self.palette(cols)))
        return subs


def h3(c):
    return bytes(c[:3])


def build():
    b = Builder()
    all_opts = [FROG]
    base = {}
    for f in FIELDS:
        base[f] = len(all_opts)
        all_opts += SLOTS[f]
    subs = [b.option(o) for o in all_opts]
    assert len(b.layers) < 256, len(b.layers)

    # names
    names = []
    def nid(s):
        if s not in names:
            names.append(s)
        return names.index(s)
    pairs = [[(nid(t), nid(v)) for t, v in o['names']] for o in all_opts]
    assert len(names) < 256
    names_b = b''.join(n.encode() for n in names)
    ends, e = [], 0
    for n in names:
        e += len(n.encode())
        ends.append(e)

    # ART: fixed colours, skins (+ the silent skin: the first), backgrounds, layer table, palettes, rectangles
    fixed = [(0, 0, 0), (255, 255, 255), (255, 0, 0), (255, 255, 0), (247, 250, 255)]
    art = bytearray()
    for c in fixed:
        art += h3(c)
    skin_list = SKIN_NAMES + [SKIN_NAMES[0]]
    for n in skin_list:
        for c in skin_cols(T.skinpal(n)):
            art += h3(c)
    bg_off = len(art)
    for n in BG_NAMES + [BG_NAMES[0]]:
        art += h3(T.H(T.BGS[n][0]))
    lt = len(art)
    art += bytes(4 * len(b.layers))
    pal_off = []
    for p in b.palettes:
        pal_off.append(len(art))
        for c in p:
            art += h3(c)
    for li, rects in enumerate(b.layers):
        off = len(art)
        for (x, y, w, h, c) in rects:
            e4 = x << 26 | y << 20 | (w - 1) << 14 | (h - 1) << 10 | c << 5
            art += e4.to_bytes(4, 'big')
        art[lt + 4 * li: lt + 4 * li + 4] = off.to_bytes(2, 'big') + len(rects).to_bytes(2, 'big')
    assert len(art) < 65536

    # OPTS: offsets (uint16 each), then per option: n, n x (layer, palette offset), pairs, pairs x (type, value)
    recs = []
    for s, p in zip(subs, pairs):
        r = bytes([len(s)]) + b''.join(bytes([l]) + pal_off[pi].to_bytes(2, 'big') for l, pi in s)
        r += bytes([len(p)]) + b''.join(bytes([t, v]) for t, v in p)
        recs.append(r)
    opts = bytearray()
    head = 2 * len(recs)
    off = head
    for r in recs:
        opts += off.to_bytes(2, 'big')
        off += len(r)
    for r in recs:
        opts += r

    # the 3,333 trait sets, in gen.py's order (token #1-4 the 1/1s)
    rng = random.Random(G.SEED)
    specs, seen = [], set()
    for k, label, bg in G.GENESIS:
        specs.append({'Genesis': k, 'Label': label, 'Background': bg})
    while len(specs) < G.SUPPLY:
        sp = G.make_spec(rng)
        dna = json.dumps(sp, sort_keys=True)
        if dna in seen:
            continue
        seen.add(dna)
        specs.append(sp)
    packed = [pack(sp) for sp in specs]
    assert len(set(packed)) == len(packed)
    spec_b = b''.join(v.to_bytes(6, 'big') for v in packed)

    sealed = {f: silent(f) for f in FIELDS}
    sealed.update(background=BG_NAMES.index('Night'), skin=0, outfit=OUTFIT_KEYS.index(('Frog Hoodie', 'Black')),
                  eyes=EYE_KEYS.index(('Sleepy', 'Blue')), mouth=list(T.MOUTHS).index('Classic Lips'),
                  hat=HAT_KEYS.index(('Beanie', 'Black')))
    sealed_v = sum(sealed[f] << SHIFT[f] for f in FIELDS)
    return dict(art=bytes(art), opts=bytes(opts), names=names_b, ends=ends, lt=lt, bg_off=bg_off, base=base,
                specs=specs, packed=packed, spec_b=spec_b, sealed=sealed_v, nopts=len(all_opts),
                nlayers=len(b.layers), ncols=sum(len(p) for p in b.palettes), nrects=sum(len(l) for l in b.layers))


# ---------------------------------------------------------------- Solidity

def hexlines(b, indent=8, width=96):
    h = b.hex()
    lines = [h[i:i + width] for i in range(0, len(h), width)] or ['']
    return '\n'.join(' ' * indent + f'hex"{l}"' for l in lines)


def degen_code():
    """_start, _paint, _card and _name from I'M DEGEN's CrafterArt, and its FACES."""
    src = open(DEGEN_ART).read()
    faces = re.search(r'bytes private constant FACES = hex"([0-9a-f]+)";', src).group(1)
    start = src.index('    /// @dev The art in memory (where its bytes start)')
    end = src.index('    /// @dev Name `i` of NAMES')
    body = src[start:end]
    # (its _background and _option read I'M DEGEN's own tables: not used here)
    body = re.sub(r'    /// @dev Background `i`.*?\n    }\n\n', '', body, flags=re.S)
    body = re.sub(r'    /// @dev Option `i` of the table.*?\n    }\n\n', '', body, flags=re.S)
    assert '_background' not in body and '_option' not in body
    name = src[end:]
    name = name[:name.index('\n    }\n') + 7]
    return faces, body, name


def solidity(d):
    faces, body, name = degen_code()
    assert body.count('add(195, shl(2, layer))') == 1
    body = body.replace('add(195, shl(2, layer))', f'add({d["lt"]}, shl(2, layer))')
    body = body.replace('web/degen-skin.js', "I'M DEGEN's web/degen-skin.js")
    assert body.count('function _start() private pure') == 1 and body.count('bytes memory art = ART;') == 1
    body = body.replace('function _start() private pure', 'function _start() private view')
    body = body.replace('bytes memory art = ART;', 'bytes memory art = _artBytes();')
    consts = '\n'.join(
        f'    uint256 private constant {f.upper()}_SHIFT = {SHIFT[f]};\n'
        f'    uint256 private constant {f.upper()}_MASK = {(1 << WIDTH[f]) - 1};\n'
        f'    uint256 private constant {f.upper()}_BASE = {d["base"][f]};' for f in FIELDS)
    paint = '\n'.join(f'        _paintOption(data, canvas, o, {f.upper()}_BASE + ((v >> {f.upper()}_SHIFT) & {f.upper()}_MASK), skin);'
                      for f in PAINT_ORDER)
    attr = '\n'.join(f'        out = _pairs(out, o, {f.upper()}_BASE + ((v >> {f.upper()}_SHIFT) & {f.upper()}_MASK));'
                     for f in ATTR_ORDER)
    ends = b''.join(e.to_bytes(2, 'big') for e in d['ends'])
    names_lit = d['names'].decode()
    assert '"' not in names_lit and '\\' not in names_lit
    names_lines = '\n'.join(f'        "{names_lit[i:i + 96]}"' for i in range(0, len(names_lit), 96))
    return f'''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

// GENERATED by tools/gen_art.py from tools/art/ (traits.py, mc.py, gen.py): don't edit by hand. Change the Python,
// then run `python3 tools/gen_art.py` and `forge test`.

interface IFrogCraftSpecs {{
    function specOf(uint256 index) external view returns (uint256);
}}

/// @title FrogCraftArt
/// @notice Every frog's picture, drawn on chain. Each is a Minecraft skin (64 x 64, the standard layout with classic
///         arms and the second layer), painted layer by layer from rectangles and palettes held in this contract's own
///         code, then shown as a card: the skin seen from the front, a little to its right and above (the same view
///         and the same SVG as I'M DEGEN's cards). Its traits come from the trait set it is given (one of the 3,333 in
///         FrogCraftSpecs, 48 bits each). Holds no state and has no owner: the art can never change.
contract FrogCraftArt {{
    /// @notice The 3,333 trait sets.
    IFrogCraftSpecs public immutable specs;
    /// @notice The art's bytes, as its code (see below).
    address public immutable artData;
    uint256 private constant ART_SIZE = {len(d["art"])};
    uint256 public constant SUPPLY = {G.SUPPLY};
    /// @notice The trait set shown while the frogs are sealed.
    uint256 public constant SEALED = {d["sealed"]};

    error BadIndex();

{consts}
    uint256 private constant BG_OFFSET = {d["bg_off"]};

    /// @dev (byte offsets): [0, 15) fixed colours; [15, {d["bg_off"]}) skins, 5 colours each (S s l d B); then
    ///      the backgrounds, 3 bytes each; [{d["lt"]}, ...) {d["nlayers"]} layers (rectangles offset uint16, count uint16);
    ///      the palettes ({d["ncols"]} colours, 3 bytes each); {d["nrects"]} rectangles, 4 bytes each: x << 26 | y << 20 |
    ///      (width - 1) << 14 | (height - 1) << 10 | code << 5 (0-8 the palette's colours, 9-13 the skin's, 14-18 fixed).
    /// @dev The art lives in its own contract's code (FrogCraftArtData, after a leading STOP byte); its layout:

    /// @dev The {d["nopts"]} options (the frog, then each trait's, field by field): uint16 offsets, then for each its
    ///      layers (count, then layer uint8 and palette offset uint16 each) and its names (count, then type and value,
    ///      indexes into NAMES, a byte each).
    bytes private constant OPTS =
{hexlines(d["opts"])};

    /// @dev The card's faces (I'M DEGEN's CrafterArt): back to front, 14 bytes each.
    bytes private constant FACES = hex"{faces}";

    bytes private constant NAMES =
{names_lines};
    bytes private constant NAME_ENDS =
{hexlines(ends)};

    constructor(IFrogCraftSpecs specs_, address artData_) {{
        if (artData_.code.length != ART_SIZE + 1 || address(specs_).code.length == 0) revert BadIndex();
        specs = specs_;
        artData = artData_;
    }}

    /// @dev The art, read from FrogCraftArtData's code.
    function _artBytes() private view returns (bytes memory art) {{
        art = new bytes(ART_SIZE);
        address a = artData;
        assembly ("memory-safe") {{
            extcodecopy(a, add(art, 32), 1, ART_SIZE)
        }}
    }}

    /// @notice Trait set `index` (0 to SUPPLY - 1), as 48 bits.
    function specOf(uint256 index) public view returns (uint256) {{
        if (index >= SUPPLY) revert BadIndex();
        return specs.specOf(index);
    }}

    /// @notice The NFT picture (an SVG) of trait set `index`.
    function render(uint256 index) external view returns (string memory) {{
        uint256 v = specOf(index);
        return _card(_skin(v), _background(v));
    }}

    /// @notice The picture shown before the reveal.
    function sealedSvg() external view returns (string memory) {{
        return _card(_skin(SEALED), _background(SEALED));
    }}

    /// @notice The traits as marketplaces list them: a JSON array of {{"trait_type", "value"}}.
    function attributes(uint256 index) external view returns (string memory) {{
        uint256 v = specOf(index);
        bytes memory opts = OPTS;
        uint256 o;
        assembly ("memory-safe") {{
            o := add(opts, 32)
        }}
        bytes memory out;
{attr}
        return string.concat("[", string(out), "]");
    }}

    /// @notice Trait set `index`'s skin as RGBA bytes (64 x 64 x 4, row by row), as a PNG of it would hold: what a game
    ///         puts on the player.
    function skinPixels(uint256 index) external view returns (bytes memory rgba) {{
        uint256 canvas = _skin(specOf(index));
        rgba = new bytes(16384);
        assembly ("memory-safe") {{
            let out := add(rgba, 32)
            for {{ let i := 0 }} lt(i, 4096) {{ i := add(i, 1) }} {{
                let c := mload(add(canvas, shl(5, i)))
                if c {{
                    let p := add(out, shl(2, i))
                    mstore8(p, and(shr(16, c), 255))
                    mstore8(add(p, 1), and(shr(8, c), 255))
                    mstore8(add(p, 2), and(c, 255))
                    mstore8(add(p, 3), 255)
                }}
            }}
        }}
    }}

    /// @dev The skin: the frog in its colours, then each trait's layers in turn.
    function _skin(uint256 v) internal view returns (uint256 canvas) {{
        uint256 data;
        (data, canvas) = _start();
        bytes memory opts = OPTS;
        uint256 o;
        assembly ("memory-safe") {{
            o := add(opts, 32)
        }}
        uint256 skin = data + 15 + 15 * ((v >> SKIN_SHIFT) & SKIN_MASK);
        _paintOption(data, canvas, o, 0, skin);
{paint}
    }}

    function _background(uint256 v) private view returns (uint256 c) {{
        bytes memory art = _artBytes();
        uint256 i = (v >> BACKGROUND_SHIFT) & BACKGROUND_MASK;
        assembly ("memory-safe") {{
            c := shr(232, mload(add(add(art, 32), add(BG_OFFSET, mul(3, i)))))
        }}
    }}

    /// @dev Option `opt`'s layers, each in its palette.
    function _paintOption(uint256 data, uint256 canvas, uint256 o, uint256 opt, uint256 skin) private pure {{
        uint256 rec;
        uint256 n;
        assembly ("memory-safe") {{
            rec := add(o, shr(240, mload(add(o, shl(1, opt)))))
            n := byte(0, mload(rec))
        }}
        for (uint256 k; k < n; ++k) {{
            uint256 layer;
            uint256 palette;
            assembly ("memory-safe") {{
                let w := mload(add(rec, add(1, mul(3, k))))
                layer := byte(0, w)
                palette := add(data, and(shr(232, w), 0xffff))
            }}
            _paint(data, canvas, layer, palette, skin);
        }}
    }}

    /// @dev `out`, then option `opt`'s traits as JSON objects (with a comma before each but the first).
    function _pairs(bytes memory out, uint256 o, uint256 opt) private pure returns (bytes memory) {{
        uint256 rec;
        uint256 n;
        assembly ("memory-safe") {{
            rec := add(o, shr(240, mload(add(o, shl(1, opt)))))
            rec := add(rec, add(1, mul(3, byte(0, mload(rec)))))
            n := byte(0, mload(rec))
        }}
        bytes memory names = NAMES;
        bytes memory ends = NAME_ENDS;
        for (uint256 k; k < n; ++k) {{
            uint256 t;
            uint256 val;
            assembly ("memory-safe") {{
                let w := mload(add(rec, add(1, shl(1, k))))
                t := byte(0, w)
                val := byte(1, w)
            }}
            out = abi.encodePacked(
                out, out.length == 0 ? "" : ",", '{{"trait_type":"', _name(names, ends, t), '","value":"', _name(names, ends, val), '"}}'
            );
        }}
        return out;
    }}

{body}{name}}}
'''


def art_data_solidity(d):
    return f'''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

// GENERATED by tools/gen_art.py: don't edit by hand.

/// @title FrogCraftArtData
/// @notice The frogs' art ({len(d["art"])} bytes: colours, layers, palettes, rectangles; see FrogCraftArt), as this
///         contract's code, after a STOP byte so it can't be run. FrogCraftArt reads it with extcodecopy.
contract FrogCraftArtData {{
    constructor() {{
        bytes memory code = abi.encodePacked(hex"00",
{hexlines(d["art"], 12)});
        assembly ("memory-safe") {{
            return(add(code, 32), mload(code))
        }}
    }}
}}
'''


def specs_solidity(d):
    return f'''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

// GENERATED by tools/gen_art.py: don't edit by hand.

/// @title FrogCraftSpecs
/// @notice The 3,333 trait sets, 6 bytes each (48 bits: {", ".join(f"{f} {WIDTH[f]}" for f in FIELDS)}, lowest
///         first): token #1-4 the four 1/1s. Which token gets which is decided at the reveal (FrogCraft's shuffle).
///         Holds no state and has no owner.
contract FrogCraftSpecs {{
    uint256 public constant SUPPLY = {G.SUPPLY};

    bytes private constant SPECS =
{hexlines(d["spec_b"])};

    error BadIndex();

    function specOf(uint256 index) external pure returns (uint256 v) {{
        if (index >= SUPPLY) revert BadIndex();
        bytes memory s = SPECS;
        assembly ("memory-safe") {{
            v := shr(208, mload(add(add(s, 32), mul(6, index))))
        }}
    }}
}}
'''


def main():
    d = build()
    out = {
        os.path.join(ROOT, 'src', 'FrogCraftArt.sol'): solidity(d),
        os.path.join(ROOT, 'src', 'FrogCraftSpecs.sol'): specs_solidity(d),
        os.path.join(ROOT, 'src', 'FrogCraftArtData.sol'): art_data_solidity(d),
    }
    if '--check' in sys.argv:
        stale = [p for p, s in out.items() if not os.path.exists(p) or open(p).read() != s]
        if stale:
            sys.exit('out of date: ' + ', '.join(stale))
        print('up to date')
        return
    for p, s in out.items():
        open(p, 'w').write(s)
    # what the tests compare against: every trait set, packed, and the attributes JSON
    exp = os.path.join(ROOT, 'build', 'expected')
    os.makedirs(exp, exist_ok=True)
    def attrs(v):
        u = unpack(v)
        return [{'trait_type': t, 'value': val} for f in ATTR_ORDER for t, val in SLOTS[f][u[f]]['names']]
    json.dump({'packed': d['packed'], 'sealed': d['sealed'], 'sealedBackground': BG_NAMES.index('Night'),
               'backgrounds': [T.BGS[n][0] for n in BG_NAMES], 'shifts': SHIFT, 'widths': WIDTH, 'attributes': [attrs(v) for v in d['packed']]},
              open(os.path.join(exp, 'specs.json'), 'w'))
    with open(os.path.join(exp, 'skins.bin'), 'wb') as f:
        for v in d['packed'] + [d['sealed']]:
            for c in skin_of(v):
                f.write(b'\0\0\0\0' if c < 0 else bytes([c >> 16, (c >> 8) & 255, c & 255, 255]))
    print(f'art {len(d["art"])} B, opts {len(d["opts"])} B, specs {len(d["spec_b"])} B; {d["nopts"]} options, '
          f'{d["nlayers"]} layers, {d["nrects"]} rects, fields {WIDTH}')


if __name__ == '__main__':
    main()
