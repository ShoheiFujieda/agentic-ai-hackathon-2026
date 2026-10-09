"""筑波大学の一覧・詳細ページの読み取りと、Web 取得の部品のテスト（ネットワークは使わない）。"""

from datetime import date
from pathlib import Path

from hackathon_agent.scholarship import tsukuba, web

FIXTURES = Path(__file__).parent / "fixtures"


def test_一覧を読み形の崩れた行は飛ばす():
    entries = tsukuba.parse_index((FIXTURES / "tsukuba_index_sample.json").read_text(encoding="utf-8"))
    assert len(entries) == 5  # id のない行だけ除かれる
    e = entries[0]
    assert e.deadline == date(2026, 10, 18)
    assert e.organization == "（公財） 吉川徹財団"
    assert e.url.startswith("https://www.tsukuba.ac.jp/campuslife/")
    assert e.for_undergraduates
    assert not entries[1].for_undergraduates  # 大学院のみ
    assert entries[4].deadline is None  # 「未定」


def test_詳細ページの項目を読む():
    d = tsukuba.parse_detail((FIXTURES / "tsukuba_detail_yoshikawa.html").read_text(encoding="utf-8"))
    assert d["申請方法"] == "個人応募"
    assert d["申請期限"] == "2026.10.18"
    assert d["併給"] == "可"
    assert "学部1～3年生" in d["出願資格"]
    assert "成績証明書" in d["提出書類"]
    assert d["詳細URL"] == "https://toruyoshikawa.org/#guidelines"
    assert d["タイトル"].startswith("（公財） 吉川徹財団")


def test_申請方法と併給と金額():
    assert tsukuba.application_route("大学申請") == "大学経由"
    assert tsukuba.application_route("個人応募") == "直接応募"
    assert tsukuba.application_route("") == "不明"
    assert tsukuba.concurrent_rules("可")["rules"]["JASSO貸与"] == "可"
    assert tsukuba.concurrent_rules("不可")["status"] == "不明"
    assert tsukuba.amount("3万円") | {"text": ""} == {"yen": 30_000, "per": "月額", "text": ""}
    assert tsukuba.amount("月額 40,000円")["yen"] == 40_000
    assert tsukuba.amount("年額120万円")["per"] == "年額"  # 10/9 に月額120万円と表示された実例
    assert tsukuba.amount("一時金として30万円")["per"] == "一時金"
    assert tsukuba.amount("財団の規定による")["per"] == "不明"


def test_例年の締切月():
    entries = tsukuba.parse_index((FIXTURES / "tsukuba_index_sample.json").read_text(encoding="utf-8"))
    assert tsukuba.typical_months(entries, "アイザワ記念育英財団") == [4]


def test_引用の照合は記号の違いを許し言い換えは許さない():
    text = "出願時期\n3月24日〜5月11日\n併給は民間1団体に限り可"
    assert web.quote_in("3月24日～5月11日", text)
    assert web.quote_in("併給は民間1団体に限り可", text)
    assert not web.quote_in("他財団は原則1団体に限り可", text)
    assert not web.quote_in("", text)


def test_robotstxtで禁止されたページは取得しない(monkeypatch):
    from urllib.robotparser import RobotFileParser

    parser = RobotFileParser()
    parser.parse(["User-agent: *", "Disallow: /*.pdf$", "Disallow: /private/"])
    monkeypatch.setitem(web._robots, "https://example.ac.jp", (float("inf"), parser))
    assert not web.allowed("https://example.ac.jp/private/a.html")
    assert web.allowed("https://example.ac.jp/public/a.html")
    try:
        web.fetch("https://example.ac.jp/private/a.html")
        raise AssertionError("取得されてしまった")
    except web.RobotsDisallowed:
        pass
