"""Claude Code の Stop フック: 作業を終える前に pytest を実行し、失敗していれば終了を止める。

- 未コミットの .py ファイルの変更がなければ実行しない
- 前回成功したときから .py ファイルの内容が変わっていなければ実行しない（応答のたびに約40秒かかるのを避ける）
- 一度止めた後も、毎回テストし直す（Claude Code は連続8回止めると自動で終了を許すので、無限には続かない）
- テストは実際の Firestore に少量書き込む
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAMP = ROOT / ".claude" / ".last_pytest_ok"
TIMEOUT_SEC = 300


def _changed_py_files() -> list[str]:
    out = subprocess.run(
        ["git", "-c", "core.quotepath=off", "status", "--porcelain", "-z", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return parse_porcelain_z(out)


def parse_porcelain_z(out: str) -> list[str]:
    # -z 形式: 「XY パス\0」。名前の変更は「R  新しいパス\0古いパス\0」なので、古いパスを読み飛ばす
    entries = out.split("\0")
    files: list[str] = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        if len(entry) > 3:
            files.append(entry[3:])
            if entry[0] in "RC":
                i += 1
        i += 1
    return sorted(f for f in files if f.endswith(".py"))


def _fingerprint(files: list[str]) -> str:
    h = hashlib.sha256()
    for f in files:
        p = ROOT / f
        h.update(f.encode())
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()


def _block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))


def main() -> None:
    json.load(sys.stdin)
    files = _changed_py_files()
    if not files:
        return
    fingerprint = _fingerprint(files)
    if STAMP.exists() and STAMP.read_text(encoding="utf-8") == fingerprint:
        return

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        _block(f"pytest が {TIMEOUT_SEC} 秒以内に終わりませんでした。止まっているテストがないか確認してください。")
        return
    if result.returncode == 0:
        STAMP.write_text(fingerprint, encoding="utf-8")
        return
    tail = "\n".join((result.stdout + result.stderr).strip().splitlines()[-30:])
    _block(f"pytest が失敗しています。直してから終えてください:\n{tail}")


if __name__ == "__main__":
    main()
