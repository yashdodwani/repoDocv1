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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="RepoDoctor API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global services
telegram_svc: Optional[TelegramService] = None
github_svc: Optional[GitHubService] = None
_telegram_task = None
_gh_comment_task = None


def get_llm_key():
    return os.environ.get("EMERGENT_LLM_KEY", "")


async def init_services():
    global telegram_svc, github_svc, _telegram_task, _gh_comment_task
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
    global _telegram_task, _gh_comment_task
    if _telegram_task:
        _telegram_task.cancel()
    if _gh_comment_task:
        _gh_comment_task.cancel()
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


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
