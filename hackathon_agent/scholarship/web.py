"""Webページの取得。取得の前に robots.txt を確かめ、禁止されていれば取得しない。"""

import ipaddress
import re
import socket
import threading
import time
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "ScholarshipFinderBot/0.1 (+https://github.com/ShoheiFujieda/agentic-ai-hackathon-2026)"
TIMEOUT_SEC = 20
MAX_BYTES = 5_000_000

_robots: dict[str, tuple[float, RobotFileParser]] = {}
_robots_lock = threading.Lock()
ROBOTS_TTL_SEC = 3600  # 取得できた robots.txt は1時間使う
ROBOTS_RETRY_SEC = 60  # 取得に失敗したときは、1分だけ「禁止」とみなして、その後また確かめる


class FetchError(Exception):
    pass


class RobotsDisallowed(FetchError):
    pass


class UnsafeUrl(FetchError):
    pass


MAX_REDIRECTS = 5


def check_public(url: str) -> None:
    """検索結果などから来たURLが、内部のアドレスを指していないかを確かめる（SSRF 対策）。

    http/https 以外、ホスト名なし、ループバック・プライベート・リンクローカル（メタデータサーバーなど）のアドレスは取得しない。
    """
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeUrl(f"取得できないURLです: {url}")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except OSError as e:
        raise FetchError(f"取得できませんでした: {url} (名前を解決できません)") from e
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise UnsafeUrl(f"内部のアドレスは取得しません: {url}")


def _robots_for(url: str) -> RobotFileParser:
    parts = urlparse(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    with _robots_lock:
        cached = _robots.get(origin)
        if cached and time.time() < cached[0]:
            return cached[1]
    parser = RobotFileParser()
    ttl = ROBOTS_TTL_SEC
    try:
        resp = httpx.get(
            f"{origin}/robots.txt", timeout=TIMEOUT_SEC, headers={"User-Agent": USER_AGENT}, follow_redirects=True
        )
        if resp.status_code == 200:
            parser.parse(resp.text.splitlines())
        elif resp.status_code in (401, 403):
            parser.disallow_all = True  # robots.txt 自体が拒否されたら、全体を禁止とみなす
        elif 400 <= resp.status_code < 500:
            parser.allow_all = True  # robots.txt がなければ制限なし
        else:
            parser.disallow_all = True  # サーバーの一時的な失敗。確かめられないので取得しない
            ttl = ROBOTS_RETRY_SEC
    except httpx.HTTPError:
        parser.disallow_all = True  # 確かめられないときは取得しない（すぐ確かめ直す）
        ttl = ROBOTS_RETRY_SEC
    with _robots_lock:
        _robots[origin] = (time.time() + ttl, parser)
    return parser


def allowed(url: str) -> bool:
    return _robots_for(url).can_fetch(USER_AGENT, url)


def fetch(url: str) -> httpx.Response:
    """公開のアドレスで、robots.txt で許可されているときだけ取得する（転送先も毎回確かめる）。"""
    for _ in range(MAX_REDIRECTS + 1):
        check_public(url)
        if not allowed(url):
            raise RobotsDisallowed(f"robots.txt で取得が禁止されています: {url}")
        try:
            resp = httpx.get(url, follow_redirects=False, timeout=TIMEOUT_SEC, headers={"User-Agent": USER_AGENT})
        except httpx.HTTPError as e:
            raise FetchError(f"取得できませんでした: {url} ({type(e).__name__})") from e
        if resp.is_redirect and resp.headers.get("location"):
            url = urljoin(url, resp.headers["location"])
            continue
        break
    else:
        raise FetchError(f"転送が多すぎます: {url}")
    if resp.status_code != 200:
        raise FetchError(f"取得できませんでした: {url} (HTTP {resp.status_code})")
    if len(resp.content) > MAX_BYTES:
        raise FetchError(f"ページが大きすぎます: {url}")
    return resp


def decode_html(resp: httpx.Response) -> str:
    """文字コードを決めて本文を文字にする。サーバーが知らせてこなければ、ページ内の宣言（meta charset）を使う。"""
    if "charset=" in resp.headers.get("content-type", "").lower():
        return resp.text
    m = re.search(rb"charset=[\"']?([\w-]+)", resp.content[:4000])
    for enc in ([m.group(1).decode()] if m else []) + ["utf-8", "cp932"]:
        try:
            return resp.content.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return resp.content.decode("utf-8", errors="replace")


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def html_to_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    return "\n".join(parser.parts)


# 引用の照合で同じとみなす記号（波線・中黒・句読点・括弧など）。言い換えは一致しないまま
_SYMBOLS = re.compile(r"[\s〜～~・･、。，．,.:：;；「」『』（）()\[\]【】※\-ー−‐―]")


def norm(s: str) -> str:
    """照合用に正規化する（全角半角をそろえ、空白と記号を除く）。"""
    return _SYMBOLS.sub("", unicodedata.normalize("NFKC", s or ""))


def quote_in(quote: str, text: str) -> bool:
    """AI が返した引用が、本当に原文に含まれているか。"""
    q = norm(quote)
    return bool(q) and q in norm(text)
