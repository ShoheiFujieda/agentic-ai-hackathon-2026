"""安い絞り込み: 一覧ページで分かる名前だけで、明らかに対象外の候補を除く（AIは使わない）。

迷うものは残す。見落としを防ぐのが目的なので、ここで除くのは確実に対象外と言えるものだけ。
"""

import re

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県",
    "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]  # fmt: skip
INTERNATIONAL = re.compile(r"留学生|外国人|International|Foreign", re.IGNORECASE)
# 団体名に大学名が入っているもの（「大学生奨学財団」のような「大学生」は除く）
UNIVERSITY_ORG = re.compile(r"大学(?!生)")


def prefilter(item: dict, my_prefectures: set[str], my_university: str) -> str | None:
    """除く理由を返す。残すときは None。"""
    name = f"{item.get('organization') or ''} {item.get('scholarship') or ''}"
    if INTERNATIONAL.search(name):
        return "留学生向け"
    others = [p for p in PREFECTURES if p in name and p not in my_prefectures]
    if others and not any(p in name for p in my_prefectures):
        return f"他の地域（{others[0]}）の制度"
    org = item.get("organization") or ""
    if UNIVERSITY_ORG.search(org) and my_university not in org:
        return "他大学の学内制度"
    return None
