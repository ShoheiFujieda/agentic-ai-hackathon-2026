"""Web 全体の検索（websearch.py）のテスト。Gemini とネットワークは差し替える（オフラインで動く）。"""

import json
from datetime import date

import pytest

from hackathon_agent.scholarship import websearch
from hackathon_agent.scholarship.judge import CLOSED, ELIGIBLE, NEEDS_CHECK, Profile

ME = Profile(
    school_type="大学",
    grade=3,
    field_keywords=websearch.field_keywords("理工学群"),
    home_prefecture="埼玉県",
    residence="茨城県",
    school_location="茨城県",
    guardian_residence="埼玉県",
    receiving=[],
)
TODAY = date(2026, 10, 15)

PAGE = (
    "奨学生募集要項\n応募資格: 大学の3年生、4年生で理工系の学部に在籍する者\n"
    "応募締切: 2026年11月30日\n給付額: 年額48万円（給付）\n併給: 他の奨学金との併給は可\n応募方法: 本人が直接応募する"
)


def _cond(deadline="2026-11-30", quote="大学の3年生、4年生で理工系の学部に在籍する者"):
    return {
        "page_is_about_this_scholarship": True,
        "period": {"status": "確認", "deadline": deadline, "fiscal_year": 2026, "quote": "応募締切: 2026年11月30日"},
        "international_only": False,
        "application_route": "直接応募",
        "route_quote": "本人が直接応募する",
        "targets": {"status": "制限あり", "list": [{"school_type": "大学", "grades": [3, 4]}], "quote": quote},
        "region": {"status": "制限なし"},
        "fields": {"status": "制限あり", "list": ["理工系"], "quote": quote},
        "concurrent": {
            "status": "確認",
            "rules": {"JASSO貸与": "可", "JASSO給付": "可", "他の民間給付": "可"},
            "quote": "他の奨学金との併給は可",
        },
        "amount": {"type": "給付", "yearly_yen": 480000, "quote": "年額48万円（給付）"},
    }


class _Resp:
    def __init__(self, text):
        self.text = text


def _patch(monkeypatch, cond, page_text=PAGE, sources=None):
    sources = sources if sources is not None else [{"url": "https://foundation.example.or.jp/boshu", "title": "募集"}]
    monkeypatch.setattr(websearch, "_grounded", lambda prompt: {"text": "", "sources": sources})
    monkeypatch.setattr(
        websearch,
        "read_page",
        lambda url: {"url": url, "kind": "html", "text": page_text, "links": []} if page_text else None,
    )
    monkeypatch.setattr(websearch, "_gen", lambda contents, config: _Resp(json.dumps(cond, ensure_ascii=False)))


@pytest.fixture(autouse=True)
def _no_cache(monkeypatch):
    store = {}
    monkeypatch.setattr(websearch.cache, "get", lambda key: store.get(key))
    monkeypatch.setattr(websearch.cache, "put", lambda key, value: store.__setitem__(key, value))
    return store


CAND = {"scholarship": "テスト奨学金", "organization": "公益財団法人テスト財団", "mentions": 2}


# ---------- 部品 ----------
def test_分野の自由入力から判定用の言葉を作る():
    kws = websearch.field_keywords("理工学群")
    assert {"理工学群", "理工", "工学", "理系"} <= set(kws)
    assert "文系" in websearch.field_keywords("経済学部")
    assert websearch.field_keywords("") == []


def test_団体名の法人格をそろえて同じ団体を1件にまとめる():
    assert websearch.core_name("公益財団法人テスト財団") == websearch.core_name("テスト財団")
    merged = websearch.merge(
        [
            [{"scholarship": "A奨学金", "organization": "公益財団法人テスト財団"}],
            [{"scholarship": "A奨学金（給付型）", "organization": "テスト財団"}],
        ]
    )
    assert len(merged) == 1
    only = next(iter(merged.values()))
    assert only["mentions"] == 2 and only["scholarship"] == "A奨学金（給付型）"


def test_検索語は同じものを重ねない():
    qs = websearch.build_queries(ME, "筑波大学", "理工学群", 2026)
    assert len(qs) == len(set(qs))
    assert any("埼玉県" in q for q in qs) and any("筑波大学" in q for q in qs)


def test_まとめサイトは公式ページとして選ばない():
    picked = websearch.pick_official(
        [
            {"url": "https://shougakukin-note.com/a", "title": ""},
            {"url": "https://example.ac.jp/b", "title": ""},
            {"url": "https://foundation.or.jp/c", "title": ""},
        ]
    )
    assert [p["kind"] for p in picked] == ["運営団体", "大学掲載"]


def test_作り話の引用は検証に通らない():
    cond = _cond(quote="これは原文にない作り話の引用です")
    websearch.verify_quotes(cond, PAGE)
    assert cond["targets"]["quote_verified"] is False
    assert cond["period"]["quote_verified"] is True


def test_一覧ページの項目はページに実在するものだけ使う(monkeypatch):
    page = {"url": "https://x/list", "kind": "html", "text": "公益財団法人テスト財団の奨学金。" * 20, "links": []}
    monkeypatch.setattr(websearch, "read_page", lambda url: page)
    items = [
        {"scholarship": "A", "organization": "公益財団法人テスト財団"},
        {"scholarship": "B", "organization": "ページに無い架空財団"},
    ]
    monkeypatch.setattr(websearch, "_gen", lambda contents, config: _Resp(json.dumps(items, ensure_ascii=False)))
    assert [i["organization"] for i in websearch.extract_hub("https://x/list")] == ["公益財団法人テスト財団"]


# ---------- 1件の照合 ----------
def test_公式ページで条件を確認できれば応募できると判定する(monkeypatch):
    _patch(monkeypatch, _cond())
    r = websearch.check_candidate("テスト財団", CAND, ME, TODAY)
    assert r["status"] == ELIGIBLE
    assert r["deadline"] == "2026-11-30" and r["amount"].startswith("年額 480,000円")
    assert r["official_url"] == "https://foundation.example.or.jp/boshu"


def test_締切を過ぎていれば募集終了に分ける(monkeypatch):
    _patch(monkeypatch, _cond(deadline="2026-05-06"))
    assert websearch.check_candidate("テスト財団", CAND, ME, TODAY)["status"] == CLOSED


def test_引用が原文にない条件は応募できるにしない(monkeypatch):
    _patch(monkeypatch, _cond(quote="原文にない引用"))
    assert websearch.check_candidate("テスト財団", CAND, ME, TODAY)["status"] != ELIGIBLE


def test_公式ページが見つからなければ未確認の候補にする(monkeypatch):
    _patch(monkeypatch, _cond(), sources=[{"url": "https://shougakukin-note.com/a", "title": ""}])
    r = websearch.check_candidate("テスト財団", CAND, ME, TODAY)
    assert r["status"] == websearch.UNVERIFIED and r["official_url"] == ""


def test_ページを読めなければ未確認の候補にする(monkeypatch):
    _patch(monkeypatch, _cond(), page_text="")
    assert websearch.check_candidate("テスト財団", CAND, ME, TODAY)["status"] == websearch.UNVERIFIED


def test_検索が失敗しても例外にせず未確認にする(monkeypatch):
    def boom(prompt):
        raise RuntimeError("down")

    monkeypatch.setattr(websearch, "_grounded", boom)
    r = websearch.check_candidate("テスト財団", CAND, ME, TODAY)
    assert r["status"] == websearch.UNVERIFIED and "失敗" in r["reasons"][0]


# ---------- 全体 ----------
def test_上限を超えた候補は隠さず未確認の候補として出す(monkeypatch):
    found = [{"scholarship": f"奨学金{i}", "organization": f"公益財団法人テスト{i}財団"} for i in range(5)]
    monkeypatch.setattr(websearch, "discover", lambda queries: (found, [], 0))
    _patch(monkeypatch, _cond())
    r = websearch.search(ME, "筑波大学", "理工学群", TODAY, websearch.Budget(verify=2, seconds=60))
    assert len(r["eligible"]) + len(r["needs_check"]) + r["ineligible_count"] + len(r["closed"]) == 2
    assert len(r["unverified"]) == 3
    assert r["stats"]["truncated"] is True and r["stats"]["candidates"] == 5


def test_他大学や他地域の明らかな対象外は照合しない(monkeypatch):
    found = [
        {"scholarship": "X", "organization": "他大学（北海道大学）後援会"},
        {"scholarship": "Y", "organization": "公益財団法人北海道Y財団"},
        {"scholarship": "Z", "organization": "公益財団法人テストZ財団"},
    ]
    monkeypatch.setattr(websearch, "discover", lambda queries: (found, [], 0))
    _patch(monkeypatch, _cond())
    r = websearch.search(ME, "筑波大学", "理工学群", TODAY, websearch.Budget(verify=5, seconds=60))
    assert r["excluded_by_name"] == 2 and r["stats"]["verified"] == 1


def test_時間切れなら残りを未確認の候補にする(monkeypatch):
    found = [{"scholarship": "A", "organization": "公益財団法人テストA財団"}]
    monkeypatch.setattr(websearch, "discover", lambda queries: (found, [], 0))
    _patch(monkeypatch, _cond())
    r = websearch.search(ME, "筑波大学", "理工学群", TODAY, websearch.Budget(verify=5, seconds=10))  # 残り20秒未満
    assert len(r["unverified"]) == 1 and r["stats"]["verified"] == 0


def test_判定の入力にNEEDS_CHECKが混ざる条件も落とさない(monkeypatch):
    cond = _cond()
    cond["region"] = {"status": "不明"}
    _patch(monkeypatch, cond)
    assert websearch.check_candidate("テスト財団", CAND, ME, TODAY)["status"] == NEEDS_CHECK


def test_公式ページの確認結果は共有され_2回目は検索せず判定だけする(monkeypatch):
    _patch(monkeypatch, _cond())
    first = websearch.check_candidate("テスト財団", CAND, ME, TODAY)
    assert first["status"] == ELIGIBLE

    def must_not_call(*a, **k):
        raise AssertionError("2回目は Gemini も取得も使わないはず")

    monkeypatch.setattr(websearch, "_grounded", must_not_call)
    monkeypatch.setattr(websearch, "_gen", must_not_call)
    monkeypatch.setattr(websearch, "read_page", must_not_call)
    other = Profile("大学", 1, ["理工"], "埼玉県", "茨城県", "茨城県", "埼玉県", [])  # 別の学生（1年）
    second = websearch.check_candidate("テスト財団", CAND, other, TODAY)
    assert second["official_url"] == first["official_url"]
    assert second["status"] != ELIGIBLE  # 対象は3・4年なので、同じ条件でも学生ごとに判定が変わる


def test_確認できなかった結果は共有しない(monkeypatch, _no_cache):
    _patch(monkeypatch, _cond(), page_text="")
    assert websearch.check_candidate("テスト財団", CAND, ME, TODAY)["status"] == websearch.UNVERIFIED
    assert _no_cache == {}


def test_同じ条件の再検索は発見を使い回し_確認済みが積み上がる(monkeypatch):
    found = [{"scholarship": f"奨学金{i}", "organization": f"公益財団法人テスト{i}財団"} for i in range(4)]
    calls = []

    def fake_discover(queries):
        calls.append(1)
        return found, [], 0

    monkeypatch.setattr(websearch, "discover", fake_discover)
    _patch(monkeypatch, _cond())
    first = websearch.search(ME, "筑波大学", "理工学群", TODAY, websearch.Budget(verify=2, seconds=60))
    assert first["stats"]["verified"] == 2 and len(first["unverified"]) == 2

    second = websearch.search(ME, "筑波大学", "理工学群", TODAY, websearch.Budget(verify=2, seconds=60))
    assert len(calls) == 1  # 発見は1回だけ
    assert second["stats"]["from_cache"] == 2
    assert second["stats"]["verified"] == 4 and second["unverified"] == []  # 確認済み2件＋新たに2件


def test_1文字の語の部分一致で分野を取り違えない():
    assert "理系" not in websearch.field_keywords("経営管理学部")
    assert "文系" not in websearch.field_keywords("文化財科学")  # 「文」だけでは文系にしない
    assert {"工学", "理系"} <= set(websearch.field_keywords("工学部"))
    assert {"医学", "医療"} <= set(websearch.field_keywords("医学部"))


def test_特別な条件はWebの候補でも要確認にする(monkeypatch):
    cond = _cond()
    cond["other_requirements"] = [
        {"kind": "特別", "summary": "交通遺児が対象", "quote": "保護者が交通事故で死亡した者"}
    ]
    _patch(monkeypatch, cond, page_text=PAGE + "\n保護者が交通事故で死亡した者")
    r = websearch.check_candidate("テスト財団", CAND, ME, TODAY)
    assert r["status"] == NEEDS_CHECK and any("交通遺児" in x for x in r["reasons"])


def test_引用が確認できない締切は表示しない(monkeypatch):
    cond = _cond()
    cond["period"]["quote"] = "原文にない締切の引用"
    _patch(monkeypatch, cond)
    r = websearch.check_candidate("テスト財団", CAND, ME, TODAY)
    assert r["deadline"] is None


def test_期間の引用が確認できない条件は共有キャッシュに入れない(monkeypatch, _no_cache):
    cond = _cond()
    cond["period"]["quote"] = "原文にない締切の引用"
    _patch(monkeypatch, cond)
    websearch.check_candidate("テスト財団", CAND, ME, TODAY)
    assert _no_cache == {}


def test_発見がすべて失敗したら例外にして隠さない(monkeypatch):
    monkeypatch.setattr(websearch, "discover", lambda queries: ([], [], len(queries)))
    with pytest.raises(RuntimeError):
        websearch.search(ME, "筑波大学", "理工学群", TODAY, websearch.Budget(seconds=60))


def test_一部が失敗した発見の結果は共有キャッシュに残さない(monkeypatch, _no_cache):
    found = [{"scholarship": "A", "organization": "公益財団法人テストA財団"}]
    monkeypatch.setattr(websearch, "discover", lambda queries: (found, [], 2))
    _patch(monkeypatch, _cond())
    r = websearch.search(ME, "筑波大学", "理工学群", TODAY, websearch.Budget(verify=1, seconds=60))
    assert r["stats"]["discover_failed"] == 2
    assert not any(k.startswith("webdisc-") for k in _no_cache)


def test_検証済みの件数に未確認の候補を含めない(monkeypatch):
    found = [{"scholarship": "A", "organization": "公益財団法人テストA財団"}]
    monkeypatch.setattr(websearch, "discover", lambda queries: (found, [], 0))
    _patch(monkeypatch, _cond(), sources=[{"url": "https://shougakukin-note.com/a", "title": ""}])
    r = websearch.search(ME, "筑波大学", "理工学群", TODAY, websearch.Budget(verify=1, seconds=60))
    assert len(r["unverified"]) == 1 and r["stats"]["verified"] == 0
