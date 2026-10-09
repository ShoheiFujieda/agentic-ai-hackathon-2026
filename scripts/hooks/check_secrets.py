"""git の pre-commit フック: コミットしようとしている変更に秘密情報が含まれていないか検査する。

見つかったらコミットを止める（終了コード1）。git が失敗して検査できなかったときも止める。
誤検知のときは、その行に `secret-scan: allow` と書く。標準ライブラリだけで動く。
"""

import re
import subprocess
import sys

# ファイル名だけでコミットを止めるもの（.env.example などのひな形は除く）
BLOCKED_FILES = [
    re.compile(r"(^|/)\.env(?!\.(example|sample|template)$)(\..+)?$"),
    re.compile(r"\.(pem|p12|pfx|key)$"),
    re.compile(r"(^|/)(credentials|service[-_]?account)[^/]*\.json$", re.IGNORECASE),
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
    "Anthropic / OpenAI の API キー": re.compile(r"(?<![0-9A-Za-z])sk-(ant-)?[0-9A-Za-z_\-]{20,}"),
}
ALLOW = "secret-scan: allow"


class GitError(Exception):
    pass


def _git(*args: str) -> str:
    # quotepath=off: 日本語などのファイル名を "\346..." のように引用符で囲ませない
    result = subprocess.run(
        ["git", "-c", "core.quotepath=off", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise GitError(result.stderr.strip())
    return result.stdout


def find_problems() -> list[str]:
    problems: list[str] = []
    names = _git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").split("\0")
    for name in filter(None, names):
        if any(p.search(name) for p in BLOCKED_FILES):
            problems.append(f"{name}: 秘密情報を含む可能性が高いファイルです")

    current = ""
    previous = ""
    for line in _git("diff", "--cached", "-U0", "--no-color", "--diff-filter=ACMR").splitlines():
        # ファイルの見出しは必ず「--- 」の直後の「+++ 」。それ以外の「+」で始まる行は追加された中身
        if previous.startswith("--- ") and line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
        elif line.startswith("+") and ALLOW not in line:
            for label, pattern in PATTERNS.items():
                if pattern.search(line[1:]):
                    problems.append(f"{current}: {label}の可能性があります")
        previous = line
    return sorted(set(problems))


def main() -> int:
    sys.stderr.reconfigure(encoding="utf-8")  # Windows でも git の画面で文字化けしないように
    try:
        problems = find_problems()
    except (GitError, OSError) as e:
        print(f"秘密情報の検査ができなかったため、コミットを止めました: {e}", file=sys.stderr)
        return 1

    if problems:
        print("秘密情報の可能性があるため、コミットを止めました:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(f"誤検知なら、その行に `{ALLOW}` と書いてください。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
