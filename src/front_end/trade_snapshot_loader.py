from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Optional, Tuple, TypeVar

from filelock import FileLock
from src.trade_lifecycle_manager import TradeLifecycleManager

T = TypeVar("T")


def _read_pickle_envelope(path: Path, lock_path: Path, timeout_s: float = 60.0) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None

    lock = FileLock(str(lock_path), timeout=timeout_s)
    lock.acquire()
    try:
        with open(path, "rb") as f:
            raw = pickle.load(f)
        if isinstance(raw, dict) and "version" in raw and "payload" in raw:
            return raw
        return None
    finally:
        lock.release()


def _unwrap_envelope(envelope: dict[str, Any]) -> Any:
    return envelope["payload"]


def load_trade_lifecycle_from_disk() -> TradeLifecycleManager:
    """
    Restore the persisted TradeLifecycleManager snapshot from disk only.

    This intentionally avoids `PersistentDataService.load_all()` because that also restores news
    and can trigger RSS scraping during initialization.
    """

    snapshot_path = Path("persistent_data") / "trade_lifecycle.snapshot"
    lock_path = Path("persistent_data") / "trade_lifecycle.lock"

    envelope = _read_pickle_envelope(snapshot_path, lock_path)
    if envelope is None:
        return None

    payload = _unwrap_envelope(envelope)
    manager = TradeLifecycleManager()
    manager.restore_from_persistent_snapshot(payload)
    return manager

