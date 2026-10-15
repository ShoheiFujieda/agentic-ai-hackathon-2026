"""ツール実行前のガード（引数の許可リストと検索回数の上限）のテスト。"""

from types import SimpleNamespace

from hackathon_agent.governance import guard

OK = {
    "university": "筑波大学",
    "university_prefecture": "茨城県",
    "field": "理工学群",
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
    assert "学校の所在地" in _check(university_prefecture="つくば市")
    assert "学校名" in _check(university="")
    assert "学校名" in _check(university="あ" * 51)
    assert "学部・分野" in _check(field="あ" * 51)
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


# ---------- 立場と目的（10/15） ----------
def test_高校生は学校名なしで通り_学年は1から3():
    base = {**OK, "status": "高校生", "university": "", "university_prefecture": "", "field": "", "grade": 2}
    assert guard._validate_find_scholarships(base, _ctx()) is None
    assert "1〜3" in guard._validate_find_scholarships({**base, "grade": 4}, _ctx())


def test_卒業後は最終学歴と年数が必要で_学年は使わない():
    base = {**OK, "status": "卒業後（社会人）", "university": "", "university_prefecture": "", "field": "", "grade": 0}
    assert "最終学歴" in guard._validate_find_scholarships(base, _ctx())
    ok = {**base, "last_school": "大学", "years_since_graduation": 1}
    assert guard._validate_find_scholarships(ok, _ctx()) is None
    assert "年数" in guard._validate_find_scholarships({**ok, "years_since_graduation": -1}, _ctx())
    assert "年数" in guard._validate_find_scholarships({**ok, "years_since_graduation": True}, _ctx())


def test_立場と目的は許可リストの値だけ():
    assert "立場" in guard._validate_find_scholarships({**OK, "status": "会社員"}, _ctx())
    assert "目的" in guard._validate_find_scholarships({**OK, "purposes": ["投資"]}, _ctx())
    assert guard._validate_find_scholarships({**OK, "purposes": ["留学", "研究"]}, _ctx()) is None
    assert guard._validate_find_scholarships({**OK, "purposes": []}, _ctx()) is None  # 空なら既定（学業・生活費）


def test_従来の呼び出し_立場なし_は大学生として通る():
    assert guard._validate_find_scholarships(OK, _ctx()) is None
