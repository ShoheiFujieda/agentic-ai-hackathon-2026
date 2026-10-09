# Perplexity の検索の仕組みと弱点（2026-10-09 調査）

## 1. 仕組み（Perplexity 自身の公開情報）
Perplexity は検索の仕組みを査読論文ではなく、自社の研究ブログと、検索基盤の提供元（Vespa）の記事で公開している。研究ブログ本体はアクセスが拒否された（403）ため、内容は Vespa の記事と、研究ブログを要約した記事から確認した。

1. **索引**：自社クローラー（PerplexityBot）と外部から購入したクロールデータで、数千億ページの索引を持つ。毎秒数万件の更新で鮮度を保つ
2. **検索**：キーワード検索と意味検索（埋め込み）を組み合わせる（ハイブリッド検索）。ページ全体ではなく**段落（パッセージ）単位**で検索・順位付けする
3. **順位付け**：軽い採点で候補を絞り、最後に強力なモデル（クロスエンコーダー）で並べ直す。ここまでを**約100ミリ秒**で行う
4. **回答の生成**：上位の段落だけを LLM（Sonar。Llama 3.3 70B を調整したもの）に渡し、文ごとに出典を付けて回答する
5. **Deep Research（2025年2月〜）**：質問を小さな問いに分け、数十回検索し、読んだ内容から次の検索を決めて、レポートにまとめる。詳しい手順は非公開
6. **自社の評価**：SimpleQA、FRAMES、BrowseComp、HLE で評価し、評価の仕組みを公開している（search_evals）。**どれも「正解が1つの質問」で、「該当するものを漏れなく全部挙げる」力は測っていない**

## 2. 外部の研究で確認された弱点
| 弱点 | 根拠 |
|---|---|
| 出典として示す情報源が少ない。取得した情報源より、回答に使う情報源の方が少ない | Narayanan Venkit ほか（Salesforce AI Research、arXiv 2410.22349、2024）。Perplexity が示す情報源は平均3.4件 |
| 出典が主張を支えていない。根拠のない文がある | 同上：出典の正確さ49.0%、根拠のない文31.6% |
| 質問の言い回しに引きずられ、自信過剰に答える | 同上：一方的な回答83.4%、自信過剰な回答81.6%（調べた3つの回答エンジンの中で、多くの指標で最下位） |
| 出典の特定を間違える | Tow Center（コロンビア大学、2025年3月）：8つのAI検索で1,600問を試し、全体で60%以上が誤り。Perplexity は8つの中で最も良かったが、それでも37%が誤り |
| 第三者メディアや大手を優先し、小さな発信元は不利 | Chen ほか（arXiv 2509.08919、2025）：AI検索は第三者メディアに強く偏る（Perplexity：自動車分野の米国で81.9%）。ニッチな発信元に不利な「大手ブランドへの偏り」がある |
| AIが生成した低品質な記事を出典にする | GPTZero の調査（2024年6月）：京都の祭りについて聞くと、AI生成とみられる LinkedIn の記事1件だけを出典にした |
| 数値の出典が確認できない | 監査記事：数値に付いた出典のうち34.7%が、開けないか、その数字を含まない（二次情報。手法は未確認） |

※ 研究の多くは2024〜2025年のもので、2026年の Perplexity は改善している可能性がある。

## 3. 利用者の意見（研究とは別）
- 「最近少し正確性が落ちた気がします。いわゆるハルシネーションなのかもしれません」（ITreview、組込み開発の利用者、2026-01-06）
- 出典は出るが、文のどこがどの出典から来たかが分かりにくくなった（Reddit r/perplexity_ai「Citations have gone bad」、2025-04。要約記事経由）
- 情報が古いことがある。簡単な質問でも数分かかることがある。Proプランが高い（各種レビューのまとめ）
- 良い点：出典のURLが出るので確かめられる。短い調べものに便利

## 4. このプロジェクトへの示唆
Perplexity は「**速く（約100ミリ秒）、1つの正しい答えを、少数の出典で返す**」ことに最適化されている。奨学金探しは「**時間をかけて、条件に合うものを全部数える**」作業で、目的が違う。

| Perplexity の設計 | 奨学金探しで起きる問題 | このエージェントでの対応 |
|---|---|---|
| 上位の段落だけを LLM に渡す | 該当する奨学金が多くても、数件しか出ない | 漏れなく数えることを目的にし、捕獲・再捕獲法で漏れの量を推定する |
| 100ミリ秒の速さを優先 | 深く探せない | 1回の探索に数分かけてよい設計にする（結果は保存して使い回す） |
| 段落単位で読む | 条件が表や注記に分かれていると取りこぼす | 要項を全文読み、条件を項目にする |
| 大手・第三者メディアを優先 | 小さな財団の公式ページが出にくい | ハブ（一覧ページ）から財団名を集め、公式ページを直接確認する |
| 応募資格の判断を LLM が行う | 自信過剰に誤る | 応募資格・募集中かどうかはコードで判定する |
| 正解1つの質問で評価 | 漏れは評価されない | 再現率で評価する |

## 出典
- Perplexity Research「Architecting and Evaluating an AI-First Search API」 https://research.perplexity.ai/articles/architecting-and-evaluating-an-ai-first-search-api （本文は403。下の2つで内容を確認）
- Vespa「Perplexity builds AI Search at scale on Vespa.ai」（2025-04-15） https://blog.vespa.ai/perplexity-builds-ai-search-at-scale-on-vespa-ai/
- 「How Perplexity Built Their Search Engine」 https://theaiengineer.substack.com/p/how-perplexity-built-their-search
- search_evals https://github.com/liquid4all/search_evals
- Narayanan Venkit et al. 2024 https://arxiv.org/html/2410.22349
- Tow Center / CJR 2025 https://www.cjr.org/tow_center/we-compared-eight-ai-search-engines-theyre-all-bad-at-citing-news.php
- Chen et al. 2025 https://arxiv.org/html/2509.08919v1
- Futurism（GPTZero の調査） https://futurism.com/the-byte/perplexity-citing-ai-generated-spam
- ITreview https://www.itreview.jp/products/perplexity/reviews/233555
