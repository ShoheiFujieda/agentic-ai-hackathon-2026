"""開発用フック（scripts/hooks/）のテスト。10/9 のコードレビューで指摘された不具合が再発しないことを確かめる。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "hooks"))

import check_secrets  # noqa: E402
import stop_pytest  # noqa: E402

FAKE_KEY = "AIza" + "Sy" + "F" * 33  # 本物ではない形だけのキー（ファイルに直接書かないよう分割）


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _stage(repo: Path, rel: str, content: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", rel], cwd=repo, check=True)


def test_秘密情報がなければ通る(repo):
    _stage(repo, "a.py", "x = 1\n")
    assert check_secrets.find_problems() == []


def test_APIキーを止める(repo):
    _stage(repo, "a.py", f'KEY = "{FAKE_KEY}"\n')
    assert any("Google API キー" in p for p in check_secrets.find_problems())


def test_プラス記号で始まる行も検査する(repo):
    _stage(repo, "a.txt", f"++{FAKE_KEY}\n")
    assert any("a.txt" in p for p in check_secrets.find_problems())


def test_日本語フォルダのenvも止める(repo):
    _stage(repo, "docs/資料/.env", "X=1\n")
    assert any("docs/資料/.env" in p for p in check_secrets.find_problems())


def test_envのひな形は通す(repo):
    _stage(repo, ".env.example", "GOOGLE_CLOUD_PROJECT=\n")
    assert check_secrets.find_problems() == []


def test_許可の印がある行は通す(repo):
    _stage(repo, "a.py", f'KEY = "{FAKE_KEY}"  # secret-scan: allow\n')
    assert check_secrets.find_problems() == []


def test_単語の途中のskは誤検知しない():
    pattern = check_secrets.PATTERNS["Anthropic / OpenAI の API キー"]
    assert not pattern.search("risk-assessment-for-scholarship-deadline")
    assert pattern.search("sk-" + "a" * 24)


def test_gitが失敗したら止める(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # git リポジトリではない場所
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    with pytest.raises(check_secrets.GitError):
        check_secrets.find_problems()


def test_名前の変更は新しいパスだけを数える():
    out = "R  b.py\0a.py\0 M c.py\0?? d.txt\0"
    assert stop_pytest.parse_porcelain_z(out) == ["b.py", "c.py"]


def test_precommitに実行権限がある():
    mode = subprocess.run(
        ["git", "ls-files", "-s", ".githooks/pre-commit"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()[0]
    assert mode == "100755"


@pytest.mark.skipif(os.name != "nt", reason="Windows の文字コードの問題の確認")
def test_日本語のファイル名でもgitの出力を読める(repo):
    _stage(repo, "資料.py", "x = 1\n")
    assert check_secrets.find_problems() == []
