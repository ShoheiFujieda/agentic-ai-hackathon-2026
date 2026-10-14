"""監査ログ: 誰が・いつ・何を・なぜ・結果どうなったかを Firestore に記録する。"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from google.cloud import firestore

logger = logging.getLogger(__name__)

COLLECTION = "audit_logs"

_client: firestore.Client | None = None


def _db() -> firestore.Client:
    global _client
    if _client is None:
        _client = firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    return _client


def recent(user_id: str, limit: int = 50, scan: int = 300) -> list[dict[str, Any]]:
    """本人の直近の監査ログ（新しい順）。複合インデックスを避けるため、新しい順に scan 件読んで本人分を絞る。"""
    docs = _db().collection(COLLECTION).order_by("at", direction=firestore.Query.DESCENDING).limit(scan).stream()
    rows = [d.to_dict() for d in docs]
    return [r for r in rows if r.get("user_id") == user_id][:limit]


def record(
    *,
    user_id: str,
    session_id: str,
    tool: str,
    args: dict[str, Any],
    decision: str,
    reason: str,
    result: dict[str, Any] | None = None,
) -> bool:
    """監査ログを1件書く。書けたら True。

    decision: allowed / blocked / pending / executed のいずれか。
    """
    entry = {
        "at": datetime.now(UTC),
        "user_id": user_id,
        "session_id": session_id,
        "tool": tool,
        "args": args,
        "decision": decision,
        "reason": reason,
        "result": result,
    }
    # Cloud Run では標準出力が Cloud Logging に入るので、Firestore と二重に残す
    logger.info("AUDIT %s", json.dumps({**entry, "at": entry["at"].isoformat()}, ensure_ascii=False, default=str))
    try:
        _db().collection(COLLECTION).add(entry)
        return True
    except Exception:
        logger.exception("監査ログを Firestore に書けませんでした")
        return False
