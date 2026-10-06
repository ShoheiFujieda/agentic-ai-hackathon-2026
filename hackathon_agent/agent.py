from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import types

from .governance.fallback import on_model_error_fallback
from .governance.guard import after_tool_audit, before_tool_guard
from .tools import get_balance, send_payment

root_agent = Agent(
    name="hackathon_agent",
    # Gemini の応答がまれに数分かかるため、30秒で打ち切って最大3回まで試す
    model=Gemini(
        model="gemini-3.8-flash",
        retry_options=types.HttpRetryOptions(attempts=3, initial_delay=1, max_delay=4),
    ),
    description="ガバナンス付きエージェントの技術検証（架空の送金）",
    instruction=(
        "あなたは経理担当を手伝うアシスタントです。日本語で答えてください。\n"
        "- 残高の確認には get_balance、支払いには send_payment を使います。\n"
        "- send_payment には必ず支払いの理由（reason）を入れます。理由が分からなければユーザーに聞き返してください。\n"
        "- ツールの結果の status が blocked / pending / error のときは、実行されていないことと"
        "その理由（reason）をそのままユーザーに伝えてください。勝手に条件を変えて再試行してはいけません。"
    ),
    tools=[get_balance, send_payment],
    generate_content_config=types.GenerateContentConfig(
        http_options=types.HttpOptions(timeout=30_000),
        # ルール判定はガード（コード）が担うので、モデルに深い思考は不要。速度とコストを優先する
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
    ),
    before_tool_callback=before_tool_guard,
    after_tool_callback=after_tool_audit,
    on_model_error_callback=on_model_error_fallback,
)
