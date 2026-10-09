# 網羅的なWeb検索の先行研究と、このプロジェクトへの取り入れ方（2026-10-09 調査）

## 1. 先行研究（分野別）

### A. AIエージェントの「広く集める」検索（2025〜2026）
| 研究 | 要点 |
|---|---|
| WideSearch（ByteDance、arXiv 2508.07999、ICLR 2026） | 大量の項目を集める課題。最良のエージェントでも完全正解は5%。弱点は精度ではなく再現率。失敗の原因は、検索語の分解が不完全、結果が少ないときに戦略を変えない、作り話で埋める |
| DeepSearchQA（Google DeepMind、arXiv 2601.20975、2026-01） | 900問。最良の Gemini Deep Research でも完全正解は66%。**目立たない項目（ロングテール）を取りこぼす**失敗と、自信のない項目を大量に入れて再現率を水増しする失敗が両方ある。改善には「体系的な探索」「重複の統合」「**『見つからない』と『存在しない』を区別する止め方**」が必要。安いモデルに替えると性能が階段状に落ちる |
| Diagnosing Search Behavior…（Liu ほか、arXiv 2608.01913、2026-08） | 長い探索では、同じような検索語の繰り返しと早すぎる打ち切りが多い。検索履歴の記録と、止める条件の明確化を推奨 |
| QAMPARI（ACL 2023） | 答えが複数ある質問のベンチマーク。最良でも F1 は32.8。答えが多くの段落に散らばっていると検索で拾いきれない |

### B. 「条件に合うものを全部見つける」商用サービス
| サービス | 方式 |
|---|---|
| Exa Websets | 候補を検索 → **候補1件ずつ条件に合うか検証** → 合格したものだけ結果にする → 追加情報を取得。指定件数に達するか、候補が尽きるまで探す |
| Parallel FindAll（2025） | 候補の生成 → 複数のページをまたいで条件を照合 → 情報を追加。出典・判断理由・確信度を付ける。自社ベンチマーク（40問）の再現率：FindAll Pro 61%、OpenAI Deep Research 19.5%、Anthropic Deep Research 15.3%、Exa 19.2%。**正解データは全サービスの正解を合わせて作る**（プール方式） |

### C. 情報検索の古典研究
| 研究 | 要点 |
|---|---|
| フォーカスドクローラー（Chakrabarti ほか 1999、Vieira ほか 2016「Finding seeds…」） | 一覧ページ（ハブ）から始める方が効率がよい。検索結果をそのまま出発点にするより、検索結果を指しているページ（ハブ）を探す方がよい |
| SEAL（Wang & Cohen 2007、CMU） | **既知の項目（種）を2〜3個含むページは「一覧ページ」である可能性が高い**。そこから同じ形式で並んでいる他の項目を抜き出して、集合を広げる（集合拡張） |
| 隠れたWebの収集（Ntoulas・Zerfos・Cho 2005） | 検索フォームの奥にあるデータベースを、検索語を送って集める。**次の検索語は、それまでに集めた結果から「新しく見つかる件数が最も多そうなもの」を貪欲に選ぶ**。適当に選ぶより少ない検索回数で多く集まる |
| 技術支援レビュー（TAR）の止め方 | ニー法（Cormack & Grossman 2016）：見つかった件数の伸びが鈍る「膝」で止める。Chao 推定量（2024）：独立した複数の探索の重なりから残りの件数を推定する。95%前後の再現率で、作業量を約半分にした |

## 2. 取り入れ方（検索方式の改訂案）

| 段階 | やること | 参考にした研究 |
|---|---|---|
| ① 種集め | プロフィールに合う検索で、最初の奨学金を数件見つける | — |
| ② 一覧ページの発見 | **見つかった奨学金名を2〜3個組み合わせて検索**し、それらがまとめて載っているページ（大学の募集一覧、自治体の一覧など）を探す。そこから全項目を抜き出す | SEAL、フォーカスドクローラー |
| ③ 次の検索語の選択 | 実行した検索語をすべて記録する。集めた奨学金に出てくる言葉（「〇〇県出身」「工学系女子」など）のうち、まだ検索していないもので、新しく見つかる件数が多そうなものから検索する | Ntoulas 2005、Diagnosing（繰り返し防止） |
| ④ 重複の統合 | 同じ奨学金の別名や別年度をまとめる | DeepSearchQA |
| ⑤ 候補ごとの照合 | 候補を1件ずつ公式ページで確認し、条件の項目ごとにコードで判定する。出典と理由を付ける | Exa Websets、Parallel FindAll |
| ⑥ 止め方 | 見つかった件数の伸びの「膝」と、Chao 推定量による残りの件数の推定の両方で判断する | ニー法、Chao 推定量 |
| ⑦ 出し方 | 「応募できる（確認済み）」「条件の確認が必要」「見つけたが公式情報を確認できない」を分けて表示する。確認できないものを「応募できる」に混ぜない | DeepSearchQA（水増し・「見つからない」と「存在しない」の区別） |

- 検索の進め方はコードで決め、AIは文章の読み取りと検索語の候補出しに使う。DeepSearchQA によると、安いモデルは計画を立てる力が大きく落ちる。Flash 系を使うこのプロジェクトでは、計画をコードに持たせる方が安全
- 評価は Parallel と同じプール方式で行う（全方式で見つかったものを公式ページで確認し、正解データにする）

## 3. 独自性として言えること（調べた範囲で）
- 集合拡張（SEAL）、検索語の貪欲な選択（Ntoulas）、捕獲・再捕獲法による止め方（TAR）を、LLMエージェントの網羅的な検索に組み合わせ、奨学金という具体的な分野に当てはめた例は、今回調べた範囲では見当たらなかった（「世界初」とは言えない）
- 商用サービス（Exa、Parallel）は企業や人物を探すもので、奨学金特有の条件（学年、地域条件の種類、募集期間、併給）は扱わない

## 出典
- WideSearch https://arxiv.org/html/2508.07999v1
- DeepSearchQA https://arxiv.org/html/2601.20975v1
- Diagnosing Search Behavior and Failure Modes in Long-Horizon Search Agents https://arxiv.org/pdf/2608.01913
- QAMPARI https://arxiv.org/pdf/2205.12665
- Exa Websets https://exa.ai/docs/websets/api/how-it-works
- Parallel FindAll https://www.parallel.ai/blog/introducing-findall-api
- Finding seeds to bootstrap focused crawlers https://research.ibm.com/publications/finding-seeds-to-bootstrap-focused-crawlers
- SEAL（Wang & Cohen） https://www.lti.cs.cmu.edu/people/alumni/alumni-thesis/wang-richard-thesis.pdf
- Ntoulas, Zerfos, Cho 2005 https://cgi.di.uoa.gr/~antoulas/publications.html
- Heuristic Stopping Rules for TAR https://arxiv.org/pdf/2106.09871
- Chao's Estimator as a Stopping Criterion https://arxiv.org/pdf/2404.01176
