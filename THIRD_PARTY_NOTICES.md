# サードパーティのライセンス表記（Third-party notices）

このプロジェクトは、次のオープンソースソフトウェア・フォント・アイコンを利用している。各ライセンスの条件に従い、ここに出典とライセンスを明記する。
バージョンは `uv.lock` で固定している（推移的な依存を含む全体の一覧は `uv.lock` を参照）。

## 直接利用しているライブラリ（Python）
| ライブラリ | バージョン | ライセンス | 用途 |
|---|---|---|---|
| google-adk（Agent Development Kit） | 2.11.0 | Apache-2.0 | エージェントの実行基盤、コールバック、評価（`adk eval`）、API サーバー |
| google-genai | 2.28.0 | Apache-2.0 | Gemini（Vertex AI）の呼び出し、Google 検索グラウンディング |
| google-cloud-firestore | 2.34.0 | Apache-2.0 | 監査ログ・承認・キャッシュ・保存リストの保存 |
| pypdf | 6.19.0 | BSD-3-Clause | 募集要項 PDF からの文字の取り出し |
| httpx | 0.28.1 | BSD-3-Clause | Web ページの取得 |
| FastAPI | 0.141.1 | MIT | 画面・許可・保存 API |
| Starlette | 1.7.0 | BSD-3-Clause | ミドルウェア（Basic 認証）、ルーティング |
| Uvicorn | 0.54.0 | BSD-3-Clause | ASGI サーバー |
| Pydantic | 2.13.5 | MIT | 入力の検証 |
| python-dotenv | 1.2.4 | BSD-3-Clause | 環境変数の読み込み |

開発用: pytest（MIT）、ruff（MIT）、google-adk の評価用の追加依存（`google-adk[eval]`）。

## コンテナ
- ベースイメージ: `python:3.12-slim`（Python Software Foundation License ほか。Debian のパッケージを含む）
- `uv`（Astral、MIT または Apache-2.0）をビルドに使用

## フォント（画面で、Google Fonts から読み込む）
| フォント | ライセンス |
|---|---|
| Roboto | Apache-2.0 |
| Noto Sans JP | SIL Open Font License 1.1 |

## アイコン・デザイン
- 画面のアイコンは、Material Icons（© Google、Apache-2.0）の図形を、SVG としてコードに埋め込んで使用
- 画面の設計は、Material Design 3（Google）の考え方に沿って、独自に実装した（Material Design のソースコードは使用していない）

- アーキテクチャ図のアイコンは、Google Cloud のプロダクト アイコン（公式ライブラリ https://cloud.google.com/icons、© Google）。Cloud Run・Vertex AI は `core-products-icons.zip`、Firestore（データベース）・Secret Manager（セキュリティ）は、製品固有のアイコンが無いため `category-icons.zip` のカテゴリのアイコンを使用。図の作成のために、同ライブラリの案内に従って使用（`docs/submission/icons/`）

## 外部のデータ
- 奨学金の情報は、各団体の公式ページおよび筑波大学の公開一覧から、robots.txt を守って取得した公開情報
- Gemini・Google 検索グラウンディングは、Google Cloud（Vertex AI）の利用規約に従って使用
