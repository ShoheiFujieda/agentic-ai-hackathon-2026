# 初日セットアップ手順（Windows / 所要の目安: 2〜3時間 ※私の推定）

ゴール: **空のADKエージェントが Cloud Run 上で動き、URLで応答する**状態にする。題材はまだ決まっていなくてよい。
★は未検証（公式ドキュメントの要約に基づく）。詰まったら、公式ドキュメントを優先する。

## A. あなた自身がやること（Claude Codeには任せない）
1. **ハッカソンにエントリー**: https://zenn.dev/hackathons/google-cloud-japan-ai-hackathon-vol5 の「申し込む」。
2. **クーポン登録（10/20まで）**: エントリー後に案内されるコードを http://cloud.google.com/redeem で入力。有料アカウントへのアップグレードが条件。過去に無料トライアルを使っている場合の扱いは★未確認。
3. **個人のGoogleアカウント**でGoogle Cloudにログイン（大学・職場アカウントは制限の可能性）。
4. **新規プロジェクトを作る**（例: `agentic-hackathon-2026`）。請求先アカウントを紐付ける。
5. **予算アラートを設定**: 請求 → 予算とアラート。例として $20 / $50 で通知（金額は自分で決める）。
6. **Gemini APIキーを取得**: https://aistudio.google.com/app/apikey （ローカル開発用。リポジトリには絶対に入れない）。
7. **GitHubで新しいリポジトリ**を作る（非公開でよい）。

## B. PCに入れるもの
- Python 3.10以上、Git
- uv（PowerShellで）: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- Google Cloud CLI（gcloud）: 公式インストーラ https://cloud.google.com/sdk/docs/install

## C. ログインと設定（あなたがブラウザで認証）
```
gcloud auth login
gcloud auth application-default login
gcloud config set project <プロジェクトID>
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com aiplatform.googleapis.com
```

## D. ここからClaude Codeに任せてよい
このフォルダを開いてClaude Codeを起動し、`CLAUDE.md` を読ませたうえで次を依頼する。
1. 「SETUP.md のDの手順で、ADKの雛形を作って `adk web` でローカル動作を確認して」
   - 公式の手順（★）: `uvx google-agents-cli setup` → `agents-cli create <名前> --prototype --yes`。手書きなら `pip install google-adk` と `adk web --port 8000`。
   - `.env` に `GOOGLE_API_KEY=...` を置く。`.env` は `.gitignore` と `.gcloudignore` に必ず入れる。
2. 「空のエージェントを Cloud Run にデプロイして」
   - 公式の手順（★）: `adk deploy cloud_run --project=<ID> --region=<リージョン> <エージェントのパス> --with_ui`
   - 「Allow unauthenticated invocations?」は、まず **N（認証必須）**。デモ公開時に決め直す。
   - リージョンは、料金が安い Tier 1 の `us-central1` を基本にする（★東京の課金階層は未確認）。
3. 「最大インスタンス数を1〜2に制限して」（予期しない課金の防止）。

## E. 初日の完了条件
- [ ] ハッカソンにエントリー済み、クーポン登録済み
- [ ] 予算アラート設定済み
- [ ] `adk web` がローカルで動く
- [ ] Cloud RunのURLでエージェントが応答する
- [ ] GitHubにpush済み（`.env` が含まれていないことを確認）

## 詰まりやすい点（調査より）
- Cloud Run上のセッションはデフォルトでメモリ内。インスタンスが入れ替わると消える。
- ADKのバージョンで挙動が違う。古いブログのコードは動かないことがある。
- Tool Confirmation（人間承認）は DatabaseSessionService / VertexAiSessionService と併用不可（公式記載）。承認は自前でFirestoreに保存する方式を試作する（★未検証）。
