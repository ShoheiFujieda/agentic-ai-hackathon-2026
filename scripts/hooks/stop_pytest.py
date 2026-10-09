"""Claude Code の Stop フック: 作業を終える前に pytest を実行し、失敗していれば終了を止める。

- 未コミットの .py ファイルの変更がなければ実行しない
- 前回成功したときから .py ファイルの内容が変わっていなければ実行しない（応答のたびに約40秒かかるのを避ける）
- テストは実際の Firestore に少量書き込む
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAMP = ROOT / ".claude" / ".last_pytest_ok"


def _changed_py_files() -> list[str]:
    out = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    files = [line[3:].strip().strip('"') for line in out.splitlines()]
    return sorted(f for f in files if f.endswith(".py"))


def _fingerprint(files: list[str]) -> str:
    h = hashlib.sha256()
    for f in files:
        p = ROOT / f
        h.update(f.encode())
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()


def main() -> None:
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return  # すでに一度止めた後なので、繰り返し止めない

    files = _changed_py_files()
    if not files:
        return
    fingerprint = _fingerprint(files)
    if STAMP.exists() and STAMP.read_text(encoding="utf-8") == fingerprint:
        return

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    if result.returncode == 0:
        STAMP.write_text(fingerprint, encoding="utf-8")
        return
    tail = "\n".join((result.stdout + result.stderr).strip().splitlines()[-30:])
    print(json.dumps({"decision": "block", "reason": f"pytest が失敗しています。直してから終えてください:\n{tail}"}))


if __name__ == "__main__":
    main()
