from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

from models import Analysis, AnalysisCreate, Settings
from agent import run_analysis_task
from telegram_service import TelegramService
from github_service import GitHubService
from watcher_service import WatcherService
import guardrails_service as gs_mod

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="repoDoc API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global services
telegram_svc: Optional[TelegramService] = None
github_svc: Optional[GitHubService] = None
watcher_svc: Optional[WatcherService] = None
_telegram_task = None
_gh_comment_task = None
_watcher_task = None


def get_llm_key():
    return os.environ.get("EMERGENT_LLM_KEY", "")


async def _agent_runner(analysis_id: str, repo_url: str, target_branch: Optional[str] = None,
                        seed_bugs: Optional[list] = None, watch_event_id: Optional[str] = None,
                        telegram_chat_id: Optional[str] = None):
    """Wrapper that injects current service refs into the agent."""
    await run_analysis_task(
        analysis_id=analysis_id,
        repo_url=repo_url,
        db=db,
        llm_key=get_llm_key(),
        telegram_svc=telegram_svc,
        github_svc=github_svc,
        telegram_chat_id=telegram_chat_id,
        target_branch=target_branch,
        seed_bugs=seed_bugs,
        watch_event_id=watch_event_id,
    )


async def init_services():
    global telegram_svc, github_svc, watcher_svc, _telegram_task, _gh_comment_task, _watcher_task
    settings = await db.settings.find_one({"id": "global"})

    gh_token = (settings or {}).get("github_token") or os.environ.get("GITHUB_TOKEN", "")
    tg_token = (settings or {}).get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if gh_token:
        github_svc = GitHubService(gh_token)
        # Start GitHub PR comment polling
        if _gh_comment_task is None or _gh_comment_task.done():
            _gh_comment_task = asyncio.create_task(
                github_svc.poll_pr_comments(db, get_llm_key())
            )

    if tg_token and (_telegram_task is None or _telegram_task.done()):
        telegram_svc = TelegramService(tg_token)
        _telegram_task = asyncio.create_task(
            telegram_svc.start_polling(db, trigger_analysis_from_telegram, llm_key=get_llm_key())
        )

    # Start the continuous repo watcher (runs always; no-op if no watched repos)
    if watcher_svc is None:
        watcher_svc = WatcherService()
    if _watcher_task is None or _watcher_task.done():
        _watcher_task = asyncio.create_task(
            watcher_svc.start(
                db,
                lambda: github_svc,
                lambda: telegram_svc,
                _agent_runner,
                get_llm_key,
            )
        )


async def trigger_analysis_from_telegram(repo_url: str, chat_id: str):
    analysis = Analysis(repo_url=repo_url, telegram_chat_id=chat_id)
    doc = analysis.model_dump()
    await db.analyses.insert_one(doc)
    asyncio.create_task(run_analysis_task(
        analysis.id, repo_url, db, get_llm_key(),
        telegram_svc=telegram_svc,
        github_svc=github_svc,
        telegram_chat_id=chat_id,
    ))


@app.on_event("startup")
async def startup():
    await db.analyses.update_many(
        {"status": {"$in": ["cloning", "analyzing", "fixing", "verifying", "creating_pr"]}},
        {"$set": {"status": "failed", "error": "Server restarted during analysis"}}
    )
    await init_services()


@app.on_event("shutdown")
async def shutdown():
    global _telegram_task, _gh_comment_task, _watcher_task
    if _telegram_task:
        _telegram_task.cancel()
    if _gh_comment_task:
        _gh_comment_task.cancel()
    if _watcher_task:
        _watcher_task.cancel()
    client.close()


# ── GitHub Webhook ────────────────────────────────────────────────────────────

@api_router.post("/webhook/github")
async def github_webhook(request: dict):
    """Receive GitHub webhook events for PR comments."""
    action = request.get("action", "")
    comment = request.get("comment", {})
    pr = request.get("issue", {}) or request.get("pull_request", {})
    pr_url = pr.get("html_url", "")

    if action == "created" and comment and pr_url and github_svc:
        # Find the matching analysis
        analysis = await db.analyses.find_one({"pr_url": pr_url}, {"_id": 0})
        if analysis:
            asyncio.create_task(
                github_svc._check_and_reply(analysis, db, get_llm_key())
            )
    return {"ok": True}


# ── Analysis Routes ───────────────────────────────────────────────────────────

@api_router.post("/analyses", response_model=dict)
async def create_analysis(body: AnalysisCreate):
    analysis = Analysis(
        repo_url=body.repo_url,
        telegram_chat_id=body.telegram_chat_id,
    )
    doc = analysis.model_dump()
    await db.analyses.insert_one(doc)

    asyncio.create_task(run_analysis_task(
        analysis.id, body.repo_url, db, get_llm_key(),
        telegram_svc=telegram_svc,
        github_svc=github_svc,
        telegram_chat_id=body.telegram_chat_id,
    ))

    return {"id": analysis.id, "status": "queued", "message": "Analysis started"}


@api_router.get("/analyses", response_model=List[dict])
async def list_analyses():
    docs = await db.analyses.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    for doc in docs:
        doc.pop("logs", None)
        doc.pop("file_map", None)
    return docs


@api_router.get("/analyses/{analysis_id}", response_model=dict)
async def get_analysis(analysis_id: str):
    doc = await db.analyses.find_one({"id": analysis_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return doc


@api_router.delete("/analyses/{analysis_id}")
async def delete_analysis(analysis_id: str):
    result = await db.analyses.delete_one({"id": analysis_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"message": "Deleted"}


@api_router.get("/analyses/{analysis_id}/stream")
async def stream_logs(analysis_id: str):
    async def event_generator():
        last_count = 0
        attempts = 0
        while attempts < 300:
            doc = await db.analyses.find_one({"id": analysis_id}, {"_id": 0, "logs": 1, "status": 1})
            if not doc:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Not found'})}\n\n"
                break
            logs = doc.get("logs", [])
            if len(logs) > last_count:
                for log in logs[last_count:]:
                    yield f"data: {json.dumps({'type': 'log', **log})}\n\n"
                last_count = len(logs)
            status = doc.get("status", "")
            if status in ("completed", "failed"):
                yield f"data: {json.dumps({'type': 'done', 'status': status})}\n\n"
                break
            yield f"data: {json.dumps({'type': 'heartbeat', 'status': status})}\n\n"
            await asyncio.sleep(1)
            attempts += 1

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Stats Route ───────────────────────────────────────────────────────────────

@api_router.get("/stats")
async def get_stats():
    total = await db.analyses.count_documents({})
    completed = await db.analyses.count_documents({"status": "completed"})
    failed = await db.analyses.count_documents({"status": "failed"})
    running = await db.analyses.count_documents({"status": {"$nin": ["completed", "failed", "queued"]}})
    pipeline = [
        {"$group": {"_id": None,
                    "bugs": {"$sum": {"$size": {"$ifNull": ["$bugs", []]}}},
                    "fixes": {"$sum": {"$size": {"$filter": {"input": {"$ifNull": ["$fixes", []]},
                                                              "cond": {"$eq": ["$$this.verified", True]}}}}}}}
    ]
    agg = await db.analyses.aggregate(pipeline).to_list(1)
    bugs_total = agg[0]["bugs"] if agg else 0
    fixes_total = agg[0]["fixes"] if agg else 0
    prs = await db.analyses.count_documents({"pr_url": {"$ne": None, "$exists": True}})
    return {
        "total_analyses": total,
        "completed": completed,
        "failed": failed,
        "running": running,
        "bugs_found": bugs_total,
        "fixes_applied": fixes_total,
        "prs_created": prs,
    }


# ── Settings Routes ───────────────────────────────────────────────────────────

@api_router.get("/settings")
async def get_settings():
    doc = await db.settings.find_one({"id": "global"}, {"_id": 0})
    if not doc:
        return Settings().model_dump()
    result = dict(doc)
    if result.get("github_token"):
        t = result["github_token"]
        result["github_token_masked"] = t[:4] + "****" + t[-4:] if len(t) > 8 else "****"
    if result.get("telegram_bot_token"):
        t = result["telegram_bot_token"]
        result["telegram_bot_token_masked"] = t[:4] + "****" + t[-4:] if len(t) > 8 else "****"
    return result


@api_router.post("/settings")
async def save_settings(body: dict):
    body["id"] = "global"
    body["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.settings.replace_one({"id": "global"}, body, upsert=True)
    await init_services()
    return {"message": "Settings saved"}


@api_router.get("/health")
async def health():
    return {"status": "ok", "telegram": telegram_svc is not None, "github": github_svc is not None}


# ── Guardrails Routes ─────────────────────────────────────────────────────────

@api_router.get("/guardrails/builtin")
async def list_builtin_guardrails():
    return {
        "rules": gs_mod.BUILTIN_RULES,
        "presets": [
            {"key": k, **v} for k, v in gs_mod.PRESET_TEMPLATES.items()
        ],
    }


@api_router.post("/guardrails/from-preset")
async def create_guardrails_from_preset(body: dict):
    preset_key = body.get("preset", "startup")
    template = gs_mod.build_guardrails_from_preset(preset_key)
    from models import Guardrails
    gr = Guardrails(
        name=body.get("name") or template["name"],
        description=template["description"],
        rules=template["rules"],
    )
    doc = gr.model_dump()
    await db.guardrails.insert_one(dict(doc))
    return doc


@api_router.get("/guardrails")
async def list_guardrails():
    docs = await db.guardrails.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return docs


@api_router.get("/guardrails/{gid}")
async def get_guardrails(gid: str):
    doc = await db.guardrails.find_one({"id": gid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Guardrails not found")
    return doc


@api_router.post("/guardrails")
async def create_guardrails(body: dict):
    from models import Guardrails
    gr = Guardrails(
        name=body.get("name", "Custom Ruleset"),
        description=body.get("description", ""),
        rules=body.get("rules", []),
    )
    doc = gr.model_dump()
    await db.guardrails.insert_one(dict(doc))
    return doc


@api_router.put("/guardrails/{gid}")
async def update_guardrails(gid: str, body: dict):
    body.pop("_id", None)
    body["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.guardrails.update_one({"id": gid}, {"$set": body})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Guardrails not found")
    return await db.guardrails.find_one({"id": gid}, {"_id": 0})


@api_router.delete("/guardrails/{gid}")
async def delete_guardrails(gid: str):
    result = await db.guardrails.delete_one({"id": gid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Guardrails not found")
    # Detach from any watched repos
    await db.watched_repos.update_many({"guardrails_id": gid}, {"$set": {"guardrails_id": None}})
    return {"message": "Deleted"}


# ── Watched Repos Routes ──────────────────────────────────────────────────────

@api_router.get("/watched-repos")
async def list_watched_repos():
    docs = await db.watched_repos.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs


@api_router.post("/watched-repos")
async def add_watched_repo(body: dict):
    from models import WatchedRepo
    wr = WatchedRepo(
        repo_url=body.get("repo_url", ""),
        telegram_chat_id=body.get("telegram_chat_id", "") or "",
        guardrails_id=body.get("guardrails_id"),
    )
    if not wr.repo_url:
        raise HTTPException(status_code=400, detail="repo_url required")
    # Pre-fill repo_name
    try:
        owner = wr.repo_url.rstrip("/").split("/")[-2]
        name = wr.repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        wr.repo_name = f"{owner}/{name}"
    except Exception:
        pass
    doc = wr.model_dump()
    await db.watched_repos.insert_one(dict(doc))
    return doc


@api_router.put("/watched-repos/{wid}")
async def update_watched_repo(wid: str, body: dict):
    body.pop("_id", None)
    body.pop("id", None)
    result = await db.watched_repos.update_one({"id": wid}, {"$set": body})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Watched repo not found")
    return await db.watched_repos.find_one({"id": wid}, {"_id": 0})


@api_router.delete("/watched-repos/{wid}")
async def delete_watched_repo(wid: str):
    result = await db.watched_repos.delete_one({"id": wid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Watched repo not found")
    return {"message": "Deleted"}


@api_router.post("/watched-repos/{wid}/check-now")
async def check_watched_repo_now(wid: str):
    """Force an immediate watcher pass for a single repo."""
    watched = await db.watched_repos.find_one({"id": wid}, {"_id": 0})
    if not watched:
        raise HTTPException(status_code=404, detail="Watched repo not found")
    if not github_svc:
        raise HTTPException(status_code=400, detail="GitHub token not configured")
    if watcher_svc is None:
        raise HTTPException(status_code=400, detail="Watcher not initialized")
    asyncio.create_task(
        watcher_svc.check_repo(watched, db, github_svc, telegram_svc, _agent_runner, get_llm_key())
    )
    return {"message": "Check triggered"}


@api_router.get("/watch-events")
async def list_watch_events(watched_repo_id: Optional[str] = None, limit: int = 50):
    q = {}
    if watched_repo_id:
        q["watched_repo_id"] = watched_repo_id
    docs = await db.watch_events.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return docs


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
