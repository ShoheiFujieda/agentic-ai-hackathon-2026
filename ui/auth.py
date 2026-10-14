"""Basic 認証（純粋な ASGI ミドルウェア）。審査員にテスト用のID／パスワードを渡すための最小の認証。

- パスワードが未設定のときは、全アクセスを拒否する（設定忘れで公開されない）
- 比較は定数時間（secrets.compare_digest）
"""

import base64
import binascii
import os
import secrets

REALM = 'Basic realm="scholarship-agent", charset="UTF-8"'


class BasicAuthMiddleware:
    def __init__(self, app, username: str | None = None, password: str | None = None):
        self.app = app
        self.username = username if username is not None else os.environ.get("APP_USER", "")
        self.password = password if password is not None else os.environ.get("APP_PASSWORD", "")

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        if not self.username or not self.password:
            return await self._deny(scope, receive, send, 503, "認証が設定されていないため、アクセスできません")
        if self._ok(dict(scope["headers"]).get(b"authorization", b"").decode("latin-1")):
            return await self.app(scope, receive, send)
        return await self._deny(scope, receive, send, 401, "認証が必要です", challenge=True)

    def _ok(self, header: str) -> bool:
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "basic":
            return False
        try:
            user, _, pw = base64.b64decode(token, validate=True).decode("utf-8").partition(":")
        except (binascii.Error, UnicodeDecodeError):
            return False
        # どちらも常に比較して、どちらが違うかを時間差で漏らさない
        ok_user = secrets.compare_digest(user.encode(), self.username.encode())
        ok_pw = secrets.compare_digest(pw.encode(), self.password.encode())
        return ok_user and ok_pw

    async def _deny(self, scope, receive, send, status: int, text: str, challenge: bool = False):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        headers = [(b"content-type", b"text/plain; charset=utf-8"), (b"cache-control", b"no-store")]
        if challenge:
            headers.append((b"www-authenticate", REALM.encode()))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": text.encode()})
