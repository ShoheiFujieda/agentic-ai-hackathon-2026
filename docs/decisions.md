# 設計判断の記録

各判断を1〜3行で記録する（日付・何を・なぜ）。

## 2026-10-06
- **Firestore は `(default)` DB を Native モード・us-central1 に作成。** Cloud Run と同じリージョンにして遅延を抑え、無料枠（1プロジェクト1DB）に収めるため。ロケーションは後から変更できない。
- **エージェント専用サービスアカウント `hackathon-agent-sa` を用意し、付与するのは `roles/aiplatform.user`（Gemini呼び出し）と `roles/datastore.user`（Firestore読み書き）の2つだけ。** デフォルトのCompute SAは権限が広すぎるため使わない（最小権限）。Cloud Run はこのSAで動作（revision 00002）。
- **人間の承認は ADK の Tool Confirmation を使わず、Firestore に承認待ちを保存する自前方式にする。** 公式ドキュメント上、Tool Confirmation は実験的な機能で、DatabaseSessionService / VertexAiSessionService では使えない。Firestore のセッション保存も Java 版にしかない（2026-10-06 に adk.dev で確認）。
- **ルール判定（許可リスト・上限）はモデルに任せず、`before_tool_callback` のコードで行う。** モデルが判断を誤っても、コードが最後の砦になる。拒否時はツールを実行せず、理由をエージェントに返して説明させる。
- **監査ログは Firestore `audit_logs` と標準出力（Cloud Logging）の両方に書き、書けない場合は低リスク操作でも実行しない。** ADK はガードが止めた呼び出しにも after_tool_callback を呼ぶため、`temp:` state の印で「実行済み」の誤記録を防ぐ。
- **Gemini 呼び出しは thinking=LOW、30秒タイムアウト、最大3回リトライ。失敗時は `on_model_error_callback` で「処理は行っていない」と返す。** 検証中に、応答に約3分かかる呼び出しがまれに発生したため。
- **承認は「依頼者本人は承認不可・承認時と同じ引数のみ・1回限り・24時間有効」とし、引数の指紋（SHA-256）で一致を確認する。** モデルがユーザーの「承認された」という言葉を信じても、最終判断は Firestore 上の承認記録で行う（E2E 検証で実際にこの場面が起き、コードが止めた）。
- **予算アラートを月3,000円（50%/90%/100%でメール通知）で設定。** 想定外の課金に早く気づくため。通知のみでサービスは止まらない。

## 2026-10-07
- **AI Studio が自動で作った「Gemini API Key」と、そのキー専用のサービスアカウントを削除した。** Gemini は専用SA＋IAMで Vertex AI 経由で呼び出しており、キーは不要。キーがなければ漏れることもない。規約上も Agent Platform（旧 Vertex AI）経由が推奨されている。直近の利用は 10/5 の初期設定時の2回だけで、どちらも失敗していた（Cloud Monitoring で確認）。
- **スポンサーAPIなど外部サービスのキーが必要になったら、Secret Manager に保存し、コードや `.env` には書かない。**
