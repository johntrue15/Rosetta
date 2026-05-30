#!/usr/bin/env bash
# Load cloudflare/credentials.env into the current shell.
# Usage: source cloudflare/load-credentials.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILE="$HERE/credentials.env"

if [[ ! -f "$FILE" ]]; then
  echo "Missing $FILE" >&2
  echo "  cp cloudflare/credentials.example.env cloudflare/credentials.env" >&2
  return 1 2>/dev/null || exit 1
fi

set -a
# shellcheck disable=SC1090
source "$FILE"
set +a

echo "[cloudflare] Loaded credentials from credentials.env"
[[ -n "${CLOUDFLARE_API_TOKEN:-}" ]] || echo "[cloudflare] warning: CLOUDFLARE_API_TOKEN is empty" >&2
[[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ]] || echo "[cloudflare] warning: CLOUDFLARE_ACCOUNT_ID is empty" >&2
