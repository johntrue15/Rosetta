#!/usr/bin/env node
/**
 * Cross-platform wrapper: loads cloudflare/credentials.env then runs wrangler.
 * Usage: node cloudflare/run.mjs [deploy|secrets|dev]
 */
import { spawnSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "..");
const credFile = join(__dirname, "credentials.env");

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
    console.error("Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in credentials.env");
    process.exit(1);
  }
  return env;
}

const cmd = process.argv[2] || "deploy";
const env = loadCredentials();
const devVars = join(repoRoot, ".dev.vars");

function wrangler(args) {
  const r = spawnSync("npx", ["wrangler", ...args], { stdio: "inherit", env, cwd: repoRoot, shell: true });
  process.exit(r.status ?? 1);
}

switch (cmd) {
  case "deploy":
    wrangler(["deploy"]);
    break;
  case "secrets":
    if (!existsSync(devVars)) {
      console.error(`Missing ${devVars} — copy .dev.vars.example to .dev.vars`);
      process.exit(1);
    }
    wrangler(["secret", "bulk", devVars]);
    break;
  case "dev":
    wrangler(["dev"]);
    break;
  default:
    console.error("Usage: node cloudflare/run.mjs [deploy|secrets|dev]");
    process.exit(1);
}
