from pydantic import BaseModel, Field
from typing import Annotated, Any, List, Optional, Dict
from datetime import datetime, timezone
import uuid


def utc_now():
    return datetime.now(timezone.utc).isoformat()




class LogEntry(BaseModel):
    timestamp: str = Field(default_factory=utc_now)
    level: str = "info"
    message: str


class AgentStep(BaseModel):
    step: str
    label: str
    status: str = "pending"
    message: str = ""
    updated_at: Optional[str] = None


class Bug(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    file: str = ""
    line: Optional[int] = None
    description: str
    stacktrace: str = ""
    severity: str = "medium"


class Fix(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bug_id: str
    file: str = ""
    original_code: str = ""
    fixed_code: str = ""
    diff: str = ""
    explanation: str = ""
    verified: bool = False


class FileMap(BaseModel):
    language: str = "unknown"
    total_files: int = 0
    test_files: List[str] = []
    entry_points: List[str] = []
    has_requirements: bool = False
    has_package_json: bool = False
    has_pytest: bool = False
    has_jest: bool = False


class Analysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_url: str
    repo_name: str = ""
    status: str = "queued"
    agent_steps: List[AgentStep] = Field(default_factory=lambda: [
        AgentStep(step="observe", label="Observe", status="pending"),
        AgentStep(step="decide", label="Decide", status="pending"),
        AgentStep(step="act", label="Act", status="pending"),
        AgentStep(step="verify", label="Verify", status="pending"),
        AgentStep(step="create_pr", label="Create PR", status="pending"),
    ])
    bugs: List[Bug] = []
    fixes: List[Fix] = []
    logs: List[LogEntry] = []
    file_map: Optional[dict] = None
    pr_url: Optional[str] = None
    pr_branch: Optional[str] = None
    error: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    target_branch: Optional[str] = None   # branch to target for fix PR
    triggered_by: str = "manual"          # manual | watcher
    created_at: str = Field(default_factory=utc_now)
    completed_at: Optional[str] = None


class AnalysisCreate(BaseModel):
    repo_url: str
    telegram_chat_id: Optional[str] = None


class Settings(BaseModel):
    id: str = "global"
    github_token: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    updated_at: str = Field(default_factory=utc_now)


# ── Guardrails Models ─────────────────────────────────────────────────────────

class GuardrailRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    category: str = "quality"          # security | quality | compliance
    type: str = "pattern"              # pattern | llm | builtin
    pattern: Optional[str] = None
    llm_prompt: Optional[str] = None
    builtin_id: Optional[str] = None
    severity: str = "warning"          # critical | warning | info
    enabled: bool = True


class Guardrails(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    rules: List[GuardrailRule] = []
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


# ── Watched Repo Models ───────────────────────────────────────────────────────

class WatchedRepo(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_url: str
    repo_name: str = ""
    telegram_chat_id: str = ""
    guardrails_id: Optional[str] = None
    active: bool = True
    last_commits: Dict[str, str] = {}   # branch -> last_sha
    events_count: int = 0
    issues_count: int = 0
    created_at: str = Field(default_factory=utc_now)
    last_checked_at: Optional[str] = None


class WatchEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    watched_repo_id: str
    repo_name: str = ""
    repo_url: str = ""
    branch: str
    commit_sha: str
    commit_message: str = ""
    commit_author: str = ""
    issues: List[dict] = []
    github_issue_url: Optional[str] = None
    analysis_id: Optional[str] = None
    pr_url: Optional[str] = None
    status: str = "clean"              # clean | issues_found
    created_at: str = Field(default_factory=utc_now)


class WatchCreate(BaseModel):
    repo_url: str
    telegram_chat_id: Optional[str] = None
    guardrails_id: Optional[str] = None
