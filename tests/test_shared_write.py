"""共有データへの書き込み（高リスク）の承認フローを、実際の Firestore で通しで確かめる（F11）。"""

import uuid
from types import SimpleNamespace

import pytest
from dotenv import load_dotenv

load_dotenv(".env")

from hackathon_agent import tools  # noqa: E402
from hackathon_agent.governance import approvals, audit, guard  # noqa: E402


@pytest.fixture
def req():
    user = f"test-user-{uuid.uuid4().hex[:6]}"
    url = f"https://example.org/test-{uuid.uuid4().hex[:8]}"
    args = {"name": "テスト奨学金", "official_url": url, "deadline_note": "不明", "reason": "学生からの依頼"}
    ctx = SimpleNamespace(
        user_id=user, session=SimpleNamespace(id="test"), state={}, function_call_id=f"fc-{uuid.uuid4().hex[:6]}"
    )
    yield user, args, ctx
    import hashlib

    doc_id = hashlib.sha256(url.encode()).hexdigest()[:16]
    audit._db().collection(tools.SHARED_COLLECTION).document(doc_id).delete()


TOOL = SimpleNamespace(name="register_shared_scholarship")


def _guard(args, ctx, approval_id=""):
    return guard.before_tool_guard(TOOL, {**args, "approval_id": approval_id}, ctx)


def test_承認なしでは共有データに書けず承認待ちになる(req):
    _, args, ctx = req
    r = _guard(args, ctx)
    assert r["status"] == "pending" and r["approval_id"]


def test_承認後に1回だけ書ける(req):
    user, args, ctx = req
    ap = _guard(args, ctx)["approval_id"]
    # 承認前は止まる
    assert _guard(args, ctx, ap)["status"] == "blocked"
    assert approvals.decide(approval_id=ap, approver="admin", approve=True)[0]
    assert _guard(args, ctx, ap) is None  # ガードを通過 = ツールが実行される
    out = tools.register_shared_scholarship(**args, approval_id=ap, tool_context=ctx)
    assert out["status"] == "ok"
    assert out["registered"]["approved_by"] == "admin" and out["registered"]["registered_by"] == user
    assert _guard(args, ctx, ap)["status"] == "blocked"  # 使い回しは不可


def test_承認後に内容をすり替えると止まる(req):
    _, args, ctx = req
    ap = _guard(args, ctx)["approval_id"]
    approvals.decide(approval_id=ap, approver="admin", approve=True)
    r = _guard({**args, "official_url": "https://evil.example.com/x"}, ctx, ap)
    assert r["status"] == "blocked" and "一致しません" in r["reason"]


def test_依頼者本人は承認できない(req):
    user, args, ctx = req
    ap = _guard(args, ctx)["approval_id"]
    ok, why = approvals.decide(approval_id=ap, approver=user, approve=True)
    assert not ok and "職務分離" in why


@pytest.mark.parametrize(
    "bad",
    [
        {"official_url": "http://example.org/x"},  # https 以外
        {"official_url": "javascript:alert(1)"},
        {"official_url": "https://localhost/x"},  # ドットのないホスト名
        {"name": ""},
        {"name": "あ" * (guard.MAX_NAME + 1)},
        {"reason": "  "},
    ],
)
def test_不正な引数は承認待ちを作る前に止める(req, bad):
    _, args, ctx = req
    r = _guard({**args, **bad}, ctx)
    assert r["status"] == "blocked" and "approval_id" not in r
