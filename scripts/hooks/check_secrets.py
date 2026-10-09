"""git の pre-commit フック: コミットしようとしている変更に秘密情報が含まれていないか検査する。

見つかったらコミットを止める（終了コード1）。誤検知のときは、その行に `secret-scan: allow` と書く。
"""

import re
import subprocess
import sys

# ファイル名だけでコミットを止めるもの
BLOCKED_FILES = [
    re.compile(r"(^|/)\.env(\..+)?$"),
    re.compile(r"\.(pem|p12|pfx|key)$"),
    re.compile(r"(^|/)(credentials|service[-_]?account).*\.json$", re.IGNORECASE),
]
# 追加された行の中身で止めるもの
PATTERNS = {
    "Google API キー": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "秘密鍵": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "サービスアカウントの鍵": re.compile(r'"private_key(_id)?"\s*:'),
    "Google OAuth クライアントシークレット": re.compile(r"GOCSPX-[0-9A-Za-z_\-]{20,}"),
    "GitHub トークン": re.compile(r"gh[pousr]_[0-9A-Za-z]{36,}"),
    "AWS アクセスキー": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Slack トークン": re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    "Anthropic / OpenAI の API キー": re.compile(r"sk-(ant-)?[0-9A-Za-z_\-]{20,}"),
}
ALLOW = "secret-scan: allow"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def main() -> int:
    sys.stderr.reconfigure(encoding="utf-8")  # Windows でも git の画面で文字化けしないように
    problems: list[str] = []
    for name in _git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines():
        if any(p.search(name) for p in BLOCKED_FILES):
            problems.append(f"{name}: 秘密情報を含む可能性が高いファイルです")

    current = ""
    for line in _git("diff", "--cached", "-U0", "--diff-filter=ACMR").splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++") and ALLOW not in line:
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    problems.append(f"{current}: {label}の可能性があります")

    if problems:
        print("秘密情報の可能性があるため、コミットを止めました:", file=sys.stderr)
        for p in sorted(set(problems)):
            print(f"  - {p}", file=sys.stderr)
        print(f"誤検知なら、その行に `{ALLOW}` と書いてください。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
