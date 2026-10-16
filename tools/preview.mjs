// Writes build/preview.html: the on-chain cards (the same SVG bytes FrogCraftArt.render returns, drawn by I'M DEGEN's
// cardOf from the reference skins) for trait sets 0-3 (the 1/1s), the sealed card and a random 43 more.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const MINEWORLD = process.env.MINEWORLD ?? "/home/user/adamnakamoto/mineworld";
const { cardOf } = await import(pathToFileURL(path.join(MINEWORLD, "web/degen-skin.js")).href);
const exp = JSON.parse(fs.readFileSync(path.join(ROOT, "build/expected/specs.json")));
const skins = fs.readFileSync(path.join(ROOT, "build/expected/skins.bin"));
const N = exp.packed.length;
const bgOf = (v) => "#" + exp.backgrounds[Number((BigInt(v) >> BigInt(exp.shifts.background)) & ((1n << BigInt(exp.widths.background)) - 1n))];
const pxOf = (k) => Array.from({ length: 4096 }, (_, i) => {
  const o = k * 16384 + 4 * i;
  return skins[o + 3] === 0 ? -1 : (skins[o] << 16) | (skins[o + 1] << 8) | skins[o + 2];
});
let r = 7; const rand = () => (r = (r * 1103515245 + 12345) % 2147483648) / 2147483648;
const ids = [0, 1, 2, 3, N];
while (ids.length < 48) { const k = 4 + Math.floor(rand() * (N - 4)); if (!ids.includes(k)) ids.push(k); }
const cell = (k) => `<div>${cardOf(pxOf(k), bgOf(k === N ? exp.sealed : exp.packed[k]))}</div>`;
fs.writeFileSync(path.join(ROOT, "build/preview.html"), `<!doctype html><style>body{margin:0;display:grid;grid-template-columns:repeat(8,200px)}div{width:200px;height:200px}svg{width:200px;height:200px;display:block}</style>${ids.map(cell).join("")}`);
