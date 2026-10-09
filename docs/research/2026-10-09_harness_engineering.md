# ハーネスエンジニアリングと Claude Code の使い方（2026-10-09 調査）

「エージェント＝モデル＋ハーネス」。ハーネスとは、モデルの周りにある指示ファイル・ツール・検証の仕組み・記憶・ガードレールのこと。2026年初めに一つの分野として名前が付き、「普通のモデル＋良いハーネスは、優れたモデル＋悪いハーネスに勝つ」と言われる。

## 1. 主な情報源と要点
| 情報源 | 要点 |
|---|---|
| OpenAI「Harness engineering」（2026-02） | 手書きのコード0行で製品を作った実験。「人間が舵を取り、エージェントが実行する」。人間の仕事は、目標を明確にすること、リポジトリの知識をエージェントが見つけられるようにすること、**境界をチェックで機械的に強制すること**、エージェントが自分で直せるフィードバックの仕組みを作ること |
| Anthropic「Effective harnesses for long-running agents」（2025-11） | 長い作業では毎回記憶がない状態から始まる。必要なのは凝った仕組みではなく、**進捗ログ・機械が読める機能リスト（JSON、各項目に合否）・起動スクリプト・きれいな git 履歴**。起きた失敗：早すぎる「完成」宣言、一度に作りすぎる、壊れた状態で引き継ぐ。対策：1回に1機能、毎回の最初に動作確認、利用者と同じ操作での E2E テスト |
| Anthropic「Harness design for long-running application development」（2026-03） | **自分の作ったものを自分で評価させると、凡庸でも褒めてしまう**。評価役を分けて厳しくする方が、作り手を自己批判的にするより簡単。作る前に「完成の基準」を合意する。モデルが良くなったら、不要になったハーネスの部品は外す |
| Anthropic「Writing effective tools for agents」（2025-09） | **ツールの設計がエージェントの性能を最も左右する**。ツールは少なく、名前と説明を明確に、返す内容は必要十分に（トークンを節約）、評価セットでツールの説明を改善する |
| Addy Osmani「Agent Harness Engineering」（2026-04） | 指示ファイルの各行は「実際に起きた失敗」に由来すべき。短く（60行以内）、チェックリストのように。「成功は静かに、失敗は詳しく」伝える。**ラチェット**：一度起きた失敗は、フック・検証ルール・テストで二度と起きないようにする |
| 「Evaluating AGENTS.md」（arXiv 2602.11988、2026-02） | 指示ファイル（AGENTS.md）は、**成功率をほとんど上げず、コストを20%以上増やす**。AIが自動生成したものはわずかに逆効果。コードから分からない「追加の指示」だけを書くべき |
| Claude Code のベストプラクティス（各種まとめ、2026） | CLAUDE.md は約200行が上限の目安。強制したいことはフックや権限設定で行い、文章で頼まない。編集後に自動でリンターを走らせる PostToolUse フックが、最も安い検証ループ |
| METR のランダム化比較試験（2025） | 熟練の開発者がAIを使うと、本人は24%速くなったと感じたが、実際には19%遅くなった。体感ではなく計測で判断する |
| Barbaste ほか「Harness Engineering: Anatomy…」（arXiv 2609.00006、2026） | 11のコーディングエージェントのソースコードを分析。重要な部品は、文脈の管理・ツール・検証・サブエージェント・記憶・権限 |

## 2. このプロジェクトでの開発の進め方に取り入れること
1. **CLAUDE.md を短くする**：今は115行で、その半分以上が進捗メモ。進捗は `docs/progress.md` に移し、CLAUDE.md には「コードから分からない指示」だけを残す
2. **毎回の作業の始め方を決める**：`docs/progress.md` と `git log` を読む → テストを実行して壊れていないか確認 → 未完了の最優先の項目を1つ選ぶ
3. **機能リストを JSON で持つ**：`docs/features.json` に、デモに必要な機能を「確認手順」と「合否」付きで並べる。テストで確認するまで「完成」と言わない
4. **検証を自動にする（フック）**：Python を編集したらリンター（ruff）を自動で実行する。作業を終える前にテスト（pytest）を実行する
5. **作り手と評価役を分ける**：大きな区切りでは、作業の文脈を持たない別の評価（`/code-review` など）を通してからコミットする
6. **ラチェット**：起きた失敗はテストやフックにして再発を防ぐ（例：AIが「4月締切の奨学金を10月に募集中」と答えた → 募集状態の判定にテストを書く）
7. **秘密情報の混入を機械的に止める**：コミットの前に秘密情報をスキャンする（文章のルールだけに頼らない）
8. **時間を計測する**：作業ごとに予定と実際の時間を `docs/progress.md` に記録し、日程の遅れを早く見つける

## 3. 作る製品（奨学金エージェント）に取り入れること
- **作り手と評価役の分離**：AIが要項から読み取った条件を、コード（引用が原文と一致するかの照合、日付の判定）が別に検証する。AI自身に「正しいか」を判断させない（設計済みの方針の裏付け）
- **ツールは少なく明確に**：ADK のツールは2〜3個。説明文を評価セット（`adk eval`）の結果で改善する
- **完成の基準を先に決める**：比較実験の評価指標（再現率など）を、実装の前に固定する

## 出典
- OpenAI, Harness engineering https://openai.com/index/harness-engineering/ （本文は403。要約記事で確認：https://www.theneuron.ai/explainer-articles/openais-harness-engineering-playbook-how-to-ship-1m-lines-of-code-without-writing-any/ ）
- Anthropic, Effective harnesses for long-running agents https://anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic, Harness design for long-running application development https://www.anthropic.com/engineering/harness-design-long-running-apps
- Anthropic, Writing effective tools for agents https://www.anthropic.com/engineering/writing-tools-for-agents
- Addy Osmani, Agent Harness Engineering https://addyosmani.com/blog/agent-harness-engineering/
- Evaluating AGENTS.md https://arxiv.org/html/2602.11988v1
- Claude Code Advanced Best Practices 2026 https://smartscope.blog/en/generative-ai/claude/claude-code-best-practices-advanced-2026/
- METR study（要約） https://the-decoder.com/ai-coding-can-make-developers-slower-even-if-they-feel-faster/
- Harness Engineering: Anatomy, Architecture, and Evolution of Coding Agents https://arxiv.org/pdf/2609.00006
