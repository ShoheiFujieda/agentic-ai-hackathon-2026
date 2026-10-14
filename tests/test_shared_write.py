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
    assert approvals.decide(approval_id=ap, approver=user, approve=True)[0]
    assert _guard(args, ctx, ap) is None  # ガードを通過 = ツールが実行される
    out = tools.register_shared_scholarship(**args, approval_id=ap, tool_context=ctx)
    assert out["status"] == "ok"
    assert out["registered"]["approved_by"] == user and out["registered"]["registered_by"] == user
    assert _guard(args, ctx, ap)["status"] == "blocked"  # 使い回しは不可


def test_承認後に内容をすり替えると止まる(req):
    user, args, ctx = req
    ap = _guard(args, ctx)["approval_id"]
    approvals.decide(approval_id=ap, approver=user, approve=True)
    r = _guard({**args, "official_url": "https://evil.example.com/x"}, ctx, ap)
    assert r["status"] == "blocked" and "一致しません" in r["reason"]


def test_本人以外は承認できない(req):
    _, args, ctx = req
    ap = _guard(args, ctx)["approval_id"]
    ok, why = approvals.decide(approval_id=ap, approver="someone-else", approve=True)
    assert not ok and "依頼した本人だけ" in why
    assert _guard(args, ctx, ap)["status"] == "blocked"  # 承認されていないので実行できない


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


def test_AIが使えるツールに承認の操作はない():
    from hackathon_agent.agent import root_agent

    names = {getattr(t, "__name__", str(t)) for t in root_agent.tools}
    assert not {n for n in names if "approv" in n or "decide" in n}
    assert set(guard.TOOL_RISK) == names  # 許可リストと実際のツールが一致している
