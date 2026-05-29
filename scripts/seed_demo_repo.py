#!/usr/bin/env python3
"""Seed the repodoc-demo repo with clean baseline + one bug-laden commit."""
import base64
import os
import requests
import sys

PAT = os.environ.get("GITHUB_TOKEN")
OWNER = "yashdodwani"
REPO = "repodoc-demo"
API = "https://api.github.com"

if not PAT:
    print("Set GITHUB_TOKEN before running this script.", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {PAT}",
    "Accept": "application/vnd.github+json",
}


def put_file(path, content, message, branch="main"):
    # Get existing SHA if file exists
    r = requests.get(f"{API}/repos/{OWNER}/{REPO}/contents/{path}?ref={branch}", headers=HEADERS)
    existing_sha = r.json().get("sha") if r.status_code == 200 else None

    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    resp = requests.put(
        f"{API}/repos/{OWNER}/{REPO}/contents/{path}",
        headers=HEADERS, json=payload,
    )
    if resp.status_code in (200, 201):
        sha = resp.json().get("commit", {}).get("sha", "")[:8]
        print(f"  {path:<28} commit={sha} {message}")
        return resp.json().get("commit", {}).get("sha", "")
    else:
        print(f"  FAIL {path}: {resp.status_code} {resp.text[:150]}")
        return None


# ── 1. Clean baseline files ──────────────────────────────────────────────────

README = """# Acme Payments Service

Internal payments processing microservice. Handles checkout, subscription
renewals, and partner reconciliation.

## Setup
```bash
pip install -r requirements.txt
python app.py
```

## Endpoints
- `POST /charge` — process a one-off charge
- `POST /subscribe` — create a subscription
- `GET /health` — service health
"""

APP_PY = '''"""Acme Payments — main entry point."""
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "acme-payments"})


@app.route("/charge", methods=["POST"])
def charge():
    data = request.get_json() or {}
    amount = data.get("amount", 0)
    currency = data.get("currency", "USD")
    return jsonify({"charged": amount, "currency": currency, "status": "pending"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
'''

REQS = """flask==3.0.0
requests==2.31.0
sqlalchemy==2.0.25
"""

UTILS_PY = '''"""Shared utilities."""
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def safe_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default
'''

print("=== Phase 1: Clean baseline ===")
put_file("README.md", README, "docs: initial readme")
put_file("requirements.txt", REQS, "chore: pin dependencies")
put_file("app.py", APP_PY, "feat: initial flask scaffold")
put_file("utils.py", UTILS_PY, "feat: shared utility helpers")

# ── 2. The "bad commit" — one realistic-looking feature with many violations ─

BUGGY_FILE = '''"""Payment provider integration — Stripe + legacy ACH gateway.

Author: dev-rushing-on-friday
"""
import os
import sqlite3
import requests


# TODO: move these to env vars before prod  -- intentional violation
api_key = "DEMO_PROVIDER_KEY_abc123_NOT_REAL_xyz789"
ACH_GATEWAY_URL = "http://10.0.42.17:8080/ach"
admin_password = "P_assw0rd_admin_2024_temp_demo"


def get_user_balance(user_id):
    """Look up a user's wallet balance. FIXME: parametrize this query."""
    conn = sqlite3.connect("payments.db")
    cur = conn.cursor()
    # SQL INJECTION: user_id is concatenated directly into the query string
    query = "SELECT balance FROM wallets WHERE user_id = '" + str(user_id) + "'"
    cur.execute(query)
    row = cur.fetchone()
    print("DEBUG: balance lookup for", user_id, "->", row)
    return row[0] if row else 0


def apply_dynamic_discount(rule_string, cart_total):
    """Apply a discount rule defined as a Python expression. HACK: temporary."""
    # CRITICAL: eval on user-influenced input — RCE vector
    discount = eval(rule_string)
    return max(0, cart_total - discount)


def charge_user(user_id, amount):
    """Charge a user via the payments provider."""
    headers = {"Authorization": "Bearer " + api_key}
    payload = {"amount": amount, "user_id": user_id}
    resp = requests.post("https://provider.example.com/v1/charges", headers=headers, json=payload)
    print("DEBUG: provider response =", resp.status_code, resp.text)
    return resp.json()


def transfer_via_ach(account_number, amount):
    """Send money via the legacy ACH gateway."""
    # XXX: hardcoded internal IP — should be config
    url = ACH_GATEWAY_URL + "/transfer"
    return requests.post(url, json={"account": account_number, "amount": amount}).json()
'''

print()
print("=== Phase 2: The bad commit (the demo trigger) ===")
put_file(
    "payment_provider.py",
    BUGGY_FILE,
    "feat(payments): integrate Stripe + ACH gateway for checkout flow",
)

print()
print("=== DONE ===")
print(f"Demo repo: https://github.com/{OWNER}/{REPO}")
print()
print("Demo flow:")
print("  1. Open repoDoc → /watch")
print("  2. Add this repo + pick 'Enterprise Grade' guardrails")
print("  3. Wait 5 min OR click 'Check Now' → first run baselines silently")
print("  4. To replay: PUT /api/watched-repos/{id} last_commits.main = '0'*40")
print("     then click 'Check Now' → watch Issue + PR fly in")
