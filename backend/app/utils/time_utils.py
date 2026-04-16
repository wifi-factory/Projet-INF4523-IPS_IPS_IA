from __future__ import annotations

from datetime import datetime, timezone

try:
    from datetime import UTC  # Python 3.11+
except ImportError:  # pragma: no cover - compatibility path
    UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_iso() -> str:
    return utc_now().isoformat()
