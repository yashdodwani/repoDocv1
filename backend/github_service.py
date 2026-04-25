import httpx
import asyncio
import logging
import os
import re
import base64
import uuid
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

GH_BOT_SYSTEM = """You are RepoDoctor, an autonomous AI bug-fixing agent. You raised this PR by:
1. Cloning the repository
2. Running tests (pytest) and lint (flake8) to detect bugs
3. Using Gemini AI to generate minimal fixes
4. Verifying fixes by re-running the checks

You are now replying to a comment on the GitHub PR you created. Be concise, technical, and helpful.
Use GitHub Markdown formatting. Keep replies focused and under 300 words.
Never fabricate details — only refer to facts from the PR context provided."""


async def _ai_reply_for_pr(comment_body: str, pr_context: str, llm_key: str) -> str:
    """Generate AI reply to a PR comment using Gemini."""
    prompt = f"""PR Context:
{pr_context}

User's comment: {comment_body}

Reply to this comment as RepoDoctor."""
    try:
        chat = LlmChat(
            api_key=llm_key,
            session_id=f"gh-pr-{uuid.uuid4()}",
            system_message=GH_BOT_SYSTEM,
        ).with_model("gemini", "gemini-3-flash-preview")
        return await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        logger.warning(f"GH PR comment LLM error: {e}")
        return None


class GitHubService:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.api_url = "https://api.github.com"

    def _parse_repo(self, repo_url: str):
        match = re.search(r"github\.com[/:]([^/]+)/([^/\\.]+)", repo_url)
        if not match:
            raise ValueError(f"Cannot parse GitHub URL: {repo_url}")
        return match.group(1), match.group(2).replace(".git", "")

    async def _get(self, path: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{self.api_url}{path}", headers=self.headers)
            return r.json()

    async def _post(self, path: str, data: dict) -> dict:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{self.api_url}{path}", headers=self.headers, json=data)
            return r.json()

    async def _put(self, path: str, data: dict) -> dict:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.put(f"{self.api_url}{path}", headers=self.headers, json=data)
            return r.json()

    async def get_default_branch(self, owner: str, repo: str) -> str:
        data = await self._get(f"/repos/{owner}/{repo}")
        return data.get("default_branch", "main")

    async def get_branch_sha(self, owner: str, repo: str, branch: str) -> str:
        data = await self._get(f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
        return data["object"]["sha"]

    async def create_branch(self, owner: str, repo: str, branch: str, sha: str) -> bool:
        data = await self._post(
            f"/repos/{owner}/{repo}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": sha},
        )
        return "ref" in data

    async def get_file_sha(self, owner: str, repo: str, path: str, branch: str) -> str:
        """Get existing file SHA for update (required by GitHub API)"""
        try:
            data = await self._get(f"/repos/{owner}/{repo}/contents/{path}?ref={branch}")
            return data.get("sha", "")
        except Exception:
            return ""

    async def upsert_file(self, owner: str, repo: str, path: str,
                          content: str, message: str, branch: str) -> bool:
        """Create or update a file on a branch via GitHub Contents API"""
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        existing_sha = await self.get_file_sha(owner, repo, path, branch)
        payload = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        if existing_sha:
            payload["sha"] = existing_sha
        data = await self._put(f"/repos/{owner}/{repo}/contents/{path}", payload)
        return "content" in data

    async def create_pr(self, repo_url: str, repo_dir: str, analysis_id: str, fixes: list) -> str:
        owner, repo = self._parse_repo(repo_url)
        branch_name = f"repodoctor/fix-{analysis_id[:8]}"
        short_id = analysis_id[:8]

        # Get default branch and its HEAD SHA
        default_branch = await self.get_default_branch(owner, repo)
        base_sha = await self.get_branch_sha(owner, repo, default_branch)

        # Create new branch
        created = await self.create_branch(owner, repo, branch_name, base_sha)
        if not created:
            # Branch might already exist — ignore
            logger.warning(f"Branch {branch_name} may already exist")

        # Commit each fixed file via Contents API
        committed_files = []
        verified_fixes = [f for f in fixes if f.get("verified")]

        for fix in verified_fixes:
            file_rel = fix.get("file", "").lstrip("./")
            if not file_rel:
                continue

            full_path = os.path.join(repo_dir, file_rel)
            if not os.path.exists(full_path):
                # Try with leading ./
                alt = os.path.join(repo_dir, fix.get("file", ""))
                if os.path.exists(alt):
                    full_path = alt
                    file_rel = fix.get("file", "").lstrip("./")
                else:
                    logger.warning(f"Fixed file not found: {file_rel}")
                    continue

            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    new_content = f.read()
            except Exception as e:
                logger.warning(f"Could not read fixed file {file_rel}: {e}")
                continue

            commit_msg = f"fix({file_rel}): {fix.get('explanation', 'bug fix')[:72]}"
            ok = await self.upsert_file(owner, repo, file_rel, new_content, commit_msg, branch_name)
            if ok:
                committed_files.append(file_rel)
                logger.info(f"Committed fix to {file_rel} on branch {branch_name}")
            else:
                logger.warning(f"Failed to commit fix to {file_rel}")

        if not committed_files:
            raise Exception("No fixed files could be committed to the branch")

        # Build PR description
        fix_lines = "\n".join(
            f"- **{f.get('file', '?')}**: {f.get('explanation', 'fixed')}"
            for f in verified_fixes[:5]
        )
        pr_body = f"""## RepoDoctor Autonomous Fix

This PR was automatically generated by **[RepoDoctor](https://repodoctor-1.preview.emergentagent.com)** — an autonomous bug fixing agent.

### Bugs Fixed ({len(verified_fixes)})
{fix_lines}

### What RepoDoctor did
1. Cloned repository and built file map
2. Ran tests (`pytest`) and lint (`flake8`) to find failures
3. Used **Gemini 3 Flash** to generate minimal, targeted fixes
4. Verified each fix by re-running the checks
5. Opened this PR for your review

> Analysis ID: `{short_id}` &nbsp;|&nbsp; Files changed: `{', '.join(committed_files[:3])}`

---
*Please review the changes above and merge if they look correct.*
"""

        pr_data = await self._post(
            f"/repos/{owner}/{repo}/pulls",
            {
                "title": f"fix: {len(verified_fixes)} bug(s) fixed by RepoDoctor [{short_id}]",
                "body": pr_body,
                "head": branch_name,
                "base": default_branch,
            },
        )

        if "html_url" not in pr_data:
            raise Exception(f"PR creation failed: {pr_data.get('message', str(pr_data))}")

        return pr_data["html_url"]

    # ── PR Comment Bot ─────────────────────────────────────────────────────────

    def _pr_number_from_url(self, pr_url: str) -> int | None:
        """Extract PR number from GitHub PR URL."""
        m = re.search(r"/pull/(\d+)$", pr_url)
        return int(m.group(1)) if m else None

    def _build_pr_context(self, analysis: dict) -> str:
        bugs = analysis.get("bugs", [])
        fixes = [f for f in analysis.get("fixes", []) if f.get("verified")]
        bug_lines = "\n".join(f"- {b.get('description','')[:100]}" for b in bugs[:8])
        fix_lines = "\n".join(
            f"- **{f.get('file','?')}**: {f.get('explanation','')[:100]}" for f in fixes[:5]
        )
        return (
            f"Repo: {analysis.get('repo_name','?')}\n"
            f"Bugs found ({len(bugs)}):\n{bug_lines}\n\n"
            f"Fixes applied ({len(fixes)}):\n{fix_lines}\n\n"
            f"PR: {analysis.get('pr_url','')}"
        )

    async def get_pr_comments(self, owner: str, repo: str, pr_number: int) -> list:
        data = await self._get(f"/repos/{owner}/{repo}/issues/{pr_number}/comments")
        return data if isinstance(data, list) else []

    async def post_pr_comment(self, owner: str, repo: str, pr_number: int, body: str) -> bool:
        data = await self._post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            {"body": body},
        )
        return "id" in data

    async def poll_pr_comments(self, db, llm_key: str):
        """Background task: poll all RepoDoctor PRs for new comments and reply with AI."""
        logger.info("GitHub PR comment polling started")
        while True:
            try:
                analyses = await db.analyses.find(
                    {"pr_url": {"$ne": None, "$exists": True}},
                    {"_id": 0},
                ).sort("created_at", -1).to_list(30)

                for analysis in analyses:
                    await self._check_and_reply(analysis, db, llm_key)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"PR comment poll error: {e}")

            await asyncio.sleep(30)

    async def _check_and_reply(self, analysis: dict, db, llm_key: str):
        pr_url = analysis.get("pr_url", "")
        if not pr_url:
            return
        try:
            owner, repo = self._parse_repo(pr_url)
            pr_number = self._pr_number_from_url(pr_url)
            if not pr_number:
                return

            comments = await self.get_pr_comments(owner, repo, pr_number)
            if not comments:
                return

            # Get already-responded comment IDs from DB
            record = await db.pr_responded_comments.find_one(
                {"pr_url": pr_url}, {"_id": 0}
            )
            responded_ids = set(record.get("comment_ids", [])) if record else set()

            for comment in comments:
                cid = comment.get("id")
                body = comment.get("body", "").strip()

                # Skip: already responded, empty, or our own RepoDoctor reply
                if cid in responded_ids or not body:
                    continue
                # Skip replies we already posted (identified by our footer)
                if "*— RepoDoctor AI*" in body or body.startswith("> ") and "RepoDoctor AI" in body:
                    responded_ids.add(cid)
                    continue

                # Generate AI reply
                pr_context = self._build_pr_context(analysis)
                reply = await _ai_reply_for_pr(body, pr_context, llm_key)
                if not reply:
                    continue

                bot_reply = f"> {body[:120]}{'...' if len(body)>120 else ''}\n\n{reply}\n\n---\n*— RepoDoctor AI*"
                posted = await self.post_pr_comment(owner, repo, pr_number, bot_reply)
                if posted:
                    logger.info(f"Replied to PR#{pr_number} comment #{cid} on {owner}/{repo}")
                    responded_ids.add(cid)
                    await db.pr_responded_comments.update_one(
                        {"pr_url": pr_url},
                        {"$set": {"comment_ids": list(responded_ids), "pr_url": pr_url}},
                        upsert=True,
                    )

        except Exception as e:
            logger.warning(f"_check_and_reply error for {pr_url}: {e}")
