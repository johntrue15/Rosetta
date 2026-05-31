/**
 * Rosetta Upload Worker
 *
 * Backs two flows:
 *
 *   1. Browser OAuth for the Setup-Facility wizard (legacy GET handler at /).
 *      The client secret never leaves the Worker.
 *
 *   2. Device-code flow + GitHub-App-backed self-service install for the
 *      per-facility self-hosted runner + Rosetta Watchdog.
 *
 * Required environment variables (Cloudflare dashboard / wrangler secrets):
 *   GITHUB_CLIENT_ID         OAuth client id of the "Rosetta Upload" app
 *   GITHUB_CLIENT_SECRET     OAuth client secret (browser OAuth only)
 *   GITHUB_REDIRECT_URI      This Worker's URL (browser OAuth callback)
 *   ALLOWED_ORIGIN           https://johntrue15.github.io
 *   GITHUB_APP_ID            Numeric App id for "Rosetta Upload"
 *   GITHUB_APP_PRIVATE_KEY   PEM-encoded RSA private key for the App
 *   INSTALL_TICKET_KEY       Random 32+ byte secret used to HMAC install
 *                            tickets handed to the bootstrap script + watchdog
 *   ONBOARD_HMAC_KEY         Shared secret with .github/workflows/facility-onboard.yml
 *                            so the workflow can request companion-repo creation
 *   MAIN_REPO                "johntrue15/Rosetta"
 *   FACILITY_OWNER           "johntrue15"  (account/org that owns the
 *                            rosetta-facility-* private repos)
 *
 * Routes:
 *   GET  /                            Legacy browser OAuth (redirect/callback)
 *   POST /device/init                 Start device-code flow
 *   POST /device/poll                 Poll for device-code completion
 *   POST /facility/create-companion-repo
 *                                     Create + seed rosetta-facility-<slug>
 *   POST /runner/registration-token   Mint runner reg token + install ticket
 *   POST /watchdog/token              Mint short-lived push token for the watchdog
 *   POST /watchdog/heartbeat          Ingest a watchdog status heartbeat (KV); returns commands
 *   POST /watchdog/version            Target version for the facility's channel
 *   POST /facility/status             Single-facility status (auth: install ticket or org member)
 *   POST /facility/data               List uploaded data in the companion repo (ticket or org)
 *   GET  /fleet/status                Org-gated fleet status for the dashboard
 *   POST /fleet/command               Org-gated: queue a control command for a facility
 *   POST /fleet/revoke|unrevoke       Org-gated: revoke/restore an install ticket (kill switch)
 *   POST /fleet/set-channel           Org-gated: set a facility's update channel
 *   GET  /fleet/audit                 Org-gated: recent security/control events for a facility
 *   POST /workflow/dispatch-deploy    Trigger deploy-watchdog.yml (App token)
 *   POST /e2e/cleanup                 Tear down companion repo + facility data + issue
 *   GET  /bootstrap-windows.ps1       PowerShell installer
 *   GET  /bootstrap-unix.sh           Bash installer
 */

const PAGES_ORIGIN = "https://johntrue15.github.io";
const GH_API = "https://api.github.com";
const DEFAULT_MAIN_REPO = "johntrue15/Rosetta";
const DEFAULT_FACILITY_OWNER = "x-raymetadata";

const INSTALL_TICKET_TTL_SECONDS = 90 * 24 * 60 * 60;
const APP_JWT_TTL_SECONDS = 540;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    try {
      switch (url.pathname) {
        case "/":
          return await handleBrowserOAuth(request, env, url);
        case "/device/init":
          return await handleDeviceInit(request, env);
        case "/device/poll":
          return await handleDevicePoll(request, env);
        case "/facility/create-companion-repo":
          return await handleCreateCompanionRepo(request, env);
        case "/runner/registration-token":
          return await handleRunnerRegistrationToken(request, env);
        case "/watchdog/token":
          return await handleWatchdogToken(request, env);
        case "/watchdog/heartbeat":
          return await handleHeartbeat(request, env);
        case "/watchdog/version":
          return await handleWatchdogVersion(request, env);
        case "/facility/status":
          return await handleFacilityStatus(request, env);
        case "/facility/data":
          return await handleFacilityData(request, env);
        case "/fleet/status":
          return await handleFleetStatus(request, env);
        case "/fleet/command":
          return await handleFleetCommand(request, env);
        case "/fleet/revoke":
          return await handleFleetRevoke(request, env, true);
        case "/fleet/unrevoke":
          return await handleFleetRevoke(request, env, false);
        case "/fleet/set-channel":
          return await handleFleetSetChannel(request, env);
        case "/fleet/audit":
          return await handleFleetAudit(request, env);
        case "/deploy/status":
          return await handleDeployStatus(request, env);
        case "/workflow/dispatch-deploy":
          return await handleDispatchDeploy(request, env);
        case "/e2e/cleanup":
          return await handleE2eCleanup(request, env);
        case "/bootstrap-windows.ps1":
          return serveBootstrap(env, "windows");
        case "/bootstrap-unix.sh":
          return serveBootstrap(env, "unix");
        default:
          return jsonResponse({ error: "not_found" }, 404);
      }
    } catch (err) {
      console.log("Worker error:", err && (err.stack || err.message || err));
      return jsonResponse({ error: "internal_error", message: String(err && err.message || err) }, 500);
    }
  },

  // Stale-facility detection. Runs on the cron schedule in wrangler.toml and
  // flags facilities whose watchdog has not sent a heartbeat within
  // STALE_THRESHOLD_SECONDS. No-op until the FLEET KV namespace is configured.
  async scheduled(event, env, ctx) {
    try {
      await detectStaleFacilities(env);
    } catch (err) {
      console.log("Scheduled error:", err && (err.stack || err.message || err));
    }
  },
};

/* ===================================================================== */
/* 1. Legacy browser OAuth                                                */
/* ===================================================================== */

async function handleBrowserOAuth(request, env, url) {
  const clientId = env.GITHUB_CLIENT_ID;
  const clientSecret = env.GITHUB_CLIENT_SECRET;
  const redirectUri = env.GITHUB_REDIRECT_URI;

  if (!url.searchParams.has("code")) {
    const state = crypto.randomUUID();
    const ghUrl = new URL("https://github.com/login/oauth/authorize");
    ghUrl.searchParams.set("client_id", clientId);
    ghUrl.searchParams.set("redirect_uri", redirectUri);
    ghUrl.searchParams.set("scope", "repo");
    ghUrl.searchParams.set("state", state);

    return new Response(null, {
      status: 302,
      headers: { Location: ghUrl.toString(), "Set-Cookie": stateCookie(state) },
    });
  }

  const returnedState = url.searchParams.get("state") ?? "";
  const savedState = parseCookie(request.headers.get("Cookie") ?? "", "gh_oauth_state");
  const clearCookieHeader = { "Set-Cookie": stateCookie("", 0) };

  if (!savedState || savedState !== returnedState) {
    return htmlPage("Security error",
      "<h2>State mismatch</h2><p>Possible CSRF attempt. Please close this window and try again.</p>",
      true, clearCookieHeader);
  }

  let tokenData;
  try {
    const tokenRes = await fetch("https://github.com/login/oauth/access_token", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        client_id: clientId,
        client_secret: clientSecret,
        code: url.searchParams.get("code"),
        redirect_uri: redirectUri,
      }),
    });
    tokenData = await tokenRes.json();
  } catch (err) {
    return htmlPage("Error", `<h2>Token exchange failed</h2><p>${err.message}</p>`, true, clearCookieHeader);
  }

  if (tokenData.error) {
    return htmlPage("Auth error",
      `<h2>${tokenData.error}</h2><p>${tokenData.error_description ?? ""}</p>`,
      true, clearCookieHeader);
  }

  const token = tokenData.access_token;
  const pagesAuth = (env.ALLOWED_ORIGIN || PAGES_ORIGIN) +
    "/Rosetta/docs/auth#token=" + encodeURIComponent(token);

  return new Response(null, {
    status: 302,
    headers: { Location: pagesAuth, ...clearCookieHeader },
  });
}

/* ===================================================================== */
/* 2. Device flow                                                         */
/* ===================================================================== */

async function handleDeviceInit(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);

  const clientId = env.GITHUB_CLIENT_ID;
  const body = await safeJson(request);
  // The install flow needs no scopes; the fleet dashboard asks for "read:org"
  // so /fleet/status can verify org membership with the caller's own token.
  const scope = body && body.scope === "read:org" ? "read:org" : "";
  const res = await fetch("https://github.com/login/device/code", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ client_id: clientId, scope }),
  });
  const data = await res.json();
  return jsonResponse(data, res.status);
}

async function handleDevicePoll(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);

  const body = await safeJson(request);
  if (!body || !body.device_code) {
    return jsonResponse({ error: "missing_device_code" }, 400);
  }

  const res = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      client_id: env.GITHUB_CLIENT_ID,
      device_code: body.device_code,
      grant_type: "urn:ietf:params:oauth:grant-type:device_code",
    }),
  });
  const data = await res.json();
  return jsonResponse(data, res.status);
}

/* ===================================================================== */
/* 3. Companion repo creation                                             */
/* ===================================================================== */

async function handleCreateCompanionRepo(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);

  const body = await safeJson(request);
  if (!body || !body.slug || !body.facility) {
    return jsonResponse({ error: "missing_slug_or_facility" }, 400);
  }

  const slug = sanitizeSlug(body.slug);
  const requester = await authenticateCaller(request, env, body);
  if (!requester.ok) return jsonResponse({ error: requester.error }, requester.status);

  // Untrusted (device-flow) callers may only act on facilities that the
  // maintainer has already approved (data/<slug>/config.yml in the main repo).
  if (!requester.trusted && !(await isApprovedFacility(env, slug))) {
    return jsonResponse({ error: "facility_not_approved", slug }, 403);
  }

  const mainRepo = env.MAIN_REPO || DEFAULT_MAIN_REPO;
  const owner = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  const repoName = `rosetta-facility-${slug}`;

  // Repo creation cannot be scoped to a not-yet-existing repo, so this token is
  // org-scoped with only the permissions needed to create + seed the repo. It
  // is used server-side only and never returned to the caller.
  const installationToken = await mintInstallationToken(env, {
    owner,
    permissions: { administration: "write", contents: "write", workflows: "write" },
  });

  // GitHub Apps can only create repositories inside an Organization
  // (POST /orgs/{org}/repos). Personal user accounts are not supported by the
  // App API — POST /user/repos returns "Resource not accessible by integration".
  if (installationToken.account_type !== "Organization") {
    return jsonResponse({
      error: "owner_not_an_org",
      message: `FACILITY_OWNER "${owner}" is a ${installationToken.account_type} account. ` +
        `GitHub Apps cannot create repositories in personal accounts; the facility ` +
        `owner must be a GitHub Organization with the Rosetta Upload app installed ` +
        `(Administration: read & write).`,
    }, 409);
  }

  const createRes = await fetch(`${GH_API}/orgs/${owner}/repos`, {
    method: "POST",
    headers: githubAppHeaders(installationToken),
    body: JSON.stringify({
      name: repoName,
      description: `Self-hosted runner companion for Rosetta facility: ${body.facility}`,
      private: true,
      auto_init: true,
    }),
  });

  if (createRes.status === 422) {
    console.log(`Companion repo ${owner}/${repoName} already exists`);
  } else if (!createRes.ok) {
    const detail = await createRes.text();
    return jsonResponse({ error: "repo_create_failed", status: createRes.status, detail }, 502);
  }

  await seedCompanionRepo({
    env,
    installationToken,
    owner,
    repoName,
    slug,
    facility: body.facility,
    mainRepo,
  });

  return jsonResponse({
    ok: true,
    companion_repo: `${owner}/${repoName}`,
    requester: requester.login,
  });
}

async function seedCompanionRepo({ env, installationToken, owner, repoName, slug, facility, mainRepo }) {
  const workerUrl = new URL(env.GITHUB_REDIRECT_URI || "https://rosetta.jtrue15.workers.dev");
  const workerOrigin = workerUrl.origin;

  const dataRepo = `${owner}/${repoName}`;
  const templates = {
    ".github/workflows/deploy-watchdog.yml": deployWorkflowYaml({ slug, mainRepo, workerOrigin, dataRepo }),
    ".github/workflows/update-watchdog.yml": updateWorkflowYaml({ slug }),
    "README.md": companionReadme({ slug, facility, mainRepo, owner, repoName }),
  };

  for (const [path, content] of Object.entries(templates)) {
    await putFile({
      installationToken,
      owner,
      repoName,
      path,
      content,
      message: `chore: seed ${path}`,
    });
  }
}

async function putFile({ installationToken, owner, repoName, path, content, message }) {
  const existingRes = await fetch(`${GH_API}/repos/${owner}/${repoName}/contents/${path}`, {
    headers: githubAppHeaders(installationToken),
  });
  let sha;
  if (existingRes.ok) {
    const existing = await existingRes.json();
    sha = existing.sha;
  }

  const body = {
    message,
    content: btoa(unescape(encodeURIComponent(content))),
  };
  if (sha) body.sha = sha;

  const res = await fetch(`${GH_API}/repos/${owner}/${repoName}/contents/${path}`, {
    method: "PUT",
    headers: githubAppHeaders(installationToken),
    body: JSON.stringify(body),
  });
  if (!res.ok && res.status !== 422) {
    const detail = await res.text();
    throw new Error(`putFile ${path} failed: ${res.status} ${detail}`);
  }
}

/* ===================================================================== */
/* 4. Runner registration token + install ticket                          */
/* ===================================================================== */

async function handleRunnerRegistrationToken(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);

  const body = await safeJson(request);
  if (!body || !body.slug) return jsonResponse({ error: "missing_slug" }, 400);

  const slug = sanitizeSlug(body.slug);
  const requester = await authenticateCaller(request, env, body);
  if (!requester.ok) return jsonResponse({ error: requester.error }, requester.status);
  if (requester.slug && sanitizeSlug(requester.slug) !== slug) {
    return jsonResponse({ error: "slug_mismatch" }, 403);
  }
  if (!requester.trusted && !(await isApprovedFacility(env, slug))) {
    return jsonResponse({ error: "facility_not_approved", slug }, 403);
  }

  const owner = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  const repoName = `rosetta-facility-${slug}`;

  // Runner registration needs administration:write, but only on this one repo.
  const installationToken = await mintInstallationToken(env, {
    owner,
    repositories: [repoName],
    permissions: { administration: "write" },
  });

  const tokenRes = await fetch(
    `${GH_API}/repos/${owner}/${repoName}/actions/runners/registration-token`,
    { method: "POST", headers: githubAppHeaders(installationToken) },
  );
  if (!tokenRes.ok) {
    const detail = await tokenRes.text();
    return jsonResponse({ error: "registration_token_failed", detail, status: tokenRes.status }, 502);
  }
  const regToken = await tokenRes.json();

  const installTicket = await signInstallTicket(env, {
    slug,
    sub: requester.login || "anonymous",
    purpose: "install",
    exp: nowSeconds() + INSTALL_TICKET_TTL_SECONDS,
  });

  return jsonResponse({
    registration_token: regToken.token,
    registration_token_expires_at: regToken.expires_at,
    runner_repo_url: `https://github.com/${owner}/${repoName}`,
    runner_label: `facility-${slug}`,
    install_ticket: installTicket,
    install_ticket_expires_at: nowSeconds() + INSTALL_TICKET_TTL_SECONDS,
  });
}

/* ===================================================================== */
/* 5. Watchdog token refresh                                              */
/* ===================================================================== */

async function handleWatchdogToken(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);

  const body = await safeJson(request);
  if (!body || !body.install_ticket) {
    return jsonResponse({ error: "missing_install_ticket" }, 400);
  }

  const verified = await verifyInstallTicket(env, body.install_ticket);
  if (!verified.ok) return jsonResponse({ error: verified.error }, 401);

  const slug = sanitizeSlug(verified.claims.slug || "");
  if (!slug) return jsonResponse({ error: "ticket_missing_slug" }, 400);

  // Machine binding: record the machine_id the ticket is used from. When
  // ENFORCE_MACHINE_BINDING is set, deny a ticket presented from a different
  // machine than first seen (a leaked ticket is then useless elsewhere).
  const machineId = body.machine_id ? String(body.machine_id).slice(0, 80) : null;
  if (machineId) {
    const denied = await enforceMachineBinding(env, slug, machineId);
    if (denied) return jsonResponse({ error: denied }, 403);
  }

  // The watchdog only ever pushes scan data into its own facility's companion
  // repo. The token is scoped to that single repo with contents:write only — it
  // cannot reach the main repo, other facilities, workflows, or org admin.
  const dataRepo = facilityDataRepo(env, slug);
  const installationToken = await mintInstallationToken(env, {
    owner: dataRepo.owner,
    repositories: [dataRepo.name],
    permissions: { contents: "write" },
  });

  return jsonResponse({
    token: installationToken.token,
    expires_at: installationToken.expires_at,
    repo: dataRepo.full,
    upload_path_prefix: "data/",
    facility_slug: slug,
  });
}

/* ===================================================================== */
/* 5b. Fleet monitoring: heartbeat ingest + dashboard read + stale alerts  */
/* ===================================================================== */

const HEARTBEAT_TTL_SECONDS = 30 * 24 * 60 * 60; // keep last-seen for 30 days
const STALE_THRESHOLD_SECONDS = 15 * 60;         // silent longer than this = stale

// Cap the size/shape of what we persist so a compromised or buggy watchdog
// cannot write arbitrary blobs into KV.
function sanitizeHeartbeatStatus(raw) {
  if (!raw || typeof raw !== "object") return {};
  const s = {};
  const str = (v, n = 200) => (v == null ? undefined : String(v).slice(0, n));
  const num = (v) => (typeof v === "number" && isFinite(v) ? v : undefined);
  s.version = str(raw.version, 40);
  s.hostname = str(raw.hostname, 120);
  s.platform = str(raw.platform, 120);
  s.pid = num(raw.pid);
  s.state = str(raw.state, 20);               // "running" | "stopped"
  s.started_at = str(raw.started_at, 40);
  s.last_cycle_at = str(raw.last_cycle_at, 40);
  s.cycle_count = num(raw.cycle_count);
  s.processed = num(raw.processed);
  s.errors = num(raw.errors);
  s.state_count = num(raw.state_count);
  s.polling_interval = num(raw.polling_interval);
  s.repo = str(raw.repo, 140);
  if (Array.isArray(raw.watch_dirs)) {
    s.watch_dirs = raw.watch_dirs.slice(0, 25).map((d) => ({
      path: str(d && d.path, 300),
      ok: !!(d && d.ok),
    }));
  }
  // Drop undefined keys for compactness.
  return JSON.parse(JSON.stringify(s));
}

async function handleHeartbeat(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);

  const body = await safeJson(request);
  if (!body || !body.install_ticket) {
    return jsonResponse({ error: "missing_install_ticket" }, 400);
  }

  const verified = await verifyInstallTicket(env, body.install_ticket);
  if (!verified.ok) return jsonResponse({ error: verified.error }, 401);

  const slug = sanitizeSlug(verified.claims.slug || "");
  if (!slug) return jsonResponse({ error: "ticket_missing_slug" }, 400);

  const serverTime = new Date().toISOString();

  // KV is optional: without it the watchdog still runs, we just can't store
  // status or deliver commands. Acknowledge so the watchdog doesn't error.
  if (!env.FLEET) {
    return jsonResponse({ ok: true, stored: false, reason: "kv_not_configured", server_time: serverTime, commands: [] });
  }

  const machineId = body.machine_id ? String(body.machine_id).slice(0, 80) : null;
  const binding = await checkMachineBinding(env, slug, machineId);

  const record = {
    slug,
    received_at: serverTime,
    ip: request.headers.get("CF-Connecting-IP") || null,
    machine_id: machineId,
    binding: binding.state,            // "first" | "match" | "conflict" | "unknown"
    status: sanitizeHeartbeatStatus(body.status),
  };
  await env.FLEET.put(`hb:${slug}`, JSON.stringify(record), {
    expirationTtl: HEARTBEAT_TTL_SECONDS,
  });

  // Pop acked commands, then return whatever is still pending.
  const acked = Array.isArray(body.acked_command_ids) ? body.acked_command_ids.map(String) : [];
  const commands = await popAndListCommands(env, slug, acked);

  return jsonResponse({
    ok: true,
    stored: true,
    server_time: serverTime,
    binding: binding.state,
    commands,
  });
}

/* ----------------------------- machine binding ----------------------------- */

// Records the first machine_id seen for a facility and compares subsequent
// ones. A mismatch ("conflict") means the same install ticket is being used
// from a different machine — surfaced in the dashboard and, when
// ENFORCE_MACHINE_BINDING is set, rejected at token-mint time.
async function checkMachineBinding(env, slug, machineId) {
  if (!env.FLEET || !machineId) return { state: "unknown" };
  const key = `machine:${slug}`;
  const existing = await env.FLEET.get(key);
  if (!existing) {
    await env.FLEET.put(key, JSON.stringify({ machine_id: machineId, first_seen: new Date().toISOString() }));
    await recordAudit(env, slug, { type: "machine_first_seen", machine_id: machineId });
    return { state: "first" };
  }
  let rec;
  try { rec = JSON.parse(existing); } catch { rec = {}; }
  if (rec.machine_id === machineId) return { state: "match" };
  await recordAudit(env, slug, { type: "machine_conflict", expected: rec.machine_id, got: machineId });
  return { state: "conflict", expected: rec.machine_id };
}

async function enforceMachineBinding(env, slug, machineId) {
  // Returns null if allowed, or an error string if it should be denied.
  if (!env.FLEET || !truthy(env.ENFORCE_MACHINE_BINDING)) return null;
  const b = await checkMachineBinding(env, slug, machineId);
  if (b.state === "conflict") return "machine_binding_conflict";
  return null;
}

/* ------------------------------- audit log -------------------------------- */

const AUDIT_CAP = 100;

async function recordAudit(env, slug, event) {
  if (!env.FLEET) return;
  const key = `audit:${sanitizeSlug(slug)}`;
  let list = [];
  try { list = JSON.parse((await env.FLEET.get(key)) || "[]"); } catch { list = []; }
  list.push({ ts: new Date().toISOString(), ...event });
  if (list.length > AUDIT_CAP) list = list.slice(-AUDIT_CAP);
  await env.FLEET.put(key, JSON.stringify(list), { expirationTtl: HEARTBEAT_TTL_SECONDS });
}

async function handleFleetAudit(request, env) {
  if (request.method !== "GET") return jsonResponse({ error: "method_not_allowed" }, 405);
  const member = await requireOrgMember(request, env);
  if (!member.ok) return jsonResponse({ error: member.error }, member.status);
  const url = new URL(request.url);
  const slug = sanitizeSlug(url.searchParams.get("slug") || "");
  if (!slug) return jsonResponse({ error: "missing_slug" }, 400);
  if (!env.FLEET) return jsonResponse({ slug, events: [], kv_configured: false });
  let events = [];
  try { events = JSON.parse((await env.FLEET.get(`audit:${slug}`)) || "[]"); } catch { events = []; }
  return jsonResponse({ slug, events: events.reverse(), kv_configured: true });
}

/* ----------------------------- command queue ------------------------------ */

const COMMAND_TTL_SECONDS = 7 * 24 * 60 * 60;
const ALLOWED_COMMANDS = new Set([
  "pause", "resume", "run-once", "reload-config", "update-now", "restart", "configure",
]);

async function popAndListCommands(env, slug, ackedIds) {
  const key = `cmd:${slug}`;
  let list = [];
  try { list = JSON.parse((await env.FLEET.get(key)) || "[]"); } catch { list = []; }
  if (ackedIds.length) {
    const before = list.length;
    list = list.filter((c) => !ackedIds.includes(String(c.id)));
    if (list.length !== before) {
      await env.FLEET.put(key, JSON.stringify(list), { expirationTtl: COMMAND_TTL_SECONDS });
    }
  }
  return list;
}

async function handleFleetCommand(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);
  const body = await safeJson(request);
  if (!body || !body.type) return jsonResponse({ error: "missing_type" }, 400);
  // Org members can command any facility; a facility operator can command their
  // own (slug derived from their install ticket). All commands are
  // self-management (pause/resume/run-once/update/restart/...), so ticket auth
  // scoped to the same slug is safe.
  const authz = await authorizeFacility(request, env, body);
  if (!authz.ok) return jsonResponse({ error: authz.error }, authz.status);
  const slug = authz.slug;
  const type = String(body.type);
  if (!ALLOWED_COMMANDS.has(type)) return jsonResponse({ error: "unknown_command", type }, 400);
  if (!env.FLEET) return jsonResponse({ error: "kv_not_configured" }, 503);

  const cmd = {
    id: (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()),
    type,
    args: body.args && typeof body.args === "object" ? body.args : {},
    created_at: new Date().toISOString(),
    by: authz.login || "unknown",
  };
  const key = `cmd:${slug}`;
  let list = [];
  try { list = JSON.parse((await env.FLEET.get(key)) || "[]"); } catch { list = []; }
  // De-dupe: at most one pending command of each type (latest wins).
  list = list.filter((c) => c.type !== type);
  list.push(cmd);
  await env.FLEET.put(key, JSON.stringify(list), { expirationTtl: COMMAND_TTL_SECONDS });
  await recordAudit(env, slug, { type: "command_queued", command: type, by: cmd.by });

  return jsonResponse({ ok: true, slug, command: cmd });
}

/* --------------------------- revocation kill switch ------------------------ */

async function handleFleetRevoke(request, env, revoke) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);
  const member = await requireOrgMember(request, env);
  if (!member.ok) return jsonResponse({ error: member.error }, member.status);

  const body = await safeJson(request);
  if (!body || (!body.slug && !body.jti)) return jsonResponse({ error: "missing_slug_or_jti" }, 400);
  if (!env.FLEET) return jsonResponse({ error: "kv_not_configured" }, 503);

  const targets = [];
  if (body.slug) targets.push(`revoked:slug:${sanitizeSlug(body.slug)}`);
  if (body.jti) targets.push(`revoked:jti:${String(body.jti).slice(0, 80)}`);

  for (const key of targets) {
    if (revoke) {
      await env.FLEET.put(key, JSON.stringify({ at: new Date().toISOString(), by: member.login || "unknown" }));
    } else {
      await env.FLEET.delete(key);
    }
  }
  await recordAudit(env, sanitizeSlug(body.slug || "unknown"), {
    type: revoke ? "ticket_revoked" : "ticket_unrevoked",
    jti: body.jti || null,
    by: member.login || "unknown",
  });
  return jsonResponse({ ok: true, revoked: revoke, targets });
}

/* ------------------------------- update channel ---------------------------- */

const DEFAULT_CHANNEL = "stable";

async function getChannelConfig(env, slug) {
  const fallback = { channel: DEFAULT_CHANNEL, pin_version: null };
  if (!env.FLEET) return fallback;
  try {
    const raw = await env.FLEET.get(`channel:${slug}`);
    if (!raw) return fallback;
    const c = JSON.parse(raw);
    return { channel: c.channel || DEFAULT_CHANNEL, pin_version: c.pin_version || null };
  } catch { return fallback; }
}

async function handleFleetSetChannel(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);
  const member = await requireOrgMember(request, env);
  if (!member.ok) return jsonResponse({ error: member.error }, member.status);

  const body = await safeJson(request);
  if (!body || !body.slug || !body.channel) return jsonResponse({ error: "missing_slug_or_channel" }, 400);
  const channel = String(body.channel);
  if (!["stable", "beta", "pinned"].includes(channel)) return jsonResponse({ error: "bad_channel" }, 400);
  if (!env.FLEET) return jsonResponse({ error: "kv_not_configured" }, 503);

  const slug = sanitizeSlug(body.slug);
  const cfg = { channel, pin_version: channel === "pinned" ? String(body.pin_version || "").slice(0, 40) : null };
  await env.FLEET.put(`channel:${slug}`, JSON.stringify(cfg));
  await recordAudit(env, slug, { type: "channel_set", channel, pin_version: cfg.pin_version, by: member.login || "unknown" });
  return jsonResponse({ ok: true, slug, ...cfg });
}

// Tells a watchdog which version it should be running, based on its facility's
// channel. Source of truth = GitHub Releases on the main repo:
//   stable = latest non-prerelease, beta = latest prerelease,
//   pinned  = the exact tag the maintainer set.
// Falls back to tracking a branch (STABLE_REF / main) when no releases exist.
async function handleWatchdogVersion(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);
  const body = await safeJson(request);
  if (!body || !body.install_ticket) return jsonResponse({ error: "missing_install_ticket" }, 400);
  const verified = await verifyInstallTicket(env, body.install_ticket);
  if (!verified.ok) return jsonResponse({ error: verified.error }, 401);
  const slug = sanitizeSlug(verified.claims.slug || "");
  if (!slug) return jsonResponse({ error: "ticket_missing_slug" }, 400);

  const { channel, pin_version } = await getChannelConfig(env, slug);
  const target = await resolveTargetVersion(env, channel, pin_version);
  return jsonResponse({ slug, channel, ...target });
}

async function resolveTargetVersion(env, channel, pinVersion) {
  const mainRepo = env.MAIN_REPO || DEFAULT_MAIN_REPO;
  const ghHeaders = { Accept: "application/vnd.github+json", "User-Agent": "rosetta-upload-worker" };

  const tagTarget = (tag, body) => ({
    version: normalizeVersion(tag),
    ref: tag,
    zip_url: `https://github.com/${mainRepo}/archive/refs/tags/${encodeURIComponent(tag)}.zip`,
    sha256: parseSha256(body),
    source: "release",
  });

  try {
    if (channel === "pinned" && pinVersion) {
      const res = await fetch(`${GH_API}/repos/${mainRepo}/releases/tags/${encodeURIComponent(pinVersion)}`, { headers: ghHeaders });
      if (res.ok) { const r = await res.json(); return tagTarget(r.tag_name, r.body); }
      // Pinned to a bare tag/branch with no release.
      return { version: normalizeVersion(pinVersion), ref: pinVersion,
        zip_url: `https://github.com/${mainRepo}/archive/refs/tags/${encodeURIComponent(pinVersion)}.zip`, sha256: null, source: "pinned-tag" };
    }

    if (channel === "beta") {
      const res = await fetch(`${GH_API}/repos/${mainRepo}/releases?per_page=20`, { headers: ghHeaders });
      if (res.ok) {
        const rels = await res.json();
        const pre = rels.find((r) => r.prerelease && !r.draft);
        if (pre) return tagTarget(pre.tag_name, pre.body);
        const stable = rels.find((r) => !r.prerelease && !r.draft);
        if (stable) return tagTarget(stable.tag_name, stable.body);
      }
    } else {
      // stable
      const res = await fetch(`${GH_API}/repos/${mainRepo}/releases/latest`, { headers: ghHeaders });
      if (res.ok) { const r = await res.json(); return tagTarget(r.tag_name, r.body); }
    }
  } catch (_) { /* fall through to branch tracking */ }

  // No releases yet: track a branch. No auto-update signal (version "main"),
  // but an explicit update-now command can still force a ref.
  const ref = env.STABLE_REF || "main";
  return {
    version: ref,
    ref,
    zip_url: `https://github.com/${mainRepo}/archive/refs/heads/${encodeURIComponent(ref)}.zip`,
    sha256: null,
    source: "branch",
  };
}

function normalizeVersion(tag) {
  // "watchdog-v0.2.1" / "v0.2.1" -> "0.2.1"; leave non-semver tags as-is.
  const m = String(tag || "").match(/(\d+\.\d+\.\d+)/);
  return m ? m[1] : String(tag || "");
}

function parseSha256(body) {
  if (!body) return null;
  const m = String(body).match(/sha256[:=\s]+([a-f0-9]{64})/i);
  return m ? m[1].toLowerCase() : null;
}

function truthy(v) {
  return v === true || v === 1 || /^(1|true|yes|on)$/i.test(String(v || ""));
}

// Read-only fleet status for the org dashboard. Gated to members of the
// facility-owner org: the dashboard runs device OAuth with `read:org` and we
// verify membership with the caller's own token (no extra App permission).
async function handleFleetStatus(request, env) {
  if (request.method !== "GET") return jsonResponse({ error: "method_not_allowed" }, 405);

  const member = await requireOrgMember(request, env);
  if (!member.ok) return jsonResponse({ error: member.error }, member.status);

  if (!env.FLEET) {
    return jsonResponse({ facilities: [], generated_at: new Date().toISOString(), kv_configured: false });
  }

  const now = Date.now();
  const facilities = [];
  let cursor;
  do {
    const page = await env.FLEET.list({ prefix: "hb:", cursor });
    for (const key of page.keys) {
      const raw = await env.FLEET.get(key.name);
      if (!raw) continue;
      let rec;
      try { rec = JSON.parse(raw); } catch { continue; }
      const seen = Date.parse(rec.received_at || "") || 0;
      const ageSeconds = seen ? Math.round((now - seen) / 1000) : null;
      const stale = ageSeconds == null || ageSeconds > STALE_THRESHOLD_SECONDS;
      const stopped = rec.status && rec.status.state === "stopped";
      const ch = await getChannelConfig(env, rec.slug);
      facilities.push({
        slug: rec.slug,
        received_at: rec.received_at,
        age_seconds: ageSeconds,
        health: stopped ? "stopped" : (stale ? "stale" : "online"),
        ip: rec.ip || null,
        machine_id: rec.machine_id || null,
        binding: rec.binding || "unknown",
        channel: ch.channel,
        pin_version: ch.pin_version,
        status: rec.status || {},
      });
    }
    cursor = page.cursor;
  } while (cursor);

  facilities.sort((a, b) => (a.slug || "").localeCompare(b.slug || ""));
  return jsonResponse({
    facilities,
    generated_at: new Date().toISOString(),
    stale_threshold_seconds: STALE_THRESHOLD_SECONDS,
    kv_configured: true,
  });
}

async function requireOrgMember(request, env) {
  const auth = request.headers.get("Authorization") || "";
  if (!auth.startsWith("Bearer ")) return { ok: false, status: 401, error: "missing_bearer_token" };
  const userToken = auth.slice(7).trim();
  const org = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;

  const res = await fetch(`${GH_API}/user/memberships/orgs/${org}`, {
    headers: {
      Authorization: `Bearer ${userToken}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "rosetta-upload-worker",
    },
  });
  if (res.status === 401) return { ok: false, status: 401, error: "invalid_user_token" };
  if (!res.ok) {
    // 403 usually means the token lacks the read:org scope; 404 = not a member.
    return { ok: false, status: 403, error: "not_org_member_or_missing_read_org_scope" };
  }
  const data = await res.json();
  if (data.state !== "active") return { ok: false, status: 403, error: "org_membership_inactive" };
  return { ok: true, login: data.user && data.user.login, role: data.role, org };
}

// Authorizes access to a single facility's status/data/control. Two callers:
//   - an org member (bearer token) acting on any facility (slug from body), or
//   - a facility operator presenting their install ticket (slug from the
//     ticket; this is how the post-install wizard manages its own watchdog).
async function authorizeFacility(request, env, body) {
  const auth = request.headers.get("Authorization") || "";
  if (auth.startsWith("Bearer ")) {
    const m = await requireOrgMember(request, env);
    if (!m.ok) return { ok: false, status: m.status, error: m.error };
    const slug = sanitizeSlug((body && body.slug) || "");
    if (!slug) return { ok: false, status: 400, error: "missing_slug" };
    return { ok: true, via: "org", login: m.login, slug };
  }
  if (body && body.install_ticket) {
    const v = await verifyInstallTicket(env, body.install_ticket);
    if (!v.ok) return { ok: false, status: 401, error: v.error };
    const slug = sanitizeSlug(v.claims.slug || "");
    if (!slug) return { ok: false, status: 400, error: "ticket_missing_slug" };
    if (body.slug && sanitizeSlug(body.slug) !== slug) return { ok: false, status: 403, error: "slug_mismatch" };
    return { ok: true, via: "ticket", login: v.claims.sub || "install-ticket", slug };
  }
  return { ok: false, status: 401, error: "missing_authentication" };
}

// Single-facility status for the post-install wizard dashboard (and the fleet
// dashboard's drill-in). Authorized by install ticket or org membership.
async function handleFacilityStatus(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);
  const body = await safeJson(request);
  const authz = await authorizeFacility(request, env, body);
  if (!authz.ok) return jsonResponse({ error: authz.error }, authz.status);
  const slug = authz.slug;

  if (!env.FLEET) {
    return jsonResponse({ slug, kv_configured: false, health: "unknown", status: {}, pending_commands: 0 });
  }
  let rec = null;
  try { rec = JSON.parse((await env.FLEET.get(`hb:${slug}`)) || "null"); } catch { rec = null; }
  let pending = [];
  try { pending = JSON.parse((await env.FLEET.get(`cmd:${slug}`)) || "[]"); } catch { pending = []; }
  const ch = await getChannelConfig(env, slug);

  if (!rec) {
    return jsonResponse({
      slug, kv_configured: true, health: "unknown", received_at: null, age_seconds: null,
      channel: ch.channel, pin_version: ch.pin_version, status: {}, pending_commands: pending.length,
    });
  }
  const seen = Date.parse(rec.received_at || "") || 0;
  const ageSeconds = seen ? Math.round((Date.now() - seen) / 1000) : null;
  const stale = ageSeconds == null || ageSeconds > STALE_THRESHOLD_SECONDS;
  const stopped = rec.status && rec.status.state === "stopped";
  return jsonResponse({
    slug,
    kv_configured: true,
    health: stopped ? "stopped" : (stale ? "stale" : "online"),
    received_at: rec.received_at,
    age_seconds: ageSeconds,
    binding: rec.binding || "unknown",
    channel: ch.channel,
    pin_version: ch.pin_version,
    status: rec.status || {},
    pending_commands: pending.length,
  });
}

// Lists what the watchdog has uploaded to its companion repo (data/<slug>/),
// using a read-only App token so the operator (who is not an org member and
// can't read the private repo directly) can still confirm uploads.
async function handleFacilityData(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);
  const body = await safeJson(request);
  const authz = await authorizeFacility(request, env, body);
  if (!authz.ok) return jsonResponse({ error: authz.error }, authz.status);
  const slug = authz.slug;

  const dataRepo = facilityDataRepo(env, slug);
  const installationToken = await mintInstallationToken(env, {
    owner: dataRepo.owner,
    repositories: [dataRepo.name],
    permissions: { contents: "read" },
  });
  const dirPath = `data/${slug}`;
  const treeUrl = `https://github.com/${dataRepo.full}/tree/main/${dirPath}`;

  const res = await fetch(
    `${GH_API}/repos/${dataRepo.full}/contents/${dirPath}?ref=main`,
    { headers: githubAppHeaders(installationToken) },
  );
  if (res.status === 404) {
    return jsonResponse({ slug, repo: dataRepo.full, exists: false, count: 0, files: [], tree_url: treeUrl });
  }
  if (!res.ok) {
    const detail = await res.text();
    return jsonResponse({ error: "contents_failed", status: res.status, detail }, 502);
  }
  const listing = await res.json();
  const isData = (n) => /\.(json|pca|txrm)$/i.test(n) && n !== "config.yml";
  const files = (Array.isArray(listing) ? listing : [])
    .filter((f) => f.type === "file" && isData(f.name))
    .map((f) => ({ name: f.name, size: f.size, html_url: f.html_url, sha: f.sha }))
    .sort((a, b) => a.name.localeCompare(b.name));

  // Latest commit touching the data dir (best-effort).
  let lastCommit = null;
  try {
    const cRes = await fetch(
      `${GH_API}/repos/${dataRepo.full}/commits?path=${encodeURIComponent(dirPath)}&per_page=1`,
      { headers: githubAppHeaders(installationToken) },
    );
    if (cRes.ok) {
      const commits = await cRes.json();
      if (commits[0]) {
        lastCommit = {
          message: commits[0].commit && commits[0].commit.message,
          date: commits[0].commit && commits[0].commit.committer && commits[0].commit.committer.date,
          html_url: commits[0].html_url,
        };
      }
    }
  } catch (_) { /* ignore */ }

  return jsonResponse({
    slug, repo: dataRepo.full, exists: true, count: files.length, files,
    last_commit: lastCommit, tree_url: treeUrl,
  });
}

async function detectStaleFacilities(env) {
  if (!env.FLEET) return;
  const now = Date.now();
  const stale = [];
  let cursor;
  do {
    const page = await env.FLEET.list({ prefix: "hb:", cursor });
    for (const key of page.keys) {
      const raw = await env.FLEET.get(key.name);
      if (!raw) continue;
      let rec;
      try { rec = JSON.parse(raw); } catch { continue; }
      const seen = Date.parse(rec.received_at || "") || 0;
      const ageSeconds = seen ? Math.round((now - seen) / 1000) : null;
      if (ageSeconds == null || ageSeconds > STALE_THRESHOLD_SECONDS) {
        stale.push({ slug: rec.slug, age_seconds: ageSeconds, last_seen: rec.received_at });
      }
    }
    cursor = page.cursor;
  } while (cursor);

  if (!stale.length) return;
  console.log(`Stale facilities (${stale.length}):`, JSON.stringify(stale));

  // Optional Slack alert. Set ALERT_SLACK_WEBHOOK as a Worker secret to enable.
  if (env.ALERT_SLACK_WEBHOOK) {
    const lines = stale.map(
      (s) => `• *${s.slug}* — last seen ${s.last_seen || "never"} (${s.age_seconds == null ? "no heartbeat" : s.age_seconds + "s ago"})`,
    );
    try {
      await fetch(env.ALERT_SLACK_WEBHOOK, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: `:warning: Rosetta watchdog stale (${stale.length}):\n${lines.join("\n")}`,
        }),
      });
    } catch (err) {
      console.log("Slack alert failed:", err && err.message);
    }
  }
}

/* ===================================================================== */
/* 6. Deploy status proxy                                                 */
/* ===================================================================== */

async function handleDeployStatus(request, env) {
  let slug, installTicket;
  if (request.method === "GET") {
    const url = new URL(request.url);
    slug = url.searchParams.get("slug");
    installTicket = url.searchParams.get("install_ticket");
  } else if (request.method === "POST") {
    const body = await safeJson(request);
    if (body) { slug = body.slug; installTicket = body.install_ticket; }
  } else {
    return jsonResponse({ error: "method_not_allowed" }, 405);
  }
  if (!slug || !installTicket) return jsonResponse({ error: "missing_slug_or_install_ticket" }, 400);

  const verified = await verifyInstallTicket(env, installTicket);
  if (!verified.ok) return jsonResponse({ error: verified.error }, 401);
  if (verified.claims.slug && sanitizeSlug(verified.claims.slug) !== sanitizeSlug(slug)) {
    return jsonResponse({ error: "slug_mismatch" }, 403);
  }

  const owner = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  const repoName = `rosetta-facility-${sanitizeSlug(slug)}`;
  const installationToken = await mintInstallationToken(env, {
    owner,
    repositories: [repoName],
    permissions: { actions: "read" },
  });

  const res = await fetch(
    `${GH_API}/repos/${owner}/${repoName}/actions/workflows/deploy-watchdog.yml/runs?per_page=1`,
    { headers: githubAppHeaders(installationToken) },
  );
  if (!res.ok) {
    const detail = await res.text();
    return jsonResponse({ error: "workflow_runs_failed", status: res.status, detail }, 502);
  }
  const data = await res.json();
  const run = (data.workflow_runs && data.workflow_runs[0]) || null;

  return jsonResponse({
    companion_repo: `${owner}/${repoName}`,
    run: run ? {
      id: run.id,
      run_number: run.run_number,
      status: run.status,
      conclusion: run.conclusion,
      html_url: run.html_url,
      created_at: run.created_at,
      updated_at: run.updated_at,
    } : null,
  });
}

/* ===================================================================== */
/* 7. Dispatch deploy workflow (App installation token)                     */
/* ===================================================================== */

async function handleDispatchDeploy(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);

  const body = await safeJson(request);
  if (!body || !body.slug) return jsonResponse({ error: "missing_slug" }, 400);

  const slug = sanitizeSlug(body.slug);
  const requester = await authenticateCaller(request, env, body);
  if (!requester.ok) return jsonResponse({ error: requester.error }, requester.status);
  if (requester.slug && sanitizeSlug(requester.slug) !== slug) {
    return jsonResponse({ error: "slug_mismatch" }, 403);
  }
  if (!requester.trusted && !(await isApprovedFacility(env, slug))) {
    return jsonResponse({ error: "facility_not_approved", slug }, 403);
  }

  const owner = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  const repoName = `rosetta-facility-${slug}`;
  const ref = body.ref || "main";
  const installationToken = await mintInstallationToken(env, {
    owner,
    repositories: [repoName],
    permissions: { actions: "write" },
  });

  const res = await fetch(
    `${GH_API}/repos/${owner}/${repoName}/actions/workflows/deploy-watchdog.yml/dispatches`,
    {
      method: "POST",
      headers: githubAppHeaders(installationToken),
      body: JSON.stringify({ ref, inputs: { ref: body.rosetta_ref || ref } }),
    },
  );
  if (res.status !== 204 && !res.ok) {
    const detail = await res.text();
    return jsonResponse({ error: "dispatch_failed", status: res.status, detail }, 502);
  }
  return jsonResponse({ ok: true, companion_repo: `${owner}/${repoName}`, ref });
}

/* ===================================================================== */
/* 8. E2E cleanup (companion repo, facility dir, issue)                   */
/* ===================================================================== */

async function handleE2eCleanup(request, env) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);

  const body = await safeJson(request);
  if (!body || !body.slug) return jsonResponse({ error: "missing_slug" }, 400);

  const slug = sanitizeSlug(body.slug);
  const requester = await authenticateCaller(request, env, body);
  if (!requester.ok) return jsonResponse({ error: requester.error }, requester.status);
  // Cleanup is destructive (deletes a repo, removes data, deletes issues), so it
  // is restricted to trusted callers: the maintainer onboarding workflow
  // (onboard HMAC) or an install ticket bound to this exact slug. An ordinary
  // device-flow user token can never trigger it.
  if (!requester.trusted) {
    return jsonResponse({ error: "cleanup_requires_trusted_caller" }, 403);
  }
  if (requester.slug && sanitizeSlug(requester.slug) !== slug) {
    return jsonResponse({ error: "slug_mismatch" }, 403);
  }

  const owner = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  const mainRepo = env.MAIN_REPO || DEFAULT_MAIN_REPO;
  const [mainOwner, mainName] = mainRepo.split("/");
  const companionName = `rosetta-facility-${slug}`;
  const results = {};

  // Delete companion repo (ignore 404) — token scoped to that one repo.
  const orgToken = await mintInstallationToken(env, {
    owner,
    repositories: [companionName],
    permissions: { administration: "write" },
  });
  const delRepo = await fetch(`${GH_API}/repos/${owner}/${companionName}`, {
    method: "DELETE",
    headers: githubAppHeaders(orgToken),
  });
  results.companion_repo = delRepo.status === 204 ? "deleted" : `status_${delRepo.status}`;

  // Main-repo cleanup (approval marker dir + onboarding issue) uses a separate
  // token from the main repo's installation, scoped to the main repo with only
  // contents:write + issues:write. This installation is distinct from the org's.
  let mainHeaders;
  try {
    const mainToken = await mintInstallationToken(env, {
      owner: mainOwner,
      repositories: [mainName],
      permissions: { contents: "write", issues: "write" },
    });
    mainHeaders = githubAppHeaders(mainToken);
  } catch (e) {
    results.facility_dir = "skipped_no_main_installation";
  }

  if (mainHeaders) {
    const dirPath = `data/${slug}`;
    const contentsRes = await fetch(
      `${GH_API}/repos/${mainOwner}/${mainName}/contents/${dirPath}?ref=main`,
      { headers: mainHeaders },
    );
    if (contentsRes.ok) {
      const items = await contentsRes.json();
      for (const item of items) {
        if (item.type === "file") {
          await fetch(`${GH_API}/repos/${mainOwner}/${mainName}/contents/${item.path}`, {
            method: "DELETE",
            headers: mainHeaders,
            body: JSON.stringify({
              message: `chore(e2e): remove ${item.path} [skip ci]`,
              sha: item.sha,
              branch: "main",
            }),
          });
        }
      }
      results.facility_dir = "cleared";
    } else {
      results.facility_dir = `status_${contentsRes.status}`;
    }

    if (body.issue_number) {
      const issueNum = parseInt(body.issue_number, 10);
      await fetch(`${GH_API}/repos/${mainOwner}/${mainName}/issues/${issueNum}`, {
        method: "PATCH",
        headers: mainHeaders,
        body: JSON.stringify({ state: "closed" }),
      });
      const delIssue = await fetch(`${GH_API}/repos/${mainOwner}/${mainName}/issues/${issueNum}`, {
        method: "DELETE",
        headers: mainHeaders,
      });
      results.issue = delIssue.status === 204 ? "deleted" : `closed_status_${delIssue.status}`;
    }
  }

  return jsonResponse({ ok: true, slug, results });
}

/* ===================================================================== */
/* 9. Bootstrap script delivery                                           */
/* ===================================================================== */

function serveBootstrap(env, kind) {
  const workerUrl = (env.GITHUB_REDIRECT_URI || "https://rosetta.jtrue15.workers.dev").replace(/\/$/, "");
  const owner = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  const body = kind === "windows"
    ? windowsBootstrap({ workerUrl, owner })
    : unixBootstrap({ workerUrl, owner });
  const ct = kind === "windows" ? "text/plain; charset=utf-8" : "text/x-shellscript; charset=utf-8";
  return new Response(body, { status: 200, headers: { "Content-Type": ct, ...corsHeaders() } });
}

/* ===================================================================== */
/* Caller authentication                                                  */
/* ===================================================================== */

/**
 * A caller may authenticate via:
 *   - `Authorization: Bearer <github user token>`  (device-flow user)
 *   - `body.onboard_signature` HMAC of the body keyed by ONBOARD_HMAC_KEY
 *     (used by facility-onboard.yml so the maintainer-side workflow can
 *      request a companion repo without re-doing device flow).
 */
async function authenticateCaller(request, env, body) {
  const auth = request.headers.get("Authorization") || "";
  if (auth.startsWith("Bearer ")) {
    const userToken = auth.slice(7).trim();
    const userRes = await fetch(`${GH_API}/user`, {
      headers: {
        Authorization: `Bearer ${userToken}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "rosetta-upload-worker",
      },
    });
    if (!userRes.ok) return { ok: false, status: 401, error: "invalid_user_token" };
    const user = await userRes.json();
    // `bearer` = an authenticated but otherwise untrusted GitHub user (anyone
    // who completed device auth). These callers are gated by the approved-
    // facility allow-list before they can create repos or mint tokens.
    return { ok: true, login: user.login, via: "bearer", trusted: false };
  }

  if (body && body.onboard_signature) {
    const ok = await verifyHmac(
      env.ONBOARD_HMAC_KEY || "",
      canonicalOnboardPayload(body),
      body.onboard_signature,
    );
    if (ok) return { ok: true, login: "facility-onboard-workflow", via: "onboard", trusted: true };
    return { ok: false, status: 401, error: "invalid_onboard_signature" };
  }

  if (body && body.install_ticket) {
    const verified = await verifyInstallTicket(env, body.install_ticket);
    if (verified.ok) {
      return {
        ok: true,
        login: verified.claims.sub || "install-ticket",
        slug: verified.claims.slug,
        via: "install_ticket",
        trusted: true,
      };
    }
    return { ok: false, status: 401, error: verified.error };
  }

  return { ok: false, status: 401, error: "missing_authentication" };
}

function canonicalOnboardPayload(body) {
  return JSON.stringify({
    slug: body.slug,
    facility: body.facility,
    issued_at: body.issued_at,
  });
}

/* ===================================================================== */
/* GitHub App helpers                                                     */
/* ===================================================================== */

// Installation IDs are stable per account, so cache the lookup. We deliberately
// do NOT cache access tokens: every endpoint mints a fresh, narrowly scoped
// token (specific repositories + least-privilege permissions) so a token that
// leaves the Worker (e.g. the watchdog data-push token) can never be reused to
// reach the main repo, other facilities, or org administration.
const installationCache = {}; // owner -> { id, account_type }

function appJwtHeaders(jwt) {
  // GitHub's REST API rejects requests without a User-Agent header (HTTP 403).
  return {
    Authorization: `Bearer ${jwt}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "rosetta-upload-worker",
    "Content-Type": "application/json",
  };
}

async function resolveInstallation(env, owner) {
  if (installationCache[owner]) return installationCache[owner];
  const jwt = await signAppJwt(env);
  const headers = appJwtHeaders(jwt);

  let res = await fetch(`${GH_API}/users/${owner}/installation`, { headers });
  let accountType = "User";
  if (!res.ok) {
    res = await fetch(`${GH_API}/orgs/${owner}/installation`, { headers });
    accountType = "Organization";
  }
  if (!res.ok) {
    throw new Error(`Could not resolve installation for ${owner}: ${res.status}`);
  }
  const inst = await res.json();
  installationCache[owner] = {
    id: inst.id,
    account_type: (inst.account && inst.account.type) || accountType,
  };
  return installationCache[owner];
}

/**
 * Mint a GitHub App installation token.
 * @param {object} opts
 *   owner        - account that owns the target repos (defaults to FACILITY_OWNER)
 *   repositories - array of repo names to restrict the token to (omit only for
 *                  org-level operations like repo creation)
 *   permissions  - least-privilege permission map, e.g. { contents: "write" }
 */
async function mintInstallationToken(env, opts = {}) {
  const owner = opts.owner || env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  const { id, account_type } = await resolveInstallation(env, owner);
  const jwt = await signAppJwt(env);

  const body = {};
  if (opts.repositories && opts.repositories.length) body.repositories = opts.repositories;
  if (opts.permissions) body.permissions = opts.permissions;

  const res = await fetch(`${GH_API}/app/installations/${id}/access_tokens`, {
    method: "POST",
    headers: appJwtHeaders(jwt),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Installation token mint failed for ${owner}: ${res.status} ${detail}`);
  }
  const data = await res.json();
  return {
    token: data.token,
    account_type,
    expires_at: data.expires_at,
    expires_epoch: Math.floor(new Date(data.expires_at).getTime() / 1000),
  };
}

// Per-facility data repository (the facility's own companion repo). Scan data is
// pushed here, never to the main repo, so the watchdog's contents:write token
// cannot touch upstream code or workflows.
function facilityDataRepo(env, slug) {
  const owner = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  return { owner, name: `rosetta-facility-${slug}`, full: `${owner}/rosetta-facility-${slug}` };
}

/**
 * A facility is "approved" once the maintainer-side onboarding workflow has
 * committed data/<slug>/config.yml to the (public) main repo. Untrusted
 * device-flow callers may only act on approved facilities.
 */
async function isApprovedFacility(env, slug) {
  const mainRepo = env.MAIN_REPO || DEFAULT_MAIN_REPO;
  const res = await fetch(
    `${GH_API}/repos/${mainRepo}/contents/data/${sanitizeSlug(slug)}/config.yml?ref=main`,
    { headers: { Accept: "application/vnd.github+json", "User-Agent": "rosetta-upload-worker" } },
  );
  return res.ok;
}

async function signAppJwt(env) {
  const appId = env.GITHUB_APP_ID;
  const pem = env.GITHUB_APP_PRIVATE_KEY;
  if (!appId || !pem) throw new Error("GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY not configured");

  const header = base64UrlJson({ alg: "RS256", typ: "JWT" });
  const iat = nowSeconds() - 30;
  const payload = base64UrlJson({
    iat,
    exp: iat + APP_JWT_TTL_SECONDS,
    iss: String(appId),
  });
  const signingInput = `${header}.${payload}`;

  const key = await importRsaPrivateKey(pem);
  const sig = await crypto.subtle.sign(
    { name: "RSASSA-PKCS1-v1_5" },
    key,
    new TextEncoder().encode(signingInput),
  );
  return `${signingInput}.${base64Url(new Uint8Array(sig))}`;
}

async function importRsaPrivateKey(pem) {
  // GitHub App keys are issued in PKCS#1 form ("BEGIN RSA PRIVATE KEY"), but
  // WebCrypto's importKey only accepts PKCS#8 ("BEGIN PRIVATE KEY"). Detect
  // PKCS#1 and wrap it in a PKCS#8 envelope so either format works.
  const isPkcs1 = /BEGIN RSA PRIVATE KEY/.test(pem);
  const cleaned = pem
    .replace(/-----BEGIN [^-]+-----/g, "")
    .replace(/-----END [^-]+-----/g, "")
    .replace(/\s+/g, "");
  let der = Uint8Array.from(atob(cleaned), c => c.charCodeAt(0));
  if (isPkcs1) der = pkcs1ToPkcs8(der);
  return crypto.subtle.importKey(
    "pkcs8",
    der,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
}

function derLength(n) {
  if (n < 0x80) return [n];
  const bytes = [];
  let v = n;
  while (v > 0) { bytes.unshift(v & 0xff); v >>>= 8; }
  return [0x80 | bytes.length, ...bytes];
}

function pkcs1ToPkcs8(pkcs1) {
  // PrivateKeyInfo ::= SEQUENCE { version INTEGER(0),
  //   privateKeyAlgorithm AlgorithmIdentifier(rsaEncryption),
  //   privateKey OCTET STRING (the PKCS#1 RSAPrivateKey) }
  const version = [0x02, 0x01, 0x00];
  const algId = [
    0x30, 0x0d, 0x06, 0x09, 0x2a, 0x86, 0x48, 0x86,
    0xf7, 0x0d, 0x01, 0x01, 0x01, 0x05, 0x00,
  ];
  const pkcs1Arr = Array.from(pkcs1);
  const octet = [0x04, ...derLength(pkcs1Arr.length), ...pkcs1Arr];
  const inner = [...version, ...algId, ...octet];
  const seq = [0x30, ...derLength(inner.length), ...inner];
  return new Uint8Array(seq);
}

function githubAppHeaders(installationToken) {
  return {
    Authorization: `Bearer ${installationToken.token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Content-Type": "application/json",
    "User-Agent": "rosetta-upload-worker",
  };
}

/* ===================================================================== */
/* Install ticket (HMAC-SHA256, compact JWT-like)                         */
/* ===================================================================== */

async function signInstallTicket(env, claims) {
  const header = base64UrlJson({ alg: "HS256", typ: "RIT" });
  // jti lets us revoke a single ticket (kill switch) without rotating the key.
  const jti = (crypto.randomUUID && crypto.randomUUID()) || `${nowSeconds()}-${Math.random().toString(36).slice(2)}`;
  const payload = base64UrlJson({ iat: nowSeconds(), jti, ...claims });
  const signingInput = `${header}.${payload}`;
  const sig = await hmacSign(env.INSTALL_TICKET_KEY || "", signingInput);
  return `${signingInput}.${base64Url(sig)}`;
}

async function verifyInstallTicket(env, ticket) {
  const parts = String(ticket).split(".");
  if (parts.length !== 3) return { ok: false, error: "bad_ticket_format" };
  const [header, payload, sig] = parts;
  const expectedSig = await hmacSign(env.INSTALL_TICKET_KEY || "", `${header}.${payload}`);
  const expectedSigB64 = base64Url(expectedSig);
  if (!timingSafeEqual(expectedSigB64, sig)) return { ok: false, error: "bad_signature" };
  let claims;
  try {
    claims = JSON.parse(new TextDecoder().decode(base64UrlDecode(payload)));
  } catch (e) {
    return { ok: false, error: "bad_payload" };
  }
  if (!claims.exp || claims.exp < nowSeconds()) return { ok: false, error: "ticket_expired" };
  // Kill switch: a maintainer can revoke a single ticket (by jti) or every
  // ticket for a facility (by slug) via /fleet/revoke. No-op without KV.
  if (await isTicketRevoked(env, claims)) return { ok: false, error: "ticket_revoked" };
  return { ok: true, claims };
}

async function isTicketRevoked(env, claims) {
  if (!env.FLEET) return false;
  try {
    if (claims.jti && (await env.FLEET.get(`revoked:jti:${claims.jti}`))) return true;
    const slug = sanitizeSlug(claims.slug || "");
    if (slug && (await env.FLEET.get(`revoked:slug:${slug}`))) return true;
  } catch (_) { /* fail open on KV errors so a KV outage can't brick installs */ }
  return false;
}

async function hmacSign(secret, input) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(input));
  return new Uint8Array(sig);
}

async function verifyHmac(secret, message, providedHex) {
  const expected = await hmacSign(secret, message);
  const expectedHex = Array.from(expected).map(b => b.toString(16).padStart(2, "0")).join("");
  return timingSafeEqual(expectedHex, String(providedHex || ""));
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/* ===================================================================== */
/* Workflow + script templates                                            */
/* ===================================================================== */

function deployWorkflowYaml({ slug, mainRepo, workerOrigin, dataRepo }) {
  return `name: Deploy Rosetta Watchdog
on:
  workflow_dispatch:
    inputs:
      ref:
        description: Git ref of ${mainRepo} to deploy
        required: false
        default: main

permissions:
  contents: read

jobs:
  deploy:
    runs-on: [self-hosted, facility-${slug}]
    steps:
      - name: Checkout upstream Rosetta
        uses: actions/checkout@v4
        with:
          repository: ${mainRepo}
          ref: \${{ inputs.ref || 'main' }}
          path: rosetta

      - name: Install Python deps
        shell: bash
        run: |
          python -m pip install --upgrade pip
          python -m pip install ./rosetta/edge

      - name: Fetch facility config
        shell: bash
        env:
          GH_TOKEN: \${{ secrets.GITHUB_TOKEN }}
        run: |
          curl -fsSL \\
            -H "Authorization: Bearer $GH_TOKEN" \\
            -H "Accept: application/vnd.github.raw" \\
            -o config.yml \\
            "https://api.github.com/repos/${mainRepo}/contents/data/${slug}/config.yml"

      - name: Patch config to use Worker auth
        shell: bash
        run: |
          python -c "
          import yaml, pathlib
          p = pathlib.Path('config.yml')
          cfg = yaml.safe_load(p.read_text())
          cfg.setdefault('auth', {})
          cfg['auth']['token_url'] = '${workerOrigin}/watchdog/token'
          cfg['auth']['install_ticket_env'] = 'ROSETTA_INSTALL_TICKET'
          # Scan data is pushed to this facility's own companion repo, never the
          # main repo. The Worker-issued token is scoped to this repo with
          # contents:write only, so it cannot reach upstream code or workflows.
          cfg.setdefault('github', {})
          cfg['github']['repo'] = '${dataRepo}'
          cfg['github']['branch'] = 'main'
          cfg['github']['upload_path'] = 'data/${slug}/'
          p.write_text(yaml.safe_dump(cfg, sort_keys=False))
          "

      - name: Load install ticket from machine environment (Windows)
        if: runner.os == 'Windows'
        shell: pwsh
        run: |
          \$ticket = [Environment]::GetEnvironmentVariable('ROSETTA_INSTALL_TICKET', 'Machine')
          if (-not \$ticket) { throw 'ROSETTA_INSTALL_TICKET is not set in the machine environment' }
          "ROSETTA_INSTALL_TICKET=\$ticket" | Out-File -FilePath \$env:GITHUB_ENV -Append -Encoding utf8

      - name: Install/refresh watchdog service
        shell: bash
        env:
          ROSETTA_INSTALL_TICKET: \${{ runner.os != 'Windows' && secrets.ROSETTA_INSTALL_TICKET || '' }}
        run: |
          if [ "\${RUNNER_OS}" = "Windows" ]; then
            python ./rosetta/edge/scripts/install_service_windows.py \\
              --config "$(pwd)/config.yml" \\
              --install-ticket "$ROSETTA_INSTALL_TICKET"
          else
            python ./rosetta/edge/scripts/install_service_unix.py \\
              --config "$(pwd)/config.yml" \\
              --install-ticket "$ROSETTA_INSTALL_TICKET"
          fi
`;
}

function updateWorkflowYaml({ slug }) {
  return `name: Update Rosetta Watchdog
on:
  schedule:
    - cron: '0 6 * * *'
  workflow_dispatch: {}

permissions:
  contents: read
  actions: write

jobs:
  trigger-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger deploy-watchdog
        uses: actions/github-script@v7
        with:
          script: |
            await github.rest.actions.createWorkflowDispatch({
              owner: context.repo.owner,
              repo: context.repo.repo,
              workflow_id: 'deploy-watchdog.yml',
              ref: 'main',
              inputs: { ref: 'main' },
            });
`;
}

function companionReadme({ slug, facility, mainRepo, owner, repoName }) {
  return `# rosetta-facility-${slug}

Per-facility companion repository for the Rosetta CT metadata pipeline.

This repository exists to host the self-hosted GitHub Actions runner that
keeps the Rosetta Watchdog deployed and updated on facility **${facility}**.

- Main repo: https://github.com/${mainRepo}
- Setup wizard: https://${(mainRepo.split('/')[0])}.github.io/Rosetta/docs/setup-facility/
- Companion: \`${owner}/${repoName}\`

Workflows:
- \`deploy-watchdog.yml\` — installs / refreshes the watchdog service on the
  facility's self-hosted runner.
- \`update-watchdog.yml\` — daily trigger to pick up new releases of the
  watchdog from the main repo.

The runner itself auto-updates as part of \`actions/runner\`.
`;
}

function windowsBootstrap({ workerUrl, owner }) {
  return `# Rosetta Watchdog one-liner bootstrap (Windows / PowerShell 5.1+)
# Usage:
#   $env:ROSETTA_SLUG = "amnh-xradia520"
#   $env:ROSETTA_INSTALL_TICKET = "<ticket from the setup wizard>"
#   irm ${workerUrl}/bootstrap-windows.ps1 | iex

[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
function Info($msg) { Write-Host "[rosetta] $msg" -ForegroundColor Cyan }

$slug   = $env:ROSETTA_SLUG
$ticket = $env:ROSETTA_INSTALL_TICKET
$worker = ($env:ROSETTA_WORKER_URL -replace '/$', '')
if (-not $slug -or -not $ticket) {
  throw "Set ROSETTA_SLUG and ROSETTA_INSTALL_TICKET before piping this script into iex."
}
if (-not $worker) {
  throw "Set ROSETTA_WORKER_URL to the Rosetta Upload Worker base URL."
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  throw "This advanced installer registers a Windows service and must run in an elevated PowerShell. Re-open PowerShell as Administrator, or use the simpler 'Download & run' installer from the setup wizard (no admin required)."
}

$runnerDir  = if ($env:ROSETTA_RUNNER_DIR) { $env:ROSETTA_RUNNER_DIR } else { "C:\\rosetta-runner" }
$runnerName = if ($env:ROSETTA_RUNNER_NAME) { $env:ROSETTA_RUNNER_NAME } else { "rosetta-$slug" }

Info "Requesting runner registration token for facility '$slug'..."
$resp = Invoke-RestMethod -Method Post -Uri "$worker/runner/registration-token" \`
  -Headers @{ "Content-Type" = "application/json" } \`
  -Body (ConvertTo-Json @{ slug = $slug; install_ticket = $ticket })

$runnerRepo = $resp.runner_repo_url
$regToken   = $resp.registration_token
$label      = $resp.runner_label
$newTicket  = $resp.install_ticket

New-Item -ItemType Directory -Force -Path $runnerDir | Out-Null
Set-Location $runnerDir

if (-not (Test-Path "$runnerDir\\config.cmd")) {
  Info "Downloading actions/runner..."
  $latest = Invoke-RestMethod "https://api.github.com/repos/actions/runner/releases/latest"
  $asset  = $latest.assets | Where-Object { $_.name -like "actions-runner-win-x64-*.zip" } | Select-Object -First 1
  Invoke-WebRequest -Uri $asset.browser_download_url -OutFile runner.zip
  Expand-Archive -Path runner.zip -DestinationPath . -Force
  Remove-Item runner.zip
}

Info "Configuring runner '$runnerName' against $runnerRepo with label $label..."
.\\config.cmd --unattended --url $runnerRepo --token $regToken --labels $label --name $runnerName --replace

Info "Installing runner as a Windows service..."
.\\svc.cmd install
.\\svc.cmd start

Info "Storing install ticket for the deploy workflow..."
[Environment]::SetEnvironmentVariable("ROSETTA_INSTALL_TICKET", $newTicket, "Machine")

Info "Triggering initial deploy of rosetta-watchdog via Worker..."
Invoke-RestMethod -Method Post -Uri "$worker/workflow/dispatch-deploy" \`
  -Headers @{ "Content-Type" = "application/json" } \`
  -Body (ConvertTo-Json @{ slug = $slug; install_ticket = $newTicket; ref = "main" })

Info "Bootstrap complete. Watch the deploy progress on $runnerRepo/actions."
`;
}

function unixBootstrap({ workerUrl, owner }) {
  return `#!/usr/bin/env bash
# Rosetta Watchdog one-liner bootstrap (macOS / Linux)
# Usage:
#   export ROSETTA_SLUG=amnh-xradia520
#   export ROSETTA_INSTALL_TICKET="<ticket from the setup wizard>"
#   curl -fsSL ${workerUrl}/bootstrap-unix.sh | bash

set -euo pipefail

slug="\${ROSETTA_SLUG:-}"
ticket="\${ROSETTA_INSTALL_TICKET:-}"
if [ -z "$slug" ] || [ -z "$ticket" ]; then
  echo "Set ROSETTA_SLUG and ROSETTA_INSTALL_TICKET before piping this script into bash." >&2
  exit 1
fi

echo "[rosetta] Requesting runner registration token for facility '$slug'..."
resp=$(curl -fsSL -X POST "${workerUrl}/runner/registration-token" \\
  -H "Content-Type: application/json" \\
  -d "{\\"slug\\":\\"$slug\\",\\"install_ticket\\":\\"$ticket\\"}")

runnerRepo=$(printf '%s' "$resp" | python3 -c "import sys,json;print(json.load(sys.stdin)['runner_repo_url'])")
regToken=$(printf '%s' "$resp" | python3 -c "import sys,json;print(json.load(sys.stdin)['registration_token'])")
label=$(printf '%s' "$resp" | python3 -c "import sys,json;print(json.load(sys.stdin)['runner_label'])")
newTicket=$(printf '%s' "$resp" | python3 -c "import sys,json;print(json.load(sys.stdin)['install_ticket'])")

runnerDir="/opt/rosetta-runner"
sudo mkdir -p "$runnerDir"
sudo chown "$(id -u):$(id -g)" "$runnerDir"
cd "$runnerDir"

if [ ! -x ./config.sh ]; then
  echo "[rosetta] Downloading actions/runner..."
  os=$(uname -s | tr '[:upper:]' '[:lower:]')
  arch=$(uname -m); case "$arch" in x86_64) arch=x64;; arm64|aarch64) arch=arm64;; esac
  case "$os" in darwin) plat=osx;; linux) plat=linux;; *) echo "unsupported os: $os" >&2; exit 1;; esac
  url=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest \\
    | python3 -c "import sys,json,re; r=json.load(sys.stdin);
print(next(a['browser_download_url'] for a in r['assets'] if re.match(r'actions-runner-' + '$plat' + '-' + '$arch' + r'-.*\\.tar\\.gz$', a['name'])))")
  curl -fsSL "$url" -o runner.tar.gz
  tar xzf runner.tar.gz && rm runner.tar.gz
fi

echo "[rosetta] Configuring runner against $runnerRepo with label $label..."
./config.sh --unattended --url "$runnerRepo" --token "$regToken" --labels "$label" --name "rosetta-$slug" --replace

if [ -x ./svc.sh ]; then
  echo "[rosetta] Installing runner as a service..."
  sudo ./svc.sh install
  sudo ./svc.sh start
fi

echo "[rosetta] Storing install ticket in /etc/rosetta/install-ticket..."
sudo mkdir -p /etc/rosetta
echo "$newTicket" | sudo tee /etc/rosetta/install-ticket > /dev/null
sudo chmod 600 /etc/rosetta/install-ticket

echo "[rosetta] Triggering initial deploy of rosetta-watchdog..."
repoPath=$(printf '%s' "$runnerRepo" | sed 's|https://github.com/||')
curl -fsSL -X POST "https://api.github.com/repos/$repoPath/actions/workflows/deploy-watchdog.yml/dispatches" \\
  -H "Authorization: Bearer $regToken" \\
  -H "Accept: application/vnd.github+json" \\
  -H "Content-Type: application/json" \\
  -d '{"ref":"main"}'

echo "[rosetta] Bootstrap complete. Watch the deploy progress on $runnerRepo/actions."
`;
}

/* ===================================================================== */
/* Misc helpers                                                           */
/* ===================================================================== */

function sanitizeSlug(slug) {
  return String(slug).toLowerCase().replace(/[^a-z0-9-]/g, "-").replace(/(^-+|-+$)/g, "").slice(0, 64);
}

function nowSeconds() { return Math.floor(Date.now() / 1000); }

function base64Url(bytes) {
  let s = "";
  if (bytes instanceof Uint8Array) {
    for (const b of bytes) s += String.fromCharCode(b);
  } else {
    s = bytes;
  }
  return btoa(s).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
}

function base64UrlJson(obj) {
  return base64Url(new TextEncoder().encode(JSON.stringify(obj)));
}

function base64UrlDecode(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function safeJson(request) {
  try { return await request.json(); } catch { return null; }
}

function jsonResponse(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders() },
  });
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": PAGES_ORIGIN,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
  };
}

function stateCookie(value, maxAge = 600) {
  return `gh_oauth_state=${value}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`;
}

function parseCookie(cookieStr, name) {
  return cookieStr
    .split(";")
    .map(c => c.trim())
    .find(c => c.startsWith(name + "="))
    ?.split("=")[1] ?? null;
}

function htmlPage(title, body, isError = false, extraHeaders = {}) {
  const bg = isError ? "#2d1515" : "#0d1117";
  const color = isError ? "#f85149" : "#3fb950";
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>${title} – Rosetta</title>
  <style>
    body { font-family: -apple-system, sans-serif; background: ${bg}; color: #e6edf3;
           display: flex; align-items: center; justify-content: center;
           min-height: 100vh; margin: 0; }
    .box { text-align: center; padding: 2rem; }
    h2 { color: ${color}; }
    p  { color: #8b949e; }
  </style>
</head>
<body>
  <div class="box">${body}</div>
</body>
</html>`;
  return new Response(html, {
    status: isError ? 400 : 200,
    headers: { "Content-Type": "text/html", ...extraHeaders },
  });
}
