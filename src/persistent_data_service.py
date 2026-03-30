"""
Singleton service that persists in-memory state for TradeLifecycleManager and NewsScrapingService.
"""
from __future__ import annotations

import os
import pickle
import tempfile
from pathlib import Path
from typing import Literal, Optional, Union

from filelock import FileLock

from src.base.singleton import SingletonMeta
from src.base.tl_logger import LoggingService
from src.configs import PERSISTENT_DATA_DIR
from src.news_scraper import NewsScrapingService
from src.trade_lifecycle_manager import TradeLifecycleManager

EnvelopeVersion = 1
SaveReason = Literal["flush", "shutdown"]


class PersistentDataService(metaclass=SingletonMeta):
    """Persists and restores snapshot state using pickle, atomic writes, and file locks."""

    _SHUTDOWN_SAVE_DONE = False

    def __init__(self, data_dir: Optional[Union[str, Path]] = None) -> None:
        self._logger = LoggingService()
        self._data_dir = Path(data_dir) if data_dir is not None else Path(PERSISTENT_DATA_DIR)
        self._trade_snapshot = self._data_dir / "trade_lifecycle.snapshot"
        self._trade_lock = self._data_dir / "trade_lifecycle.lock"
        self._news_snapshot = self._data_dir / "news_scraper.snapshot"
        self._news_lock = self._data_dir / "news_scraper.lock"

    def load_all(self) -> None:
        """Restore state from disk if snapshot files exist and are valid."""
        loaded_any = False
        try:
            payload = self._read_snapshot(self._trade_snapshot, self._trade_lock)
            if payload is not None:
                TradeLifecycleManager().restore_from_persistent_snapshot(payload)
                loaded_any = True
        except Exception as e:
            self._logger.log_warning(f"Could not load trade lifecycle snapshot: {e}")

        try:
            payload = self._read_snapshot(self._news_snapshot, self._news_lock)
            if payload is not None:
                NewsScrapingService().restore_from_persistent_snapshot(payload)
                loaded_any = True
        except Exception as e:
            self._logger.log_warning(f"Could not load news scraper snapshot: {e}")

        if loaded_any:
            self._logger.log_info("Persistent data loaded from disk.")

    def save_all(self, reason: SaveReason = "flush") -> None:
        """
        Write current service state to disk.

        Args:
            reason: ``flush`` for routine loop saves; ``shutdown`` when the process is stopping.
        """
        if reason == "shutdown" and PersistentDataService._SHUTDOWN_SAVE_DONE:
            return

        trade = TradeLifecycleManager().get_persistent_snapshot()
        news = NewsScrapingService().get_persistent_snapshot()

        try:
            self._write_snapshot(self._trade_snapshot, self._trade_lock, trade)
            self._write_snapshot(self._news_snapshot, self._news_lock, news)
        except Exception as e:
            self._logger.log_error(f"Persistent data save failed: {e}")
            raise

        if reason == "flush":
            self._logger.log_info("Persistent data saved (routine flush).")
        else:
            self._logger.log_info("Persistent data saved (program termination).")
            PersistentDataService._SHUTDOWN_SAVE_DONE = True

    @staticmethod
    def _wrap_envelope(payload: object) -> dict:
        return {"version": EnvelopeVersion, "payload": payload}

    @staticmethod
    def _unwrap_envelope(data: dict) -> object:
        if not isinstance(data, dict) or "version" not in data or "payload" not in data:
            raise ValueError("Invalid snapshot envelope")
        if data["version"] != EnvelopeVersion:
            raise ValueError(f"Unsupported snapshot version: {data['version']}")
        return data["payload"]

    def _read_snapshot(self, path: Path, lock_path: Path) -> Optional[object]:
        if not path.is_file():
            return None
        lock = FileLock(str(lock_path), timeout=60)
        lock.acquire()
        try:
            with open(path, "rb") as f:
                raw = pickle.load(f)
            return self._unwrap_envelope(raw)
        finally:
            lock.release()

    def _write_atomic_pickle(self, path: Path, envelope: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=path.parent, prefix=".tmp_", suffix=".snapshot", text=False
        )
        try:
            with os.fdopen(fd, "wb") as tmp_f:
                pickle.dump(envelope, tmp_f, protocol=pickle.HIGHEST_PROTOCOL)
                tmp_f.flush()
                os.fsync(tmp_f.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def _write_snapshot(self, path: Path, lock_path: Path, payload: object) -> None:
        lock = FileLock(str(lock_path), timeout=60)
        lock.acquire()
        try:
            self._write_atomic_pickle(path, self._wrap_envelope(payload))
        finally:
            lock.release()
