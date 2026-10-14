"""管理画面のAPIのテスト。実際の Firestore を使う（テスト用のユーザーIDで書き込む）。"""

import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(".env")

from fastapi.testclient import TestClient  # noqa: E402

from hackathon_agent.governance import approvals  # noqa: E402
from ui.app import app  # noqa: E402

client = TestClient(app, base_url="http://testserver")
SAME = {"Origin": "http://testserver"}


@pytest.fixture
def user() -> str:
    return f"test-ui-{uuid.uuid4().hex[:6]}"


def _pending(user: str) -> str:
    return approvals.create(
        user_id=user, session_id="t", tool="register_shared_scholarship", args={"name": "<img src=x onerror=alert(1)>"}
    )


def test_承認待ちが一覧に出る(user):
    ap = _pending(user)
    s = client.get("/api/state", params={"user_id": user}).json()
    assert [a["id"] for a in s["approvals"]] == [ap]
    assert s["stats"]["pending"] == 1


def test_他のユーザーには見えない(user):
    _pending(user)
    s = client.get("/api/state", params={"user_id": "someone-else-" + user}).json()
    assert s["approvals"] == []


def test_本人は同じオリジンから承認できる(user):
    ap = _pending(user)
    r = client.post(f"/api/approvals/{ap}/decide", json={"user_id": user, "approve": True}, headers=SAME)
    assert r.json()["ok"] is True
    s = client.get("/api/state", params={"user_id": user}).json()
    assert s["approvals"][0]["status"] == "approved" and s["stats"]["median_seconds"] is not None
    assert any(a["tool"] == "(approval)" and a["decision"] == "approved" for a in s["audit"])  # 監査ログに残る


def test_別のオリジンからの承認は拒否する(user):
    ap = _pending(user)
    body = {"user_id": user, "approve": True}
    assert client.post(f"/api/approvals/{ap}/decide", json=body).status_code == 403
    r = client.post(f"/api/approvals/{ap}/decide", json=body, headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 403
    assert approvals.get(ap)["status"] == "pending"


def test_本人以外は承認できない(user):
    ap = _pending(user)
    r = client.post(f"/api/approvals/{ap}/decide", json={"user_id": "other", "approve": True}, headers=SAME)
    assert r.json()["ok"] is False and approvals.get(ap)["status"] == "pending"


def test_画面はHTMLとして解釈しない書き方になっている():
    html = (Path("ui") / "index.html").read_text(encoding="utf-8")
    assert "innerHTML" not in html and "insertAdjacentHTML" not in html and "document.write" not in html
