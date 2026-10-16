// Drives the launch page in headless Chromium against a local Anvil (port 8545), with a stand-in wallet that sends as
// the owner (impersonated on Anvil): connect, save the secret, deploy, set links, open the mint, mint from other
// wallets, reveal. Uses the Chrome DevTools Protocol directly (Node's built-in WebSocket).
//   python3 tools/launch/build.py file://$PWD/node_modules/ethers/dist/ethers.umd.min.js > build/launch-test.html
//   anvil --gas-limit 1000000000 & node tools/launch/test.mjs
import { spawn, execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));
const OWNER = "0x3c8A4d94B3219F6633F2cC94094f4765b30c691C";
const RPC = "http://127.0.0.1:8545";
const CHROME = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const rpc = async (method, params = []) => {
  const r = await fetch(RPC, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
  const j = await r.json();
  if (j.error) throw new Error(method + ": " + j.error.message);
  return j.result;
};
await rpc("anvil_impersonateAccount", [OWNER]);
await rpc("anvil_setBalance", [OWNER, "0x56BC75E2D63100000"]);

const chrome = spawn(CHROME, ["--headless=new", "--no-sandbox", "--disable-gpu", "--remote-debugging-port=9333", "--allow-file-access-from-files", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) {
  await sleep(200);
  try { target = (await (await fetch("http://127.0.0.1:9333/json")).json()).find((t) => t.type === "page"); } catch {}
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pending = new Map();
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const cdp = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};

// The stand-in wallet: every request goes to Anvil, sending as the owner.
const shim = `window.ethereum = {
  request: async ({ method, params }) => {
    if (method === "eth_requestAccounts" || method === "eth_accounts") return ["${OWNER}"];
    if (method === "wallet_switchEthereumChain" || method === "wallet_addEthereumChain") return null;
    if (method === "eth_sendTransaction") params = [{ ...params[0], from: "${OWNER}" }];
    const r = await fetch("${RPC}", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
    const j = await r.json();
    if (j.error) { const e = new Error(j.error.message); e.code = j.error.code; e.data = j.error.data; throw e; }
    return j.result;
  },
  on() {}, removeListener() {},
};`;
await cdp("Page.enable");
await cdp("Runtime.enable");
await cdp("Page.addScriptToEvaluateOnNewDocument", { source: shim });
await cdp("Page.navigate", { url: "file://" + path.join(ROOT, "build/launch-test.html") + "#localtest" });
await sleep(1500);
const logText = () => evaluate(`document.getElementById("log").textContent`);
const waitLog = async (needle, ms = 120000) => {
  const t = Date.now();
  while (Date.now() - t < ms) { const l = await logText(); if (l.includes(needle)) return l; await sleep(300); }
  throw new Error("timed out waiting for: " + needle + "\n" + (await logText()));
};
const click = (id) => evaluate(`document.getElementById("${id}").click()`);
const ok = (cond, what) => { if (!cond) { console.log("FAIL", what); process.exitCode = 1; } else console.log("ok  ", what); };

ok(await evaluate(`!!window.ethers`), "ethers loaded");
await click("connect");
await waitLog("Connected");
ok((await evaluate(`document.getElementById("s1pill").textContent`)) === "Owner connected", "owner connected");
ok(await evaluate(`document.getElementById("deploy").disabled`), "deploy locked until the secret is confirmed");
const secret = await evaluate(`document.getElementById("secret").textContent`);
await evaluate(`(() => { const i = document.getElementById("secretCheck"); i.value = "${secret}"; i.dispatchEvent(new Event("input")); })()`);
ok(!(await evaluate(`document.getElementById("deploy").disabled`)), "deploy unlocked");
await click("deploy");
await waitLog("PEPES FAMILY is deployed", 300000);
await sleep(800);
const rec = JSON.parse(await evaluate(`document.getElementById("record").textContent`));
const P = rec.pepesFamily;
const cast = (...a) => execFileSync("cast", [...a, "--rpc-url", RPC]).toString().trim();
ok(cast("call", P, "owner()(address)").toLowerCase() === OWNER.toLowerCase(), "owner is 0x3c8A…691C");
ok(cast("call", P, "price()(uint256)").startsWith("400000000000000"), "price 0.0004 ETH");
const local = (...a) => execFileSync("cast", a).toString().trim();
const commit = local("keccak", local("abi-encode", "f(uint256)", secret));
ok(cast("call", P, "seedCommit()(bytes32)") === commit, "commit matches the secret shown");
const royalty = cast("call", P, "royaltyInfo(uint256,uint256)(address,uint256)", "1", "10000").split("\n");
ok(royalty[0].toLowerCase() === OWNER.toLowerCase() && royalty[1].startsWith("500"), "5% royalty to the owner");

await evaluate(`document.getElementById("website").value = "https://pepesfamily.xyz"; document.getElementById("xlink").value = "https://x.com/pepesfamily"`);
await click("saveLinks");
await waitLog("Saving the links: approve it in your wallet...\n  sent");
await waitLog("done.");
await sleep(500);
ok(cast("call", P, "xLink()(string)") === '"https://x.com/pepesfamily"', "X link saved on chain");
await click("openMint");
await sleep(3000);
ok(cast("call", P, "saleOpen()(bool)") === "true", "mint opened");

// three wallets mint (Anvil's default accounts 3-5)
const keys = ["0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6", "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a", "0x8b3a350cf5c34c9194ca85829a2df0ec3153be0318b5e2d3348e872092edffba"];
for (const k of keys) cast("send", P, "mint(uint256)", "3", "--value", "1200000000000000", "--private-key", k);
ok(cast("call", P, "totalMinted()(uint256)") === "9", "9 minted");
await sleep(1500);
await evaluate(`document.getElementById("mintState") && 0`);
// let blocks pass while the page reveals (Anvil only mines on transactions)
const miner = setInterval(() => rpc("evm_mine").catch(() => {}), 300);
await evaluate(`(async () => { document.getElementById("reveal").disabled = false; })()`);
await click("reveal");
await waitLog("Revealed.", 120000);
clearInterval(miner);
ok(cast("call", P, "revealStatus()(uint8)") === "4", "revealed on chain");
const uri = cast("call", P, "tokenURI(uint256)(string)", "1").replace(/"/g, "");
const json = JSON.parse(Buffer.from(uri.split(",")[1], "base64").toString());
ok(json.external_url === "https://pepesfamily.xyz" && json.attributes.length > 3, "token #1 revealed with traits and website");
console.log(await logText());
chrome.kill();
process.exit();
