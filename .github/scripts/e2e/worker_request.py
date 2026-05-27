#!/usr/bin/env python3
"""Call Rosetta Upload Worker endpoints from CI with HMAC auth."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request


def sign_body(body: dict, key: str) -> dict:
    canonical = json.dumps(
        {"slug": body["slug"], "facility": body["facility"], "issued_at": body["issued_at"]},
        separators=(",", ":"),
    )
    signature = hmac.new(key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return {**body, "onboard_signature": signature}


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        raise SystemExit(f"HTTP {exc.code} from {url}: {detail}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Rosetta Worker helper for CI e2e")
    parser.add_argument("action", choices=[
        "create-companion-repo",
        "registration-token",
        "dispatch-deploy",
        "deploy-status",
        "cleanup",
    ])
    parser.add_argument("--worker-url", required=True)
    parser.add_argument("--hmac-key", default="")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--facility", default="")
    parser.add_argument("--install-ticket", default="")
    parser.add_argument("--issue-number", default="")
    parser.add_argument("--ref", default="main")
    parser.add_argument("--github-output", default="")
    args = parser.parse_args()

    worker = args.worker_url.rstrip("/")
    action = args.action

    if action in ("create-companion-repo", "registration-token", "cleanup"):
        if not args.hmac_key:
            raise SystemExit("--hmac-key required for this action")
        body = sign_body(
            {"slug": args.slug, "facility": args.facility or args.slug, "issued_at": int(time.time())},
            args.hmac_key,
        )
        if action == "cleanup" and args.issue_number:
            body["issue_number"] = int(args.issue_number)
        route = {
            "create-companion-repo": "facility/create-companion-repo",
            "registration-token": "runner/registration-token",
            "cleanup": "e2e/cleanup",
        }[action]
        data = post_json(f"{worker}/{route}", body)
    elif action == "dispatch-deploy":
        if not args.install_ticket:
            raise SystemExit("--install-ticket required for dispatch-deploy")
        data = post_json(f"{worker}/workflow/dispatch-deploy", {
            "slug": args.slug,
            "install_ticket": args.install_ticket,
            "ref": args.ref,
            "rosetta_ref": args.ref,
        })
    elif action == "deploy-status":
        if not args.install_ticket:
            raise SystemExit("--install-ticket required for deploy-status")
        data = post_json(f"{worker}/deploy/status", {
            "slug": args.slug,
            "install_ticket": args.install_ticket,
        })
    else:
        raise SystemExit(f"Unhandled action: {action}")

    print(json.dumps(data, indent=2))

    if args.github_output:
        mapping = {
            "install_ticket": data.get("install_ticket"),
            "companion_repo": data.get("companion_repo"),
            "registration_token": data.get("registration_token"),
            "run_status": (data.get("run") or {}).get("status"),
            "run_conclusion": (data.get("run") or {}).get("conclusion"),
        }
        with open(args.github_output, "a", encoding="utf-8") as fh:
            for key, value in mapping.items():
                if value is not None:
                    fh.write(f"{key}={value}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
