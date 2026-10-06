"""技術検証用の架空ツール。実際のお金は動かない。題材が決まったら差し替える。"""

import uuid

from google.adk.tools import ToolContext

INITIAL_BALANCE = 500_000


def get_balance(tool_context: ToolContext) -> dict:
    """口座の残高を確認する（読み取りのみ）。"""
    balance = tool_context.state.get("balance", INITIAL_BALANCE)
    return {"status": "ok", "balance": balance}


def send_payment(payee: str, amount: int, reason: str, tool_context: ToolContext) -> dict:
    """支払先に送金する（架空）。

    Args:
        payee: 支払先の名前。
        amount: 金額（円、整数）。
        reason: 支払いの理由。監査ログに残る。
    """
    balance = tool_context.state.get("balance", INITIAL_BALANCE)
    if amount > balance:
        return {"status": "error", "reason": "残高が足りません"}
    tool_context.state["balance"] = balance - amount
    return {
        "status": "ok",
        "transaction_id": f"tx-{uuid.uuid4().hex[:8]}",
        "payee": payee,
        "amount": amount,
        "balance_after": balance - amount,
    }
