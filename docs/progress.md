# 進捗ログ

作業の始めに読み、終わりに更新する。設計は `DESIGN_SPEC.md`、判断の理由は `docs/decisions.md`、調査は `docs/research/`。

## 現在の状態（最終更新: 2026-10-14）

### 環境（変わらない事実）
- uv + Python 3.12.10（python.org の署名つき。`%LOCALAPPDATA%\Python\pythoncore-3.12-64`。uv が入れる署名なしの Python はスマート アプリ コントロールに止められる）+ google-adk 2.11.0。エージェント: `hackathon_agent/agent.py`（model: gemini-3.8-flash）
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
- ハーネスの改善（10/9）：CLAUDE.md を指示だけに整理、作業の始め方・終わり方、機能リスト `docs/features.json`、ruff と pytest の自動実行フック（`.claude/settings.json`）、秘密情報の pre-commit 検査（`.githooks/`）、区切りでの `/code-review`
- 実験（10/9、`docs/experiments/`）：一覧ページ経由で候補 約10件→約680件。公式要項で30件照合（10月時点で28件中12件が募集終了、大学経由44%）。筑波大学の公開一覧で大学経由12件中10件を確認
- 設計への反映（10/9、ユーザー確認済み）：来年の準備カレンダー、本人の大学の一覧、明らかな別分野は対象外、奨学金データの共有、robots.txt の遵守。デモの大学は筑波大学
- **縦1本（10/9）**：筑波大学の公開一覧（`scholarship.json`＋詳細ページ）で、会話→判定→説明まで動作。`adk web` でユーザーの確認済み（約20秒）
  - コード: `hackathon_agent/scholarship/`（web / tsukuba / extract / judge / prefilter / cache / service）、ツール `find_scholarships` と `get_scholarship_detail`、ガード（許可リスト・1セッション5回）
  - AIが読むのは「出願資格」の文章だけ。締切・申請方法・併給・金額はコードで読み、判定もコード
  - テスト66件。コードレビュー2回（指摘20件をすべて修正し、再発防止のテストを追加）
- ローカル環境の修正（10/9）：スマート アプリ コントロールが uv の Python を止めたため、署名つき Python 3.12.10 に替えた。日本時間をタイムゾーンのデータなしで求めるよう修正

- **人間の承認（10/13）**：対象は共有データへの書き込み、承認者は依頼した本人（10/14に管理者案から変更。`DESIGN_SPEC.md` 3.5、`docs/research/2026-10-13_human_approval.md`）。ツール `register_shared_scholarship`（高リスク）を実装。承認のテスト10件（`tests/test_shared_write.py`）、pytest は計77件
- **管理画面（10/14）**：`ui/`（FastAPI＋1枚のHTML）。承認待ちの承認／却下、承認の履歴と所要時間、監査ログ、来年の準備カレンダー。起動は `uv run uvicorn ui.app:app --port 9100`。同一オリジンのPOSTのみ・本人のみ承認・Web由来の文字列はテキスト表示。テスト6件（`tests/test_ui.py`）。**公開前に IAP などの認証が必要**
- **デプロイの準備（10/14、ローカルのみ）**：`main.py`（ADK の会話画面 `/` と管理画面 `/admin/` を1サービスに）、`ui/auth.py`（Basic 認証。未設定は全拒否）、`Dockerfile`、`.gcloudignore` の追加。構成は `DESIGN_SPEC.md` 3.7。ローカルで `APP_USER=… APP_PASSWORD=… uv run uvicorn main:app --port 8080` を起動し、認証なしは全経路401、会話は約42秒、承認→実行まで確認。認証のテスト13件、pytest は計97件。**Dockerfile は Docker が無く未検証（Cloud Build で初めて確かめる）**
- **評価セット（10/13）**：`hackathon_agent/evals/` に adk eval の4ケース（正常系・聞き返し・存在しない学群・指示の無視要求）。結果は `docs/experiments/2026-10-13_adk_eval/`。ページ内インジェクションは `tests/test_injection.py`（F10 合格）。検索回数の上限は `tests/test_guard.py`

### 未完了（優先順）
1. **画面の残り**：結果の3区分と並べ替えの表示（F08）、検索語・止めた理由のログ表示（F12。F03・F07 が前提）。最小版は完了
2. **Cloud Run へのデプロイ**（準備は完了。実行前にユーザーに確認：Secret Manager の秘密の作成、`secretmanager.secretAccessor` の付与、公開（未認証の呼び出し許可）への変更、最大インスタンス1での新リビジョン）。提出までに公開URL＋アプリ側ログイン（テスト用アカウント）へ切り替える（F15）
3. 未決事項：ログイン方式（メール受信不要）。本人確認が今は `--by` のユーザーID の一致だけで弱い（ログインと合わせて直す）
4. 比較実験の全方式の比較（`DESIGN_SPEC.md` 1.4、F13）と、Web 全体を探す部分（①〜⑤）を縦1本につなぐか（日程次第で「拡張予定」）
5. ユーザーにお願い中：ガクシーにログインして「学年の選択肢」と「締切後の奨学金が出るか」をスクリーンショットで確認
6. ユーザーに確認中：`.venv.old`（古い仮想環境）を削除してよいか

### 次回の再開手順
1. `CLAUDE.md` の「始め方」どおり、このファイルと `git log` を読み、`uv run pytest -q` を実行する
2. `uv run adk web --port 9000` で動作を確かめる（基準日を固定したいときは環境変数 `DEMO_TODAY=2026-10-09`）
3. 未完了の2（デプロイ。上の確認事項を1つずつ確認して実行）から始める。管理画面は `uv run uvicorn ui.app:app --port 9100` で確認できる。承認は `uv run python scripts/approve.py list / approve <ID> --by <ユーザーID（adk web の既定は user）>` で今もできる
4. 評価は `PYTHONUTF8=1 DEMO_TODAY=2026-10-13 uv run adk eval hackathon_agent hackathon_agent/evals/governance.evalset.json --config_file_path hackathon_agent/evals/test_config.json`（承認は approval.evalset.json と test_config_approval.json）。並列でモデルが混むとフォールバック文になるので、失敗したケースは単独で再実行する

### 日程の状況
- 10/10-11 は作業記録なし。10/13 時点で機能凍結（10/12）を過ぎている。残りは画面・デプロイ・動画・説明文なので、機能追加はせず「拡張予定」に回す。
- 10/8 は作業なし。10/9 に調査・設計の見直し・縦1本まで進み、当初の日程（10/7-8 に縦1本）より約1日遅れ。10/10-11 で評価・画面・デプロイ、10/12 の機能凍結は維持する

### 教訓（次から気をつけること）
- テストで日付を固定していたため、実際の日付で動かしたときの不具合（タイムゾーンのデータがない）に気づけなかった。区切りでは、ユーザーと同じ経路（`adk web` の API）で、日付を固定せずに通しで確かめる
- AI の抜き出しは毎回少し揺れる。判定の誤りは「対象外」側に出ると見落としになるので、迷う読み取りは「要確認」に倒す（コードとテストで強制）

## 作業記録
| 日付 | 内容 | 時間 |
|---|---|---|
| 10/5 | 環境構築、雛形エージェント、Cloud Run デプロイ | — |
| 10/6 | Firestore、専用SA、予算アラート、ガバナンス部品の技術検証 | — |
| 10/7 | 秘密情報の点検、題材検討（奨学金・連携型に仮決定）、PDF抽出の検証 | — |
| 10/9 | 題材を個人向けに見直し、各種調査、検索方式の改訂、ハーネス改善（1〜6、レビュー指摘10件修正）、設計書の全体構成、実験①②（一覧ページ経由で候補 約680件）、判定モジュール（テスト17件）、実験⑥（30件照合）、筑波大学の一覧の調査、縦1本（テスト54件）、レビュー指摘10件の修正、署名つき Python への切り替え、日付の不具合の修正（テスト66件） | 1日 |
| 10/13 | pytest を確認、adk eval の評価セット（現在6ケース）と注入テストを追加（F10 合格）。開発用に google-adk[eval] を追加 | 約1時間 |
| 10/13 | 人間の承認の調査と方針決定（当初は管理者承認案、10/14に本人承認へ変更）、`register_shared_scholarship` と承認フローのテスト、adk eval に承認の2ケース追加（F11、F14 合格） | 約1時間 |
| 10/14 | 承認者を本人に変更、管理画面（承認・監査ログ・カレンダー）の最小版とテスト6件 | 約1時間 |
| 10/14 | デプロイの準備（main.py、Basic 認証、Dockerfile）、ローカルでの通し確認、認証のテスト13件 | 約1時間 |
