"""最小の管理画面。承認待ちの承認／却下、監査ログ、来年の準備カレンダーを1ページで見せる。

AI の会話（adk web）とは別の経路で承認するための画面。公開デプロイの前に IAP などの認証で守ること。
起動: uv run uvicorn ui.app:app --port 9100
"""

import logging
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from hackathon_agent.governance import approvals, audit  # noqa: E402

logger = logging.getLogger(__name__)
app = FastAPI(title="奨学金エージェント 管理画面", docs_url=None, redoc_url=None, openapi_url=None)
INDEX = Path(__file__).with_name("index.html")


def _plain(v: Any) -> Any:
    """Firestore の値を JSON にできる形にする（日時は ISO 文字列）。"""
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return v


def _seconds(ap: dict) -> float | None:
    if ap.get("decided_at") and ap.get("created_at"):
        return (ap["decided_at"] - ap["created_at"]).total_seconds()
    return None


def _calendar(rows: list[dict]) -> dict:
    for r in rows:
        res = r.get("result") or {}
        if r.get("tool") == "find_scholarships" and r.get("decision") == "executed" and res.get("status") == "ok":
            return {"at": _plain(r["at"]), "today": res.get("today"), "items": res.get("next_year_calendar") or []}
    return {"at": None, "today": None, "items": []}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX.read_text(encoding="utf-8")


@app.get("/api/state")
def state(user_id: str = "user") -> dict:
    aps = approvals.list_for_user(user_id)
    rows = audit.recent(user_id, limit=300)
    times = [t for a in aps if (t := _seconds(a)) is not None]
    return {
        "user_id": user_id,
        "approvals": _plain(
            [
                {
                    k: a.get(k)
                    for k in ("id", "status", "tool", "args", "created_at", "expires_at", "decided_at", "comment")
                }
                for a in aps[:30]
            ]
        ),
        "stats": {
            "total": len(aps),
            "pending": sum(a["status"] == "pending" for a in aps),
            "approved": sum(a["status"] in ("approved", "used") for a in aps),
            "rejected": sum(a["status"] == "rejected" for a in aps),
            "median_seconds": statistics.median(times) if times else None,
        },
        "audit": _plain(
            [
                {
                    "at": r["at"],
                    "tool": r["tool"],
                    "args": r.get("args"),
                    "decision": r["decision"],
                    "reason": r.get("reason"),
                }
                for r in rows[:50]
            ]
        ),
        "calendar": _calendar(rows),
    }


class Decision(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    approve: bool
    comment: str = Field(default="", max_length=200)


@app.post("/api/approvals/{approval_id}/decide")
def decide(approval_id: str, body: Decision, request: Request) -> dict:
    # 別のサイトからの送信を防ぐ: 同じオリジンからの POST だけ受け付ける
    origin = request.headers.get("origin")
    if not origin or urlparse(origin).netloc != request.headers.get("host"):
        raise HTTPException(403, "同じオリジンからの操作だけ受け付けます")
    ok, msg = approvals.decide(
        approval_id=approval_id, approver=body.user_id, approve=body.approve, comment=body.comment
    )
    audit.record(
        user_id=body.user_id,
        session_id="-",
        tool="(approval)",
        args={"approval_id": approval_id, "comment": body.comment},
        decision=("approved" if body.approve else "rejected") if ok else "blocked",
        reason=msg,
    )
    return {"ok": ok, "message": msg}
