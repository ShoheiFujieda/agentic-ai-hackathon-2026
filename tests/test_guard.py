"""ツール実行前のガード（引数の許可リストと検索回数の上限）のテスト。"""

from types import SimpleNamespace

from hackathon_agent.governance import guard

OK = {
    "gakugun": "理工学群",
    "grade": 2,
    "home_prefecture": "埼玉県",
    "residence_prefecture": "茨城県",
    "guardian_prefecture": "埼玉県",
    "receiving": ["JASSO貸与"],
}


def _ctx(search_count: int = 0):
    return SimpleNamespace(state={"search_count": search_count})


def _check(**over):
    return guard._validate_find_scholarships({**OK, **over}, _ctx())


def test_正しいプロフィールは通す():
    assert _check() is None
    assert _check(receiving=[]) is None


def test_許可リストにない値は止める():
    assert "学群名" in _check(gakugun="工学部")
    assert "都道府県名" in _check(residence_prefecture="つくば市")
    assert "受給中" in _check(receiving=["ガクシー"])


def test_学年は1から6の整数だけ():
    assert _check(grade=0)
    assert _check(grade=7)
    assert _check(grade="2")
    assert _check(grade=True)


def test_検索回数の上限で止める():
    limit = guard.MAX_SEARCHES_PER_SESSION
    assert guard._validate_find_scholarships(OK, _ctx(limit - 1)) is None
    assert "上限" in guard._validate_find_scholarships(OK, _ctx(limit))


def test_許可されていないツールは実行しない(monkeypatch):
    recorded = []
    monkeypatch.setattr(guard.audit, "record", lambda **kw: recorded.append(kw) or True)
    ctx = SimpleNamespace(state={}, user_id="u", session=SimpleNamespace(id="s"), function_call_id="f")
    result = guard.before_tool_guard(SimpleNamespace(name="send_payment"), {}, ctx)
    assert result["status"] == "blocked"
    assert recorded[0]["decision"] == "blocked"


def test_詳細のidは正の整数だけ():
    assert guard._validate_get_scholarship_detail({"scholarship_id": 84987}, _ctx()) is None
    assert guard._validate_get_scholarship_detail({"scholarship_id": -1}, _ctx())
    assert guard._validate_get_scholarship_detail({"scholarship_id": "84987"}, _ctx())
