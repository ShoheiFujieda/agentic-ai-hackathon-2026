"""ツール実行前後のガード。

before_tool_callback で「許可リスト → 引数の検証 → リスク判定」の順にチェックし、
問題があればツールを実行せずに理由つきの結果を返す（安全なフォールバック）。
"""

from typing import Any

from google.adk.tools import BaseTool, ToolContext

from . import approvals, audit

# 技術検証用の架空ルール。題材が決まったら差し替える。
MAX_AMOUNT = 100_000
ALLOWED_PAYEES = {"A社", "B社", "C社"}

# 許可リスト: ここにないツールは実行させない
TOOL_RISK = {
    "get_balance": "low",
    "send_payment": "high",
}


def _validate_send_payment(args: dict[str, Any]) -> str | None:
    """問題があれば理由を返す。問題なければ None。"""
    payee = args.get("payee")
    amount = args.get("amount")
    reason = (args.get("reason") or "").strip()
    if payee not in ALLOWED_PAYEES:
        return f"支払先「{payee}」は許可リストにありません（許可: {', '.join(sorted(ALLOWED_PAYEES))}）"
    if not isinstance(amount, int) or isinstance(amount, bool):
        return "金額は整数（円）で指定してください"
    if amount <= 0:
        return "金額は1円以上にしてください"
    if amount > MAX_AMOUNT:
        return f"金額が上限（{MAX_AMOUNT:,}円）を超えています"
    if not reason:
        return "支払いの理由（reason）が必要です"
    return None


VALIDATORS = {
    "send_payment": _validate_send_payment,
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
    if validator and (problem := validator(args)):
        return _blocked(name, args, tool_context, "blocked", problem)

    # 3. リスク判定: 高リスクは人間の承認がないと実行しない
    allow_reason = "ルール適合"
    if risk == "high":
        approval_id = args.get("approval_id")
        if not approval_id:
            new_id = approvals.create(**_who(tool_context), tool=name, args=args)
            result = _blocked(name, args, tool_context, "pending", f"高リスク操作のため人間の承認が必要です（承認ID: {new_id}）")
            return {**result, "approval_id": new_id}
        ok, why = approvals.consume(approval_id=approval_id, user_id=tool_context.user_id, tool=name, args=args)
        if not ok:
            return _blocked(name, args, tool_context, "blocked", why)
        allow_reason = why

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
