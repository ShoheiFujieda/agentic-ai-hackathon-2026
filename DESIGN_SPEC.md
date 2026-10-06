# DESIGN_SPEC.md

最終更新: 2026-10-06

## 1. 題材
（未定。決まり次第、対象ユーザー・課題・定量効果をここに書く）

## 2. 全体構成（題材によらず共通）
- ADK (Python) 単一エージェント `hackathon_agent` ＋ ツール2〜3個
- モデル: `gemini-3.8-flash`（Vertex AI, location=global）
- 実行: Cloud Run（専用SA `hackathon-agent-sa`、最大2インスタンス、認証必須）
- 保存: Firestore `(default)`（us-central1）

## 3. ガバナンス部品（題材によらず共通）

### 3.1 ツール呼び出しのガード（`before_tool_callback`）
ツールが実行される直前に、次の順番でチェックする。
1. **許可リスト**: 登録されたツール以外は拒否
2. **引数の検証**: 型・範囲・上限（例: 金額の上限）。違反したら理由つきで拒否
3. **リスク判定**: 高リスク操作は「承認待ち」を作って実行を止める（3.2）
- 拒否したときは、ツールを実行せずに `{"status": "blocked", "reason": ...}` をエージェントに返す。エージェントはそれを見てユーザーに説明する（安全なフォールバック）

### 3.2 人間の承認（自前方式・Firestore）
ADK組み込みの Tool Confirmation は実験的な機能で、永続セッションでは使えないため、自分たちで作る（`docs/decisions.md` 参照）。
- 高リスクのツール呼び出し → Firestore `approvals/{id}` に `status=pending` で保存し、エージェントには `pending_approval` と承認IDを返す
- 承認者が承認または却下する（検証段階ではCLIスクリプト、後で画面）
- エージェントが同じ承認IDで再実行 → ガードが確認する。`approved` で、**引数が承認時と同じ**で、**未使用**のときだけ実行し、`used` にする（使い回しと中身のすり替えを防ぐ）
- 依頼した本人は承認できない（職務分離）。承認は依頼者本人のみが使え、有効期限は24時間
- 確認と更新は Firestore のトランザクションで一度に行い、同時実行による二重使用を防ぐ
- 実装: `hackathon_agent/governance/approvals.py`、承認CLI `scripts/approve.py`、テスト `tests/test_approvals.py`（7件）

### 3.3 監査ログ
Firestore `audit_logs` に1操作1件で記録する。
- 誰が（user_id）、いつ（UTC時刻）、何を（ツール名・引数）、なぜ（高リスクツールは `reason` 引数を必須にする）、結果（allowed / blocked / pending / executed / error）
- ガードでの判定と、ツール実行後の結果（`after_tool_callback`）の両方を記録する

### 3.4 評価
- `adk eval` の評価セット: 正常系 / 上限超えで拒否 / 承認待ちになる / 未承認のまま実行しようとして止められる

## 4. 技術検証（10/6）の範囲
題材が決まる前に、**おもちゃのツール2つ**で 3.1〜3.4 が縦に1本動くことを確かめる。題材が決まったらツールだけ差し替える。
- `get_balance()`: 低リスク（読み取りのみ）
- `send_payment(payee, amount, reason, approval_id=None)`: 高リスク（架空の送金。実際には何も送らない）
- 置き場所: `hackathon_agent/governance/`（guard.py / approvals.py / audit.py）、`hackathon_agent/tools.py`、承認CLI `scripts/approve.py`
- 追加する依存パッケージ: `google-cloud-firestore`
- ローカルからは自分のアカウント（ADC）で Firestore にアクセスする。デプロイは今回しない
