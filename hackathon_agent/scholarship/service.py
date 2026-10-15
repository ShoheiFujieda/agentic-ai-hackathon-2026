"""筑波大学の公開一覧（大学経由の奨学金）から、締切前のものを判定する。

AI を使うのは「出願資格」の文章の読み取りだけ。締切・申請方法・併給・金額はコードで読み、判定もコードで行う。
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from . import cache, extract, tsukuba, web
from .judge import ELIGIBLE, INELIGIBLE, NEEDS_CHECK, Profile, judge
from .prefilter import prefilter

logger = logging.getLogger(__name__)

UNIVERSITY = "筑波大学"
CACHE_VERSION = "v3"  # 抜き出し方を変えたら上げて、古いキャッシュを使わないようにする
WORKERS = 4
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


def _fallback(entry: tsukuba.Entry, reason: str) -> dict:
    """判定できなかったときの結果。通常の結果と同じ項目をそろえる（id や締切を欠かさない）。"""
    return {
        "id": entry.id,
        "organization": entry.organization,
        "deadline": entry.deadline.isoformat() if entry.deadline else None,
        "route": "不明",
        "kind": entry.kind,
        "amount": None,
        "status": NEEDS_CHECK,
        "reasons": [reason],
        "url": entry.url,
        "official_url": "",
    }


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
            except Exception as err:
                if not isinstance(err, web.FetchError):
                    logger.exception("判定に失敗しました: %s", e.url)
                why = str(err) if isinstance(err, web.FetchError) else f"処理に失敗しました（{type(err).__name__}）"
                results.append(_fallback(e, f"{why}。詳細ページを直接確認してください"))

    def pick(status: str) -> list[dict]:
        return [r for r in results if r["status"] == status]

    # 3つの区分以外の判定（募集終了・公式情報なし）は、黙って落とさずに要確認へ入れる
    others = [r for r in results if r["status"] not in (ELIGIBLE, NEEDS_CHECK, INELIGIBLE)]
    for r in others:
        r["reasons"] = [f"{r['status']}: " + "、".join(r["reasons"])]
        r["status"] = NEEDS_CHECK

    return {
        "today": today.isoformat(),
        "university": UNIVERSITY,
        "source": tsukuba.INDEX_URL,
        "open_now_total": len(open_now),
        "eligible": pick(ELIGIBLE),
        "needs_check": pick(NEEDS_CHECK),
        "ineligible": pick(INELIGIBLE),
        "excluded_by_name": excluded,
        "not_checked_over_limit": skipped,
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
