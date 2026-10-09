"""承認ロジックのテスト。実際の Firestore を使う（テスト用のユーザーIDで書き込む）。"""

import uuid

import pytest
from dotenv import load_dotenv

load_dotenv(".env")

from hackathon_agent.governance import approvals  # noqa: E402

TOOL = "send_payment"
ARGS = {"payee": "B社", "amount": 30000, "reason": "備品購入"}


@pytest.fixture
def requester() -> str:
    return f"test-user-{uuid.uuid4().hex[:6]}"


def _new(requester: str) -> str:
    return approvals.create(user_id=requester, session_id="test", tool=TOOL, args=ARGS)


def _consume(approval_id: str, user: str, args: dict = ARGS) -> tuple[bool, str]:
    return approvals.consume(
        approval_id=approval_id, user_id=user, tool=TOOL, args={**args, "approval_id": approval_id}
    )


def test_承認前は実行できない(requester):
    ap = _new(requester)
    ok, why = _consume(ap, requester)
    assert not ok and "まだ承認されていません" in why


def test_承認後に1回だけ実行できる(requester):
    ap = _new(requester)
    assert approvals.decide(approval_id=ap, approver="manager", approve=True)[0]
    assert _consume(ap, requester)[0]
    ok, why = _consume(ap, requester)
    assert not ok and "使用済み" in why


def test_依頼した本人は承認できない(requester):
    ap = _new(requester)
    ok, why = approvals.decide(approval_id=ap, approver=requester, approve=True)
    assert not ok and "職務分離" in why


def test_承認後に金額を変えると実行できない(requester):
    ap = _new(requester)
    approvals.decide(approval_id=ap, approver="manager", approve=True)
    ok, why = _consume(ap, requester, {**ARGS, "amount": 90000})
    assert not ok and "一致しません" in why
    # すり替えに失敗しても、正しい内容ならまだ使える
    assert _consume(ap, requester)[0]


def test_別のユーザーは承認を使えない(requester):
    ap = _new(requester)
    approvals.decide(approval_id=ap, approver="manager", approve=True)
    ok, why = _consume(ap, "someone-else")
    assert not ok and "別のユーザー" in why


def test_却下されたら実行できない(requester):
    ap = _new(requester)
    approvals.decide(approval_id=ap, approver="manager", approve=False, comment="予算外")
    ok, why = _consume(ap, requester)
    assert not ok and "却下" in why and "予算外" in why


def test_存在しない承認IDは拒否(requester):
    ok, why = _consume("ap-doesnotexist", requester)
    assert not ok and "存在しません" in why
