/**
 * Rosetta OAuth Worker
 *
 * Handles the GitHub App OAuth code-for-token exchange for the
 * static GitHub Pages frontend. The client secret never leaves
 * this Worker — it is stored as an environment variable.
 *
 * Environment variables to set in the Cloudflare dashboard:
 *   GITHUB_CLIENT_ID     = Iv23liekYxnX8xk9amRo
 *   GITHUB_CLIENT_SECRET = 449868d349085ae1088646f146864f4b85e0c2f7
 *   GITHUB_REDIRECT_URI  = https://rosetta.jtrue15.workers.dev  (this Worker's URL)
 *   ALLOWED_ORIGIN       = https://johntrue15.github.io
 *
 * GitHub App callback URL must be set to this Worker's URL.
 */

const PAGES_ORIGIN = "https://johntrue15.github.io";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // ── CORS preflight ────────────────────────────────────────────────
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    const clientId     = env.GITHUB_CLIENT_ID;
    const clientSecret = env.GITHUB_CLIENT_SECRET;
    const redirectUri  = env.GITHUB_REDIRECT_URI;   // this Worker's own URL

    // ── Step 1: No ?code yet → redirect to GitHub for authorization ───
    if (!url.searchParams.has("code")) {
      const state    = crypto.randomUUID();
      const ghUrl    = new URL("https://github.com/login/oauth/authorize");
      ghUrl.searchParams.set("client_id",    clientId);
      ghUrl.searchParams.set("redirect_uri", redirectUri);
      ghUrl.searchParams.set("scope",        "repo");
      ghUrl.searchParams.set("state",        state);

      return new Response(null, {
        status: 302,
        headers: {
          Location:    ghUrl.toString(),
          "Set-Cookie": stateCookie(state),
        },
      });
    }

    // ── Step 2: GitHub sent us back ?code + ?state ────────────────────
    const returnedState = url.searchParams.get("state") ?? "";
    const savedState    = parseCookie(request.headers.get("Cookie") ?? "", "gh_oauth_state");

    const clearCookieHeader = { "Set-Cookie": stateCookie("", 0) };

    if (!savedState || savedState !== returnedState) {
      return htmlPage(
        "Security error",
        "<h2>State mismatch</h2><p>Possible CSRF attempt. Please close this window and try again.</p>",
        true,
        clearCookieHeader
      );
    }

    // Exchange the code for a token (server-side — no CORS issue)
    let tokenData;
    try {
      const tokenRes = await fetch("https://github.com/login/oauth/access_token", {
        method:  "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body:    JSON.stringify({
          client_id:     clientId,
          client_secret: clientSecret,
          code:          url.searchParams.get("code"),
          redirect_uri:  redirectUri,
        }),
      });
      tokenData = await tokenRes.json();
    } catch (err) {
      return htmlPage("Error", `<h2>Token exchange failed</h2><p>${err.message}</p>`, true, clearCookieHeader);
    }

    if (tokenData.error) {
      return htmlPage(
        "Auth error",
        `<h2>${tokenData.error}</h2><p>${tokenData.error_description ?? ""}</p>`,
        true,
        clearCookieHeader
      );
    }

    // ── Step 3: Write token to opener (the Rosetta Pages tab) and close ──
    const token = tokenData.access_token;
    return htmlPage(
      "Authorized",
      `<h2>Authorized!</h2><p>Closing this window…</p>
       <script>
         try {
           if (window.opener && !window.opener.closed) {
             window.opener.localStorage.setItem('gh_token', ${JSON.stringify(token)});
             window.opener.dispatchEvent(new Event('gh_token_ready'));
           }
         } catch (e) {
           document.body.innerHTML += '<p>Done — you can close this tab.</p>';
         }
         window.close();
       </script>`,
      false,
      clearCookieHeader
    );
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin":  PAGES_ORIGIN,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
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
  const bg    = isError ? "#2d1515" : "#0d1117";
  const color = isError ? "#f85149" : "#3fb950";
  const html  = `<!DOCTYPE html>
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
    status:  isError ? 400 : 200,
    headers: { "Content-Type": "text/html", ...extraHeaders },
  });
}
