"""Claude Code の PostToolUse フック: 編集された .py ファイルに ruff（自動修正と整形）をかける。

直せない指摘が残ったときだけ、内容を Claude に返す（成功時は何も出さない）。
"""

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    payload = json.load(sys.stdin)
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    path = Path(file_path)
    if path.suffix != ".py" or not path.exists():
        return

    ruff = [sys.executable, "-m", "ruff"]
    subprocess.run([*ruff, "check", "--fix", "--quiet", str(path)], capture_output=True)
    subprocess.run([*ruff, "format", "--quiet", str(path)], capture_output=True)
    result = subprocess.run(
        [*ruff, "check", "--output-format", "concise", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print(
            json.dumps(
                {"decision": "block", "reason": f"ruff の指摘が残っています。直してください:\n{result.stdout.strip()}"}
            )
        )


if __name__ == "__main__":
    main()
