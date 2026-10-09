"""ツール実行前後のガード。

before_tool_callback で「許可リスト → 引数の検証 → リスク判定」の順にチェックし、
問題があればツールを実行せずに理由つきの結果を返す（安全なフォールバック）。
"""

from typing import Any

from google.adk.tools import BaseTool, ToolContext

from ..scholarship.prefilter import PREFECTURES
from ..tools import FACULTY_KEYWORDS, RECEIVING
from . import approvals, audit

# 1セッションで find_scholarships を呼べる回数（Gemini の費用の上限）
MAX_SEARCHES_PER_SESSION = 5

# 許可リスト: ここにないツールは実行させない
TOOL_RISK = {
    "find_scholarships": "low",
    "get_scholarship_detail": "low",
}


def _validate_find_scholarships(args: dict[str, Any], tool_context: ToolContext) -> str | None:
    """問題があれば理由を返す。問題なければ None。"""
    if args.get("gakugun") not in FACULTY_KEYWORDS:
        return f"学群名「{args.get('gakugun')}」は使えません（使える値: {'、'.join(FACULTY_KEYWORDS)}）"
    grade = args.get("grade")
    if not isinstance(grade, int) or isinstance(grade, bool) or not 1 <= grade <= 6:
        return "学年は1〜6の整数で指定してください"
    for key, label in (
        ("home_prefecture", "出身地"),
        ("residence_prefecture", "本人の住所"),
        ("guardian_prefecture", "保護者の住所"),
    ):
        if args.get(key) not in PREFECTURES:
            return f"{label}「{args.get(key)}」は都道府県名（例: 埼玉県）で指定してください"
    receiving = args.get("receiving")
    if not isinstance(receiving, list) or not set(receiving) <= RECEIVING:
        return f"受給中の奨学金は {'、'.join(sorted(RECEIVING))} から選んでください（なければ空のリスト）"
    used = tool_context.state.get("search_count", 0)
    if used >= MAX_SEARCHES_PER_SESSION:
        return f"このセッションでの検索は上限（{MAX_SEARCHES_PER_SESSION}回）に達しました。新しいセッションで試してください"
    return None


def _validate_get_scholarship_detail(args: dict[str, Any], tool_context: ToolContext) -> str | None:
    sid = args.get("scholarship_id")
    if not isinstance(sid, int) or isinstance(sid, bool) or sid <= 0:
        return "scholarship_id は find_scholarships の結果にある正の整数を指定してください"
    return None


VALIDATORS = {
    "find_scholarships": _validate_find_scholarships,
    "get_scholarship_detail": _validate_get_scholarship_detail,
}


def _who(tool_context: ToolContext) -> dict[str, str]:
    return {"user_id": tool_context.user_id, "session_id": tool_context.session.id}


def _skip_key(tool_context: ToolContext) -> str:
    # "temp:" で始まる state はその実行の間だけ残り、セッションには保存されない
    return f"temp:guard_skipped:{tool_context.function_call_id}"


def _blocked(tool: str, args: dict, tool_context: ToolContext, decision: str, reason: str) -> dict:
    audit.record(**_who(tool_context), tool=tool, args=args, decision=decision, reason=reason)
    # ADK はガードが止めた場合も after_tool_callback を呼ぶので、「実行済み」と記録しないよう印を付ける
    tool_context.state[_skip_key(tool_context)] = True
    return {"status": decision, "reason": reason}


def before_tool_guard(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> dict | None:
    """None を返すとツールが実行され、dict を返すとそれがツールの結果の代わりになる。"""
    name = tool.name

    # 1. 許可リスト
    risk = TOOL_RISK.get(name)
    if risk is None:
        return _blocked(name, args, tool_context, "blocked", f"ツール「{name}」は許可されていません")

    # 2. 引数の検証
    validator = VALIDATORS.get(name)
    if validator and (problem := validator(args, tool_context)):
        return _blocked(name, args, tool_context, "blocked", problem)

    # 3. リスク判定: 高リスクは人間の承認がないと実行しない
    allow_reason = "ルール適合"
    if risk == "high":
        approval_id = args.get("approval_id")
        if not approval_id:
            new_id = approvals.create(**_who(tool_context), tool=name, args=args)
            result = _blocked(
                name, args, tool_context, "pending", f"高リスク操作のため人間の承認が必要です（承認ID: {new_id}）"
            )
            return {**result, "approval_id": new_id}
        ok, why = approvals.consume(approval_id=approval_id, user_id=tool_context.user_id, tool=name, args=args)
        if not ok:
            return _blocked(name, args, tool_context, "blocked", why)
        allow_reason = why

    if name == "find_scholarships":
        tool_context.state["search_count"] = tool_context.state.get("search_count", 0) + 1
    if not audit.record(**_who(tool_context), tool=name, args=args, decision="allowed", reason=allow_reason):
        # 監査ログが残せない操作は、低リスクでも実行しない
        tool_context.state[_skip_key(tool_context)] = True
        return {"status": "error", "reason": "監査ログを記録できないため実行を中止しました"}
    return None


def after_tool_audit(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: dict
) -> dict | None:
    """実行されたツールの結果を監査ログに残す。結果自体は変更しない。"""
    if tool_context.state.get(_skip_key(tool_context)):
        return None
    audit.record(
        **_who(tool_context),
        tool=tool.name,
        args=args,
        decision="executed",
        reason="ツール実行完了",
        result=tool_response if isinstance(tool_response, dict) else {"value": str(tool_response)},
    )
    return None
