"""Backend tests for repoDoc SaaS pivot: guardrails, watched-repos, watch-events.

Notes:
- Uses REACT_APP_BACKEND_URL from env (no defaults).
- Uses a non-spam test repo (octocat/Hello-World) for read-only watcher logic and
  passes empty/no guardrails so the agent is NOT triggered (violations=0).
- Cleans up all created watched-repos and guardrails at the end.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"

# Use a tiny public repo for read-only watcher tests (no write ops).
TEST_REPO_URL = "https://github.com/octocat/Hello-World"


# ── Health & regression ──────────────────────────────────────────────────────
class TestHealthAndRegression:
    def test_health(self):
        r = requests.get(f"{API}/health", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        # github should be wired up since GITHUB_TOKEN is set in .env
        assert data.get("github") is True

    def test_stats_regression(self):
        r = requests.get(f"{API}/stats", timeout=15)
        assert r.status_code == 200
        for k in ["total_analyses", "completed", "failed", "running",
                  "bugs_found", "fixes_applied", "prs_created"]:
            assert k in r.json()

    def test_list_analyses_regression(self):
        r = requests.get(f"{API}/analyses", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ── Guardrails: builtin + presets ────────────────────────────────────────────
class TestGuardrailsBuiltins:
    def test_builtin_returns_8_rules_and_4_presets(self):
        r = requests.get(f"{API}/guardrails/builtin", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "rules" in data and "presets" in data
        assert len(data["rules"]) == 8, f"Expected 8 builtin rules, got {len(data['rules'])}"
        assert len(data["presets"]) == 4, f"Expected 4 presets, got {len(data['presets'])}"
        keys = {p["key"] for p in data["presets"]}
        assert keys == {"security_first", "startup", "enterprise", "open_source"}
        # Sanity-check rule shapes
        for rule in data["rules"]:
            assert "id" in rule and "name" in rule and "type" in rule


# ── Guardrails: CRUD ─────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def created_ids():
    return {"guardrails": [], "watched": []}


class TestGuardrailsCRUD:
    def test_create_from_preset_security_first(self, created_ids):
        r = requests.post(f"{API}/guardrails/from-preset",
                          json={"preset": "security_first"}, timeout=15)
        assert r.status_code == 200
        doc = r.json()
        assert doc["name"] == "Security First"
        assert isinstance(doc["rules"], list) and len(doc["rules"]) == 4
        assert "id" in doc
        created_ids["guardrails"].append(doc["id"])

        # GET-after-create persistence check
        g = requests.get(f"{API}/guardrails/{doc['id']}", timeout=15)
        assert g.status_code == 200
        assert g.json()["id"] == doc["id"]

    def test_create_custom_with_regex(self, created_ids):
        payload = {
            "name": "TEST_custom_ruleset",
            "description": "Test custom regex",
            "rules": [{
                "id": "r1",
                "name": "Permissive Added Line",
                "category": "quality",
                "type": "pattern",
                "pattern": r"^\+.+",
                "severity": "info",
                "enabled": True,
            }],
        }
        r = requests.post(f"{API}/guardrails", json=payload, timeout=15)
        assert r.status_code == 200
        doc = r.json()
        assert doc["name"] == "TEST_custom_ruleset"
        assert len(doc["rules"]) == 1
        created_ids["guardrails"].append(doc["id"])

    def test_list_guardrails(self, created_ids):
        r = requests.get(f"{API}/guardrails", timeout=15)
        assert r.status_code == 200
        ids = {g["id"] for g in r.json()}
        for gid in created_ids["guardrails"]:
            assert gid in ids

    def test_update_guardrails(self, created_ids):
        gid = created_ids["guardrails"][0]
        r = requests.put(f"{API}/guardrails/{gid}",
                         json={"name": "TEST_renamed", "description": "updated"},
                         timeout=15)
        assert r.status_code == 200
        assert r.json()["name"] == "TEST_renamed"

        # GET to confirm persistence
        g = requests.get(f"{API}/guardrails/{gid}", timeout=15)
        assert g.status_code == 200
        assert g.json()["name"] == "TEST_renamed"

    def test_get_404(self):
        r = requests.get(f"{API}/guardrails/does-not-exist", timeout=15)
        assert r.status_code == 404


# ── Watched Repos CRUD + check-now (no agent trigger) ────────────────────────
class TestWatchedRepos:
    def test_create_watched_repo_populates_repo_name(self, created_ids):
        # Use no guardrails => watcher won't trigger agent even if a commit is "new"
        r = requests.post(
            f"{API}/watched-repos",
            json={"repo_url": TEST_REPO_URL, "telegram_chat_id": ""},
            timeout=15,
        )
        assert r.status_code == 200
        doc = r.json()
        assert doc["repo_name"] == "octocat/Hello-World"
        assert doc["active"] is True
        assert doc["repo_url"] == TEST_REPO_URL
        created_ids["watched"].append(doc["id"])

    def test_create_missing_url_returns_400(self):
        r = requests.post(f"{API}/watched-repos", json={}, timeout=15)
        assert r.status_code == 400

    def test_list_watched_repos(self, created_ids):
        r = requests.get(f"{API}/watched-repos", timeout=15)
        assert r.status_code == 200
        ids = {w["id"] for w in r.json()}
        assert created_ids["watched"][0] in ids

    def test_toggle_active(self, created_ids):
        wid = created_ids["watched"][0]
        r = requests.put(f"{API}/watched-repos/{wid}", json={"active": False}, timeout=15)
        assert r.status_code == 200
        assert r.json()["active"] is False
        # toggle back
        r2 = requests.put(f"{API}/watched-repos/{wid}", json={"active": True}, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["active"] is True

    def test_check_now_first_run_records_no_violations(self, created_ids):
        """First check should populate last_commits without alerting / no watch_events."""
        wid = created_ids["watched"][0]
        r = requests.post(f"{API}/watched-repos/{wid}/check-now", timeout=15)
        assert r.status_code == 200

        # Wait for background task to finish
        time.sleep(8)

        # Refresh the watched record and ensure last_commits is populated
        w = next(w for w in requests.get(f"{API}/watched-repos").json() if w["id"] == wid)
        assert isinstance(w.get("last_commits"), dict)
        assert len(w["last_commits"]) >= 1, "First-run should populate last_commits with HEAD shas"

        # No watch_events should exist for first run (silent baseline)
        ev = requests.get(f"{API}/watch-events", params={"watched_repo_id": wid}, timeout=15)
        assert ev.status_code == 200
        assert isinstance(ev.json(), list)
        assert len(ev.json()) == 0, "First run must not create watch_events"

    def test_check_now_with_reset_records_clean_event_no_agent(self, created_ids):
        """Reset last_commits to a sentinel, attach NO guardrails => watcher detects 'new'
        commit, evaluates against no rules (=> 0 violations), records a 'clean' event,
        and does NOT trigger the agent / GH issue."""
        wid = created_ids["watched"][0]

        # Reset last_commits so the next check sees real HEAD as "new"
        r = requests.put(
            f"{API}/watched-repos/{wid}",
            json={"last_commits": {"master": "0" * 40}},  # Hello-World default branch is 'master'
            timeout=15,
        )
        assert r.status_code == 200

        r2 = requests.post(f"{API}/watched-repos/{wid}/check-now", timeout=15)
        assert r2.status_code == 200
        time.sleep(10)

        ev = requests.get(f"{API}/watch-events", params={"watched_repo_id": wid}, timeout=15)
        assert ev.status_code == 200
        events = ev.json()
        # Should have at least one event, and all should be 'clean' since no guardrails attached
        assert len(events) >= 1, "Expected at least one watch_event after reset+check"
        assert all(e["status"] == "clean" for e in events), \
            f"Expected all clean events (no guardrails), got: {[e['status'] for e in events]}"
        assert all(e.get("analysis_id") is None for e in events), \
            "Agent must NOT be triggered when there are no violations"
        # filter: ensure watched_repo_id matching
        assert all(e["watched_repo_id"] == wid for e in events)

    def test_watch_events_filter(self, created_ids):
        # Same as above but verifying the filter param works (negative case)
        r = requests.get(f"{API}/watch-events",
                         params={"watched_repo_id": "nonexistent-id"}, timeout=15)
        assert r.status_code == 200
        assert r.json() == []


# ── Delete ordering: deleting guardrails detaches from watched ───────────────
class TestGuardrailsDetachOnDelete:
    def test_delete_guardrails_detaches_from_watched(self, created_ids):
        # Create a fresh guardrails + watched repo wiring
        gres = requests.post(f"{API}/guardrails/from-preset",
                             json={"preset": "startup"}, timeout=15)
        assert gres.status_code == 200
        gid = gres.json()["id"]

        wres = requests.post(
            f"{API}/watched-repos",
            json={"repo_url": TEST_REPO_URL + "-detach", "guardrails_id": gid},
            timeout=15,
        )
        assert wres.status_code == 200
        wid = wres.json()["id"]
        assert wres.json()["guardrails_id"] == gid
        created_ids["watched"].append(wid)

        # Delete the guardrails
        d = requests.delete(f"{API}/guardrails/{gid}", timeout=15)
        assert d.status_code == 200

        # Confirm watched repo is detached
        w = next(w for w in requests.get(f"{API}/watched-repos").json() if w["id"] == wid)
        assert w.get("guardrails_id") is None, "guardrails_id should be nulled after deletion"


# ── Final cleanup ────────────────────────────────────────────────────────────
def test_zzz_cleanup(created_ids):
    """Best-effort cleanup of test-created data."""
    for wid in created_ids["watched"]:
        requests.delete(f"{API}/watched-repos/{wid}", timeout=15)
    for gid in created_ids["guardrails"]:
        requests.delete(f"{API}/guardrails/{gid}", timeout=15)
    print(f"Cleaned up {len(created_ids['watched'])} watched + {len(created_ids['guardrails'])} guardrails")
