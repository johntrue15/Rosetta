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
 *   POST /workflow/dispatch-deploy    Trigger deploy-watchdog.yml (App token)
 *   POST /e2e/cleanup                 Tear down companion repo + facility data + issue
 *   GET  /bootstrap-windows.ps1       PowerShell installer
 *   GET  /bootstrap-unix.sh           Bash installer
 */

const PAGES_ORIGIN = "https://johntrue15.github.io";
const GH_API = "https://api.github.com";
const DEFAULT_MAIN_REPO = "johntrue15/Rosetta";
const DEFAULT_FACILITY_OWNER = "johntrue15";

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
  const res = await fetch("https://github.com/login/device/code", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ client_id: clientId, scope: "" }),
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

  const mainRepo = env.MAIN_REPO || DEFAULT_MAIN_REPO;
  const owner = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  const repoName = `rosetta-facility-${slug}`;

  const installationToken = await getAppInstallationToken(env);

  const createRes = await fetch(`${GH_API}/user/repos`, {
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

  const templates = {
    ".github/workflows/deploy-watchdog.yml": deployWorkflowYaml({ slug, mainRepo, workerOrigin }),
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

  const owner = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  const repoName = `rosetta-facility-${slug}`;

  const installationToken = await getAppInstallationToken(env);

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

  const installationToken = await getAppInstallationToken(env);

  return jsonResponse({
    token: installationToken.token,
    expires_at: installationToken.expires_at,
    repo: env.MAIN_REPO || DEFAULT_MAIN_REPO,
    facility_slug: verified.claims.slug,
  });
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
  const installationToken = await getAppInstallationToken(env);

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

  const owner = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  const repoName = `rosetta-facility-${slug}`;
  const ref = body.ref || "main";
  const installationToken = await getAppInstallationToken(env);

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

  const owner = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  const mainRepo = env.MAIN_REPO || DEFAULT_MAIN_REPO;
  const [mainOwner, mainName] = mainRepo.split("/");
  const companionName = `rosetta-facility-${slug}`;
  const installationToken = await getAppInstallationToken(env);
  const headers = githubAppHeaders(installationToken);
  const results = {};

  // Delete companion repo (ignore 404)
  const delRepo = await fetch(`${GH_API}/repos/${owner}/${companionName}`, {
    method: "DELETE",
    headers,
  });
  results.companion_repo = delRepo.status === 204 ? "deleted" : `status_${delRepo.status}`;

  // Remove data/<slug>/ from main repo
  const dirPath = `data/${slug}`;
  const contentsRes = await fetch(
    `${GH_API}/repos/${mainOwner}/${mainName}/contents/${dirPath}?ref=main`,
    { headers },
  );
  if (contentsRes.ok) {
    const items = await contentsRes.json();
    for (const item of items) {
      if (item.type === "file") {
        await fetch(`${GH_API}/repos/${mainOwner}/${mainName}/contents/${item.path}`, {
          method: "DELETE",
          headers,
          body: JSON.stringify({
            message: `chore(e2e): remove ${item.path} [skip ci]`,
            sha: item.sha,
            branch: "main",
          }),
        });
      }
    }
    // Remove README + config if present as individual deletes above; remove dir marker files
    results.facility_dir = "cleared";
  } else {
    results.facility_dir = `status_${contentsRes.status}`;
  }

  // Close + delete issue when provided
  if (body.issue_number) {
    const issueNum = parseInt(body.issue_number, 10);
    await fetch(`${GH_API}/repos/${mainOwner}/${mainName}/issues/${issueNum}`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ state: "closed" }),
    });
    const delIssue = await fetch(`${GH_API}/repos/${mainOwner}/${mainName}/issues/${issueNum}`, {
      method: "DELETE",
      headers,
    });
    results.issue = delIssue.status === 204 ? "deleted" : `closed_status_${delIssue.status}`;
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
      headers: { Authorization: `Bearer ${userToken}`, Accept: "application/vnd.github+json" },
    });
    if (!userRes.ok) return { ok: false, status: 401, error: "invalid_user_token" };
    const user = await userRes.json();
    return { ok: true, login: user.login };
  }

  if (body && body.onboard_signature) {
    const ok = await verifyHmac(
      env.ONBOARD_HMAC_KEY || "",
      canonicalOnboardPayload(body),
      body.onboard_signature,
    );
    if (ok) return { ok: true, login: "facility-onboard-workflow" };
    return { ok: false, status: 401, error: "invalid_onboard_signature" };
  }

  if (body && body.install_ticket) {
    const verified = await verifyInstallTicket(env, body.install_ticket);
    if (verified.ok) {
      return {
        ok: true,
        login: verified.claims.sub || "install-ticket",
        slug: verified.claims.slug,
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

let cachedInstallationToken = null;

async function getAppInstallationToken(env) {
  if (cachedInstallationToken && cachedInstallationToken.expires_epoch > nowSeconds() + 60) {
    return cachedInstallationToken;
  }

  const jwt = await signAppJwt(env);

  const owner = env.FACILITY_OWNER || DEFAULT_FACILITY_OWNER;
  const instRes = await fetch(`${GH_API}/users/${owner}/installation`, {
    headers: { Authorization: `Bearer ${jwt}`, Accept: "application/vnd.github+json" },
  });

  let installationId;
  if (instRes.ok) {
    installationId = (await instRes.json()).id;
  } else {
    const orgRes = await fetch(`${GH_API}/orgs/${owner}/installation`, {
      headers: { Authorization: `Bearer ${jwt}`, Accept: "application/vnd.github+json" },
    });
    if (!orgRes.ok) {
      throw new Error(`Could not resolve installation for ${owner}: ${instRes.status}/${orgRes.status}`);
    }
    installationId = (await orgRes.json()).id;
  }

  const tokenRes = await fetch(`${GH_API}/app/installations/${installationId}/access_tokens`, {
    method: "POST",
    headers: { Authorization: `Bearer ${jwt}`, Accept: "application/vnd.github+json" },
  });
  if (!tokenRes.ok) {
    const detail = await tokenRes.text();
    throw new Error(`Installation token mint failed: ${tokenRes.status} ${detail}`);
  }
  const data = await tokenRes.json();

  cachedInstallationToken = {
    token: data.token,
    expires_at: data.expires_at,
    expires_epoch: Math.floor(new Date(data.expires_at).getTime() / 1000),
  };
  return cachedInstallationToken;
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
  const cleaned = pem
    .replace(/-----BEGIN [^-]+-----/g, "")
    .replace(/-----END [^-]+-----/g, "")
    .replace(/\s+/g, "");
  const der = Uint8Array.from(atob(cleaned), c => c.charCodeAt(0));
  return crypto.subtle.importKey(
    "pkcs8",
    der,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
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
  const payload = base64UrlJson({ iat: nowSeconds(), ...claims });
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
  return { ok: true, claims };
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

function deployWorkflowYaml({ slug, mainRepo, workerOrigin }) {
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
