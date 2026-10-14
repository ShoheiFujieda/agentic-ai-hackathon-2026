"""Basic 認証のテスト。"""

import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ui.auth import BasicAuthMiddleware


def _client(user="tester", password="s3cret-ピ") -> TestClient:
    app = FastAPI()

    @app.get("/x")
    def x():
        return {"ok": True}

    app.add_middleware(BasicAuthMiddleware, username=user, password=password)
    return TestClient(app)


def _basic(user: str, pw: str) -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()}


def test_認証なしは401で認証を求める():
    r = _client().get("/x")
    assert r.status_code == 401 and "Basic" in r.headers["www-authenticate"]


def test_正しいIDとパスワードは通る():
    assert _client().get("/x", headers=_basic("tester", "s3cret-ピ")).json() == {"ok": True}


@pytest.mark.parametrize("user,pw", [("tester", "wrong"), ("other", "s3cret-ピ"), ("", ""), ("tester", "")])
def test_誤った資格情報は401(user, pw):
    assert _client().get("/x", headers=_basic(user, pw)).status_code == 401


@pytest.mark.parametrize(
    "header", ["Basic !!!notbase64", "Bearer abc", "Basic", "Basic " + base64.b64encode(b"\xff\xfe:x").decode()]
)
def test_壊れたヘッダは401(header):
    assert _client().get("/x", headers={"Authorization": header}).status_code == 401


@pytest.mark.parametrize("user,pw", [("", ""), ("tester", ""), ("", "pw")])
def test_未設定のときは正しそうな資格情報でも全拒否(user, pw):
    r = _client(user, pw).get("/x", headers=_basic("tester", "pw"))
    assert r.status_code == 503
