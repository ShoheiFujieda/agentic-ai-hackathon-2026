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


def test_利用者向けサイトもHTMLとして解釈しない書き方になっている():
    html = (Path("ui") / "site.html").read_text(encoding="utf-8")
    assert "innerHTML" not in html and "insertAdjacentHTML" not in html and "document.write" not in html
    assert "eval(" not in html


def test_サイトの都道府県の選択肢が本体の許可リストと一致している():
    import re

    from hackathon_agent.scholarship.prefilter import PREFECTURES

    html = (Path("ui") / "site.html").read_text(encoding="utf-8")
    pref = re.search(r'const PREF = "(.*?)"\.split', html, re.S).group(1).split(" ")
    assert set(pref) == set(PREFECTURES)


def test_準備カレンダーは画面にもAPIにもない(user):
    s = client.get("/api/state", params={"user_id": user}).json()
    assert "calendar" not in s
    for name in ("site.html", "index.html"):
        assert "カレンダー" not in (Path("ui") / name).read_text(encoding="utf-8")


# ---------- 保存リスト ----------
ITEM = {
    "id": "abc123",
    "name": "テスト財団奨学金",
    "organization": "公益財団法人テスト財団",
    "status": "応募できる",
    "deadline": "2026-11-30",
    "amount": "年額 480,000円（給付）",
    "route": "直接応募",
    "reasons": ["確認できました"],
    "official_url": "https://example.org/x",
    "source": "Web検索",
}


def test_保存して一覧とCSVで取り出せる(user):
    r = client.post("/api/saved", json={"user_id": user, "items": [ITEM]}, headers=SAME)
    assert r.json() == {"ok": True, "count": 1}
    assert [i["name"] for i in client.get("/api/saved", params={"user_id": user}).json()["items"]] == [
        "テスト財団奨学金"
    ]
    csv_body = client.get("/api/saved.csv", params={"user_id": user}).content.decode("utf-8-sig")
    assert "テスト財団奨学金" in csv_body and "公式ページ" in csv_body.splitlines()[0]
    # 同じ項目をもう一度保存しても重複しない
    client.post("/api/saved", json={"user_id": user, "items": [ITEM]}, headers=SAME)
    assert len(client.get("/api/saved", params={"user_id": user}).json()["items"]) == 1
    # 外すと消える。他のユーザーのものは見えない
    assert client.get("/api/saved", params={"user_id": "x-" + user}).json()["items"] == []
    client.delete(f"/api/saved/{ITEM['id']}", params={"user_id": user}, headers=SAME)
    assert client.get("/api/saved", params={"user_id": user}).json()["items"] == []


def test_保存は同じオリジンからだけ受け付ける(user):
    body = {"user_id": user, "items": [ITEM]}
    assert client.post("/api/saved", json=body).status_code == 403
    assert client.post("/api/saved", json=body, headers={"Origin": "https://evil.example.com"}).status_code == 403
    assert client.delete(f"/api/saved/{ITEM['id']}", params={"user_id": user}).status_code == 403


def test_保存の入力は検証される(user):
    too_long = {**ITEM, "name": "あ" * 201}
    assert client.post("/api/saved", json={"user_id": user, "items": [too_long]}, headers=SAME).status_code == 422
    assert client.post("/api/saved", json={"user_id": user, "items": []}, headers=SAME).status_code == 422


def test_https以外のURLは保存しない(user):
    bad = {**ITEM, "official_url": "javascript:alert(1)"}
    client.post("/api/saved", json={"user_id": user, "items": [bad]}, headers=SAME)
    assert client.get("/api/saved", params={"user_id": user}).json()["items"][0]["official_url"] == ""
    client.delete(f"/api/saved/{ITEM['id']}", params={"user_id": user}, headers=SAME)


def test_CSVは式として実行されないようにする(user):
    evil = {**ITEM, "name": '=HYPERLINK("http://evil")', "organization": "+cmd"}
    client.post("/api/saved", json={"user_id": user, "items": [evil]}, headers=SAME)
    body = client.get("/api/saved.csv", params={"user_id": user}).content.decode("utf-8-sig")
    assert "'=HYPERLINK" in body and "'+cmd" in body
    client.delete(f"/api/saved/{ITEM['id']}", params={"user_id": user}, headers=SAME)
