#!/usr/bin/env python3
"""Drive the GitHub *device* OAuth flow against the Rosetta Worker from CI.

This simulates exactly what a real operator does in the setup wizard:

  1. ``init``      — POST /device/init, print the user code + URL, and wait
                     (polling /device/poll) up to ``--wait`` seconds for a human
                     to approve at https://github.com/login/device.
  2. with the resulting user token, POST /facility/create-companion-repo and
     POST /runner/registration-token to obtain the install ticket — the same
     calls the wizard makes after approval.

Outputs ``install_ticket``, ``companion_repo`` and ``user_token`` to
``--github-output`` (the tokens are also registered as ``::add-mask::`` so they
never appear in logs).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

UA = "rosetta-device-e2e/1.0"


def post_json(url: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": UA,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"error": f"http_{exc.code}", "detail": body}


def mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}")


def summary(lines: list[str]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def banner(user_code: str, verification_uri: str, wait: int) -> None:
    bar = "=" * 64
    print(bar, flush=True)
    print(" DEVICE AUTHORIZATION REQUIRED - action needed within "
          f"{wait}s", flush=True)
    print(bar, flush=True)
    print(f"  1) Open:  {verification_uri}", flush=True)
    print(f"  2) Enter code:   {user_code}", flush=True)
    print(bar, flush=True)
    print(f"::notice title=Enter device code {user_code}::"
          f"Open {verification_uri} and enter {user_code} (waiting {wait}s)", flush=True)
    summary([
        "### Device authorization",
        "",
        f"1. Open **{verification_uri}**",
        f"2. Enter code: **`{user_code}`**",
        f"3. Approve the Rosetta Upload app (waiting up to {wait}s).",
        "",
    ])


def authorize(args: argparse.Namespace) -> int:
    worker = args.worker_url.strip().rstrip("/")

    status, init = post_json(f"{worker}/device/init", {"scope": args.scope})
    if status >= 400 or "device_code" not in init:
        raise SystemExit(f"device/init failed (HTTP {status}): {json.dumps(init)}")

    device_code = init["device_code"]
    user_code = init.get("user_code", "????-????")
    verification_uri = init.get("verification_uri", "https://github.com/login/device")
    interval = max(int(init.get("interval", 5)), 5)
    banner(user_code, verification_uri, args.wait)

    token = None
    deadline = time.time() + args.wait
    while time.time() < deadline:
        time.sleep(interval)
        status, poll = post_json(f"{worker}/device/poll", {"device_code": device_code})
        err = poll.get("error")
        if poll.get("access_token"):
            token = poll["access_token"]
            break
        if err in ("authorization_pending", None):
            remaining = int(deadline - time.time())
            print(f"  ...waiting for approval ({remaining}s left)", flush=True)
            continue
        if err == "slow_down":
            interval += 5
            continue
        raise SystemExit(f"device/poll error: {json.dumps(poll)}")

    if not token:
        raise SystemExit(f"Timed out after {args.wait}s waiting for device approval.")

    mask(token)
    print("Device authorization approved.", flush=True)

    facility = args.facility or args.slug
    status, repo = post_json(
        f"{worker}/facility/create-companion-repo",
        {"slug": args.slug, "facility": facility},
        token=token,
    )
    if status >= 400:
        raise SystemExit(f"create-companion-repo failed (HTTP {status}): {json.dumps(repo)}")
    companion_repo = repo.get("companion_repo", "")
    print(f"Companion repo ready: {companion_repo}", flush=True)

    status, reg = post_json(
        f"{worker}/runner/registration-token",
        {"slug": args.slug, "facility": facility},
        token=token,
    )
    if status >= 400 or not reg.get("install_ticket"):
        raise SystemExit(f"registration-token failed (HTTP {status}): {json.dumps(reg)}")
    install_ticket = reg["install_ticket"]
    mask(install_ticket)
    print("Install ticket minted.", flush=True)

    summary([
        "",
        "Approved. Proceeding with install on the Dell runner.",
        f"- Companion repo: `{companion_repo}`",
    ])

    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"install_ticket={install_ticket}\n")
            fh.write(f"companion_repo={companion_repo}\n")
            fh.write(f"user_token={token}\n")
    return 0


def verify(args: argparse.Namespace) -> int:
    """Confirm the dashboard data path: /facility/status + /facility/data."""
    worker = args.worker_url.strip().rstrip("/")
    deadline = time.time() + args.wait
    last = {}
    while time.time() < deadline:
        _, data = post_json(f"{worker}/facility/data", {"install_ticket": args.install_ticket})
        last = data
        if data.get("count", 0) > 0:
            print(f"Dashboard /facility/data sees {data['count']} file(s) in "
                  f"{data.get('repo')}", flush=True)
            _, st = post_json(f"{worker}/facility/status", {"install_ticket": args.install_ticket})
            print(f"Dashboard /facility/status health={st.get('health')} "
                  f"processed={(st.get('status') or {}).get('processed')}", flush=True)
            summary([
                "### Verified via Worker dashboard endpoints",
                f"- `/facility/data` → **{data['count']}** file(s) in `{data.get('repo')}`",
                f"- `/facility/status` → health **{st.get('health')}**, "
                f"processed **{(st.get('status') or {}).get('processed')}**",
            ])
            return 0
        print("  ...no uploaded data visible yet via Worker; retrying", flush=True)
        time.sleep(10)
    raise SystemExit(f"Timed out; last /facility/data response: {json.dumps(last)}")


def main() -> int:
    p = argparse.ArgumentParser(description="Rosetta device-flow E2E driver")
    sub = p.add_subparsers(dest="action", required=True)

    a = sub.add_parser("authorize", help="device init + poll + mint install ticket")
    a.add_argument("--worker-url", required=True)
    a.add_argument("--slug", required=True)
    a.add_argument("--facility", default="")
    a.add_argument("--scope", default="")
    a.add_argument("--wait", type=int, default=120)
    a.add_argument("--github-output", default="")
    a.set_defaults(func=authorize)

    v = sub.add_parser("verify", help="confirm /facility/data + /facility/status")
    v.add_argument("--worker-url", required=True)
    v.add_argument("--install-ticket", required=True)
    v.add_argument("--wait", type=int, default=120)
    v.set_defaults(func=verify)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
