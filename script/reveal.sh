#!/usr/bin/env bash
# Reveals PEPES FAMILY after the mint: closes the sale, publishes the secret committed at deploy (reveal), then seals
# the seed at once (seal: anyone can, for 256 L2 blocks, about 26 seconds on Robinhood Chain). Every frog's look then
# shows, for everyone at once.
#
#   ./script/reveal.sh                 # owner, keystore: reveal and seal
#   BROWSER=1 ./script/reveal.sh       # owner, browser wallet: approve at http://127.0.0.1:9545 (reveal; seal is sent
#                                      #   from the keystore if given, else approve it there too, quickly: ~26 s window)
#   ./script/reveal.sh --seal-only     # anyone: keep trying seal() until it lands (run it at the announced time)
set -euo pipefail
cd "$(dirname "$0")/.."
RPC_URL=${RPC_URL:-https://rpc.mainnet.chain.robinhood.com}
ACCOUNT=${ACCOUNT:-pepes-owner}
SECRET_FILE=${SECRET_FILE:-$HOME/pepes-family-reveal-secret.txt}
CHAIN=$(cast chain-id --rpc-url "$RPC_URL")
PEPES=${PEPES:-$(python3 -c "import json; print(json.load(open('deployments/chain-$CHAIN.json'))['pepesFamily'])")}
if [ -n "${DEV_PRIVATE_KEY:-}" ]; then SIGN=(--private-key "$DEV_PRIVATE_KEY")
elif [ "${BROWSER:-0}" = 1 ]; then SIGN=(--browser --browser-disable-open); echo "Approve each transaction at http://127.0.0.1:9545"
else SIGN=(--account "$ACCOUNT"); fi
status() { cast call "$PEPES" "revealStatus()(uint8)" --rpc-url "$RPC_URL"; }

if [ "${1:-}" != "--seal-only" ]; then
  [ "$(cast call "$PEPES" "saleOpen()(bool)" --rpc-url "$RPC_URL")" = "true" ] &&
    cast send "$PEPES" "setSaleOpen(bool)" false --rpc-url "$RPC_URL" "${SIGN[@]}" >/dev/null && echo "Sale closed."
  cast send "$PEPES" "reveal(uint256)" "$(cat "$SECRET_FILE")" --rpc-url "$RPC_URL" "${SIGN[@]}" >/dev/null
  echo "Secret published; sealing..."
fi
# 0 None, 1 Waiting, 2 Sealable, 3 Expired, 4 Revealed, 5 Stuck
for _ in $(seq 1 600); do
  s=$(status)
  case "$s" in
    4) echo "Revealed: seed $(cast call "$PEPES" "seed()(uint256)" --rpc-url "$RPC_URL")"; exit 0 ;;
    2) cast send "$PEPES" "seal()" --rpc-url "$RPC_URL" "${SIGN[@]}" >/dev/null 2>&1 || true ;;
    3) echo "The window passed unsealed: the owner can run cast send $PEPES 'moveEntropyOn()' then seal again."; exit 1 ;;
    5) echo "Stuck: no moves left."; exit 1 ;;
  esac
  sleep 0.2
done
echo "Gave up waiting (status $(status))."; exit 1
