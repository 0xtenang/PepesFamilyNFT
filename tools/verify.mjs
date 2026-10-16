// Deploys FrogCraftSpecs, FrogCraftArtData and FrogCraftArt on a local Anvil and checks, for trait
// sets `from` to `to` (default: all 3,333) and the sealed one, that the contract's
//   - skin (skinPixels) is the Python reference skin pixel for pixel (build/expected/skins.bin, tools/gen_art.py),
//   - picture (render) is byte for byte the card I'M DEGEN's JS draws from that skin (MineWorld web/degen-skin.js
//     cardOf), and
//   - attributes are the expected traits (build/expected/specs.json).
//
//   forge build && python3 tools/gen_art.py && anvil --gas-limit 1000000000 & node tools/verify.mjs [from] [to]
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ethers } from "ethers";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const MINEWORLD = process.env.MINEWORLD ?? "/home/user/adamnakamoto/mineworld";
const { cardOf } = await import(pathToFileURL(path.join(MINEWORLD, "web/degen-skin.js")).href);

const exp = JSON.parse(fs.readFileSync(path.join(ROOT, "build/expected/specs.json")));
const skins = fs.readFileSync(path.join(ROOT, "build/expected/skins.bin"));
const artifact = (name) => JSON.parse(fs.readFileSync(path.join(ROOT, `out/${name}.sol/${name}.json`)));

// A local Anvil (anvil --gas-limit 1000000000 --port 8545): its first default account deploys.
const provider = new ethers.JsonRpcProvider(process.env.RPC ?? "http://127.0.0.1:8545");
const signer = await provider.getSigner(0);
async function deploy(name, ...args) {
  const a = artifact(name);
  const c = await new ethers.ContractFactory(a.abi, a.bytecode.object, signer).deploy(...args, { gasLimit: 900_000_000 });
  await c.waitForDeployment();
  return c;
}
const specs = await deploy("FrogCraftSpecs");
const data = await deploy("FrogCraftArtData");
const art = await deploy("FrogCraftArt", await specs.getAddress(), await data.getAddress());

const N = exp.packed.length;
const from = Number(process.argv[2] ?? 0), to = Number(process.argv[3] ?? N - 1);
const bgOf = (v) => "#" + exp.backgrounds[Number((BigInt(v) >> BigInt(exp.shifts.background)) & ((1n << BigInt(exp.widths.background)) - 1n))];
const pxOf = (k) => {
  const px = new Array(4096);
  for (let i = 0; i < 4096; i++) {
    const o = k * 16384 + 4 * i;
    px[i] = skins[o + 3] === 0 ? -1 : (skins[o] << 16) | (skins[o + 1] << 8) | skins[o + 2];
  }
  return px;
};
const opts = { gasLimit: 900_000_000 };
let bad = 0, maxGas = 0n;
const fail = (msg) => { bad++; console.log("MISMATCH", msg); };

// the sealed card
{
  const svg = await art.sealedSvg(opts);
  if (svg !== cardOf(pxOf(N), bgOf(exp.sealed))) fail("sealed card");
}
const t0 = Date.now();
for (let i = from; i <= to; i++) {
  if (BigInt(await specs.specOf(i)) !== BigInt(exp.packed[i])) fail(`${i} spec`);
  const rgba = ethers.getBytes(await art.skinPixels(i, opts));
  if (!Buffer.from(rgba).equals(skins.subarray(i * 16384, (i + 1) * 16384))) fail(`${i} skin`);
  const svg = await art.render(i, opts);
  if (svg !== cardOf(pxOf(i), bgOf(exp.packed[i]))) fail(`${i} card`);
  const attrs = JSON.parse(await art.attributes(i, opts));
  if (JSON.stringify(attrs) !== JSON.stringify(exp.attributes[i])) fail(`${i} attributes ${JSON.stringify(attrs)}`);
  if (i % 50 === 0 || i === from) {
    const g = await art.render.estimateGas(i, opts);
    if (g > maxGas) maxGas = g;
  }
  if ((i - from) % 250 === 0) console.log(`#${i} ok so far (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
}
fs.mkdirSync(path.join(ROOT, "build/cards"), { recursive: true });
for (const i of [0, 1, 2, 3, 4, 5, 6, 7]) fs.writeFileSync(path.join(ROOT, `build/cards/${i}.svg`), await art.render(i, opts));
fs.writeFileSync(path.join(ROOT, "build/cards/sealed.svg"), await art.sealedSvg(opts));
console.log(`checked ${to - from + 1} trait sets + sealed: ${bad} mismatches; render gas up to ${maxGas}`);
process.exit(bad ? 1 : 0);
