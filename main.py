"""Cloud Run の入口。利用者向けのサイト（/）と管理画面（/admin/）、ADK の API を1つのサービスにまとめ、Basic 認証で守る。

ADK の開発者向け画面（dev-ui）は本番には出さない（web=False）。ローカルの開発では `adk web` を使う。

ローカルでの確認: APP_USER=demo APP_PASSWORD=... uv run uvicorn main:app --port 8080
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.cli.fast_api import get_fast_api_app
from starlette.responses import HTMLResponse
from starlette.routing import Mount, Route

load_dotenv(Path(__file__).resolve().parent / ".env")

from ui.app import app as admin_app  # noqa: E402
from ui.auth import BasicAuthMiddleware  # noqa: E402

AGENTS_DIR = os.environ.get("AGENTS_DIR") or str(Path(__file__).resolve().parent)

app = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    web=False,  # 開発者向けの画面は出さず、API（/run_sse など）だけ残す
    use_local_storage=False,  # セッションはメモリ内。コンテナ内にファイルを書かない
    allow_origins=[],
    max_llm_calls=20,  # 1回の呼び出しで LLM を呼ぶ回数の上限（費用の上限）
)
SITE = Path(__file__).resolve().parent / "ui" / "site.html"


async def site(request):
    return HTMLResponse(SITE.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store"})


app.router.routes.insert(0, Mount("/admin", app=admin_app))
app.router.routes.insert(0, Route("/", site))
app.add_middleware(BasicAuthMiddleware)
