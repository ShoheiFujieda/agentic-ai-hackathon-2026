FROM python:3.12-slim
WORKDIR /app

# 依存だけを先に入れる（コードを変えても再利用される）
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# エージェントは agents/ の下に置き、ADK と管理画面が同じモジュールを読む
COPY hackathon_agent ./agents/hackathon_agent
COPY ui ./ui
COPY main.py ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/agents" AGENTS_DIR="/app/agents" PYTHONUNBUFFERED=1

# 非 root で実行する
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Cloud Run が PORT を渡す。ASGI のミドルウェアがすべての経路を守る
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
