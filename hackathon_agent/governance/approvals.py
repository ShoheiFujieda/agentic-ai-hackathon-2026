"""人間の承認（自前方式）。承認待ちを Firestore `approvals` に保存する。

状態の流れ: pending → approved / rejected → used（approved を1回だけ実行に使える）
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from google.cloud import firestore

from .audit import _db

COLLECTION = "approvals"
EXPIRES_AFTER = timedelta(hours=24)


def _args_hash(tool: str, args: dict[str, Any]) -> str:
    """承認時と実行時で中身が同じかを比べるための指紋。approval_id 自体は含めない。"""
    body = {k: v for k, v in args.items() if k != "approval_id"}
    canonical = json.dumps({"tool": tool, "args": body}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def create(*, user_id: str, session_id: str, tool: str, args: dict[str, Any]) -> str:
    """承認待ちを作り、承認IDを返す。"""
    approval_id = f"ap-{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    _db().collection(COLLECTION).document(approval_id).set(
        {
            "status": "pending",
            "requested_by": user_id,
            "session_id": session_id,
            "tool": tool,
            "args": {k: v for k, v in args.items() if k != "approval_id"},
            "args_hash": _args_hash(tool, args),
            "created_at": now,
            "expires_at": now + EXPIRES_AFTER,
        }
    )
    return approval_id


def consume(*, approval_id: str, user_id: str, tool: str, args: dict[str, Any]) -> tuple[bool, str]:
    """承認済みで中身が一致すれば used にして (True, 理由) を返す。だめなら (False, 理由)。

    2つの実行が同時に同じ承認を使えないよう、トランザクションで確認と更新を一度に行う。
    """
    ref = _db().collection(COLLECTION).document(approval_id)

    @firestore.transactional
    def _txn(txn: firestore.Transaction) -> tuple[bool, str]:
        snap = ref.get(transaction=txn)
        if not snap.exists:
            return False, f"承認ID「{approval_id}」は存在しません"
        ap = snap.to_dict()
        if ap["requested_by"] != user_id:
            return False, "この承認は別のユーザーの依頼に対するものです"
        if ap["tool"] != tool or ap["args_hash"] != _args_hash(tool, args):
            return False, "承認された内容と今回の内容が一致しません（承認後の変更は不可）"
        status = ap["status"]
        if status == "pending":
            return False, "まだ承認されていません。承認者の判断を待ってください"
        if status == "rejected":
            comment = ap.get("comment") or "コメントなし"
            return False, f"承認者が却下しました（{comment}）"
        if status == "used":
            return False, "この承認はすでに使用済みです（1回の承認で実行できるのは1回のみ）"
        if datetime.now(UTC) > ap["expires_at"]:
            return False, "承認の有効期限（24時間）が切れています。もう一度依頼してください"
        if status != "approved":
            return False, f"承認の状態が不正です（{status}）"
        txn.update(ref, {"status": "used", "used_at": datetime.now(UTC)})
        return True, f"承認済み（承認者: {ap.get('decided_by')}、承認ID: {approval_id}）"

    return _txn(_db().transaction())


def decide(*, approval_id: str, approver: str, approve: bool, comment: str = "") -> tuple[bool, str]:
    """承認者が承認または却下する。依頼した本人は承認できない（職務分離）。"""
    ref = _db().collection(COLLECTION).document(approval_id)

    @firestore.transactional
    def _txn(txn: firestore.Transaction) -> tuple[bool, str]:
        snap = ref.get(transaction=txn)
        if not snap.exists:
            return False, f"承認ID「{approval_id}」は存在しません"
        ap = snap.to_dict()
        if ap["status"] != "pending":
            return False, f"承認待ちではありません（現在: {ap['status']}）"
        if ap["requested_by"] == approver:
            return False, "依頼した本人は承認できません（職務分離）"
        txn.update(
            ref,
            {
                "status": "approved" if approve else "rejected",
                "decided_by": approver,
                "decided_at": datetime.now(UTC),
                "comment": comment,
            },
        )
        return True, "承認しました" if approve else "却下しました"

    return _txn(_db().transaction())


def list_pending() -> list[dict[str, Any]]:
    docs = _db().collection(COLLECTION).where(filter=firestore.FieldFilter("status", "==", "pending")).stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]
