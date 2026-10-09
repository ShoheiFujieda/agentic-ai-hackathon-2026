# 進捗ログ

作業の始めに読み、終わりに更新する。設計は `DESIGN_SPEC.md`、判断の理由は `docs/decisions.md`、調査は `docs/research/`。

## 現在の状態（最終更新: 2026-10-09）

### 環境（変わらない事実）
- uv + Python 3.12 + google-adk 2.11.0。エージェント: `hackathon_agent/agent.py`（model: gemini-3.8-flash）
- ローカル起動: `uv run adk web --port 9000`
- Cloud Run: `https://hackathon-agent-525978871269.us-central1.run.app`（認証必須、最大2インスタンス、専用SA `hackathon-agent-sa`）
- Firestore `(default)`（Native / us-central1）。予算アラート 月3,000円。300ドルのクーポン適用済み
- GitHub: https://github.com/ShoheiFujieda/agentic-ai-hackathon-2026 （ブランチ `main`）
- 開発用: ruff（Python の編集後に自動実行）、pytest（作業の終了前に自動実行）、秘密情報の検査（`git config core.hooksPath .githooks` で有効）
- `.env`（コミット対象外）: `GOOGLE_CLOUD_PROJECT=agentic-hackathon-2026-510706` / `GOOGLE_CLOUD_LOCATION=global`（gemini-3.x は global のみ。us-central1 は404）/ `GOOGLE_GENAI_USE_VERTEXAI=true`

### 完了済み
- ガバナンス部品の技術検証（10/6）：ツール実行前のガード、監査ログ、失敗時のフォールバック、Firestore の承認フロー（`hackathon_agent/governance/`、テスト `tests/test_approvals.py`）
- PDF抽出の技術検証（10/7）：公開の募集要項PDF 2件を Gemini で抽出（12〜18秒）。画像のページも読めた。pypdf の文字抽出は画像ページを取りこぼす（`scripts/spike_extract_pdf.py`）
- 個人情報・秘密情報の点検（10/7）。未使用の Gemini API Key は削除
- 題材の見直し（10/9）：個人向け・Webから漏れなく探す奨学金エージェント
- 調査（10/9）：ガクシーの裏付け、Perplexity、網羅的な検索の先行研究、ハーネスエンジニアリング（`docs/research/`）
- 検索方式を先行研究ベースに改訂（`DESIGN_SPEC.md` 1.3）
- ハーネスの改善（10/9）：CLAUDE.md を指示だけに整理、作業の始め方・終わり方、機能リスト `docs/features.json`（下書き）、ruff と pytest の自動実行フック（`.claude/settings.json`）、秘密情報の pre-commit 検査（`.githooks/`）、区切りでの `/code-review`

### 未完了（優先順）
1. 比較実験：①②⑥は機能を確認済み（`docs/experiments/` の seed_hub と verify。30件照合で募集終了12・要確認14・大学経由44%）。次はユーザーと設計への反映（来年の準備カレンダー、本人の大学の一覧、分野の判定）を決める → 全方式の比較（`DESIGN_SPEC.md` 1.4）
2. 縦に1本通す：筑波大学の公開一覧で、会話→判定→説明まで動作（`find_scholarships` / `get_scholarship_detail`、約22秒）。コードレビュー中。次は `adk web` でユーザーが試す → adk eval → 画面（カレンダー・監査ログ）
3. 未決事項：高リスク操作を何にするか、ログイン方式（メール受信不要）とテスト用アカウント
4. **提出までに**：Cloud Run を公開URLにし、アプリ側のログイン（テストアカウント）に切り替える
5. ユーザーにお願い中：ガクシーにログインして「学年の選択肢」と「締切後の奨学金が出るか」をスクリーンショットで確認

### 日程の状況
- 当初の日程より約1日遅れ（10/8 は作業なし、10/9 は調査と設計の見直し）。10/12 の機能凍結は維持する

## 作業記録
| 日付 | 内容 | 時間 |
|---|---|---|
| 10/5 | 環境構築、雛形エージェント、Cloud Run デプロイ | — |
| 10/6 | Firestore、専用SA、予算アラート、ガバナンス部品の技術検証 | — |
| 10/7 | 秘密情報の点検、題材検討（奨学金・連携型に仮決定）、PDF抽出の検証 | — |
| 10/9 | 題材を個人向けに見直し、各種調査、検索方式の改訂、ハーネス改善（1〜6、レビュー指摘10件修正）、設計書の全体構成、実験①②（一覧ページ経由で候補 約680件）、判定モジュール（テスト17件）、実験⑥（30件照合）、筑波大学の一覧の調査、縦1本（テスト54件） | — |
