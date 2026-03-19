#!/usr/bin/env bash
# Creates the labels required by the facility onboarding workflow.
# Run once from the repo root:  bash .github/setup-labels.sh

set -euo pipefail

REPO="johntrue15/Rosetta"

gh label create "request-facility" \
  --description "New facility onboarding request" \
  --color "d876e3" \
  --repo "$REPO" 2>/dev/null && echo "Created: request-facility" || echo "Exists:  request-facility"

gh label create "facility-approved" \
  --description "Facility request approved — triggers branch creation" \
  --color "0e8a16" \
  --repo "$REPO" 2>/dev/null && echo "Created: facility-approved" || echo "Exists:  facility-approved"

gh label create "facility-ready" \
  --description "Facility branch created and ready for watchdog" \
  --color "1d76db" \
  --repo "$REPO" 2>/dev/null && echo "Created: facility-ready" || echo "Exists:  facility-ready"

echo "Done."
