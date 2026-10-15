"""比較実験: 「普通のAI検索（1回の検索で出た奨学金名）」は、実際には応募できるのか。本エージェントと比べる。

同じ架空の利用者について、次の2つを測る。
  A. 普通のAI検索: Gemini＋Google検索に1回だけ聞き、出てきた奨学金・助成金の名前を受け取る（検証しない）
     → その各候補を、本エージェントの「公式ページで照合 → コードで判定」にかけ、実際の状態を数える
        （募集終了・対象外・公式ページを確認できない、などが何件混ざっていたか）
  B. 本エージェント: websearch.search（発見6通り→統合→公式ページで照合→判定）の結果

判定は同じコード（judge）を使うため、「普通のAI検索の答えのうち、応募できると言えるものがどれだけか」を測る実験であり、
正解データ（網羅した全体）との再現率を測るものではない。

使い方: EXP_DATE=2026-10-15 uv run python scripts/exp_baseline.py [プロフィール名 ...]
プロフィール名: college（筑波大学の大学生）, highschool（高校生）, abroad（留学志望の大学生）, graduate（卒業後の社会人）
結果: docs/experiments/<EXP_DATE>_baseline/result.json に保存する
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(".env")

from hackathon_agent.scholarship import websearch  # noqa: E402
from hackathon_agent.scholarship.judge import ELIGIBLE, NEEDS_CHECK, Profile  # noqa: E402

EXP_DATE = os.environ.get("EXP_DATE", date.today().isoformat())
TODAY = date.fromisoformat(EXP_DATE)
OUT_DIR = Path(f"docs/experiments/{EXP_DATE}_baseline")
MAX_BASELINE = 12  # 普通のAI検索の答えのうち、検証する件数の上限（費用の上限）
WORKERS = 6

PROFILES = {
    "college": {
        "label": "筑波大学・理工学群・大学3年（学業・生活費）",
        "who": "筑波大学（茨城県）の理工学群の大学3年生。出身高校は埼玉県、今は茨城県在住、保護者は埼玉県在住。奨学金は受けていない。目的は学業・生活費。",
        "university": "筑波大学",
        "field": "理工学群",
        "profile": Profile("大学", 3, ["理工", "工学", "理学", "理系"], "埼玉県", "茨城県", "茨城県", "埼玉県", []),
    },
    "highschool": {
        "label": "高校3年生（学業・生活費）",
        "who": "埼玉県の高校3年生。今は埼玉県在住、保護者も埼玉県在住。奨学金は受けていない。目的は学業・生活費（大学進学を含む）。",
        "university": "",
        "field": "",
        "profile": Profile("高校", 3, [], "埼玉県", "埼玉県", "埼玉県", "埼玉県", []),
    },
    "abroad": {
        "label": "東京大学・経済学部・大学3年（留学）",
        "who": "東京大学（東京都）の経済学部の大学3年生。出身高校は神奈川県、今は東京都在住、保護者は神奈川県在住。奨学金は受けていない。目的は留学。",
        "university": "東京大学",
        "field": "経済学部",
        "profile": Profile(
            "大学",
            3,
            ["経済", "経営", "商学", "文系"],
            "神奈川県",
            "東京都",
            "東京都",
            "神奈川県",
            [],
            purposes=["留学"],
        ),
    },
    "graduate": {
        "label": "卒業後1年の社会人（研究・プロジェクト・活動）",
        "who": "大学を卒業して1年の社会人。出身高校は愛知県、今は東京都在住、保護者は愛知県在住。奨学金は受けていない。目的は研究とプロジェクト・活動の支援金。",
        "university": "",
        "field": "",
        "profile": Profile(
            "大学",
            0,
            [],
            "愛知県",
            "東京都",
            "東京都",
            "愛知県",
            [],
            graduated=True,
            years_since_graduation=1,
            purposes=["研究", "プロジェクト・活動"],
        ),
    },
}

STATUSES = ("応募できる", "要確認", "募集終了", "対象外", "目的が違う", "未確認の候補")


def baseline_candidates(who: str) -> list[dict]:
    """普通のAI検索: 1回だけ聞いて、出てきた候補を受け取る。"""
    res = websearch._grounded(
        f"次の人が応募できる奨学金・助成金を、{TODAY.year}年度の募集を中心に検索して教えてください。\\n対象者: {who}"
        + websearch.DISCOVER_FORMAT
    )
    return websearch._items(res["text"])


def count(items: list[dict]) -> dict[str, int]:
    out = {s: 0 for s in STATUSES}
    for r in items:
        out[r["status"]] = out.get(r["status"], 0) + 1
    return out


def run(name: str) -> dict:
    spec = PROFILES[name]
    profile = spec["profile"]
    t0 = time.time()
    print(f"== {name}: {spec['label']}", flush=True)

    # A. 普通のAI検索 → 公式ページで照合
    cands = baseline_candidates(spec["who"])
    merged = websearch.merge([cands])
    chosen = list(merged.items())[:MAX_BASELINE]
    with ThreadPoolExecutor(WORKERS) as pool:
        checked = list(pool.map(lambda kv: websearch.check_candidate(kv[0], kv[1], profile, TODAY), chosen))
    a_counts = count(checked)
    a_valid = {websearch.core_name(r["organization"]) for r in checked if r["status"] in (ELIGIBLE, NEEDS_CHECK)}
    print(f"   A 普通のAI検索: 候補 {len(merged)} 件（検証 {len(chosen)} 件）→ {a_counts}", flush=True)

    # B. 本エージェント
    res = websearch.search(profile, spec["university"], spec["field"], TODAY)
    b_all = [*res["eligible"], *res["needs_check"], *res["unverified"], *res["closed"], *res["off_purpose"]]
    b_counts = {
        "応募できる": len(res["eligible"]),
        "要確認": len(res["needs_check"]),
        "募集終了": len(res["closed"]),
        "目的が違う": len(res["off_purpose"]),
        "未確認の候補": len(res["unverified"]),
        "対象外": res["ineligible_count"],
    }
    b_valid = {websearch.core_name(r["organization"]) for r in [*res["eligible"], *res["needs_check"]]}
    print(f"   B 本エージェント: {b_counts} / {res['stats']}", flush=True)

    only_b = b_valid - a_valid
    both = a_valid & b_valid
    return {
        "profile": spec["label"],
        "baseline": {
            "candidates": len(merged),
            "checked": len(chosen),
            "by_status": a_counts,
            "applicable_or_check": len(a_valid),
            "items": [
                {k: r.get(k) for k in ("name", "organization", "status", "deadline", "official_url", "reasons")}
                for r in checked
            ],
        },
        "agent": {
            "by_status": b_counts,
            "applicable_or_check": len(b_valid),
            "stats": res["stats"],
            "candidates_total": res["stats"].get("candidates"),
            "listed": len(b_all),
        },
        "overlap": {"both": len(both), "only_agent": len(only_b), "only_baseline": len(a_valid - b_valid)},
        "minutes": round((time.time() - t0) / 60, 1),
    }


def main() -> None:
    names = sys.argv[1:] or list(PROFILES)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = {"today": EXP_DATE, "profiles": {}}
    try:
        for n in names:
            out["profiles"][n] = run(n)
    finally:  # 途中で止まっても、そこまでの記録を残す
        (OUT_DIR / "result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                k: {"baseline": v["baseline"]["by_status"], "agent": v["agent"]["by_status"], "overlap": v["overlap"]}
                for k, v in out["profiles"].items()
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
