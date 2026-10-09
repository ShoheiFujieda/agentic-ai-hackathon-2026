"""エージェントが使うツール。検索の進め方と判定はコード（hackathon_agent.scholarship）が行う。"""

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from google.adk.tools import ToolContext

from .scholarship import service
from .scholarship.judge import Profile

# 筑波大学の学群 → 分野の言葉（出願資格の分野と照合する）
FACULTY_KEYWORDS = {
    "人文・文化学群": ["人文", "文学", "文化", "文系"],
    "社会・国際学群": ["社会", "国際", "経済", "法学", "文系"],
    "人間学群": ["教育", "心理", "障害", "人間", "文系"],
    "生命環境学群": ["生物", "生命", "農学", "環境", "地球", "理系", "自然科学"],
    "理工学群": ["理工", "工学", "理学", "数学", "物理", "化学", "理系", "自然科学"],
    "情報学群": ["情報", "工学", "IT", "理系"],
    "医学群": ["医学", "医療", "看護", "保健", "理系"],
    "体育専門学群": ["体育", "スポーツ"],
    "芸術専門学群": ["芸術", "美術", "デザイン"],
}
RECEIVING = {"JASSO貸与", "JASSO給付", "他の民間給付"}
SCHOOL_LOCATION = "茨城県"  # 筑波大学（つくば市）


def today() -> date:
    """日本時間の今日。デモでは環境変数 DEMO_TODAY（YYYY-MM-DD）で固定できる。"""
    fixed = os.environ.get("DEMO_TODAY")
    if fixed:
        return date.fromisoformat(fixed)
    return datetime.now(ZoneInfo("Asia/Tokyo")).date()


def find_scholarships(
    gakugun: str,
    grade: int,
    home_prefecture: str,
    residence_prefecture: str,
    guardian_prefecture: str,
    receiving: list[str],
    tool_context: ToolContext,
) -> dict:
    """筑波大学の学群生が今応募できる奨学金を探し、応募資格を判定する。来年の準備カレンダーも返す。

    判定はコードで行う。結果の status（応募できる／要確認／対象外）と reasons をそのまま学生に伝えること。

    Args:
        gakugun: 所属する学群の正式名（例: 理工学群）。
        grade: 学年（1〜6の整数）。
        home_prefecture: 本人の出身地（出身高校の所在地）の都道府県名（例: 埼玉県）。
        residence_prefecture: 本人が今住んでいる都道府県名（例: 茨城県）。
        guardian_prefecture: 保護者が住んでいる都道府県名（例: 埼玉県）。
        receiving: 今受けている奨学金の区分のリスト。JASSO貸与 / JASSO給付 / 他の民間給付 から選ぶ。なければ空のリスト。
    """
    profile = Profile(
        school_type="大学",
        grade=grade,
        field_keywords=FACULTY_KEYWORDS[gakugun],
        home_prefecture=home_prefecture,
        residence=residence_prefecture,
        school_location=SCHOOL_LOCATION,
        guardian_residence=guardian_prefecture,
        receiving=list(receiving),
    )
    result = service.find(profile, today())
    result.pop("profile", None)
    return {"status": "ok", **result}


def get_scholarship_detail(scholarship_id: int, tool_context: ToolContext) -> dict:
    """奨学金1件の詳細（出願資格の全文、提出書類、申請方法、公式URL、判定の根拠の引用）を返す。

    Args:
        scholarship_id: find_scholarships の結果に含まれる id。
    """
    d = service.detail(scholarship_id)
    if d is None:
        return {"status": "error", "reason": f"id {scholarship_id} の奨学金は見つかりませんでした"}
    return {"status": "ok", **d}
