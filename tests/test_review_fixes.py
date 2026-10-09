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


def test_今月が例年の締切月ならまもなく():
    entries = [_entry(1, "（公財）十月財団", date(2025, 10, 20))]
    items = service._calendar(entries, ME, set(), date(2026, 10, 9), open_now=set())
    assert items[0]["months_until"] == 0
    assert items[0]["prepare_from"] == "今すぐ"


def test_経済や医療を含む一般の財団名はカレンダーから消さない():
    entries = [_entry(1, "（一社）○○経済同友会", date(2026, 4, 20)), _entry(2, "（公財）○○美術財団", date(2026, 4, 20))]
    names = [x["organization"] for x in service._calendar(entries, ME, set(), date(2026, 10, 9), open_now=set())]
    assert "（一社）○○経済同友会" in names
    assert "（公財）○○美術財団" not in names


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
        "gakugun": "情報学群",
        "grade": 2,
        "home_prefecture": "埼玉県",
        "residence_prefecture": "茨城県",
        "guardian_prefecture": "埼玉県",
        "receiving": [],
    }
    result = guard.before_tool_guard(SimpleNamespace(name="find_scholarships"), args, ctx)
    assert result["status"] == "error"
    assert ctx.state.get("search_count", 0) == 0


def test_取得に失敗してもツールは例外を投げずerrorを返す(monkeypatch):
    def boom(*a, **kw):
        raise web.FetchError("取得できませんでした")

    monkeypatch.setattr(tools.service, "find", boom)
    monkeypatch.setattr(tools.service, "detail", boom)
    r = tools.find_scholarships("情報学群", 2, "埼玉県", "茨城県", "埼玉県", [], tool_context=None)
    assert r["status"] == "error"
    assert tools.get_scholarship_detail(1, tool_context=None)["status"] == "error"
