#!/usr/bin/env bash
# Deploys Pepes Family on Robinhood Chain (chain 4663): ImdPepeSpecs (the 3,333 trait sets), ImdPepeParts (the text
# the pictures are made of), ImdPepeData0-6 (IMD's Pepe frames), ImdPepeArt (draws every picture), then PepesFamily
# (the NFT), all fully on chain.
#
#   ./script/deploy.sh --browser                      # dry run: checks everything, sends nothing
#   ./script/deploy.sh --broadcast --browser          # deploys: open http://127.0.0.1:9545, connect the OWNER wallet
#                                                     # (on Robinhood Chain) and approve each transaction (4-6 of them)
# Or with a keystore instead of the browser: `cast wallet import pepes-owner --interactive` once, then the same
# commands without --browser. Needs Foundry 1.5 or later (`foundryup`) for --browser.
#
# Env (all optional): ACCOUNT (keystore name, default pepes-owner), RPC_URL (default Robinhood's public RPC),
# PRICE_WEI (default 413000000000000 = 0.000413 ETH, $1 at ETH $2,424 on 2026-10-18), WEBSITE and X_LINK (set now, or later with
# setLinks), VALIDATOR (OpenSea's royalty-enforcement registry), OPEN_SALE=1 (open the mint at once).
#
# Deploy from the OWNER wallet itself (0x3c8A...691C): OpenSea Studio lets only the collection's owner() edit it,
# and the deployer is its creator. The reveal secret is written to ~/pepes-family-reveal-secret.txt (never printed):
# keep a copy somewhere safe; without it the frogs can never be revealed.
set -euo pipefail
cd "$(dirname "$0")/.."

OWNER=0x3c8A4d94B3219F6633F2cC94094f4765b30c691C
TREASURY=${TREASURY:-$OWNER}
VALIDATOR=${VALIDATOR:-0xA000027A9B2802E1ddf7000061001e5c005A0000} # OpenSea's StrictAuthorizedTransferSecurityRegistry
PRICE_WEI=${PRICE_WEI:-413000000000000}
RPC_URL=${RPC_URL:-https://rpc.mainnet.chain.robinhood.com}
ACCOUNT=${ACCOUNT:-pepes-owner}
SECRET_FILE=${SECRET_FILE:-$HOME/pepes-family-reveal-secret.txt}
BROADCAST=0
BROWSER=0
for a in "$@"; do
  case "$a" in
    --broadcast) BROADCAST=1 ;;
    --browser) BROWSER=1 ;;
    *) echo "Usage: $0 [--broadcast] [--browser]"; exit 1 ;;
  esac
done

CHAIN=$(cast chain-id --rpc-url "$RPC_URL")
if [ -n "${DEV_PRIVATE_KEY:-}" ]; then
  # Local chains only (Anvil): sign with a throwaway key, own it with that key's address.
  [ "$CHAIN" = "4663" ] && { echo "DEV_PRIVATE_KEY is for local chains only"; exit 1; }
  SIGN=(--private-key "$DEV_PRIVATE_KEY")
  DEPLOYER=$(cast wallet address --private-key "$DEV_PRIVATE_KEY")
  OWNER=$DEPLOYER; TREASURY=${DEV_TREASURY:-$DEPLOYER}
  VALIDATOR_IS_DEV=1
elif [ "$BROWSER" = 1 ]; then
  # The browser wallet: each transaction waits at http://127.0.0.1:$PORT for you to connect and approve it.
  [ "$CHAIN" = "4663" ] || [ -n "${ALLOW_OTHER_CHAIN:-}" ] || { echo "RPC_URL is chain $CHAIN, not Robinhood Chain (4663)"; exit 1; }
  PORT=${BROWSER_PORT:-9545}
  SIGN=(--browser --browser-disable-open --browser-port "$PORT")
  DEPLOYER=$OWNER # (checked against the wallet you connect after the first deploy)
  VALIDATOR_IS_DEV=0
else
  [ "$CHAIN" = "4663" ] || { echo "RPC_URL is chain $CHAIN, not Robinhood Chain (4663)"; exit 1; }
  SIGN=(--account "$ACCOUNT")
  DEPLOYER=$(cast wallet address --account "$ACCOUNT")
  VALIDATOR_IS_DEV=0
fi
lc() { printf %s "$1" | tr 'A-F' 'a-f'; } # (macOS ships bash 3.2, without ${var,,})
if [ "$(lc "$DEPLOYER")" != "$(lc "$OWNER")" ]; then
  echo "The signing wallet is $DEPLOYER, not OWNER $OWNER: deploy from the OWNER wallet (OpenSea Studio)."
  exit 1
fi
echo "Chain $CHAIN, deployer = owner $OWNER, treasury (mint money + 5% royalty) $TREASURY"
echo "Price $PRICE_WEI wei ($(cast from-wei "$PRICE_WEI") ETH) a Pepe, 3 a wallet; owner balance $(cast from-wei "$(cast balance "$OWNER" --rpc-url "$RPC_URL")") ETH"

forge build -q
python3 tools/gen_imd_art.py --check || { echo "The art contracts are out of date: run python3 tools/gen_imd_art.py"; exit 1; }

if [ "$BROADCAST" = 0 ]; then
  echo "Dry run OK. Run again with --broadcast to deploy."
  exit 0
fi

# The reveal secret: random, kept on this computer; only its hash goes on chain now.
if [ ! -s "$SECRET_FILE" ]; then
  umask 077
  cast to-dec "0x$(openssl rand -hex 32)" > "$SECRET_FILE"
  echo "Reveal secret written to $SECRET_FILE (keep a copy somewhere safe)."
fi
COMMIT=$(cast keccak "$(cast abi-encode 'f(uint256)' "$(cat "$SECRET_FILE")")")

TMPD=$(mktemp -d); trap 'rm -rf "$TMPD"' EXIT
create() { # name, constructor args...  (prints the address; the deploying wallet goes to $TMPD/deployer)
  local name=$1 src=src; shift
  [ "$name" = DevTransferValidator ] && src=script
  local args=()
  [ $# -gt 0 ] && args=(--constructor-args "$@")
  [ "$BROWSER" = 1 ] && echo ">> Approve the $name deploy at http://127.0.0.1:$PORT (owner wallet, Robinhood Chain)" >&2
  forge create "$src/$name.sol:$name" --rpc-url "$RPC_URL" "${SIGN[@]}" --broadcast --json ${args[@]+"${args[@]}"} > "$TMPD/out.json"
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["deployer"])' "$TMPD/out.json" > "$TMPD/deployer"
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["deployedTo"])' "$TMPD/out.json"
}

if [ "$VALIDATOR_IS_DEV" = 1 ]; then VALIDATOR=$(create DevTransferValidator); fi
SPECS=$(create ImdPepeSpecs);                echo "ImdPepeSpecs     $SPECS"
# The wallet that signs must be the owner (OpenSea Studio): checked before anything else is deployed.
if [ "$(tr 'A-F' 'a-f' < "$TMPD/deployer")" != "$(lc "$OWNER")" ]; then
  echo "The connected wallet is $(cat "$TMPD/deployer"), not the owner $OWNER: stopping (only ImdPepeSpecs, a data"
  echo "contract, was deployed). Connect the owner wallet and run again."
  exit 1
fi
PARTS=$(create ImdPepeParts);                echo "ImdPepeParts     $PARTS"
DATA=()
for i in $(seq 0 $(( $(ls src/ImdPepeData*.sol | wc -l) - 1 ))); do
  DATA+=("$(create "ImdPepeData$i")");       echo "ImdPepeData$i     ${DATA[$i]}"
done
ART=$(create ImdPepeArt "$SPECS" "$PARTS" "${DATA[@]}"); echo "ImdPepeArt       $ART"
PEPES=$(create PepesFamily "$OWNER" "$TREASURY" "$PRICE_WEI" "$COMMIT" "$VALIDATOR" "$ART")
echo "PepesFamily      $PEPES   <- the collection"

send() {
  [ "$BROWSER" = 1 ] && echo ">> Approve $1 at http://127.0.0.1:$PORT" >&2
  cast send "$PEPES" "$@" --rpc-url "$RPC_URL" "${SIGN[@]}" >/dev/null
}
if [ -n "${WEBSITE:-}${X_LINK:-}" ]; then send "setLinks(string,string)" "${WEBSITE:-}" "${X_LINK:-}"; echo "Links set."; fi
if [ "${OPEN_SALE:-0}" = 1 ]; then send "setSaleOpen(bool)" true; echo "Mint open."; fi

mkdir -p deployments
cat > "deployments/chain-$CHAIN.json" <<EOF
{
  "chainId": $CHAIN,
  "pepesFamily": "$PEPES",
  "art": "$ART",
  "parts": "$PARTS",
  "frames": [$(printf '"%s",' "${DATA[@]}" | sed 's/,$//')],
  "specs": "$SPECS",
  "owner": "$OWNER",
  "treasury": "$TREASURY",
  "validator": "$VALIDATOR",
  "priceWei": "$PRICE_WEI"
}
EOF
echo "Written deployments/chain-$CHAIN.json"
cat <<EOF

Next steps (owner wallet; with a keystore, use --account $ACCOUNT instead of --browser):
  - Open the mint:      cast send $PEPES "setSaleOpen(bool)" true --browser --browser-disable-open --rpc-url $RPC_URL
  - Links (any time):   cast send $PEPES "setLinks(string,string)" "https://your.site" "https://x.com/you" --browser --browser-disable-open --rpc-url $RPC_URL
  - Price (any time):   cast send $PEPES "setPrice(uint256)" <wei> --browser --browser-disable-open --rpc-url $RPC_URL
    (each waits at http://127.0.0.1:9545 for you to approve)
  - OpenSea Studio: sign in with the owner wallet, turn on creator earnings (5%), add the description, links, banner.
  - After the mint: ./script/reveal.sh (announce the time first; anyone can seal with it too).
EOF
