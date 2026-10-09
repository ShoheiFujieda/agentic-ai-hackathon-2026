"""Webページの取得。取得の前に robots.txt を確かめ、禁止されていれば取得しない。"""

import re
import threading
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "ScholarshipFinderBot/0.1 (+https://github.com/ShoheiFujieda/agentic-ai-hackathon-2026)"
TIMEOUT_SEC = 20
MAX_BYTES = 5_000_000

_robots: dict[str, RobotFileParser] = {}
_robots_lock = threading.Lock()


class FetchError(Exception):
    pass


class RobotsDisallowed(FetchError):
    pass


def _robots_for(url: str) -> RobotFileParser:
    parts = urlparse(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    with _robots_lock:
        if origin in _robots:
            return _robots[origin]
    parser = RobotFileParser()
    try:
        resp = httpx.get(f"{origin}/robots.txt", timeout=TIMEOUT_SEC, headers={"User-Agent": USER_AGENT})
        if resp.status_code == 200:
            parser.parse(resp.text.splitlines())
        elif resp.status_code in (401, 403):
            parser.disallow_all = True  # robots.txt 自体が拒否されたら、全体を禁止とみなす
        else:
            parser.allow_all = True  # robots.txt がなければ制限なし
    except httpx.HTTPError:
        parser.disallow_all = True  # 確かめられないときは取得しない
    with _robots_lock:
        _robots[origin] = parser
    return parser


def allowed(url: str) -> bool:
    return _robots_for(url).can_fetch(USER_AGENT, url)


def fetch(url: str) -> httpx.Response:
    """robots.txt で許可されているときだけ取得する。"""
    if not allowed(url):
        raise RobotsDisallowed(f"robots.txt で取得が禁止されています: {url}")
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=TIMEOUT_SEC, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError as e:
        raise FetchError(f"取得できませんでした: {url} ({type(e).__name__})") from e
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
