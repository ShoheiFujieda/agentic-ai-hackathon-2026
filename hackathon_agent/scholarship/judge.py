"""応募資格と募集状態の判定。

AI が要項から読み取った条件（引用が原文と一致したかの印つき）を受け取り、学生のプロフィールと照合する。
「応募できる」と判定するのは、すべての条件が確認でき、しかも合っているときだけ。
読み取れない条件は「要確認」に回し、自信のない「対象外」は出さない（見落としを防ぐのが目的のため）。
"""

import re
from dataclasses import dataclass, field
from datetime import date

ELIGIBLE = "応募できる"
NEEDS_CHECK = "要確認"
INELIGIBLE = "対象外"
CLOSED = "募集終了"
NO_OFFICIAL = "公式情報なし"

# 地域条件の種類 → プロフィールの項目
REGION_KEYS = {
    "本人の出身": "home_prefecture",
    "本人の住所": "residence",
    "在学校の所在地": "school_location",
    "保護者の住所": "guardian_residence",
}


# 分野を表す言葉。学生の分野の言葉と一致せず、対象がこれらの分野だけなら「明らかに別の分野」として対象外にする
OTHER_FIELDS = re.compile(
    r"医学|歯学|薬学|看護|獣医|保健|医療|法学|法律|経済|経営|商学|文学|人文|教育学|芸術|美術|音楽|体育"
)


@dataclass
class Profile:
    school_type: str  # 大学 / 大学院 / 短大 / 高専 / 専門学校
    grade: int
    field_keywords: list[str]  # 学部・分野の言い換え（例: 理工, 工学, 機械, 理系）
    home_prefecture: str
    residence: str
    school_location: str
    guardian_residence: str
    receiving: list[str] = field(default_factory=list)  # 受給中の奨学金の区分（例: JASSO貸与）
    is_international: bool = False


@dataclass
class Judgement:
    status: str
    reasons: list[str]


def fiscal_year(d: date) -> int:
    """日本の年度（4月始まり）。"""
    return d.year if d.month >= 4 else d.year - 1


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _section(cond: dict, key: str) -> dict:
    """条件の1項目。引用が原文で確認できなかった項目は「不明」として扱う。"""
    sec = cond.get(key) or {}
    if sec and sec.get("quote_verified") is False:
        return {**sec, "status": "不明"}
    return sec


def judge(cond: dict | None, profile: Profile, today: date) -> Judgement:
    if not cond or not cond.get("official"):
        return Judgement(NO_OFFICIAL, ["運営団体の公式情報を確認できませんでした"])

    reasons: list[str] = []
    unknown: list[str] = []

    # 1. 募集状態（AIに判断させず、日付で決める）
    period = _section(cond, "period")
    deadline = _parse_date(period.get("deadline")) if period.get("status") != "不明" else None
    year = period.get("fiscal_year")
    if deadline and deadline < today:
        return Judgement(CLOSED, [f"締切（{deadline.isoformat()}）を過ぎています"])
    if year and year < fiscal_year(today):
        return Judgement(CLOSED, [f"{year}年度の情報です。今年度の募集は未確認です"])
    if not deadline:
        unknown.append("締切")

    # 2. 留学生のみ
    if cond.get("international_only") is True and not profile.is_international:
        return Judgement(INELIGIBLE, ["留学生のみが対象です"])

    # 3. 対象の学校種別・学年
    targets = _section(cond, "targets")
    if targets.get("status") == "制限あり" and not targets.get("list"):
        targets = {"status": "不明"}  # 「制限あり」なのに中身が空なら、読み取れていないとみなす（10/9 に誤判定あり）
    if targets.get("status") == "制限あり":
        rows = [t for t in targets.get("list", []) if t.get("school_type") == profile.school_type]
        if not rows:
            return Judgement(INELIGIBLE, [f"{profile.school_type}の学生は対象外です"])
        grades = {g for t in rows for g in (t.get("grades") or [])}
        if grades and profile.grade not in grades:
            return Judgement(INELIGIBLE, [f"対象学年（{sorted(grades)}年）に含まれません"])
        reasons.append("学年: 条件に合っています")
    elif targets.get("status") != "制限なし":
        unknown.append("対象学年")

    # 4. 地域条件（種類ごとに照合する）
    region = _section(cond, "region")
    if region.get("status") == "制限あり":
        results = []
        for c in region.get("conditions", []):
            key = REGION_KEYS.get(c.get("type"))
            area = c.get("area") or ""
            if not key or not area:
                results.append(None)
                continue
            mine = getattr(profile, key)
            if area.endswith(("都", "道", "府", "県")):
                results.append(area == mine)
            else:
                results.append(None)  # 市区町村の条件は、プロフィールに市区町村がないため判断しない
        any_logic = region.get("logic", "いずれか") == "いずれか"
        if (any_logic and True in results) or (not any_logic and results and all(r is True for r in results)):
            reasons.append("地域: 条件に合っています")
        elif None in results:
            unknown.append("地域条件")
        else:
            return Judgement(INELIGIBLE, ["地域の条件に合いません"])
    elif region.get("status") != "制限なし":
        unknown.append("地域条件")

    # 5. 学部・分野（明らかに別の分野だけが対象なら対象外。それ以外で一致が判断できなければ要確認）
    fields = _section(cond, "fields")
    if fields.get("status") == "制限あり":
        items = [x for x in fields.get("list", []) if x]
        if any(k in x for x in items for k in profile.field_keywords):
            reasons.append("分野: 条件に合っています")
        elif items and all(OTHER_FIELDS.search(x) for x in items):
            return Judgement(INELIGIBLE, [f"対象の分野（{'、'.join(items)}）に含まれません"])
        else:
            unknown.append("学部・分野")
    elif fields.get("status") != "制限なし":
        unknown.append("学部・分野")

    # 6. 併給（受給中の奨学金との組み合わせ）
    concurrent = _section(cond, "concurrent")
    for kind in profile.receiving:
        rule = (concurrent.get("rules") or {}).get(kind)
        if rule == "不可":
            return Judgement(INELIGIBLE, [f"{kind}との併給はできません"])
        if rule is None and concurrent.get("status") == "不明":
            unknown.append("併給")

    # 7. その他の条件: 特別な事情（遺児・特定の資格の志望など）は本人にしか分からないので要確認。一般的な条件は注意書き
    special = [r for r in cond.get("other_requirements") or [] if r.get("kind") == "特別"]
    general = [r for r in cond.get("other_requirements") or [] if r.get("kind") != "特別" and r.get("quote_verified")]
    if special:
        items = "、".join(r.get("summary") or r.get("quote") or "" for r in special)
        return Judgement(NEEDS_CHECK, [*reasons, f"あなたに当てはまるか確認してください: {items}"])
    if general:
        reasons.append("その他の条件: " + "、".join(r.get("summary") or "" for r in general))

    # 8. 大学経由の応募: 本人の大学の一覧に載っていれば、その大学に募集が来ている。載っていなければ確認が要る
    if cond.get("application_route") == "大学経由":
        if cond.get("listed_by_my_university"):
            reasons.append("大学申請: あなたの大学に募集が来ています。大学の申請期限までに学生支援の窓口へ提出します")
        else:
            return Judgement(
                NEEDS_CHECK, [*reasons, "大学経由の応募です。指定校かどうかと学内締切を学生課に確認してください"]
            )

    if unknown:
        return Judgement(NEEDS_CHECK, [*reasons, f"確認できなかった条件: {'、'.join(dict.fromkeys(unknown))}"])
    return Judgement(ELIGIBLE, reasons)
