# 設計判断の記録

各判断を1〜3行で記録する（日付・何を・なぜ）。

## 2026-10-06
- **Firestore は `(default)` DB を Native モード・us-central1 に作成。** Cloud Run と同じリージョンにして遅延を抑え、無料枠（1プロジェクト1DB）に収めるため。ロケーションは後から変更できない。
- **エージェント専用サービスアカウント `hackathon-agent-sa` を用意し、付与するのは `roles/aiplatform.user`（Gemini呼び出し）と `roles/datastore.user`（Firestore読み書き）の2つだけ。** デフォルトのCompute SAは権限が広すぎるため使わない（最小権限）。Cloud Run はこのSAで動作（revision 00002）。
- **予算アラートを月3,000円（50%/90%/100%でメール通知）で設定。** 想定外の課金に早く気づくため。通知のみでサービスは止まらない。
