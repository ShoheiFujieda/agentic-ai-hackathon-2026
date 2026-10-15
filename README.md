# 奨学金エージェント

**応募できる奨学金・助成金を、民間のものまで Web から漏れなく探して一覧にする、個人向けの AI エージェント。**
高校生・大学生・大学院生・短大・高専・専門学校生・卒業後の社会人が、**目的（学業・留学・研究・プロジェクトの支援金）に合うものだけ**を受け取れる。

第5回 Agentic AI Hackathon with Google Cloud への提出物。

- プロジェクト説明（ユーザー像・課題・解決策・特徴）: [`docs/submission/description.md`](docs/submission/description.md)
- アーキテクチャ図: [`docs/submission/architecture.png`](docs/submission/architecture.png)（編集用 [`architecture.svg`](docs/submission/architecture.svg)）
- 設計書: [`DESIGN_SPEC.md`](DESIGN_SPEC.md)　判断の記録: [`docs/decisions.md`](docs/decisions.md)　進捗: [`docs/progress.md`](docs/progress.md)
- デプロイ先（Google Cloud Run）: https://hackathon-agent-525978871269.us-central1.run.app
  ログインのユーザー名とパスワードは、提出フォームの「動作確認の方法」に記載（リポジトリには書かない）

## 何を作ったか（開発した部分）
すべて、このリポジトリのコードが実際に動く（モックではない）。Gemini・Google 検索・Firestore・Cloud Run を実際に使っている。

| 部分 | 場所 | 内容 |
|---|---|---|
| エージェント | `hackathon_agent/agent.py` | ADK の単一エージェント（Gemini 3.8 Flash）。聞き取り、ツールの呼び出し、短い要約 |
| ツール | `hackathon_agent/tools.py` | `find_scholarships`（探して判定）、`get_scholarship_detail`、`register_shared_scholarship`（高リスク） |
| 検索 | `hackathon_agent/scholarship/websearch.py` | 発見（Google 検索グラウンディング）→ 一覧ページの展開 → 重複の統合 → 公式ページで照合（引用を原文と照合）→ 判定 |
| 判定（AI ではなくコード） | `hackathon_agent/scholarship/judge.py` | 学年・地域・分野・併給・締切・卒業後・目的を判定。確認できないものは「要確認」に倒す |
| 取得の安全 | `hackathon_agent/scholarship/web.py` | robots.txt を守る、内部アドレスは取得しない、転送先も毎回確認 |
| 筑波大学の公開一覧 | `hackathon_agent/scholarship/tsukuba.py` `service.py` | 大学経由の奨学金（大学名に「筑波」を含むとき併用） |
| ガバナンス | `hackathon_agent/governance/` | `guard.py`（許可リスト・引数検証・上限）、`approvals.py`（人間の承認）、`audit.py`（監査ログ）、`fallback.py` |
| 画面と API | `ui/`, `main.py` | 利用者向けサイト（Material Design 3）、許可・保存・CSV の API、Basic 認証 |
| 評価・テスト | `tests/`, `hackathon_agent/evals/` | 自動テスト約170件、`adk eval` の評価セット |
| 実験 | `scripts/exp_*.py`, `docs/experiments/` | 一覧ページ経由の集合拡張、30件の公式要項での照合、普通の AI 検索との比較 |

## 使っている Google Cloud の製品
- 実行: **Cloud Run**（`Dockerfile`、最大1インスタンス、専用サービスアカウント）
- AI: **Gemini（Vertex AI）＋Google 検索グラウンディング**、**Agent Development Kit（ADK）**
- 保存: Firestore（監査ログ・承認・キャッシュ・共有リスト・保存リスト）、Secret Manager（ログインのパスワード）、Cloud Build

## 動かし方
```bash
uv sync
cp .env.example .env   # GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION=global / GOOGLE_GENAI_USE_VERTEXAI=true を設定（秘密情報はコミットしない）
uv run adk web --port 9000                                  # 開発用の会話画面
APP_USER=tester APP_PASSWORD=... uv run uvicorn main:app    # 本番と同じ構成（サイト `/`、管理 `/admin/`）
uv run pytest -q                                            # 自動テスト（実際の Firestore・Gemini を使うテストを含む）
uv run adk eval hackathon_agent hackathon_agent/evals/governance.evalset.json --config_file_path hackathon_agent/evals/test_config.json
```
評価の実行方法と結果は [`docs/experiments/2026-10-13_adk_eval/README.md`](docs/experiments/2026-10-13_adk_eval/README.md)。

## ガバナンスとセキュリティ（抜粋）
- ツール実行の直前に、許可リスト・引数・上限を検証（`before_tool_callback`）。全操作を監査ログに記録（`after_tool_callback`）
- 他の人にも影響する操作は、**本人が確認ダイアログで許可するまで実行しない**。AI は承認の操作を持たない
- Web ページの内容は命令として扱わない。要項の引用は原文と照合し、判定はコードで行う
- 取得は robots.txt を守り、内部アドレスは拒否。画面は Web 由来の文字列を HTML として解釈しない

## ライセンスと出典
- このリポジトリのコードの著作権は、作成者に帰属する。審査・評価のための閲覧と動作確認は、ハッカソンの参加規約に従う
- 使っているオープンソースソフトウェアとそのライセンス、フォント・アイコンの出典は [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) に明記
- 奨学金の情報は、各団体の公式ページ（および筑波大学の公開一覧）から取得した公開情報。最終的な応募の可否は、各団体の募集要項で確かめる必要がある

## 提出後の扱い
審査期間（2026年12月1日まで）は、デフォルトブランチ（`main`）を提出時点の状態に保ち、デプロイも更新しない。以降の開発は別ブランチで行う。
