#!/usr/bin/env node
/**
 * One-shot fleet-monitoring activation:
 *   1. Find or create the "FLEET" Workers KV namespace.
 *   2. Write its id into wrangler.toml as the `FLEET` binding (idempotent).
 *   3. Deploy the Worker (unless --no-deploy).
 *
 * Usage:
 *   node cloudflare/setup-kv.mjs            # create/bind + deploy
 *   node cloudflare/setup-kv.mjs --no-deploy
 *
 * Reads Cloudflare credentials from cloudflare/credentials.env, exactly like
 * cloudflare/run.mjs.
 */
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "..");
const credFile = join(__dirname, "credentials.env");
const wranglerToml = join(repoRoot, "wrangler.toml");

const BINDING = "FLEET";

function loadCredentials() {
  if (!existsSync(credFile)) {
    console.error(`Missing ${credFile}`);
    console.error("  copy cloudflare/credentials.example.env cloudflare/credentials.env");
    process.exit(1);
  }
  const env = { ...process.env };
  for (const line of readFileSync(credFile, "utf8").split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    const eq = t.indexOf("=");
    if (eq < 1) continue;
    const key = t.slice(0, eq).trim();
    let val = t.slice(eq + 1).trim();
    if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
    env[key] = val;
  }
  if (!env.CLOUDFLARE_API_TOKEN || !env.CLOUDFLARE_ACCOUNT_ID) {
    console.error("Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in cloudflare/credentials.env");
    process.exit(1);
  }
  return env;
}

function wrangler(args, { capture = false } = {}) {
  return spawnSync("npx", ["wrangler", ...args], {
    env,
    cwd: repoRoot,
    shell: true,
    encoding: "utf8",
    stdio: capture ? "pipe" : "inherit",
  });
}

// KV namespace ids are 32 lowercase hex chars.
function parseNamespaceId(text) {
  const m = String(text || "").match(/(?:"id"\s*:\s*"|id\s*=\s*")([0-9a-f]{32})/i);
  return m ? m[1].toLowerCase() : null;
}

function findExistingId() {
  const r = wrangler(["kv", "namespace", "list"], { capture: true });
  const out = (r.stdout || "") + (r.stderr || "");
  // wrangler prints a JSON array somewhere in stdout; extract it defensively.
  const start = out.indexOf("[");
  const end = out.lastIndexOf("]");
  if (start === -1 || end === -1) return null;
  let list;
  try { list = JSON.parse(out.slice(start, end + 1)); } catch { return null; }
  const match = list.find(
    (n) => n && typeof n.title === "string" && (n.title === BINDING || n.title.endsWith(BINDING)),
  );
  return match ? match.id : null;
}

function createNamespace() {
  console.log(`[kv] Creating Workers KV namespace "${BINDING}"...`);
  const r = wrangler(["kv", "namespace", "create", BINDING], { capture: true });
  const out = (r.stdout || "") + (r.stderr || "");
  process.stdout.write(out);
  if (r.status !== 0) {
    console.error("[kv] wrangler kv namespace create failed (see output above).");
    console.error("[kv] Make sure your API token includes 'Workers KV Storage: Edit'.");
    process.exit(1);
  }
  return parseNamespaceId(out);
}

/**
 * Ensure wrangler.toml has an active [[kv_namespaces]] block binding FLEET to
 * `id`. Replaces the commented placeholder and updates an existing id in place.
 */
function patchWranglerToml(id) {
  let toml = readFileSync(wranglerToml, "utf8");
  const block = `[[kv_namespaces]]\nbinding = "${BINDING}"\nid = "${id}"`;

  // 1. Already-active (uncommented) block for this binding → refresh the id.
  //    Anchored to the start of a line so it never matches the commented
  //    "# [[kv_namespaces]]" placeholder.
  const activeRe = new RegExp(
    `(^|\\n)\\[\\[kv_namespaces\\]\\]\\s*\\nbinding\\s*=\\s*"${BINDING}"\\s*\\nid\\s*=\\s*"[^"]*"`,
  );
  if (activeRe.test(toml)) {
    toml = toml.replace(activeRe, `$1${block}`);
    writeFileSync(wranglerToml, toml);
    return "updated";
  }

  // 2. Remove the commented placeholder block (3 leading-# lines), if present.
  const commentedRe = /#\s*\[\[kv_namespaces\]\]\s*\n#\s*binding\s*=\s*"FLEET"\s*\n#\s*id\s*=\s*"[^"]*"\s*\n/;
  const hadPlaceholder = commentedRe.test(toml);
  if (hadPlaceholder) toml = toml.replace(commentedRe, "");

  // 3. Append the active block.
  toml = toml.replace(/\s*$/, "\n") + "\n" + block + "\n";
  writeFileSync(wranglerToml, toml);
  return hadPlaceholder ? "uncommented" : "appended";
}

const env = loadCredentials();
const noDeploy = process.argv.includes("--no-deploy");

let id = findExistingId();
if (id) {
  console.log(`[kv] Found existing "${BINDING}" namespace: ${id}`);
} else {
  id = createNamespace();
  if (!id) {
    console.error("[kv] Could not parse the namespace id from wrangler output.");
    console.error("[kv] Run 'npx wrangler kv namespace list' and add the id to wrangler.toml manually.");
    process.exit(1);
  }
  console.log(`[kv] Created "${BINDING}" namespace: ${id}`);
}

const action = patchWranglerToml(id);
console.log(`[kv] wrangler.toml binding ${action} (FLEET = ${id}).`);

if (noDeploy) {
  console.log("[kv] --no-deploy set; skipping deploy. Run 'npm run worker:deploy' when ready.");
  process.exit(0);
}

console.log("[kv] Deploying Worker with fleet monitoring enabled...");
const d = wrangler(["deploy"]);
if (d.status !== 0) process.exit(d.status ?? 1);
console.log("[kv] Done. Monitoring + control + revocation + audit are now live.");
