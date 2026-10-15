"""応募資格・募集状態の判定（コード）と、安い絞り込みのテスト。"""

from datetime import date

from hackathon_agent.scholarship.judge import (
    CLOSED,
    ELIGIBLE,
    INELIGIBLE,
    NEEDS_CHECK,
    NO_OFFICIAL,
    Profile,
    fiscal_year,
    judge,
)
from hackathon_agent.scholarship.prefilter import prefilter

TODAY = date(2026, 10, 9)
ME = Profile(
    school_type="大学",
    grade=2,
    field_keywords=["理工", "工学", "機械", "理系"],
    home_prefecture="埼玉県",
    residence="東京都",
    school_location="東京都",
    guardian_residence="埼玉県",
    receiving=["JASSO貸与"],
)


def _cond(**over) -> dict:
    """すべての条件が確認でき、この学生に合っている要項。テストごとに一部を書き換える。"""
    base = {
        "official": True,
        "period": {"status": "確認", "deadline": "2026-11-30", "fiscal_year": 2026},
        "international_only": False,
        "targets": {"status": "制限あり", "list": [{"school_type": "大学", "grades": [1, 2, 3]}]},
        "region": {"status": "制限なし"},
        "fields": {"status": "制限なし"},
        "concurrent": {"status": "確認", "rules": {"JASSO貸与": "可"}},
        "application_route": "直接応募",
    }
    base.update(over)
    return base


def test_すべての条件が合えば応募できる():
    assert judge(_cond(), ME, TODAY).status == ELIGIBLE


def test_4月締切の奨学金は10月には募集終了():
    # 10/9 の調査で、要約AIが「現在は募集期間中」と誤答した実例
    result = judge(_cond(period={"status": "確認", "deadline": "2026-04-17", "fiscal_year": 2026}), ME, TODAY)
    assert result.status == CLOSED


def test_締切の当日はまだ募集中():
    result = judge(_cond(period={"status": "確認", "deadline": "2026-10-09", "fiscal_year": 2026}), ME, TODAY)
    assert result.status == ELIGIBLE


def test_去年度の要項は募集終了():
    result = judge(_cond(period={"status": "確認", "deadline": None, "fiscal_year": 2025}), ME, TODAY)
    assert result.status == CLOSED


def test_年度は4月始まり():
    assert fiscal_year(date(2027, 3, 31)) == 2026
    assert fiscal_year(date(2027, 4, 1)) == 2027


def test_締切が読み取れなければ要確認():
    result = judge(_cond(period={"status": "不明"}), ME, TODAY)
    assert result.status == NEEDS_CHECK


def test_引用が原文で確認できない項目は使わない():
    period = {"status": "確認", "deadline": "2026-11-30", "fiscal_year": 2026, "quote_verified": False}
    assert judge(_cond(period=period), ME, TODAY).status == NEEDS_CHECK


def test_学年が合わなければ対象外():
    targets = {"status": "制限あり", "list": [{"school_type": "大学", "grades": [3, 4]}]}
    assert judge(_cond(targets=targets), ME, TODAY).status == INELIGIBLE


def test_制限ありでも中身が空なら対象外にしない():
    # タクト奨学金「学生（大学院生は応募不可）」を、AI が list を空で返した実例
    targets = {"status": "制限あり", "list": [], "quote": "学生（大学院生は応募不可）"}
    assert judge(_cond(targets=targets), ME, TODAY).status == NEEDS_CHECK


def test_学校種別が合わなければ対象外():
    targets = {"status": "制限あり", "list": [{"school_type": "大学院", "grades": [1, 2]}]}
    assert judge(_cond(targets=targets), ME, TODAY).status == INELIGIBLE


def test_地域条件は種類ごとに照合する():
    # 保護者の住所が埼玉県なら合う（本人の住所は東京都）
    ok = {"status": "制限あり", "logic": "いずれか", "conditions": [{"type": "保護者の住所", "area": "埼玉県"}]}
    assert judge(_cond(region=ok), ME, TODAY).status == ELIGIBLE
    # 本人の住所が埼玉県であることが条件なら合わない
    ng = {"status": "制限あり", "logic": "いずれか", "conditions": [{"type": "本人の住所", "area": "埼玉県"}]}
    assert judge(_cond(region=ng), ME, TODAY).status == INELIGIBLE


def test_市区町村の地域条件は判断せず要確認():
    region = {"status": "制限あり", "logic": "いずれか", "conditions": [{"type": "本人の住所", "area": "川越市"}]}
    assert judge(_cond(region=region), ME, TODAY).status == NEEDS_CHECK


def test_明らかに別の分野だけが対象なら対象外():
    fields = {"status": "制限あり", "list": ["医学部", "看護学"]}
    assert judge(_cond(fields=fields), ME, TODAY).status == INELIGIBLE


def test_分野の一致が判断できなければ要確認():
    fields = {"status": "制限あり", "list": ["ITエンジニアを目指す者"]}
    assert judge(_cond(fields=fields), ME, TODAY).status == NEEDS_CHECK


def test_受給中の奨学金と併給不可なら対象外():
    concurrent = {"status": "確認", "rules": {"JASSO貸与": "不可"}}
    assert judge(_cond(concurrent=concurrent), ME, TODAY).status == INELIGIBLE


def test_本人の大学の一覧に載っている大学申請は応募できる():
    result = judge(_cond(application_route="大学経由", listed_by_my_university=True), ME, TODAY)
    assert result.status == ELIGIBLE
    assert any("大学申請" in r for r in result.reasons)


def test_大学経由の応募は要確認():
    result = judge(_cond(application_route="大学経由"), ME, TODAY)
    assert result.status == NEEDS_CHECK
    assert any("学生課" in r for r in result.reasons)


def test_特別な事情が条件なら要確認():
    other = [{"kind": "特別", "summary": "保護者が交通事故で死亡・後遺障害", "quote": "", "quote_verified": True}]
    result = judge(_cond(other_requirements=other), ME, TODAY)
    assert result.status == NEEDS_CHECK
    assert any("交通事故" in r for r in result.reasons)


def test_特別な事情は引用が確認できなくても要確認にする():
    # 見落としより確認の手間を選ぶ（応募できると言い切らない）
    other = [{"kind": "特別", "summary": "税理士を目指す", "quote": "作り話", "quote_verified": False}]
    assert judge(_cond(other_requirements=other), ME, TODAY).status == NEEDS_CHECK


def test_一般的な条件は注意書きにして応募できる():
    other = [{"kind": "一般", "summary": "経済的に困難", "quote": "", "quote_verified": True}]
    result = judge(_cond(other_requirements=other), ME, TODAY)
    assert result.status == ELIGIBLE
    assert any("経済的に困難" in r for r in result.reasons)


def test_留学生のみは対象外():
    assert judge(_cond(international_only=True), ME, TODAY).status == INELIGIBLE


def test_公式情報がなければその旨を返す():
    assert judge(None, ME, TODAY).status == NO_OFFICIAL
    assert judge(_cond(official=False), ME, TODAY).status == NO_OFFICIAL


def test_絞り込みは確実に対象外のものだけ除く():
    mine = {"埼玉県", "東京都"}
    assert prefilter({"organization": "生命保険協会", "scholarship": "留学生奨学金"}, mine, "東都工科大学")
    assert prefilter({"organization": "新潟県教育委員会", "scholarship": "奨学金"}, mine, "東都工科大学")
    assert prefilter(
        {"organization": "慶應義塾大学看護医療学部", "scholarship": "教育研究奨励基金"}, mine, "東都工科大学"
    )
    assert prefilter({"organization": "埼玉県", "scholarship": "埼玉県奨学金"}, mine, "東都工科大学") is None
    assert prefilter({"organization": "公益財団法人川村育英会", "scholarship": "奨学生"}, mine, "東都工科大学") is None
    assert (
        prefilter({"organization": "一般財団法人大学生奨学財団", "scholarship": "給付"}, mine, "東都工科大学") is None
    )
    # 市の名前だけでは地域が分からないので残す
    assert prefilter({"organization": "川越市", "scholarship": "奨学金"}, mine, "東都工科大学") is None


def test_別分野の言葉にはスポーツと美術を含む():
    from hackathon_agent.scholarship.judge import OTHER_FIELDS

    assert OTHER_FIELDS.search("（公財）ヨネックススポーツ振興財団")
    assert OTHER_FIELDS.search("（公財）現代美術文化振興財団")
    assert not OTHER_FIELDS.search("（一財）TCS奨学会")


# ---------- 幅広い利用者と目的（10/15） ----------
from hackathon_agent.scholarship.judge import OFF_PURPOSE  # noqa: E402


def _base_cond(**over):
    cond = {
        "official": True,
        "period": {"status": "確認", "deadline": "2027-03-31", "fiscal_year": 2026},
        "targets": {"status": "制限なし"},
        "region": {"status": "制限なし"},
        "fields": {"status": "制限なし"},
        "concurrent": {"status": "確認", "rules": {}},
        "application_route": "直接応募",
    }
    cond.update(over)
    return cond


def _me(**over):
    base = dict(
        school_type="大学",
        grade=3,
        field_keywords=["情報"],
        home_prefecture="埼玉県",
        residence="茨城県",
        school_location="茨城県",
        guardian_residence="埼玉県",
        receiving=[],
    )
    base.update(over)
    return Profile(**base)


TODAY2 = date(2026, 10, 15)


def test_在学生のみの奨学金は卒業後の人には対象外():
    cond = _base_cond(graduates={"status": "在学生のみ"})
    me = _me(graduated=True, years_since_graduation=1, grade=0)
    assert judge(cond, me, TODAY2).status == INELIGIBLE


def test_卒業後の年数の上限を超えると対象外_以内なら応募できる():
    cond = _base_cond(graduates={"status": "卒業生も可", "max_years": 2})
    assert judge(cond, _me(graduated=True, years_since_graduation=3, grade=0), TODAY2).status == INELIGIBLE
    assert judge(cond, _me(graduated=True, years_since_graduation=2, grade=0), TODAY2).status == ELIGIBLE


def test_卒業後の応募可否が読めなければ要確認():
    cond = _base_cond(graduates={"status": "不明"})
    assert judge(cond, _me(graduated=True, years_since_graduation=1, grade=0), TODAY2).status == NEEDS_CHECK


def test_卒業生のみの奨学金は在学生には対象外():
    cond = _base_cond(graduates={"status": "卒業生のみ", "max_years": 2})
    assert judge(cond, _me(), TODAY2).status == INELIGIBLE


def test_卒業後の人は学年の条件で落とさない():
    cond = _base_cond(
        targets={"status": "制限あり", "list": [{"school_type": "大学", "grades": [3, 4]}]},
        graduates={"status": "卒業生も可", "max_years": 2},
    )
    assert judge(cond, _me(graduated=True, years_since_graduation=1, grade=0), TODAY2).status == ELIGIBLE


def test_高校生の条件を判定できる():
    cond = _base_cond(targets={"status": "制限あり", "list": [{"school_type": "高校", "grades": [3]}]})
    assert judge(cond, _me(school_type="高校", grade=3), TODAY2).status == ELIGIBLE
    assert judge(cond, _me(school_type="高校", grade=1), TODAY2).status == INELIGIBLE
    assert judge(cond, _me(), TODAY2).status == INELIGIBLE  # 大学生は対象外


def test_使途が目的と明らかに違えば目的が違うに分ける():
    cond = _base_cond(purposes={"status": "制限あり", "list": ["留学"]})
    r = judge(cond, _me(purposes=["学業・生活費"]), TODAY2)
    assert r.status == OFF_PURPOSE and "留学" in r.reasons[0]


def test_使途が目的に合えば応募できる():
    cond = _base_cond(purposes={"status": "制限あり", "list": ["留学", "研究"]})
    assert judge(cond, _me(purposes=["留学"]), TODAY2).status == ELIGIBLE


def test_目的が留学で使途が読めなければ要確認_学業だけなら気にしない():
    cond = _base_cond(purposes={"status": "不明"})
    assert judge(cond, _me(purposes=["留学"]), TODAY2).status == NEEDS_CHECK
    assert judge(cond, _me(purposes=["学業・生活費"]), TODAY2).status == ELIGIBLE
    assert judge(_base_cond(), _me(), TODAY2).status == ELIGIBLE  # 項目自体が無い（従来の結果）も変わらない


def test_引用が確認できない使途は判定に使わない():
    cond = _base_cond(purposes={"status": "制限あり", "list": ["留学"], "quote_verified": False})
    # 使途が「不明」扱いになるので、目的が学業だけなら応募できるのまま
    assert judge(cond, _me(purposes=["学業・生活費"]), TODAY2).status == ELIGIBLE
