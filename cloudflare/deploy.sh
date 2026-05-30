#!/usr/bin/env bash
# Deploy Rosetta Upload Worker using cloudflare/credentials.env
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=load-credentials.sh
source "$(dirname "$0")/load-credentials.sh"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" || -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  echo "Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in cloudflare/credentials.env" >&2
  exit 1
fi

run_wrangler() { npx wrangler "$@"; }

DEV_VARS="$REPO_ROOT/.dev.vars"

case "${1:-deploy}" in
  secrets)
    [[ -f "$DEV_VARS" ]] || { echo "Missing $DEV_VARS" >&2; exit 1; }
    echo "[cloudflare] Uploading Worker secrets from .dev.vars..."
    run_wrangler secret bulk "$DEV_VARS"
    echo "[cloudflare] Secrets uploaded."
    ;;
  dev)
    echo "[cloudflare] Starting wrangler dev..."
    run_wrangler dev
    ;;
  deploy)
    echo "[cloudflare] Deploying rosetta-upload worker..."
    run_wrangler deploy
    echo "[cloudflare] Deploy complete."
    ;;
  *)
    echo "Usage: $0 [deploy|secrets|dev]" >&2
    exit 1
    ;;
esac
