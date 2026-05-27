# Per-facility companion repo template

The Cloudflare Worker (`cloudflare/worker.js`) creates one
`rosetta-facility-<slug>` private repository per facility and seeds it with the
workflows in `.github/workflows/` plus a `README.md`.

These files are kept under `templates/facility-repo/` for visibility and code
review. The Worker keeps its own inline copies (in
`deployWorkflowYaml()` / `updateWorkflowYaml()` / `companionReadme()`) so that
seeding a new companion repo is a single-step API call — no main-repo round
trip required.

Whenever you change one of these templates, also update the matching template
function in `cloudflare/worker.js`. A drift-detection step is on the manual
e2e checklist in `edge/README.md`.
