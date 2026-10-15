"""エージェントが使うツール。検索の進め方と判定はコード（hackathon_agent.scholarship）が行う。"""

import asyncio
import hashlib
import logging
import os
from datetime import UTC, date, datetime, timedelta, timezone

from google.adk.tools import ToolContext

from .governance import approvals, audit
from .scholarship import service, web, websearch
from .scholarship.judge import Profile

logger = logging.getLogger(__name__)

RECEIVING = {"JASSO貸与", "JASSO給付", "他の民間給付"}
# 日本時間。日本には夏時間がないので固定の +9時間 で求める（Windows はタイムゾーンのデータを持たないため ZoneInfo を使わない）
JST = timezone(timedelta(hours=9), "JST")
TSUKUBA = "筑波"  # 大学名にこの言葉があれば、筑波大学の公開一覧（大学経由の奨学金）も使う


def today() -> date:
    """日本時間の今日。デモでは環境変数 DEMO_TODAY（YYYY-MM-DD）で固定できる。"""
    fixed = os.environ.get("DEMO_TODAY")
    if fixed:
        return date.fromisoformat(fixed)
    return datetime.now(JST).date()


def _amount_text(a) -> str | None:
    """筑波大学の一覧の金額（{yen, per, text}）を、画面と保存に使える短い文字列にする。"""
    if isinstance(a, dict):
        yen = a.get("yen")
        if isinstance(yen, int) and yen > 0:
            per = a.get("per")
            return f"{per if per in ('月額', '年額') else ''}{yen:,}円"
        a = a.get("text")
    return str(a)[:60] if a else None


def _tsukuba_item(r: dict) -> dict:
    """筑波大学の一覧の結果を、Web検索の結果と同じ形にそろえる。"""
    return {
        "id": r["id"],
        "name": r["organization"],
        "organization": r["organization"],
        "source": "筑波大学の公開一覧",
        "status": r["status"],
        "reasons": r["reasons"],
        "deadline": r.get("deadline"),
        "amount": _amount_text(r.get("amount")),
        "route": r.get("route"),
        "official_url": r.get("official_url") or r.get("url") or "",
        "sources": [r["url"]] if r.get("url") else [],
    }


async def find_scholarships(
    university: str,
    university_prefecture: str,
    field: str,
    grade: int,
    home_prefecture: str,
    residence_prefecture: str,
    guardian_prefecture: str,
    receiving: list[str],
    tool_context: ToolContext,
) -> dict:
    """学生が応募できる奨学金を、民間のものも含めて Web から探し、応募資格を判定して一覧にする。

    判定はコードで行う。結果の eligible（応募できる）/ needs_check（要確認）/ unverified（公式ページ未確認の候補）を、
    そのまま学生に伝えること。結果の一覧は画面の表に出るので、回答は短い要約にする。探すのに1〜2分かかる。

    Args:
        university: 在学する大学の名前（例: 筑波大学）。
        university_prefecture: 大学の所在地の都道府県名（例: 茨城県）。
        field: 学部・学群・分野（例: 理工学群、経済学部）。
        grade: 学年（1〜6の整数）。
        home_prefecture: 本人の出身地（出身高校の所在地）の都道府県名（例: 埼玉県）。
        residence_prefecture: 本人が今住んでいる都道府県名（例: 茨城県）。
        guardian_prefecture: 保護者が住んでいる都道府県名（例: 埼玉県）。
        receiving: 今受けている奨学金の区分のリスト。JASSO貸与 / JASSO給付 / 他の民間給付 から選ぶ。なければ空のリスト。
    """
    profile = Profile(
        school_type="大学",
        grade=grade,
        field_keywords=websearch.field_keywords(field),
        home_prefecture=home_prefecture,
        residence=residence_prefecture,
        school_location=university_prefecture,
        guardian_residence=guardian_prefecture,
        receiving=list(receiving),
    )
    day = today()
    use_list = TSUKUBA in university
    jobs = [asyncio.to_thread(websearch.search, profile, university, field, day)]
    if use_list:
        jobs.append(asyncio.to_thread(service.find, profile, day))
    done = await asyncio.gather(*jobs, return_exceptions=True)
    web_res, list_res = done[0], (done[1] if use_list else None)

    notes: list[str] = []
    if isinstance(web_res, Exception):
        logger.error("Web 検索に失敗しました", exc_info=web_res)
        notes.append(f"Web 全体の検索はできませんでした（システムの内部エラー: {type(web_res).__name__}）")
        web_res = {
            "eligible": [],
            "needs_check": [],
            "unverified": [],
            "closed": [],
            "ineligible_count": 0,
            "stats": {},
        }
    if isinstance(list_res, Exception):
        logger.error("大学の一覧の検索に失敗しました", exc_info=list_res)
        if isinstance(list_res, web.FetchError):
            notes.append(f"筑波大学の公開一覧を読めませんでした（{list_res}）")
        else:
            notes.append(f"筑波大学の公開一覧を確認できませんでした（システムの内部エラー: {type(list_res).__name__}）")
        list_res = None
    if not web_res["stats"] and list_res is None:
        return {
            "status": "error",
            "reason": "検索できませんでした。" + "。".join(notes) + "。時間をおいて試してください",
        }

    buckets = {
        "eligible": [],
        "needs_check": [],
        "unverified": list(web_res["unverified"]),
        "closed": list(web_res.get("closed", [])),
    }
    seen: set[str] = set()
    if list_res:
        for key in ("eligible", "needs_check"):
            for r in list_res[key]:
                item = _tsukuba_item(r)
                buckets[key].append(item)
                seen.add(websearch.core_name(item["organization"]))
    for key in ("eligible", "needs_check"):
        for item in web_res[key]:
            if websearch.core_name(item["organization"]) not in seen:  # 大学の一覧に載っているものは、そちらを優先する
                buckets[key].append(item)
    return {
        "status": "ok",
        "today": day.isoformat(),
        **buckets,
        "ineligible_count": web_res["ineligible_count"] + (len(list_res["ineligible"]) if list_res else 0),
        "searched": {
            "web": web_res["stats"],
            "university_list": "筑波大学の公開一覧" if list_res else None,
        },
        "notes": notes,
    }


def get_scholarship_detail(scholarship_id: int, tool_context: ToolContext) -> dict:
    """奨学金1件の詳細（出願資格の全文、提出書類、申請方法、公式URL、判定の根拠の引用）を返す。

    Args:
        scholarship_id: find_scholarships の結果に含まれる id。
    """
    try:
        d = service.detail(scholarship_id)
    except Exception as e:  # 取得や読み取りの失敗で会話を止めない（安全なフォールバック）
        logger.exception("奨学金の詳細の取得に失敗しました")
        return {
            "status": "error",
            "reason": f"詳細ページを読めませんでした（{type(e).__name__}）。時間をおいて試してください",
        }
    if d is None:
        return {"status": "error", "reason": f"id {scholarship_id} の奨学金は見つかりませんでした"}
    return {"status": "ok", **d}


SHARED_COLLECTION = "shared_scholarships"


def register_shared_scholarship(
    name: str,
    official_url: str,
    deadline_note: str,
    reason: str,
    tool_context: ToolContext,
    approval_id: str = "",
) -> dict:
    """学生が見つけた奨学金を、他の学生にも見える共有データに「候補」として登録する。【高リスク】

    本人の承認が必要。最初の呼び出しは承認待ち（status が pending）になり、承認IDが返る。
    学生に「承認用の画面（またはコマンド）で承認IDを承認してほしい」と伝え、承認したと言われたら、同じ引数に approval_id を付けて呼び直す。

    Args:
        name: 奨学金の名前。
        official_url: 公式ページのURL（https:// で始まるもの）。
        deadline_note: 締切や募集時期のメモ（分からなければ「不明」）。
        reason: 登録したい理由（監査ログに残る）。
        approval_id: 承認済みのID。最初の呼び出しでは空にする。
    """
    doc_id = hashlib.sha256(official_url.encode()).hexdigest()[:16]
    ap = approvals.get(approval_id) or {}
    record = {
        "name": name,
        "official_url": official_url,
        "deadline_note": deadline_note,
        "reason": reason,
        "registered_by": tool_context.user_id,
        "approved_by": ap.get("decided_by"),
        "approval_id": approval_id,
        "status": "候補（要項の確認が必要）",
    }
    try:
        audit._db().collection(SHARED_COLLECTION).document(doc_id).set({**record, "registered_at": datetime.now(UTC)})
    except Exception as e:  # 書けなかったことを正しく伝える（安全なフォールバック）
        logger.exception("共有データへの登録に失敗しました")
        return {"status": "error", "reason": f"共有データに書き込めませんでした（{type(e).__name__}）"}
    return {"status": "ok", "registered": record}
