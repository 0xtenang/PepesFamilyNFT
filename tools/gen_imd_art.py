# Generates the PEPES FAMILY art contracts from IMD's Pepe (art/imd/: the 19 frames of imd.fun's Pepe sprite sheet,
# cropped, as WebP, and their measurements in frames.json):
#   src/ImdPepeData0.sol ... : the frames' bytes, as contract code (each under the 24 KB code limit)
#   src/ImdPepeSpecs.sol      : the 3,333 trait sets, 4 bytes each (#1-4 of the list are the four 1/1s)
#   src/ImdPepeArt.sol        : draws an NFT's picture (SVG) and lists its traits
# and build/expected/specs.json for the tests and previews.
#
#   python3 tools/gen_imd_art.py            # writes the files
#   python3 tools/gen_imd_art.py --check    # fails if they're out of date
#
# Each picture: a background, IMD's Pepe in one of 19 poses with its skin, shirt and shorts recoloured by SVG
# filters (colour-keyed masks keep IMD's lines and shading), a shadow, and maybe a hat or shades on the head.
import json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ART = os.path.join(ROOT, 'art', 'imd')
SUPPLY = 3333
CHUNK = 24574  # bytes of frames per data contract (code limit 24,576, one STOP byte in front)

FRAMES = json.load(open(os.path.join(ART, 'frames.json')))
FRAME_BYTES = [open(os.path.join(ART, f'frame{i:02d}.webp'), 'rb').read() for i in range(len(FRAMES))]
# Which way each frame shows the Pepe: back, side (facing right) or front.
VIEW = ['back'] * 7 + ['side'] * 6 + ['front'] * 4 + ['back', 'back']

# ---------------------------------------------------------------- traits: (name, value, weight)

POSES = [
    ('Turning Away', 5), ('Walking Away', 5), ('Strolling Away', 5), ('Watching the Wall', 8), ('Waiting', 6),
    ('Head Scratch (Back)', 4), ('Thinking', 4), ('Side Glance', 6), ('Walking', 6), ('Wandering', 5),
    ('Running', 4), ('Passing By', 5), ('Over the Shoulder', 6), ('Side Eye', 7), ('Classic', 12),
    ('Looking Up', 6), ('Head Scratch', 5), ('Hands Up', 3), ('Celebrate', 3),
]
SKINS = [('Classic Green', None, 62), ('Zombie', '8aa86b', 10), ('Ice', '7fd3e8', 7), ('Bubblegum', 'f29bb3', 7),
         ('Shadow', '4a4a4a', 6), ('Alien', '9b7fe0', 5), ('Gold', 'e6b422', 3)]
SHIRTS = [('IMD Blue', None, 40), ('Red', 'd23c3c', 9), ('Black', '1f1f1f', 9), ('White', 'ececec', 8),
          ('Swarm Green', '3ddc84', 8), ('Purple', '7a4fd6', 7), ('Orange', 'f28c28', 7), ('Grey', '8a8f98', 6),
          ('Yellow', 'f5d33b', 6)]
SHORTS = [('Tan', None, 50), ('Grey', '6b6b6b', 12), ('Denim', '3d5a80', 12), ('Black', '2a2a2a', 10),
          ('Red', 'a83232', 8), ('White', 'e8e8e8', 8)]
BGS = [('IMD Wall', 20), ('Terminal', 12), ('The Floor', 14), ('Paper', 12), ('Mint', 10), ('Sky', 10),
       ('Bubblegum', 8), ('Night', 8), ('Swarm Green', 4), ('Gold', 2)]
EXTRAS = [('None', 55), ('Cap', 9), ('Beanie', 8), ('Headphones', 8), ('Party Hat', 6), ('Shades', 6),
          ('Halo', 4), ('Crown', 2)]
SHADES = 5
# The four 1/1s: trait sets #1-4 (which tokens get them is decided at the reveal).
ONE_OF_ONES = [
    ('Genesis', dict(pose=18, skin=6, shirt=4, shorts=0, bg=0, extra=7)),
    ('The Swarm', dict(pose=3, skin=0, shirt=2, shorts=3, bg=1, extra=3)),
    ('Golden Pepe', dict(pose=14, skin=6, shirt=0, shorts=0, bg=9, extra=6)),
    ('Night Shift', dict(pose=15, skin=4, shirt=2, shorts=3, bg=7, extra=0)),
]

# The regions' base lightness (0-255) on IMD's art, and the masks that pick them out by colour (alpha rows of
# feColorMatrix: R G B A offset), tuned by eye on all 19 frames. The shorts are only recoloured below the head (the
# contract clips them), so the lips, close to the shorts in colour, are never caught.
BASE = {'skin': 124, 'shirt': 71, 'shorts': 145}
MASKS = {'skin': ['-10 20 -10 0 -0.8'], 'shirt': ['-6 -3 6 0 -0.4'], 'shorts': ['14 -14 0 0 -0.45', '-27.2 40 0 0 0.05']}


def tint(hexc, base):
    """feColorMatrix values that turn a pixel's lightness into the colour `hexc` at the region's base lightness."""
    t = [int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    rows = []
    for c in t:
        k = c * 255 / base
        rows.append(' '.join(f'{x * k:.4f}'.rstrip('0').rstrip('.') for x in (0.2126, 0.7152, 0.0722)) + ' 0 0')
    return ' '.join(rows) + ' 0 0 0 1 0'


def region_fx(name):
    """The filter steps for one region, up to the tint matrix (which the contract appends)."""
    s = ''
    for i, row in enumerate(MASKS[name]):
        s += f'<feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 {row}" result="{name}m{i}"/>'
    m = f'{name}m0'
    if len(MASKS[name]) > 1:
        s += f'<feComposite in="{name}m0" in2="{name}m1" operator="in" result="{name}mm"/>'
        m = f'{name}mm'
    s += f'<feComposite in="{m}" in2="SourceAlpha" operator="in" result="{name}a"/>'
    s += f'<feColorMatrix in="SourceGraphic" type="matrix" result="{name}t" values="'
    return s


def region_end(name):
    return f'"/><feComposite in="{name}t" in2="{name}a" operator="in" result="{name}c"/>'


# ---------------------------------------------------------------- backgrounds (600 x 600; the floor line is near y 500)

SPECKS = ''.join(f'<rect x="{(i * 97) % 600}" y="{506 + (i * 53) % 90}" width="{2 + i % 3}" height="2"/>' for i in range(46))
FLOOR = f'<rect y="470" width="600" height="34" fill="#050505"/><rect y="504" width="600" height="96" fill="#f4f4f1"/><g fill="#1a1a1a">{SPECKS}</g>'
WALL = ('<defs><pattern id="w" width="60" height="60" patternUnits="userSpaceOnUse">'
        '<rect x="2" y="2" width="56" height="56" fill="#dcdcd8" stroke="#151515" stroke-width="2"/>'
        '<circle cx="18" cy="18" r="8" fill="none" stroke="#151515" stroke-width="2"/>'
        '<rect x="32" y="10" width="20" height="16" fill="#101410"/><path d="M34 22l4-6 4 4 4-8 4 6" fill="none" stroke="#3ddc84" stroke-width="2"/>'
        '<circle cx="14" cy="44" r="3" fill="#151515"/><circle cx="26" cy="44" r="3" fill="#3ddc84"/>'
        '<rect x="36" y="36" width="16" height="16" fill="none" stroke="#151515" stroke-width="2"/></pattern></defs>'
        '<rect width="600" height="470" fill="#e9e9e6"/><rect width="600" height="470" fill="url(#w)"/>')
TERMINAL = ('<rect width="600" height="470" fill="#050605"/><rect x="20" y="20" width="560" height="430" fill="none" stroke="#1f5e35" stroke-width="3"/>'
            + ''.join(f'<rect x="44" y="{48 + i * 30}" width="{120 + (i * 137) % 360}" height="8" fill="{"#3ddc84" if i % 3 == 0 else "#2b3a2b"}"/>' for i in range(13)))
BG_SVG = [WALL + FLOOR, TERMINAL + FLOOR,
          '<rect width="600" height="470" fill="#0b0b0b"/><path d="M120 60v410M300 60v410M480 60v410" stroke="#262626" stroke-width="3"/>' + FLOOR,
          '<rect width="600" height="600" fill="#f3efe0"/>', '<rect width="600" height="600" fill="#cdeedd"/>',
          '<rect width="600" height="600" fill="#cfe3ff"/>', '<rect width="600" height="600" fill="#ffd6e5"/>',
          '<rect width="600" height="600" fill="#14161a"/>', '<rect width="600" height="600" fill="#3ddc84"/>',
          '<rect width="600" height="600" fill="#f5d77a"/>']

# ---------------------------------------------------------------- extras
# Drawn in IMD's style (thin, round, dark lines; flat colours) around the top of the head (shades: around the eyes),
# for a 120-wide head, in three views. The contract wraps each in the shared line style (LINE) and places it with the
# frame's placement below. Tuned by eye on every frame with tools/imd/tune.html.
LINE = 'stroke="#1c1c1c" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"'
NS = 'stroke="none"'


def at(dy, svg):
    return f'<g transform="translate(0 {dy})">{svg}</g>'


CAP_DOME = '<path d="M-58 24C-60-6-30-24 0-24C30-24 60-6 58 24C30 18-30 18-58 24Z" fill="#2563eb"/>'
BEANIE = ('<path d="M-60 26C-62-14-30-32 0-32C30-32 62-14 60 26Z" fill="#ea580c"/>'
          '<path d="M-62 14C-30 8 30 8 62 14L62 30C30 24-30 24-62 30Z" fill="#c2410c"/>'
          '<path d="M-40 12v14M-20 10v14M0 9v14M20 10v14M40 12v14" stroke="#9a3412" stroke-width="2"/><circle cy="-35" r="8" fill="#fde68a"/>')
BAND = ('<path d="{d}" fill="none" stroke-width="7"/><path d="{d}" fill="none" stroke="#4b5563" stroke-width="3"/>')
PARTY = ('<path d="M-18 10L2-54L20 8C8 13-6 13-18 10Z" fill="#a855f7"/><g fill="#fde047" ' + NS + '><circle cx="-2" cy="-14" r="3"/>'
         '<circle cx="8" cy="-30" r="3"/><circle cx="6" cy="0" r="3"/></g><circle cx="2" cy="-56" r="6" fill="#fde047"/>')
HALO = '<ellipse cy="-26" rx="40" ry="9" fill="none" stroke-width="7"/><ellipse cy="-26" rx="40" ry="9" fill="none" stroke="#fde047" stroke-width="3.5"/>'
CROWN = ('<path d="M-32 14L-36-18L-18-4L-2-26L14-4L32-18L30 14C10 10-12 10-32 14Z" fill="#facc15"/><circle cx="-1" cy="4" r="4" fill="#ef4444"/>'
         '<g fill="#facc15"><circle cx="-36" cy="-19" r="3"/><circle cx="-2" cy="-27" r="3"/><circle cx="32" cy="-19" r="3"/></g>')
HP_FRONT = (BAND.format(d='M-64 42C-66-22 66-22 64 42') +
            '<ellipse cx="-64" cy="46" rx="10" ry="16" fill="#e11d48"/><ellipse cx="64" cy="46" rx="10" ry="16" fill="#e11d48"/>')
CAP = (CAP_DOME + '<path d="M0-23C2-6 2 8 0 19" fill="none"/><circle cy="-24" r="3" fill="#1d4ed8"/>'
       '<path d="M-46 21C-30 33 30 33 46 21C28 26-28 26-46 21Z" fill="#1e40af"/>')


def float_above(bottom, svg):
    """A hat floating just above the head, like the halo: 85% size, its lowest point 10 above the head's top."""
    return f'<g transform="translate(0 {-10 - bottom * 0.85:g}) scale(.85)">{svg}</g>'


# [back, side (facing right), front]. Hats float above the head (they never press on IMD's drawing); headphones wrap
# it, in each view.
EXTRA_SVG = {
    'Cap': [float_above(33, CAP)] * 3,
    'Beanie': [float_above(30, BEANIE)] * 3,
    'Headphones': [at(16, HP_FRONT),
                   at(10, BAND.format(d='M-48 40C-56-16 4-24 14 30') + '<ellipse cx="-22" cy="44" rx="12" ry="17" fill="#e11d48"/>'),
                   at(16, HP_FRONT)],
    'Party Hat': [float_above(13, PARTY)] * 3,
    'Halo': [at(4, HALO)] * 3,
    'Crown': [float_above(14, CROWN)] * 3,
}
# Shades sit on the eyes (front frames only), drawn on a 96-wide pair of eyes.
SHADES_SVG = ('<path d="M-50-12h42c3 0 4 2 4 5v8c0 10-6 15-16 15h-18c-10 0-16-5-16-15v-8c0-3 1-5 4-5Z" fill="#111"/>'
              '<path d="M50-12h-42c-3 0-4 2-4 5v8c0 10 6 15 16 15h18c10 0 16-5 16-15v-8c0-3-1-5-4-5Z" fill="#111"/>'
              '<path d="M-4-6h8" fill="none"/><path d="M-40-6h8M16-6h8" stroke="#fff" stroke-width="2.5" opacity=".75"/>')

# Where the extras go on each frame: head top centre (x, y) in the 240 x 284 frame, scale (%, of a 120-wide head) and
# tilt (degrees); and the eyes (x, y, scale % of a 96-wide pair) on the front frames. Tuned by eye.
HAT = [(129, 67, 102, 0), (129, 67, 98, 0), (130, 60, 103, 0), (122, 79, 92, 0), (123, 80, 96, 0), (130, 74, 104, 0),
       (127, 72, 104, 0), (129, 68, 94, 0), (130, 66, 94, 0), (128, 65, 88, 0), (134, 71, 85, 0), (128, 68, 85, 0),
       (121, 71, 99, 0), (121, 89, 98, 0), (119, 79, 100, 0), (122, 66, 94, -6), (118, 79, 104, 0), (120, 24, 104, 0),
       (122, 68, 104, 0)]
EYES = {13: (159, 118, 71), 14: (121, 110, 101), 15: (121, 79, 63), 16: (122, 110, 100)}


# ---------------------------------------------------------------- trait sets

def pick(r, items, w=-1):
    tot = sum(it[w] for it in items)
    x = r.random() * tot
    for i, it in enumerate(items):
        x -= it[w]
        if x < 0:
            return i
    return len(items) - 1


def pack(s, one=0):
    return s['pose'] | s['skin'] << 5 | s['shirt'] << 8 | s['shorts'] << 12 | s['bg'] << 15 | s['extra'] << 19 | one << 23


def unpack(v):
    return dict(pose=v & 31, skin=v >> 5 & 7, shirt=v >> 8 & 15, shorts=v >> 12 & 7, bg=v >> 15 & 15, extra=v >> 19 & 15, one=v >> 23 & 7)


def specs():
    r = random.Random(3333)
    out, seen = [], set()
    for n, (_, s) in enumerate(ONE_OF_ONES):
        out.append(pack(s, n + 1))
        seen.add(tuple(s[k] for k in ('pose', 'skin', 'shirt', 'shorts', 'bg', 'extra')))
    while len(out) < SUPPLY:
        s = dict(pose=pick(r, POSES), skin=pick(r, SKINS), shirt=pick(r, SHIRTS), shorts=pick(r, SHORTS), bg=pick(r, BGS), extra=pick(r, EXTRAS))
        if s['extra'] == SHADES and s['pose'] not in EYES:
            s['extra'] = 0  # shades only where the face shows
        if s['skin'] == 6 and s['extra'] == 7:
            continue  # gold with a crown is Genesis's
        k = tuple(s[k] for k in ('pose', 'skin', 'shirt', 'shorts', 'bg', 'extra'))
        if k in seen:
            continue
        seen.add(k)
        out.append(pack(s))
    return out


# ---------------------------------------------------------------- Solidity

def hexlines(b, indent=12, width=96):
    h = b.hex()
    return '\n'.join(' ' * indent + f'hex"{h[i:i + width]}"' for i in range(0, len(h), width))


def sol_str(s):
    assert '"' not in s.replace('\\"', '') or True
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def sol_list(items):
    return '[' + ', '.join(sol_str(x) for x in items) + ']'


def chunks():
    """Frames packed into as few data contracts as possible, never split across two: first fit, largest first, then a
    fixed-seed search over other orders if that leaves a contract it could do without."""
    sizes = [len(b) for b in FRAME_BYTES]
    lower = -(-sum(sizes) // CHUNK)

    def fit(order):
        bins, table = [], [None] * len(sizes)
        for i in order:
            for n, used in enumerate(bins):
                if used + sizes[i] <= CHUNK:
                    table[i] = (n, used, sizes[i]); bins[n] += sizes[i]
                    break
            else:
                table[i] = (len(bins), 0, sizes[i]); bins.append(sizes[i])
        return len(bins), table

    best = fit(sorted(range(len(sizes)), key=lambda i: -sizes[i]))
    r = random.Random(19)
    for _ in range(20000):
        if best[0] == lower:
            break
        order = list(range(len(sizes))); r.shuffle(order)
        got = fit(order)
        if got[0] < best[0]:
            best = got
    n, table = best
    out = [bytearray() for _ in range(n)]
    for i in sorted(range(len(sizes)), key=lambda i: table[i][1]):
        c, off, ln = table[i]
        assert len(out[c]) == off
        out[c] += FRAME_BYTES[i]
    return [bytes(b) for b in out], table


def frame_table(table):
    b = bytearray()
    views = {'back': 0, 'side': 1, 'front': 2}
    for i, f in enumerate(FRAMES):
        c, off, ln = table[i]
        hx, hy, hs, hr = HAT[i]
        ex, ey, es = EYES.get(i, (0, 0, 0))
        b += bytes([c]) + off.to_bytes(2, 'big') + ln.to_bytes(2, 'big')
        b += bytes([f['x'], f['y'], f['w']]) + f['h'].to_bytes(2, 'big')
        b += bytes([hx, hy, hs, hr + 128, ex, ey, es, views[VIEW[i]]])
    return bytes(b)


def data_solidity(n, b):
    return f'''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

// GENERATED by tools/gen_imd_art.py: don't edit by hand.

/// @title ImdPepeData{n}
/// @notice Part {n} of IMD's Pepe frames ({len(b)} bytes of WebP images; see ImdPepeArt), as this contract's code,
///         after a STOP byte so it can't be run. ImdPepeArt reads it with extcodecopy. IMD's art (imd.fun).
contract ImdPepeData{n} {{
    constructor() {{
        bytes memory code = abi.encodePacked(hex"00",
{hexlines(b)}
        );
        assembly ("memory-safe") {{
            return(add(code, 32), mload(code))
        }}
    }}
}}
'''


def specs_solidity(sp):
    b = b''.join(v.to_bytes(4, 'big') for v in sp)
    return f'''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

// GENERATED by tools/gen_imd_art.py: don't edit by hand.

/// @title ImdPepeSpecs
/// @notice The 3,333 trait sets, 4 bytes each (bits, lowest first: pose 5, skin 3, shirt 4, shorts 3, background 4,
///         extra 4, 1/1 3): #1-4 the four 1/1s. Which token gets which is decided at the reveal (the NFT's
///         shuffle). Holds no state and has no owner.
contract ImdPepeSpecs {{
    uint256 public constant SUPPLY = {SUPPLY};

    bytes private constant SPECS =
{hexlines(b, 8)};

    error BadIndex();

    function specOf(uint256 index) external pure returns (uint256 v) {{
        if (index >= SUPPLY) revert BadIndex();
        bytes memory s = SPECS;
        assembly ("memory-safe") {{
            v := shr(224, mload(add(add(s, 32), mul(index, 4))))
        }}
    }}
}}
'''


def parts():
    """Every piece of text the pictures and traits use, in one blob (ImdPepeParts) with its index: names, tint
    matrices, backgrounds, extras (3 views each), and the filter steps. Returns (blob, starts, first index of each group)."""
    groups, items = {}, []

    def group(name, strs):
        groups[name] = len(items)
        items.extend(strs)

    group('pose', [p[0] for p in POSES])
    group('skin', [x[0] for x in SKINS])
    group('shirt', [x[0] for x in SHIRTS])
    group('shorts', [x[0] for x in SHORTS])
    group('bg', [x[0] for x in BGS])
    group('extra', [x[0] for x in EXTRAS])
    group('one', [''] + [o[0] for o in ONE_OF_ONES])
    for r, pal in (('skin', SKINS), ('shirt', SHIRTS), ('shorts', SHORTS)):
        group('tint_' + r, [tint(c, BASE[r]) if c else '' for _, c, _ in pal])
    group('bgsvg', BG_SVG)
    ex = []
    for name, _ in EXTRAS:
        ex += [SHADES_SVG] * 3 if name == 'Shades' else EXTRA_SVG.get(name, ['', '', ''])
    group('extrasvg', ex)
    group('fx', [region_fx(r) for r in ('skin', 'shirt', 'shorts')] + [region_end(r) for r in ('skin', 'shirt', 'shorts')])
    blob, starts = bytearray(), []
    for t in items:
        starts.append(len(blob))
        blob += t.encode()
    starts.append(len(blob))
    return bytes(blob), starts, groups


PARTS_TEMPLATE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

// GENERATED by tools/gen_imd_art.py: don't edit by hand.

/// @title ImdPepeParts
/// @notice The text PEPES FAMILY's pictures and traits are made of (@SIZE@ bytes: trait names, colour matrices,
///         backgrounds, hats and shades, filter steps), as this contract's code after a STOP byte. ImdPepeArt reads
///         each piece with extcodecopy, by its index.
contract ImdPepeParts {
    constructor() {
        bytes memory code = abi.encodePacked(hex"00",
@HEX@
        );
        assembly ("memory-safe") {
            return(add(code, 32), mload(code))
        }
    }
}
"""


def parts_solidity(blob):
    return PARTS_TEMPLATE.replace('@SIZE@', str(len(blob))).replace('@HEX@', hexlines(blob))


ART_TEMPLATE = open(os.path.join(HERE, 'imd_art_template.sol')).read()


def art_solidity(n_chunks, table, starts, groups):
    ft = frame_table(table)
    idx = b''.join(x.to_bytes(2, 'big') for x in starts)
    subs = {
        '@SUPPLY@': str(SUPPLY), '@FRAMES@': str(len(FRAMES)), '@N@': str(n_chunks),
        '@FRAME_TABLE@': hexlines(ft, 8), '@PART_INDEX@': hexlines(idx, 8), '@PARTS_SIZE@': str(starts[-1] + 1),
        '@SHADES@': str(SHADES),
        '@DATA_ARGS@': ', '.join(f'address data{i}_' for i in range(n_chunks)),
        '@DATA_SETS@': '\n'.join(f'        data[{i}] = data{i}_;' for i in range(n_chunks)),
        '@DATA_CHECKS@': ' || '.join(f'data{i}_.code.length == 0' for i in range(n_chunks)),
    }
    for k, v in groups.items():
        subs['@G_' + k.upper() + '@'] = str(v)
    s = ART_TEMPLATE
    for k, v in subs.items():
        s = s.replace(k, v)
    import re
    assert not re.search(r'@[A-Z_]+@', s), 'unfilled placeholder'
    return s



def deploy_helper(n):
    imports = '\n'.join(f'import {{ImdPepeData{i}}} from "../../src/ImdPepeData{i}.sol";' for i in range(n))
    news = ',\n            '.join(f'address(new ImdPepeData{i}())' for i in range(n))
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

// GENERATED by tools/gen_imd_art.py: don't edit by hand.

import {{ImdPepeArt, IImdPepeSpecs}} from "../../src/ImdPepeArt.sol";
import {{ImdPepeSpecs}} from "../../src/ImdPepeSpecs.sol";
import {{ImdPepeParts}} from "../../src/ImdPepeParts.sol";
{imports}

/// @notice Deploys the art (specs, parts, the {n} frame contracts, then ImdPepeArt), for the tests.
library ImdArt {{
    function deploy() internal returns (ImdPepeArt) {{
        return new ImdPepeArt(
            IImdPepeSpecs(address(new ImdPepeSpecs())),
            address(new ImdPepeParts()),
            {news}
        );
    }}
}}
"""


def main():
    cs, table = chunks()
    sp = specs()
    out = {os.path.join(ROOT, 'src', f'ImdPepeData{i}.sol'): data_solidity(i, b) for i, b in enumerate(cs)}
    out[os.path.join(ROOT, 'src', 'ImdPepeSpecs.sol')] = specs_solidity(sp)
    blob, starts, groups = parts()
    out[os.path.join(ROOT, 'src', 'ImdPepeParts.sol')] = parts_solidity(blob)
    out[os.path.join(ROOT, 'src', 'ImdPepeArt.sol')] = art_solidity(len(cs), table, starts, groups)
    out[os.path.join(ROOT, 'test', 'utils', 'ImdArt.sol')] = deploy_helper(len(cs))
    # what tools/imd/tune.html shows: the placements and designs, in its terms
    names = {'Cap': 'cap', 'Beanie': 'beanie', 'Headphones': 'headphones', 'Party Hat': 'party', 'Halo': 'halo', 'Crown': 'crown'}
    tune = {'line': LINE, 'hat': HAT, 'eyes': EYES,
            'extras': {names[k]: dict(zip(['back', 'side', 'front'], v)) for k, v in EXTRA_SVG.items()} | {'shades': {'front': SHADES_SVG}}}
    out[os.path.join(ROOT, 'art', 'imd', 'extras.json')] = json.dumps(tune, indent=1) + '\n'
    names = lambda v: dict(pose=POSES[v & 31][0], skin=SKINS[v >> 5 & 7][0], shirt=SHIRTS[v >> 8 & 15][0], shorts=SHORTS[v >> 12 & 7][0],
                           background=BGS[v >> 15 & 15][0], extra=EXTRAS[v >> 19 & 15][0], one=([''] + [o[0] for o in ONE_OF_ONES])[v >> 23 & 7])
    expected = json.dumps({'chunks': len(cs), 'specs': sp, 'traits': [names(v) for v in sp]}, indent=0)
    out[os.path.join(ROOT, 'build', 'expected', 'imd-specs.json')] = expected
    if '--check' in sys.argv:
        # build/ isn't committed: only the contracts and the test helper are checked
        stale = [p for p, s in out.items() if '/build/' not in p and (not os.path.exists(p) or open(p).read() != s)]
        if stale:
            print('out of date:', *stale, sep='\n  ')
            sys.exit(1)
        return
    for p, s in out.items():
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'w').write(s)
    print(f'{len(cs)} data contracts ({", ".join(str(len(b)) for b in cs)} bytes), {len(sp)} trait sets')


if __name__ == '__main__':
    main()
