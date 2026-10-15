"""10/9 のコードレビュー（縦1本）で指摘された不具合が再発しないことを確かめる。"""

from datetime import date
from types import SimpleNamespace

import httpx

from hackathon_agent import tools
from hackathon_agent.governance import guard
from hackathon_agent.scholarship import service, tsukuba, web
from hackathon_agent.scholarship.judge import CLOSED, INELIGIBLE, NEEDS_CHECK, Profile, judge

ME = Profile(
    school_type="大学",
    grade=2,
    field_keywords=["情報", "工学", "IT", "理系"],
    home_prefecture="埼玉県",
    residence="茨城県",
    school_location="茨城県",
    guardian_residence="埼玉県",
    receiving=[],
)
BASE = {
    "official": True,
    "period": {"status": "確認", "deadline": "2027-04-10", "fiscal_year": 2026},
    "targets": {"status": "制限なし"},
    "region": {"status": "制限なし"},
    "fields": {"status": "制限なし"},
    "concurrent": {"status": "確認", "rules": {}},
    "application_route": "直接応募",
}


def test_年度をまたいでも締切前なら募集終了にしない():
    assert judge(BASE, ME, date(2027, 4, 5)).status != CLOSED


def test_地域が制限ありで中身が空なら対象外にしない():
    cond = {**BASE, "region": {"status": "制限あり", "conditions": [], "quote": "…"}}
    assert judge(cond, ME, date(2027, 4, 5)).status == NEEDS_CHECK


def test_医学部を除くは医学部向けと読まない():
    cond = {**BASE, "fields": {"status": "制限あり", "list": ["理学部（医学部を除く）"]}}
    assert judge(cond, ME, date(2027, 4, 5)).status != INELIGIBLE


def _entry(i, org, deadline, fy=2025):
    return tsukuba.Entry(i, fy, "学群", "給与", f"{org} 2025.9.1掲載", deadline, "民間奨学団体", f"https://x/{i}")


def test_例年の締切月は団体名の完全一致で数える():
    entries = [_entry(1, "X財団", date(2025, 4, 1)), _entry(2, "X財団記念会", date(2025, 11, 1))]
    assert tsukuba.typical_months(entries, "X財団") == [4]


def test_判定できなかった結果にもidと締切がある():
    r = service._fallback(_entry(7, "Y財団", date(2026, 11, 1)), "取得できませんでした")
    assert r["id"] == 7 and r["deadline"] == "2026-11-01" and r["status"] == NEEDS_CHECK


def test_robotstxtの一時的な失敗はすぐ確かめ直す(monkeypatch):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        raise httpx.ConnectError("blip")

    monkeypatch.setattr(web.httpx, "get", fake_get)
    monkeypatch.setattr(web, "_robots", {})
    assert not web.allowed("https://blip.example/a.html")
    expires, _ = web._robots["https://blip.example"]
    assert expires - web.time.time() <= web.ROBOTS_RETRY_SEC


def test_監査ログが書けず中止した検索は回数に数えない(monkeypatch):
    monkeypatch.setattr(guard.audit, "record", lambda **kw: False)
    ctx = SimpleNamespace(state={}, user_id="u", session=SimpleNamespace(id="s"), function_call_id="f")
    args = {
        "university": "筑波大学",
        "university_prefecture": "茨城県",
        "field": "情報学群",
        "grade": 2,
        "home_prefecture": "埼玉県",
        "residence_prefecture": "茨城県",
        "guardian_prefecture": "埼玉県",
        "receiving": [],
    }
    result = guard.before_tool_guard(SimpleNamespace(name="find_scholarships"), args, ctx)
    assert result["status"] == "error"
    assert ctx.state.get("search_count", 0) == 0


ARGS = ("筑波大学", "茨城県", "情報学群", 2, "埼玉県", "茨城県", "埼玉県", [])
EMPTY_WEB = {
    "eligible": [],
    "needs_check": [],
    "unverified": [],
    "closed": [],
    "ineligible_count": 0,
    "stats": {"queries": 1},
}


def _find(*args):
    import asyncio

    return asyncio.run(tools.find_scholarships(*args, tool_context=None))


def test_取得に失敗してもツールは例外を投げずerrorを返す(monkeypatch):
    def boom(*a, **kw):
        raise web.FetchError("取得できませんでした")

    monkeypatch.setattr(tools.service, "find", boom)
    monkeypatch.setattr(tools.websearch, "search", boom)
    monkeypatch.setattr(tools.service, "detail", boom)
    r = _find(*ARGS)
    assert r["status"] == "error"
    assert tools.get_scholarship_detail(1, tool_context=None)["status"] == "error"


def test_今日の日付は環境に依存せず日本時間で求められる(monkeypatch):
    # 10/9: Windows の新しい仮想環境にタイムゾーンのデータがなく ZoneInfoNotFoundError になった
    monkeypatch.delenv("DEMO_TODAY", raising=False)
    assert isinstance(tools.today(), date)


def test_内部エラーを一覧の取得失敗と取り違えない(monkeypatch):
    def boom(*a, **kw):
        raise KeyError("x")

    monkeypatch.setattr(tools.service, "find", boom)
    monkeypatch.setattr(tools.websearch, "search", boom)
    assert "内部エラー" in _find(*ARGS)["reason"]


def test_Web検索だけ失敗しても大学の一覧の結果は返し_失敗を伝える(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("down")

    listed = {"eligible": [], "needs_check": [], "ineligible": [], "excluded_by_name": [], "not_checked_over_limit": 0}
    monkeypatch.setattr(tools.websearch, "search", boom)
    monkeypatch.setattr(tools.service, "find", lambda profile, day: listed)
    r = _find(*ARGS)
    assert r["status"] == "ok" and any("Web 全体の検索はできませんでした" in n for n in r["notes"])


def test_筑波大学以外では大学の一覧を使わない(monkeypatch):
    called = []
    monkeypatch.setattr(tools.service, "find", lambda *a: called.append(1))
    monkeypatch.setattr(tools.websearch, "search", lambda *a, **k: EMPTY_WEB)
    r = _find("東京大学", "東京都", "工学部", 2, "埼玉県", "東京都", "埼玉県", [])
    assert r["status"] == "ok" and not called and r["searched"]["university_list"] is None


def test_大学の一覧にある団体はWebの結果より優先し重複させない(monkeypatch):
    web_item = {"id": "w1", "name": "X", "organization": "公益財団法人テスト財団", "source": "Web検索", "reasons": []}
    web = {**EMPTY_WEB, "eligible": [web_item]}
    listed_row = {
        "id": 5,
        "organization": "（公財）テスト財団",
        "status": "応募できる",
        "reasons": [],
        "deadline": "2026-11-01",
        "url": "https://u/5",
    }
    listed = {"eligible": [listed_row], "needs_check": [], "ineligible": [], "excluded_by_name": [], "x": 0}
    monkeypatch.setattr(tools.websearch, "search", lambda *a, **k: web)
    monkeypatch.setattr(tools.service, "find", lambda profile, day: listed)
    r = _find(*ARGS)
    assert [i["source"] for i in r["eligible"]] == ["筑波大学の公開一覧"]
