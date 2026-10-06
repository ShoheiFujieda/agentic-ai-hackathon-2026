"""承認者用のCLI（技術検証用。後で画面に置き換える）。

使い方:
  uv run python scripts/approve.py list
  uv run python scripts/approve.py approve <承認ID> --by <承認者名>
  uv run python scripts/approve.py reject  <承認ID> --by <承認者名> --comment "理由"
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from hackathon_agent.governance import approvals, audit  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("approve", "reject"):
        s = sub.add_parser(name)
        s.add_argument("approval_id")
        s.add_argument("--by", required=True, help="承認者名")
        s.add_argument("--comment", default="")
    a = p.parse_args()

    if a.cmd == "list":
        for ap in approvals.list_pending():
            print(f"{ap['id']}  依頼者={ap['requested_by']}  {ap['tool']} {ap['args']}")
        return 0

    approve = a.cmd == "approve"
    ok, msg = approvals.decide(approval_id=a.approval_id, approver=a.by, approve=approve, comment=a.comment)
    audit.record(
        user_id=a.by,
        session_id="-",
        tool="(approval)",
        args={"approval_id": a.approval_id, "comment": a.comment},
        decision=("approved" if approve else "rejected") if ok else "blocked",
        reason=msg,
    )
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
