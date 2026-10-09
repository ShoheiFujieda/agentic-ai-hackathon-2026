"""奨学金の検索の中心。筑波大学の公開一覧を使い、締切前のものを判定し、締切後のものから来年の準備カレンダーを作る。

AI を使うのは「出願資格」の文章の読み取りだけ。締切・申請方法・併給・金額はコードで読み、判定もコードで行う。
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import date

from . import cache, extract, tsukuba, web
from .judge import ELIGIBLE, INELIGIBLE, NEEDS_CHECK, OTHER_FIELDS, Profile, fiscal_year, judge
from .prefilter import prefilter

logger = logging.getLogger(__name__)

UNIVERSITY = "筑波大学"
CACHE_VERSION = "v3"  # 抜き出し方を変えたら上げて、古いキャッシュを使わないようにする
WORKERS = 4
# 名前から「一部の人だけが対象」と推定できる言葉（カレンダーで印を付ける）
SPECIAL_HINTS = re.compile(r"障害|遺児|被災|震災|ひとり親|母子|父子|児童養護|里親|難病|がん")
INDEX_TTL_SEC = 3600

_index: tuple[float, list[tsukuba.Entry]] | None = None


def load_entries() -> list[tsukuba.Entry]:
    """一覧はプロセス内で1時間だけ使い回す。"""
    global _index
    if _index and time.time() - _index[0] < INDEX_TTL_SEC:
        return _index[1]
    entries = tsukuba.load_index()
    _index = (time.time(), entries)
    return entries


def check_entry(entry: tsukuba.Entry, profile: Profile, today: date) -> dict:
    """1件の詳細ページを読み、条件を組み立てて判定する。"""
    key = f"tsukuba-{entry.id}-{CACHE_VERSION}"
    data = cache.get(key)
    if data is None:
        detail = tsukuba.load_detail(entry.url)
        data = {"detail": detail, "eligibility": extract.extract_eligibility(detail.get("出願資格", ""))}
        if "error" not in data["eligibility"]:
            cache.put(key, data)  # AI が失敗した結果は共有しない
    detail, elig = data["detail"], data["eligibility"]

    cond = {
        "official": True,
        "period": {
            "status": "確認" if entry.deadline else "不明",
            "deadline": entry.deadline.isoformat() if entry.deadline else None,
            "fiscal_year": entry.fiscal_year,
        },
        "international_only": elig.get("international_only"),
        "targets": elig.get("targets") or {"status": "不明"},
        "region": elig.get("region") or {"status": "不明"},
        "fields": elig.get("fields") or {"status": "不明"},
        "concurrent": tsukuba.concurrent_rules(detail.get("併給", "")),
        "application_route": tsukuba.application_route(detail.get("申請方法", "")),
        # 本人の大学（筑波大学）の一覧に載っているので、大学申請でもこの大学に募集が来ている
        "listed_by_my_university": True,
        "other_requirements": elig.get("other_requirements") or [],
    }
    result = judge(cond, profile, today)
    if "error" in elig and result.status != INELIGIBLE:
        # AI の読み取りに失敗したことを隠さない（「確認できなかった」だけだと原因が分からない）
        result.reasons.append("出願資格の自動読み取りに失敗したため、出願資格の文章を直接確認してください")
    return {
        "id": entry.id,
        "organization": entry.organization,
        "deadline": cond["period"]["deadline"],
        "route": cond["application_route"],
        "kind": entry.kind,
        "amount": tsukuba.amount(detail.get("奨学金月額", "")),
        "status": result.status,
        "reasons": result.reasons,
        "url": entry.url,
        "official_url": detail.get("詳細URL", ""),
    }


def _calendar(
    entries: list[tsukuba.Entry],
    profile: Profile,
    profile_prefs: set[str],
    today: date,
    open_now: set[str],
    limit: int = 15,
) -> list[dict]:
    """今年度と昨年度に締切が過ぎたものから、準備カレンダーを作る（条件は募集時に確認）。
    今まさに募集中の団体は「今応募できる」の側に出るので、ここには入れない。名前から明らかに別分野と分かるものも除く。"""
    fy = fiscal_year(today)
    seen: dict[str, tsukuba.Entry] = {}
    for e in entries:
        if not (e.for_undergraduates and e.deadline and e.deadline < today and e.fiscal_year in (fy - 1, fy)):
            continue
        if any(k in web.norm(e.organization) or web.norm(e.organization) in k for k in open_now):
            continue
        if prefilter({"organization": e.organization}, profile_prefs, UNIVERSITY):
            continue
        name = e.organization
        if OTHER_FIELDS.search(name) and not any(k in name for k in profile.field_keywords):
            continue
        key = web.norm(e.organization)
        if key not in seen or (seen[key].deadline or date.min) < e.deadline:
            seen[key] = e
    items = []
    for e in seen.values():
        months = tsukuba.typical_months(entries, e.organization)
        if not months:
            continue
        years = len({x.fiscal_year for x in entries if web.norm(e.organization) in web.norm(x.organization)})
        # 次に来る締切月までの月数（今月より後の月を先に）
        until = (months[0] - today.month) % 12 or 12
        soon = until <= 2  # 推薦書などの準備に約2か月かかるので、2か月以内なら今すぐ動く
        items.append(
            {
                "organization": e.organization,
                "usual_deadline_month": months[0],
                "last_deadline": e.deadline.isoformat(),
                "kind": e.kind,
                "years_listed": years,
                "months_until": until,
                "timing": "まもなく今年の募集が始まる見込み" if soon else "次回の募集に向けて準備",
                "prepare_from": "今すぐ" if soon else f"{(months[0] - 2 - 1) % 12 + 1}月ごろ",
                "note": "名前から、特別な条件（障害・遺児など）の可能性があります"
                if SPECIAL_HINTS.search(name)
                else "",
                "url": e.url,
            }
        )
    items.sort(key=lambda x: (x["months_until"], -x["years_listed"]))
    return items[:limit]


def find(profile: Profile, today: date, max_checks: int = 20) -> dict:
    entries = load_entries()
    prefs = {profile.home_prefecture, profile.residence, profile.school_location, profile.guardian_residence}

    open_now = sorted(
        (e for e in entries if e.for_undergraduates and e.deadline and e.deadline >= today),
        key=lambda e: e.deadline,
    )
    excluded = []
    to_check = []
    for e in open_now:
        why = prefilter({"organization": e.organization}, prefs, UNIVERSITY)
        if why:
            excluded.append({"organization": e.organization, "reason": why})
        else:
            to_check.append(e)
    skipped = max(0, len(to_check) - max_checks)
    to_check = to_check[:max_checks]

    results: list[dict] = []
    with ThreadPoolExecutor(WORKERS) as pool:
        for e, fut in [(e, pool.submit(check_entry, e, profile, today)) for e in to_check]:
            try:
                results.append(fut.result())
            except web.FetchError as err:
                results.append(
                    {"organization": e.organization, "status": NEEDS_CHECK, "reasons": [str(err)], "url": e.url}
                )
            except Exception as err:
                logger.exception("判定に失敗しました: %s", e.url)
                results.append(
                    {
                        "organization": e.organization,
                        "status": NEEDS_CHECK,
                        "reasons": [f"処理に失敗したため判定できませんでした（{type(err).__name__}）"],
                        "url": e.url,
                    }
                )

    def pick(status: str) -> list[dict]:
        return [r for r in results if r["status"] == status]

    return {
        "today": today.isoformat(),
        "university": UNIVERSITY,
        "source": tsukuba.INDEX_URL,
        "profile": asdict(profile),
        "open_now_total": len(open_now),
        "eligible": pick(ELIGIBLE),
        "needs_check": pick(NEEDS_CHECK),
        "ineligible": pick(INELIGIBLE),
        "excluded_by_name": excluded,
        "not_checked_over_limit": skipped,
        "next_year_calendar": _calendar(entries, profile, prefs, today, {web.norm(e.organization) for e in open_now}),
    }


def detail(entry_id: int) -> dict | None:
    """1件の詳細（提出書類と、判定の根拠になった引用）。"""
    entry = next((e for e in load_entries() if e.id == entry_id), None)
    if entry is None:
        return None
    data = cache.get(f"tsukuba-{entry.id}-{CACHE_VERSION}")
    d = data["detail"] if data else tsukuba.load_detail(entry.url)
    elig = data["eligibility"] if data else {}
    return {
        "id": entry.id,
        "organization": entry.organization,
        "deadline": entry.deadline.isoformat() if entry.deadline else None,
        "application_method": d.get("申請方法", ""),
        "concurrent": d.get("併給", ""),
        "monthly_amount": d.get("奨学金月額", ""),
        "eligibility_text": d.get("出願資格", ""),
        "documents": d.get("提出書類", ""),
        "official_url": d.get("詳細URL", ""),
        "notes": d.get("備考欄", ""),
        "evidence": {k: (elig.get(k) or {}).get("quote") for k in ("targets", "region", "fields")},
        "url": entry.url,
    }
