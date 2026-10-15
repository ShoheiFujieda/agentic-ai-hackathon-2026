"""Web 取得の安全性（内部アドレスを取得しない＝SSRF 対策、転送先も毎回確かめる）のテスト。ネットワークは使わない。"""

import httpx
import pytest

from hackathon_agent.scholarship import web


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://10.0.0.5/x",
        "http://192.168.1.1/",
        "http://169.254.169.254/computeMetadata/v1/",  # クラウドのメタデータサーバー
        "http://[::1]/",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "http:///nohost",
    ],
)
def test_内部アドレスや不正な形式のURLは取得しない(url):
    with pytest.raises(web.FetchError):
        web.check_public(url)


def test_公開アドレスは通す():
    web.check_public("https://93.184.216.34/")  # IP を直接指定（名前解決なし）


def test_内部アドレスへの転送は追わない(monkeypatch):
    monkeypatch.setattr(web, "allowed", lambda url: True)
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        return httpx.Response(
            302, headers={"location": "http://169.254.169.254/latest/"}, request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(web.httpx, "get", fake_get)
    with pytest.raises(web.UnsafeUrl):
        web.fetch("https://93.184.216.34/start")
    assert calls == ["https://93.184.216.34/start"]  # 転送先には接続していない


def test_転送が多すぎれば止める(monkeypatch):
    monkeypatch.setattr(web, "allowed", lambda url: True)
    monkeypatch.setattr(
        web.httpx,
        "get",
        lambda url, **kw: httpx.Response(302, headers={"location": "/again"}, request=httpx.Request("GET", url)),
    )
    with pytest.raises(web.FetchError, match="転送が多すぎます"):
        web.fetch("https://93.184.216.34/loop")


def test_公開アドレスどうしの転送は追う(monkeypatch):
    monkeypatch.setattr(web, "allowed", lambda url: True)

    def fake_get(url, **kw):
        if url.endswith("/a"):
            return httpx.Response(301, headers={"location": "/b"}, request=httpx.Request("GET", url))
        return httpx.Response(200, text="ok", request=httpx.Request("GET", url))

    monkeypatch.setattr(web.httpx, "get", fake_get)
    assert web.fetch("https://93.184.216.34/a").text == "ok"
