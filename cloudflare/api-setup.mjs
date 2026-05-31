#!/usr/bin/env node
/**
 * Wrangler-free fleet activation over the Cloudflare REST API.
 *
 *   node cloudflare/api-setup.mjs inspect   # show live Worker bindings (redacted)
 *   node cloudflare/api-setup.mjs deploy     # create+bind FLEET KV, deploy code, set cron
 *
 * Why: this repo's machines may not have npm/npx/wrangler. This script only
 * needs Node 18+ (global fetch/FormData/Blob) and the same credentials.env.
 *
 * Safety: a Worker script upload replaces the binding list, so we GET the live
 * settings first and re-send every existing binding. Secret values are never
 * returned by the API, so we preserve them with metadata.keep_bindings
 * (["secret_text","secret_key"]); all other bindings (plain_text vars, KV, etc.)
 * are re-sent verbatim. Net effect: add the FLEET KV binding + ship new code
 * without disturbing GITHUB_APP_PRIVATE_KEY, INSTALL_TICKET_KEY, vars, etc.
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "..");
const credFile = join(__dirname, "credentials.env");
const wranglerToml = join(repoRoot, "wrangler.toml");
const workerFile = join(repoRoot, "cloudflare", "worker.js");

const SCRIPT = "rosetta";
const MAIN_MODULE = "worker.js";
const COMPAT_DATE = "2024-01-01";
const KV_BINDING = "FLEET";
const KV_TITLE = "rosetta-FLEET";
const CRON = "*/15 * * * *";
const API = "https://api.cloudflare.com/client/v4";

function loadCredentials() {
  if (!existsSync(credFile)) {
    console.error(`Missing ${credFile} (copy credentials.example.env).`);
    process.exit(1);
  }
  const env = {};
  for (const line of readFileSync(credFile, "utf8").split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    const eq = t.indexOf("=");
    if (eq < 1) continue;
    let val = t.slice(eq + 1).trim();
    if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
    env[t.slice(0, eq).trim()] = val;
  }
  if (!env.CLOUDFLARE_API_TOKEN || !env.CLOUDFLARE_ACCOUNT_ID) {
    console.error("Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in credentials.env");
    process.exit(1);
  }
  return env;
}

const env = loadCredentials();
const ACCT = env.CLOUDFLARE_ACCOUNT_ID;
const TOKEN = env.CLOUDFLARE_API_TOKEN;
const authHeaders = { Authorization: `Bearer ${TOKEN}` };

async function cf(path, init = {}) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { ...authHeaders, ...(init.headers || {}) },
  });
  const text = await res.text();
  let json;
  try { json = JSON.parse(text); } catch { json = { raw: text }; }
  return { ok: res.ok, status: res.status, json };
}

async function findOrCreateKv() {
  const list = await cf(`/accounts/${ACCT}/storage/kv/namespaces?per_page=100`);
  if (!list.ok) {
    console.error(`[kv] list failed (HTTP ${list.status}):`, JSON.stringify(list.json.errors || list.json));
    process.exit(1);
  }
  const existing = (list.json.result || []).find(
    (n) => n.title === KV_TITLE || n.title === KV_BINDING || (n.title || "").endsWith(KV_BINDING),
  );
  if (existing) {
    console.log(`[kv] Found existing namespace "${existing.title}": ${existing.id}`);
    return existing.id;
  }
  const created = await cf(`/accounts/${ACCT}/storage/kv/namespaces`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: KV_TITLE }),
  });
  if (!created.ok) {
    console.error(`[kv] create failed (HTTP ${created.status}):`, JSON.stringify(created.json.errors || created.json));
    console.error("[kv] Ensure the API token has 'Workers KV Storage: Edit'.");
    process.exit(1);
  }
  console.log(`[kv] Created namespace "${KV_TITLE}": ${created.json.result.id}`);
  return created.json.result.id;
}

async function getSettings() {
  const r = await cf(`/accounts/${ACCT}/workers/scripts/${SCRIPT}/settings`);
  if (!r.ok) {
    if (r.status === 404) return null; // script not deployed yet
    console.error(`[deploy] get settings failed (HTTP ${r.status}):`, JSON.stringify(r.json.errors || r.json));
    process.exit(1);
  }
  return r.json.result;
}

function redactBinding(b) {
  const safe = { type: b.type, name: b.name };
  if (b.type === "kv_namespace") safe.namespace_id = b.namespace_id;
  if (b.type === "plain_text") safe.text = (b.text || "").slice(0, 24) + ((b.text || "").length > 24 ? "…" : "");
  return safe;
}

function patchWranglerToml(id) {
  let toml = readFileSync(wranglerToml, "utf8");
  const block = `[[kv_namespaces]]\nbinding = "${KV_BINDING}"\nid = "${id}"`;
  const activeRe = new RegExp(
    `(^|\\n)\\[\\[kv_namespaces\\]\\]\\s*\\nbinding\\s*=\\s*"${KV_BINDING}"\\s*\\nid\\s*=\\s*"[^"]*"`,
  );
  if (activeRe.test(toml)) {
    writeFileSync(wranglerToml, toml.replace(activeRe, `$1${block}`));
    return "updated";
  }
  const commentedRe = /#\s*\[\[kv_namespaces\]\]\s*\n#\s*binding\s*=\s*"FLEET"\s*\n#\s*id\s*=\s*"[^"]*"\s*\n/;
  const had = commentedRe.test(toml);
  if (had) toml = toml.replace(commentedRe, "");
  toml = toml.replace(/\s*$/, "\n") + "\n" + block + "\n";
  writeFileSync(wranglerToml, toml);
  return had ? "uncommented" : "appended";
}

async function deploy() {
  const id = await findOrCreateKv();
  const action = patchWranglerToml(id);
  console.log(`[kv] wrangler.toml binding ${action} (FLEET = ${id}).`);

  const settings = await getSettings();
  const liveBindings = (settings && settings.bindings) || [];
  console.log(`[deploy] live bindings: ${liveBindings.map((b) => `${b.name}(${b.type})`).join(", ") || "none"}`);

  // Preserve every non-secret binding verbatim; secrets are inherited via
  // keep_bindings since their values aren't returned by the API.
  const SECRET_TYPES = new Set(["secret_text", "secret_key"]);
  const preserved = liveBindings.filter(
    (b) => !SECRET_TYPES.has(b.type) && !(b.type === "kv_namespace" && b.name === KV_BINDING),
  );

  // Only seed ALLOWED_ORIGIN on a brand-new script. If it already exists (here
  // it's a secret_text preserved via keep_bindings), do NOT re-add it as a
  // plain_text var — that would collide with the kept binding.
  if (!liveBindings.some((b) => b.name === "ALLOWED_ORIGIN")) {
    preserved.push({ type: "plain_text", name: "ALLOWED_ORIGIN", text: "https://johntrue15.github.io" });
  }
  const bindings = [...preserved, { type: "kv_namespace", name: KV_BINDING, namespace_id: id }];

  const metadata = {
    main_module: MAIN_MODULE,
    compatibility_date: (settings && settings.compatibility_date) || COMPAT_DATE,
    bindings,
    keep_bindings: ["secret_text", "secret_key"],
  };
  if (settings && settings.compatibility_flags && settings.compatibility_flags.length) {
    metadata.compatibility_flags = settings.compatibility_flags;
  }

  console.log("[deploy] sending bindings:", JSON.stringify(bindings.map(redactBinding)));
  console.log("[deploy] keep_bindings:", JSON.stringify(metadata.keep_bindings));

  const code = readFileSync(workerFile, "utf8");
  const form = new FormData();
  form.set("metadata", new Blob([JSON.stringify(metadata)], { type: "application/json" }));
  form.set(MAIN_MODULE, new Blob([code], { type: "application/javascript+module" }), MAIN_MODULE);

  const up = await cf(`/accounts/${ACCT}/workers/scripts/${SCRIPT}`, { method: "PUT", body: form });
  if (!up.ok) {
    console.error(`[deploy] script upload failed (HTTP ${up.status}):`, JSON.stringify(up.json.errors || up.json));
    process.exit(1);
  }
  console.log("[deploy] Worker code + FLEET binding deployed.");

  // Cron triggers are managed separately from the script upload.
  const sched = await cf(`/accounts/${ACCT}/workers/scripts/${SCRIPT}/schedules`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify([{ cron: CRON }]),
  });
  if (sched.ok) console.log(`[deploy] cron schedule set: ${CRON}`);
  else console.warn(`[deploy] cron set failed (HTTP ${sched.status}) — set it in the dashboard if needed.`);

  console.log("[deploy] Done. Monitoring + control + revocation + audit are live.");
}

const cmd = process.argv[2] || "deploy";
if (cmd === "inspect") {
  const s = await getSettings();
  if (!s) { console.log("[inspect] script not deployed yet."); process.exit(0); }
  console.log("compatibility_date:", s.compatibility_date);
  console.log("compatibility_flags:", JSON.stringify(s.compatibility_flags || []));
  console.log("bindings:");
  for (const b of s.bindings || []) console.log("  -", JSON.stringify(redactBinding(b)));
} else if (cmd === "deploy") {
  await deploy();
} else {
  console.error("Usage: node cloudflare/api-setup.mjs [inspect|deploy]");
  process.exit(1);
}
