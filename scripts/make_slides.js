const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const path = require("path");
const SKILL = "C:/Users/shohe/AppData/Roaming/Claude/local-agent-mode-sessions/skills-plugin/3afe219c-dd8f-427b-98d0-e6ab9e3cc6ae/25bc1336-dab8-4da2-8831-49a002a7ad08/skills/pptx";
const { applyTheme } = require(SKILL + "/scripts/apply_theme.js");

const REPO = process.env.REPO;
const OUT = path.join(REPO, "docs/submission/presentation.pptx");
const IMG = (n) => path.join(REPO, "docs/submission", n);

// ---- テーマ（画面・図と同じ Material 3 の紫を主役に） ----
const THEME = {
  name: "ScholarshipAgent",
  headFontFace: "Yu Gothic",
  bodyFontFace: "Yu Gothic",
  colors: {
    dk1: "1D1B20", lt1: "FFFFFF", dk2: "21005D", lt2: "F3EDF7",
    accent1: "6750A4", accent2: "1A73E8", accent3: "C77700",
    accent4: "2E7D32", accent5: "B3261E", accent6: "79747E",
    hlink: "1A73E8", folHlink: "6750A4",
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "奨学金エージェント 発表スライド";
pres.author = "Shohei Fujieda";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ---- レイアウト ----
pres.defineSlideMaster({
  title: "DARK",
  background: { color: "21005D" },
  objects: [],
  slideNumber: { x: 12.2, y: 7.0, w: 0.8, h: 0.3, fontSize: 10, color: "CAC4D0", align: "right" },
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: "FFFFFF" },
  objects: [
    { text: { text: "奨学金エージェント", options: { x: 0.6, y: 7.0, w: 4, h: 0.3, fontSize: 10, color: C.accent6, margin: 0 } } },
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.4, w: 12.1, h: 0.95, fontSize: 34, bold: true, color: C.text2, valign: "middle", align: "left", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.8, h: 0.3, fontSize: 10, color: C.accent6, align: "right" },
});

async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

function card(slide, x, y, w, h, name, fill = C.background2) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.15, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: name });
}
async function iconCircle(slide, Comp, x, y, d, circleColor, name) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: circleColor }, line: { color: circleColor, width: 0 }, objectName: name + " 円" });
  const p = d * 0.26;
  slide.addImage({ data: await icon(Comp, "FFFFFF"), x: x + p, y: y + p, w: d - 2 * p, h: d - 2 * p, objectName: name });
}
const T = (slide, text, o) => slide.addText(text, { isTextBox: true, margin: 0, fontFace: THEME.bodyFontFace, ...o });

(async () => {
  const notes = (s, timing, body) => s.addNotes(`【${timing}】\n${body}`);

  // 1. タイトル（暗）
  {
    const s = pres.addSlide({ masterName: "DARK" });
    T(s, "第5回 Agentic AI Hackathon with Google Cloud", { x: 0.8, y: 1.2, w: 11.5, h: 0.4, fontSize: 16, color: "CADCFC" });
    T(s, "奨学金エージェント", { x: 0.8, y: 2.0, w: 11.5, h: 1.3, fontSize: 60, bold: true, color: C.background1 });
    T(s, "応募できる奨学金・助成金を、探して「確かめて」届ける", { x: 0.8, y: 3.45, w: 11.5, h: 0.7, fontSize: 28, color: "EADDFF" });
    const chips = ["高校生〜社会人", "学業・留学・研究・プロジェクト", "公式ページで確認"];
    let cx = 0.8;
    chips.forEach((c, i) => {
      const w = 0.3 * c.length + 0.7;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: cx, y: 4.7, w, h: 0.55, rectRadius: 0.27, fill: { color: "381E72" }, line: { color: "6750A4", width: 1 }, objectName: `チップ${i + 1}` });
      T(s, c, { x: cx, y: 4.7, w, h: 0.55, fontSize: 16, color: "EADDFF", align: "center", valign: "middle" });
      cx += w + 0.25;
    });
    notes(s, "0:00〜0:05（約5秒）", "奨学金エージェントです。応募できる奨学金を、探して、確かめて届けます。");
  }

  // 2. 課題
  {
    const s = pres.addSlide({ masterName: "CONTENT" });
    s.addText("生成AIに「全部教えて」と聞くと、募集終了が混ざる", { placeholder: "title" });
    card(s, 0.6, 1.6, 5.6, 2.35, "数字カード1");
    T(s, "12 / 34件", { x: 0.9, y: 1.75, w: 5.0, h: 1.2, fontSize: 60, bold: true, color: C.accent5, valign: "middle" });
    T(s, "素のAIが挙げた回答のうち、公式ページで見ると募集終了だったもの", { x: 0.9, y: 3.0, w: 5.0, h: 0.8, fontSize: 16, color: C.text1 });
    card(s, 0.6, 4.2, 5.6, 2.35, "数字カード2");
    T(s, "約半数", { x: 0.9, y: 4.35, w: 5.0, h: 1.2, fontSize: 60, bold: true, color: C.accent1, valign: "middle" });
    T(s, "10月時点で、すでに募集終了だった奨学金（29件中14件を公式要項で照合）", { x: 0.9, y: 5.6, w: 5.0, h: 0.8, fontSize: 16, color: C.text1 });
    const gaps = [
      [fa.FaListUl, "上位数件しか読まない", "漏れる"],
      [fa.FaCalendarTimes, "古い年度・募集終了を混ぜる", "間に合わない"],
      [fa.FaUserSlash, "自分が対象外の条件を見落とす", "学年・地域・卒業後・使途"],
      [fa.FaQuestion, "「全部」と言えない", "どこまで探したか分からない"],
    ];
    for (let i = 0; i < gaps.length; i++) {
      const y = 1.6 + i * 1.25;
      await iconCircle(s, gaps[i][0], 6.8, y + 0.1, 0.8, C.accent1, `穴${i + 1}アイコン`);
      T(s, gaps[i][1], { x: 7.8, y: y, w: 5.0, h: 0.6, fontSize: 22, bold: true, color: C.text1, valign: "middle" });
      T(s, gaps[i][2], { x: 7.8, y: y + 0.6, w: 5.0, h: 0.45, fontSize: 16, color: C.accent6 });
    }
    notes(s, "0:05〜0:20（約15秒）", "奨学金は、高校生から社会人まで、目的もさまざまです。でも情報は散らばっていて、生成AIに聞くと、募集終了のものが混ざります。実測では、素のAIの回答34件のうち12件、約3分の1が募集終了でした。");
  }

  // 3. 解決
  {
    const s = pres.addSlide({ masterName: "CONTENT" });
    s.addText("探すのは AI、判定は「公式ページを読んだ」コード", { placeholder: "title" });
    const cols = [
      [fa.FaSearch, C.accent2, "確かめる", ["Google 検索で候補を集める", "公式ページを読み、条件を引用つきで抜く", "引用が原文にあるか、コードで照合"]],
      [fa.FaLayerGroup, C.accent1, "隠さず分ける", ["応募できる／要確認", "目的が違う／未確認／募集終了", "確認できない条件は「合っている」と言わない"]],
      [fa.FaShieldAlt, C.accent3, "AI の操作を管理する", ["実行前の検査、実行後の記録", "他の人に影響する操作は、本人の許可まで停止", "AI は許可の操作を持たない"]],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.6 + i * 4.1;
      card(s, x, 1.65, 3.9, 4.9, `カード${i + 1}`);
      await iconCircle(s, cols[i][0], x + 0.35, 1.95, 0.95, cols[i][1], `アイコン${i + 1}`);
      T(s, cols[i][2], { x: x + 0.35, y: 3.15, w: 3.3, h: 0.6, fontSize: 24, bold: true, color: C.text2 });
      s.addText(cols[i][3].map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < cols[i][3].length - 1 } })), {
        isTextBox: true, x: x + 0.3, y: 3.9, w: 3.45, h: 2.5, fontSize: 16, color: C.text1, margin: 0, valign: "top", paraSpaceAfter: 8,
      });
    }
    notes(s, "0:20〜0:35（約15秒）", "そこで、探すのはAI、応募できるかの判定は、公式ページを読んでコードで行います。確認できないものは隠さず分け、AIの操作は、検査・人間の承認・監査ログで管理します。");
  }

  // 4/5. デモ動画スライド
  const videoSlide = async (title, points, timing, narration) => {
    const s = pres.addSlide({ masterName: "CONTENT" });
    s.addText(title, { placeholder: "title" });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 1.55, w: 8.6, h: 4.84, rectRadius: 0.12, fill: { color: "EFEAF3" }, line: { color: "CAC4D0", width: 1.5, dashType: "dash" }, objectName: "動画の枠（この上に動画を挿入）" });
    s.addImage({ data: await icon(fa.FaPlayCircle, "6750A4"), x: 4.45, y: 3.2, w: 0.9, h: 0.9, objectName: "再生アイコン" });
    T(s, "ここにデモ動画を挿入", { x: 0.6, y: 4.2, w: 8.6, h: 0.5, fontSize: 20, bold: true, color: C.accent1, align: "center" });
    T(s, "［挿入］→［ビデオ］→［このコンピューター上のビデオ］。この枠に重ねて、サイズを合わせる（枠は削除してよい）", { x: 1.2, y: 4.75, w: 7.4, h: 0.7, fontSize: 12, color: C.accent6, align: "center" });
    card(s, 9.5, 1.55, 3.23, 4.84, "ポイントの枠");
    T(s, "見てほしいところ", { x: 9.8, y: 1.8, w: 2.7, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
    s.addText(points.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < points.length - 1 } })), {
      isTextBox: true, x: 9.8, y: 2.4, w: 2.7, h: 3.8, fontSize: 14, color: C.text1, margin: 0, valign: "top", paraSpaceAfter: 8,
    });
    notes(s, timing, narration + "\n\n（動画を挿入したら、［再生］タブで「自動」または「クリック時」を選ぶ。撮影時は、動画の音声を使うか、ナレーションをこの原稿で読む）");
    return s;
  };
  await videoSlide(
    "デモ①  条件を入れると、確かめた結果が出る",
    ["立場・地域・目的を入力", "検索中の経過表示", "応募できる／要確認／未確認／募集終了", "「確認すること」の表示", "立場・目的を替えて再検索", "保存とCSV"],
    "0:35〜1:30（約55秒）",
    "筑波大学の理工学群、大学3年、目的は学業・生活費。入力して検索します。進み具合が出ます。結果は、応募できる2件、要確認10件、未確認4件、募集終了7件。要確認には、何を確認するかが付きます。入力を、卒業後の社会人・目的は研究に替えると、出る制度が変わり、目的が違うものは別に分かれます。気になるものは保存して、CSVで持ち帰れます。"
  );
  await videoSlide(
    "デモ②  本人が許可するまで、動かない",
    ["共有リストへの追加を依頼", "承認待ちで止まる", "確認ダイアログ（押せるのは本人だけ）", "許可すると、1回だけ実行", "操作の記録（誰が・いつ・何を・なぜ）"],
    "1:30〜2:10（約40秒）",
    "他の人にも見える共有リストへの追加は、高リスクの操作です。依頼すると承認待ちで止まり、画面に確認ダイアログが出ます。許可できるのは本人だけで、AIは許可できません。許可すると1回だけ実行され、操作の記録に、誰が、いつ、何を、なぜ、が残ります。"
  );

  // 6. しくみ
  {
    const s = pres.addSlide({ masterName: "CONTENT" });
    s.addText("しくみ: 1つのエージェントと、コードの安全装置", { placeholder: "title" });
    s.addImage({ path: IMG("architecture.png"), x: 0.6, y: 1.5, w: 8.83, h: 5.3, objectName: "図1 全体像" });
    const pts = [
      [fa.FaRobot, C.accent2, "AI は読み取りだけ", "エージェントは1つ。ツールは3つ"],
      [fa.FaCode, C.accent1, "判定・安全はコード", "検査・承認・監査ログ・上限"],
      [fa.FaKey, C.accent3, "最小権限", "専用アカウント・最大1インスタンス"],
    ];
    for (let i = 0; i < 3; i++) {
      const y = 1.6 + i * 1.75;
      await iconCircle(s, pts[i][0], 10.0, y, 0.7, pts[i][1], `要点アイコン${i + 1}`);
      T(s, pts[i][2], { x: 10.85, y: y - 0.05, w: 1.9, h: 0.8, fontSize: 15, bold: true, color: C.text2, valign: "middle" });
      T(s, pts[i][3], { x: 10.0, y: y + 0.8, w: 2.75, h: 0.7, fontSize: 12, color: C.accent6, valign: "top" });
    }
    notes(s, "2:10〜2:30（約20秒）", "構成は、Cloud Run上の単一のADKエージェントと、3つのツール。探し方と判定、安全装置はコードが持ち、AIは読み取りに使います。データはFirestore、権限は専用のサービスアカウントで最小限です。");
  }

  // 7. 評価
  {
    const s = pres.addSlide({ masterName: "CONTENT" });
    s.addText("評価: 数字と、正直な限界", { placeholder: "title" });
    const stats = [
      ["176", "自動テスト（全件合格）"],
      ["7", "adk eval のケース（全件合格）"],
      ["12 / 34", "素のAIの回答のうち、募集終了"],
      ["17 対 15", "見つけた「使える」件数（本エージェント 対 素のAI）"],
    ];
    stats.forEach((st, i) => {
      const x = 0.6 + i * 3.08;
      card(s, x, 1.6, 2.9, 2.4, `評価カード${i + 1}`);
      T(s, st[0], { x: x + 0.2, y: 1.75, w: 2.5, h: 1.1, fontSize: 40, bold: true, color: C.accent1, valign: "middle" });
      T(s, st[1], { x: x + 0.2, y: 2.9, w: 2.5, h: 0.95, fontSize: 14, color: C.text1, valign: "top" });
    });
    T(s, "正直な限界", { x: 0.6, y: 4.35, w: 6, h: 0.5, fontSize: 22, bold: true, color: C.text2 });
    const lim = [
      "見つかる件数は同程度。差は「確かさ」（募集終了を分ける、引用で確認した締切）",
      "比較は4つの立場で各1回。小さな実験で、「大幅に多く見つける」とは言わない",
      "最初の検索語（年度の固定）は、この実験で劣る原因と分かり、直した",
    ];
    s.addText(lim.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < lim.length - 1 } })), {
      isTextBox: true, x: 0.6, y: 4.95, w: 12.1, h: 1.8, fontSize: 18, color: C.text1, margin: 0, valign: "top", paraSpaceAfter: 8,
    });
    notes(s, "2:30〜2:50（約20秒）", "評価です。自動テスト176件、adk eval 7ケースが合格。素のAIとの比較では、見つかる件数は同程度で、差は確かさでした。小さな実験なので、大幅に多く見つける、とは言いません。");
  }

  // 8. まとめ（暗）
  {
    const s = pres.addSlide({ masterName: "DARK" });
    T(s, "応募できる奨学金を、\n間に合ううちに。", { x: 0.8, y: 1.3, w: 11.5, h: 2.2, fontSize: 52, bold: true, color: C.background1, valign: "top" });
    T(s, "これからの拡張", { x: 0.8, y: 3.9, w: 6, h: 0.5, fontSize: 20, bold: true, color: "CADCFC" });
    s.addText([
      { text: "一覧ページの展開（実験では有効。本番への組み込みは今後）", options: { bullet: true, breakLine: true } },
      { text: "検索語の自動選択と、再現率の数値化", options: { bullet: true, breakLine: true } },
      { text: "他大学の公開一覧への対応", options: { bullet: true } },
    ], { isTextBox: true, x: 0.8, y: 4.5, w: 11.5, h: 1.6, fontSize: 18, color: "EADDFF", margin: 0, valign: "top", paraSpaceAfter: 6 });
    T(s, "GitHub: ShoheiFujieda/agentic-ai-hackathon-2026", { x: 0.8, y: 6.5, w: 11, h: 0.4, fontSize: 14, color: "CAC4D0" });
    notes(s, "2:50〜3:00（約10秒）", "応募できる奨学金を、間に合ううちに。拡張として、一覧ページの展開と、検索語の自動選択を進めます。ありがとうございました。");
  }

  // 付録（質疑・予備）
  for (const [file, title, text] of [
    ["architecture_pipeline.png", "付録: 検索の流れ（探すのは AI、判定はコード）", "予備。質問が出たとき用。"],
    ["architecture_safety.png", "付録: 安全装置と人間の承認", "予備。質問が出たとき用。"],
  ]) {
    const s = pres.addSlide({ masterName: "CONTENT" });
    s.addText(title, { placeholder: "title" });
    s.addImage({ path: IMG(file), x: 1.9, y: 1.5, w: 9.4, h: file.includes("pipeline") ? 5.29 : 5.17, objectName: title });
    s.addNotes(text);
  }

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("written", OUT);
})();
