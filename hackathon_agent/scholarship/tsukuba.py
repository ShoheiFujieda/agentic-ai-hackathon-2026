"""筑波大学が公開している民間奨学団体・地方公共団体の一覧を読む（コードで読める項目はAIを使わない）。

- 一覧: https://www.tsukuba.ac.jp/scholarship.json（年度・対象・給与/貸与・団体名と掲載日・期限・詳細ページ）
- 詳細ページ: <dt>項目名</dt><dd>内容</dd> の形（出願資格・併給・申請方法・申請期限・提出書類など）
"""

import json
import re
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser

from . import web

BASE = "https://www.tsukuba.ac.jp"
INDEX_URL = f"{BASE}/scholarship.json"


@dataclass
class Entry:
    id: int
    fiscal_year: int
    target: str  # 学群 / 大学院 / 学群・大学院
    kind: str  # 給与 / 貸与 / 給与・貸与
    title: str  # 団体名（と掲載日）
    deadline: date | None
    category: str  # 民間奨学団体 / 地方公共団体
    url: str

    @property
    def organization(self) -> str:
        """タイトルから掲載日を除いた団体名。"""
        return re.sub(r"\s*\d{4}\.\d{1,2}\.\d{1,2}\s*掲載.*$", "", self.title).strip()

    @property
    def for_undergraduates(self) -> bool:
        return "学群" in self.target or not self.target


def _date(s: str) -> date | None:
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", s or "")
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None


def parse_index(raw: str) -> list[Entry]:
    entries = []
    for x in json.loads(raw):
        try:
            entries.append(
                Entry(
                    id=int(x["id"]),
                    fiscal_year=int(x["year"]),
                    target=x.get("type1") or "",
                    kind=x.get("type2") or "",
                    title=x.get("title") or "",
                    deadline=_date(x.get("limit") or ""),
                    category=x.get("label") or "",
                    url=BASE + x["link"] if x.get("link", "").startswith("/") else x.get("link", ""),
                )
            )
        except (KeyError, ValueError, TypeError):
            continue  # 形の崩れた1件で全体を止めない
    return entries


def load_index() -> list[Entry]:
    return parse_index(web.fetch(INDEX_URL).text)


class _Definitions(HTMLParser):
    """<dl><dt>項目名</dt><dd>内容</dd></dl> を {項目名: 内容} にする。"""

    def __init__(self) -> None:
        super().__init__()
        self.items: dict[str, str] = {}
        self._mode: str | None = None
        self._key = ""
        self._buf: list[str] = []
        self.title = ""
        self._in_h3 = False

    def handle_starttag(self, tag, attrs):
        if tag in ("dt", "dd"):
            self._mode, self._buf = tag, []
        elif self._mode == "dd" and (tag == "br" or (tag == "p" and self._buf)):
            self._buf.append("\n")  # 改行と段落の区切りを残す
        elif tag == "h3" and not self.title:
            self._in_h3 = True

    def handle_endtag(self, tag):
        if tag == "dt" and self._mode == "dt":
            self._key = "".join(self._buf).strip()
            self._mode = None
        elif tag == "dd" and self._mode == "dd":
            text = re.sub(r"\n\s*\n+", "\n", "".join(self._buf)).strip()
            if self._key and self._key not in self.items:
                self.items[self._key] = text
            self._mode = None
        elif tag == "h3":
            self._in_h3 = False

    def handle_data(self, data):
        if self._mode:
            self._buf.append(data.strip())
        elif self._in_h3:
            self.title += data.strip()


def parse_detail(html: str) -> dict[str, str]:
    parser = _Definitions()
    parser.feed(html)
    return {"タイトル": parser.title, **parser.items}


def load_detail(url: str) -> dict[str, str]:
    return parse_detail(web.decode_html(web.fetch(url)))


def concurrent_rules(value: str) -> dict:
    """詳細ページの「併給」欄（可／不可）を、判定用の形にする。"""
    v = (value or "").strip()
    if v.startswith("可"):
        return {"status": "確認", "rules": {"JASSO貸与": "可", "JASSO給付": "可", "他の民間給付": "可"}, "quote": v}
    if v.startswith("不可"):
        # 何との併給が不可かは書かれていないことが多いので、JASSO については「不明」にする
        return {"status": "不明", "rules": {"他の民間給付": "不可"}, "quote": v}
    return {"status": "不明", "rules": {}, "quote": v}


def application_route(value: str) -> str:
    v = value or ""
    if "大学" in v and "申請" in v:
        return "大学経由"
    if "個人" in v:
        return "直接応募"
    return "不明"


def amount(value: str) -> dict:
    """金額欄（「3万円」「年額120万円」「一時金30万円」など）を、金額と単位（月額／年額／一時金）にする。"""
    v = (value or "").replace(",", "").replace("，", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*万円", v)
    yen = int(float(m[1]) * 10_000) if m else None
    if yen is None:
        m = re.search(r"(\d{4,})\s*円", v)
        yen = int(m[1]) if m else None
    if yen is None:
        per = "不明"
    elif re.search(r"一時金|総額|一括|一回", v):
        per = "一時金"
    elif re.search(r"年額|年間|年\s*\d|／年|/年|毎年", v):
        per = "年額"
    else:
        per = "月額"  # 筑波大学の欄名は「奨学金月額」
    return {"yen": yen, "per": per, "text": (value or "").strip()[:60]}


_CORP = re.compile(r"[（(](公財|一財|公社|一社|社福|財|社)[）)]|(公益|一般)?(財団|社団)法人|社会福祉法人|株式会社")


def org_key(organization: str) -> str:
    """団体の照合用の名前（法人の種類の書き方、記号、空白を除く）。重複の統合と履歴の照合で同じ基準を使う。"""
    return web.norm(_CORP.sub("", organization or ""))


def typical_months(entries: list[Entry], organization: str) -> list[int]:
    """過去の掲載から、その団体の例年の締切月を出す（多い順）。"""
    key = org_key(organization)
    months: dict[int, int] = {}
    for e in entries:
        # 団体名の完全一致で数える（「X財団」と「X財団記念会」を混ぜない）
        if e.deadline and key and key == org_key(e.organization):
            months[e.deadline.month] = months.get(e.deadline.month, 0) + 1
    return [m for m, _ in sorted(months.items(), key=lambda kv: -kv[1])]
