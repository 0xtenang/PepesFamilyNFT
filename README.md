# PEPES FAMILY

**Launch page:** open `index.html` from this repo's website (GitHub Pages) in the browser that has your wallet extension.

![PEPES FAMILY, as the chain draws them](preview.png)

3,333 blocky frogs on Robinhood Chain (chain 4663), **fully on chain**: every frog is a full Minecraft-style skin (64 x 64,
with its second layer), painted by a contract from data in contract code, and its NFT picture (an SVG card) and traits
are written by the contract too. No IPFS, no server: nothing can go missing.

Built on I'M DEGEN ([AdamNakamoto/MineWorld](https://github.com/AdamNakamoto/MineWorld)): the same mint, commit-reveal,
royalty enforcement and links, and the same card renderer, with this collection's own art and trait sets.

| | |
|---|---|
| Name / symbol | PEPES FAMILY / PEPES |
| Supply | 3,333 (four 1/1s: Genesis Rainbow, W Cap, Bun, Joker) |
| Price | 0.0004 ETH (about $1 at ETH $2,450); the owner can change it with `setPrice` |
| Wallet limit | 3 per wallet (owner can set 1 to 50); wallets only, no contracts |
| Owner | `0x3c8A4d94B3219F6633F2cC94094f4765b30c691C` (can never be renounced, so OpenSea Studio always works) |
| Treasury | the same address: all mint money, straight away, and the 5% royalty |
| Royalty | 5%, fixed, enforced with ERC721-C through OpenSea's registry (`0xA000…0000`): marketplaces must pay it; holders can always move their own frogs |
| Editable later | `setLinks(website, x)`, `setDescription`, `setCollectionImages(image, banner)`, `setPrice`, `setWalletLimit`: any time, sold out or not |

## Contracts

| File | What it is |
|---|---|
| `src/PepesFamily.sol` | The NFT (ERC-721 + ERC-2981 + ERC721-C). Blind mint, then reveal: a keyed shuffle from a seed nobody can know early assigns each token one of the 3,333 trait sets |
| `src/FrogCraftArt.sol` | Paints each skin and writes the card and the traits (generated) |
| `src/FrogCraftArtData.sol` | The art's bytes (14.9 KB) as contract code (generated) |
| `src/FrogCraftSpecs.sol` | The 3,333 trait sets, 6 bytes each (generated) |

The art is generated from the Python trait art in `tools/art/` by `tools/gen_art.py`; don't edit the generated files.

## Checks

```
forge build && forge test                       # 14 tests: mint, payments, limits, sell-out, reveal, royalty, links, owner-only
python3 tools/gen_art.py                        # regenerate the art (and build/expected/)
anvil --gas-limit 1000000000 & node tools/verify.mjs   # all 3,333 skins, cards and traits vs the reference
```

`verify.mjs` checks, for every trait set, that the contract's skin equals the reference pixel for pixel, its picture
equals byte for byte the card I'M DEGEN's JS renders from that skin, and its traits are right (last run: 3,333 + the
sealed card, 0 mismatches). `tools/preview.mjs` writes `build/preview.html` with cards as the chain draws them.

## Launch (from the owner wallet, in your browser)

1. Install [Foundry](https://getfoundry.sh) 1.5 or later (`foundryup`; `--browser` needs it), Python 3 and Node, then
   `npm install` in this folder. Put a little ETH on Robinhood Chain in the owner wallet for gas.
2. Dry run (sends nothing): `./script/deploy.sh --browser`
3. Deploy: `WEBSITE=https://... X_LINK=https://x.com/... ./script/deploy.sh --broadcast --browser` (links optional).
   It stops at each transaction with **">> Approve ... at http://127.0.0.1:9545"**: open http://127.0.0.1:9545 in
   your browser, connect the owner wallet (`0x3c8A…691C`) on Robinhood Chain and approve; refresh the page for the next
   one (4 deploys, plus one each for the links and opening the mint if you set them). After the first deploy it checks the
   connected wallet is the owner and stops if not.
   It writes the reveal secret to `~/pepes-family-reveal-secret.txt`: **back it up**; without it the frogs can never be
   revealed. The addresses go to `deployments/chain-4663.json`.
4. OpenSea Studio: sign in with the owner wallet, turn on creator earnings at 5%, add the description, logo, banner and links.
5. Open the mint: `cast send <PepesFamily> "setSaleOpen(bool)" true --browser --browser-disable-open --rpc-url https://rpc.mainnet.chain.robinhood.com`
   (approve at http://127.0.0.1:9545).
6. After the mint: announce the reveal time, then `BROWSER=1 ./script/reveal.sh` (approve the sale close, the reveal and
   the seal at http://127.0.0.1:9545; the seal must land within ~26 seconds of the reveal, so keep the page open; anyone
   can also seal with `./script/reveal.sh --seal-only`). Every frog's look then shows, for everyone at once.

Change links later: `cast send <PepesFamily> "setLinks(string,string)" "https://site" "https://x.com/handle" --browser --browser-disable-open --rpc-url https://rpc.mainnet.chain.robinhood.com`

Prefer a keystore to the browser? `cast wallet import pepes-owner --interactive` once, then the same commands without
`--browser` (the scripts use `--account pepes-owner`).
