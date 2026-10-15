"""奨学金データのキャッシュ（Firestore `scholarship_cache`）。学生をまたいで共有する。

キャッシュは速さのためのもの。読み書きに失敗しても処理は続ける（結果は同じで、遅くなるだけ）。
"""

import logging
import os
from datetime import UTC, datetime, timedelta

from google.cloud import firestore

logger = logging.getLogger(__name__)

COLLECTION = "scholarship_cache"
DEFAULT_TTL_DAYS = 7  # 要項は変わることがあるので、既定は1週間で読み直す。審査期間など、保存を長くしたいときは環境変数 CACHE_TTL_DAYS で変える


def ttl() -> timedelta:
    """キャッシュの保存期間。環境変数 CACHE_TTL_DAYS（日数）で変えられる。"""
    try:
        days = float(os.environ.get("CACHE_TTL_DAYS", DEFAULT_TTL_DAYS))
    except ValueError:
        days = DEFAULT_TTL_DAYS
    return timedelta(days=days if days > 0 else DEFAULT_TTL_DAYS)


_client: firestore.Client | None = None


def _db() -> firestore.Client:
    global _client
    if _client is None:
        _client = firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    return _client


def get(key: str, max_age: timedelta | None = None) -> dict | None:
    try:
        doc = _db().collection(COLLECTION).document(key).get()
    except Exception:
        logger.warning("キャッシュを読めませんでした: %s", key, exc_info=True)
        return None
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    saved = data.get("saved_at")
    if saved and datetime.now(UTC) - saved > (max_age or ttl()):
        return None
    return data.get("value")


def put(key: str, value: dict) -> None:
    try:
        _db().collection(COLLECTION).document(key).set({"value": value, "saved_at": datetime.now(UTC)})
    except Exception:
        logger.warning("キャッシュに書けませんでした: %s", key, exc_info=True)
