import httpx
import asyncio
import logging
import uuid
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are RepoDoctor, an autonomous AI bug-fixing agent. You:
- Analyze GitHub repositories for bugs (failing tests, lint errors, logical issues)
- Generate minimal code fixes using Gemini AI
- Verify fixes by re-running tests
- Raise Pull Requests automatically on separate branches

You are currently chatting via Telegram with the repo owner. Be concise, helpful, and friendly.
Use HTML formatting for Telegram: <b>bold</b>, <code>code</code>, <i>italic</i>.
Keep responses under 400 characters when possible. Never make up analysis results."""


def _build_context(analysis: dict) -> str:
    if not analysis:
        return ""
    bugs = analysis.get("bugs", [])
    fixes = [f for f in analysis.get("fixes", []) if f.get("verified")]
    bug_list = "\n".join(f"• {b.get('description','')[:80]}" for b in bugs[:5])
    fix_list = "\n".join(f"• {f.get('explanation','')[:80]}" for f in fixes[:3])
    return f"""Last analysis: <b>{analysis.get('repo_name','unknown')}</b>
Status: {analysis.get('status')}
Bugs found: {len(bugs)} | Fixes verified: {len(fixes)}
PR: {analysis.get('pr_url') or 'not created'}
Bugs:
{bug_list}
Fixes applied:
{fix_list}"""


class TelegramService:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self._running = False

    async def send_message(self, chat_id: str, text: str):
        if not self.token or not chat_id:
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{self.base_url}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                )
        except Exception as e:
            logger.warning(f"Telegram send_message failed: {e}")

    async def send_typing(self, chat_id: str):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"{self.base_url}/sendChatAction",
                    json={"chat_id": chat_id, "action": "typing"},
                )
        except Exception:
            pass

    async def get_updates(self, offset: int = 0):
        try:
            async with httpx.AsyncClient(timeout=35) as client:
                resp = await client.get(
                    f"{self.base_url}/getUpdates",
                    params={"offset": offset, "timeout": 25, "allowed_updates": ["message"]},
                )
                return resp.json().get("result", [])
        except Exception as e:
            logger.warning(f"Telegram get_updates failed: {e}")
            return []

    async def handle_conversation(self, chat_id: str, user_message: str, db, llm_key: str):
        """Handle any non-command message with Gemini AI using last analysis context."""
        await self.send_typing(chat_id)

        # Fetch last analysis for this chat for context
        last_analysis = None
        try:
            last_analysis = await db.analyses.find_one(
                {"telegram_chat_id": chat_id, "status": {"$ne": "queued"}},
                {"_id": 0},
                sort=[("created_at", -1)],
            )
        except Exception:
            pass

        context = _build_context(last_analysis) if last_analysis else ""
        prompt = f"{context}\n\nUser message: {user_message}" if context else user_message

        try:
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"tg-{chat_id}-{uuid.uuid4()}",
                system_message=SYSTEM_PROMPT,
            ).with_model("gemini", "gemini-3-flash-preview")
            response = await chat.send_message(UserMessage(text=prompt))
            await self.send_message(chat_id, response)
        except Exception as e:
            logger.warning(f"Telegram conversation LLM error: {e}")
            await self.send_message(
                chat_id,
                "Sorry, I couldn't process that right now. Use /analyze to start a new analysis."
            )

    async def start_polling(self, db, trigger_analysis_fn, llm_key: str = ""):
        self._running = True
        offset = 0
        logger.info("Telegram bot polling started")
        while self._running:
            try:
                updates = await self.get_updates(offset)
                for update in updates:
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    text = message.get("text", "").strip()
                    chat_id = str(message.get("chat", {}).get("id", ""))
                    if not text or not chat_id:
                        continue

                    if text.startswith("/analyze "):
                        repo_url = text[9:].strip()
                        if repo_url:
                            await self.send_message(
                                chat_id,
                                f"<b>RepoDoctor</b> starting analysis...\n\n<code>{repo_url}</code>"
                            )
                            asyncio.create_task(trigger_analysis_fn(repo_url, chat_id))

                    elif text in ("/start", "/help"):
                        await self.send_message(
                            chat_id,
                            "<b>RepoDoctor Bot</b>\n\n"
                            "I autonomously find and fix bugs in GitHub repos.\n\n"
                            "<b>Commands:</b>\n"
                            "<code>/analyze https://github.com/user/repo</code> — start analysis\n"
                            "<code>/status</code> — last analysis status\n\n"
                            "Or just <b>ask me anything</b> about your code!"
                        )

                    elif text == "/status":
                        last = await db.analyses.find_one(
                            {"telegram_chat_id": chat_id},
                            {"_id": 0},
                            sort=[("created_at", -1)],
                        )
                        if last:
                            bugs = len(last.get("bugs", []))
                            fixes = len([f for f in last.get("fixes", []) if f.get("verified")])
                            pr = last.get("pr_url") or "not created"
                            await self.send_message(
                                chat_id,
                                f"<b>Last Analysis</b>\n"
                                f"Repo: <code>{last.get('repo_name','?')}</code>\n"
                                f"Status: {last.get('status')}\n"
                                f"Bugs: {bugs} | Fixes: {fixes}\n"
                                f"PR: {pr}"
                            )
                        else:
                            await self.send_message(chat_id, "No analyses yet. Use /analyze to start.")

                    else:
                        # Conversational AI for any other message
                        if llm_key:
                            asyncio.create_task(
                                self.handle_conversation(chat_id, text, db, llm_key)
                            )
                        else:
                            await self.send_message(
                                chat_id,
                                "Use <code>/analyze https://github.com/user/repo</code> to start."
                            )

                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Telegram polling error: {e}")
                await asyncio.sleep(5)

    def stop(self):
        self._running = False
