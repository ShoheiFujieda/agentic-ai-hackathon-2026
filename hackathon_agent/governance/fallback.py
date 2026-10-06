"""失敗時の安全なフォールバック。"""

import logging

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

from . import audit

logger = logging.getLogger(__name__)

MODEL_ERROR_MESSAGE = (
    "申し訳ありません。AIの応答が混み合っているため、今回の処理は行っていません。"
    "少し時間をおいて、もう一度お試しください。"
)


def on_model_error_fallback(
    callback_context: CallbackContext, llm_request: LlmRequest, error: Exception
) -> LlmResponse:
    """Gemini がリトライ後も失敗したとき、例外を画面に出さず、何も実行していないことを伝える。"""
    logger.exception("モデル呼び出しに失敗しました", exc_info=error)
    audit.record(
        user_id=callback_context.user_id,
        session_id=callback_context.session.id,
        tool="(model)",
        args={},
        decision="error",
        reason=f"{type(error).__name__}: {str(error)[:200]}",
    )
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=MODEL_ERROR_MESSAGE)]))
