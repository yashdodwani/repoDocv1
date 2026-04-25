# repoDoc — PRD

## Problem Statement
Autonomous Bug Fixing Agent + SaaS-grade Continuous Repo Monitoring with Guardrails:
"Give me a repo → I find, reproduce, fix, and PR bugs automatically — and watch every new commit
across all branches against your org's coding rules."

## Architecture
- **Frontend**: React 19 + Tailwind + shadcn (dark terminal theme, Chivo + JetBrains Mono)
- **Backend**: FastAPI + MongoDB (Motor async)
- **LLM**: Gemini 3 Flash via emergentintegrations (Emergent Universal Key)
- **Agent Loop**: observe → decide → act → verify → create_pr (refactored to support seeded bugs + branch targeting)
- **Watcher**: Background asyncio task polling every 5 min per WatchedRepo
- **Integrations**: Telegram Bot (polling), GitHub REST/Contents API + Issues API

## Core Requirements
1. On-demand repo analysis via dashboard or Telegram `/analyze`
2. Continuous repo watching: poll every 5 min across all branches, detect new commits, fetch diffs
3. Per-watched-repo guardrails: regex + LLM-driven rules; 4 presets (Security First / Startup / Enterprise / Open Source) + custom rule builder
4. Violations trigger: WatchEvent record + GitHub Issue + Telegram alert + auto fix-PR back on the originating branch
5. Conversational AI on Telegram and GitHub PR comments
6. Web portal: Dashboard, Watch (continuous monitoring), Guardrails, History, Settings

## What's Implemented (Apr 2026 — SaaS Pivot Complete)

### Backend
- `agent.py` — accepts `target_branch`, `seed_bugs`, `watch_event_id`; clones with `-b`, skips pytest/flake8 when seeded, links analysis to WatchEvent
- `github_service.py` — `list_branches()`, `get_commit()`, `build_diff_from_commit()`, `create_issue()`; `create_pr(base_branch=...)` targets originating branch
- `guardrails_service.py` — 8 BUILTIN_RULES, 4 PRESET_TEMPLATES, `evaluate_diff()` (regex + LLM via Gemini), `violations_to_bugs()`
- `watcher_service.py` — `WatcherService.start/tick/check_repo/_process_commit`; first-run baselines silently
- `models.py` — Guardrails, GuardrailRule, WatchedRepo, WatchEvent
- `server.py` — full CRUD on guardrails + watched-repos, watch-events list, check-now trigger; watcher started on init_services

### Frontend
- `/guardrails` — preset cards (Security First / Startup / Enterprise / Open Source) + custom rule builder (toggle built-in rules, add regex rules with category/severity), saved rulesets list
- `/watch` — Add Repo form with guardrails dropdown + chat ID, watched-repo cards (pause/resume/check-now/delete/show events), per-repo expandable events, global recent activity feed
- NavBar: + Watch + Guardrails links

### API Endpoints (new)
- `GET /api/guardrails/builtin` — list 8 built-in rules + 4 presets
- `POST /api/guardrails/from-preset` — instantiate from preset key
- `GET|POST /api/guardrails`, `GET|PUT|DELETE /api/guardrails/{id}`
- `GET|POST /api/watched-repos`, `PUT|DELETE /api/watched-repos/{id}`, `POST /api/watched-repos/{id}/check-now`
- `GET /api/watch-events?watched_repo_id=&limit=`

### Verified Live
- yashdodwani/AuditRx: watcher detected new commit on `main` → 5 violations → opened **Issue #2** + **PR #3 → main** ✅
- 18/18 backend pytest cases passed; frontend 100% with all data-testids in place

## Backlog

### P1
- [ ] Telegram inline approve/reject buttons for fix PRs
- [ ] JS/TS guardrail support (already runs against any diff; tested only on Python repos)
- [ ] Webhook mode (replace 5-min polling with GitHub push webhooks)
- [ ] Editable saved rulesets via UI (currently create + delete only)
- [ ] Refactor server.py into routers/ subpackage (currently 442 lines)

### P2
- [ ] Multi-org / multi-tenant support with auth
- [ ] Slack notifications channel
- [ ] Email digest of weekly violations
- [ ] PR auto-merge on green CI when violations are auto-fixed
- [ ] Guardrail "dry run" mode (alert only, no auto-PR)

### P3
- [ ] GitHub App (replace PAT)
- [ ] Watch event delete API + retention policy
- [ ] Diff syntax highlighting (prism.js) on AnalysisDetail

## Test Credentials
See `/app/memory/test_credentials.md`. GitHub PAT + Telegram token configured in DB.
