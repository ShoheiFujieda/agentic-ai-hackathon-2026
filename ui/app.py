"""最小の管理画面と保存リストのAPI。承認待ちの承認／却下、監査ログ、検索結果の保存リスト（CSV出力つき）。

AI の会話（adk web）とは別の経路で承認するための画面。公開デプロイの前に IAP などの認証で守ること。
起動: uv run uvicorn ui.app:app --port 9100
"""

import csv
import hashlib
import io
import logging
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from google.cloud.firestore_v1.base_query import FieldFilter
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
    }


def _same_origin(request: Request) -> None:
    """別のサイトからの送信を防ぐ: 同じオリジンからの書き込みだけ受け付ける。"""
    origin = request.headers.get("origin")
    if not origin or urlparse(origin).netloc != request.headers.get("host"):
        raise HTTPException(403, "同じオリジンからの操作だけ受け付けます")


class Decision(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    approve: bool
    comment: str = Field(default="", max_length=200)


@app.post("/api/approvals/{approval_id}/decide")
def decide(approval_id: str, body: Decision, request: Request) -> dict:
    _same_origin(request)
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


# ---------- 保存リスト（本人の領域への保存。承認は不要） ----------
SAVED = "saved_scholarships"
MAX_SAVED_PER_CALL = 100
STATUSES = ("応募できる", "要確認", "未確認の候補", "募集終了", "対象外")


def _short(max_len: int):
    return Field(default="", max_length=max_len)


class SavedItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    organization: str = _short(200)
    status: str = Field(max_length=20)
    deadline: str | None = Field(default=None, max_length=20)
    amount: str | None = Field(default=None, max_length=60)
    route: str | None = Field(default=None, max_length=20)
    reasons: list[str] = Field(default_factory=list, max_length=6)
    official_url: str = _short(2000)
    source: str = _short(40)


class SaveRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    items: list[SavedItem] = Field(min_length=1, max_length=MAX_SAVED_PER_CALL)


def _doc_id(user_id: str, item_id: str) -> str:
    return hashlib.sha256(f"{user_id}\0{item_id}".encode()).hexdigest()[:24]


def _saved(user_id: str) -> list[dict]:
    col = audit._db().collection(SAVED)
    rows = [d.to_dict() for d in col.where(filter=FieldFilter("user_id", "==", user_id)).stream()]
    return sorted(rows, key=lambda r: r.get("saved_at") or datetime.min.replace(tzinfo=UTC), reverse=True)


@app.get("/api/saved")
def saved(user_id: str = "user") -> dict:
    return {"items": _plain([{k: v for k, v in r.items() if k != "user_id"} for r in _saved(user_id)])}


@app.post("/api/saved")
def save(body: SaveRequest, request: Request) -> dict:
    _same_origin(request)
    col = audit._db().collection(SAVED)
    for it in body.items:
        url = it.official_url
        if url and not url.startswith("https://"):
            url = ""  # https 以外のURLは保存しない
        col.document(_doc_id(body.user_id, it.id)).set(
            {**it.model_dump(), "official_url": url, "user_id": body.user_id, "saved_at": datetime.now(UTC)}
        )
    audit.record(
        user_id=body.user_id,
        session_id="-",
        tool="(save_list)",
        args={"count": len(body.items), "names": [i.name for i in body.items][:5]},
        decision="executed",
        reason="本人の保存リストに保存",
    )
    return {"ok": True, "count": len(body.items)}


@app.delete("/api/saved/{item_id}")
def unsave(item_id: str, request: Request, user_id: str = "user") -> dict:
    _same_origin(request)
    audit._db().collection(SAVED).document(_doc_id(user_id, item_id)).delete()
    return {"ok": True}


def _csv_cell(v) -> str:
    """表計算ソフトで式として実行されないよう、式の記号で始まるセルには ' を付ける（CSV インジェクション対策）。"""
    s = "" if v is None else (" / ".join(v) if isinstance(v, list) else str(v))
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


@app.get("/api/saved.csv")
def saved_csv(user_id: str = "user") -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "奨学金名",
            "運営団体",
            "判定",
            "締切",
            "金額",
            "申請方法",
            "確認すること・理由",
            "公式ページ",
            "見つけた方法",
            "保存日時",
        ]
    )
    for r in _saved(user_id):
        w.writerow(
            [
                _csv_cell(x)
                for x in (
                    r.get("name"),
                    r.get("organization"),
                    r.get("status"),
                    r.get("deadline"),
                    r.get("amount"),
                    r.get("route"),
                    r.get("reasons"),
                    r.get("official_url"),
                    r.get("source"),
                    _plain(r.get("saved_at")),
                )
            ]
        )
    # Excel で文字化けしないよう、BOM つきの UTF-8 にする
    body = "\ufeff" + buf.getvalue()
    return Response(
        body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="scholarships.csv"', "Cache-Control": "no-store"},
    )
