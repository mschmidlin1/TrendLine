#!/usr/bin/env python3
"""
One-off migration: legacy trade_lifecycle.snapshot (scalar buy_order per entry)
-> dict-keyed buy_orders / sell_orders.

Run from repo root:
  python scripts/migrate_trade_lifecycle_snapshot.py

Backs up the original file next to it with suffix .bak before overwriting.
"""
from __future__ import annotations

import os
import pickle
import shutil
import sys
import tempfile
from pathlib import Path

# Repo root (parent of scripts/)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from filelock import FileLock  # noqa: E402

from src.configs import PERSISTENT_DATA_DIR  # noqa: E402
from src.snapshot_migration import migrate_legacy_archived_entry_in_place  # noqa: E402

EnvelopeVersion = 1


def _unwrap(data: dict) -> object:
    if not isinstance(data, dict) or "version" not in data or "payload" not in data:
        raise ValueError("Invalid snapshot envelope")
    if data["version"] != EnvelopeVersion:
        raise ValueError(f"Unsupported snapshot version: {data['version']}")
    return data["payload"]


def _wrap(payload: object) -> dict:
    return {"version": EnvelopeVersion, "payload": payload}


def main() -> int:
    data_dir = Path(PERSISTENT_DATA_DIR)
    snap = data_dir / "trade_lifecycle.snapshot"
    lock_path = data_dir / "trade_lifecycle.lock"

    if not snap.is_file():
        print(f"No snapshot at {snap}; nothing to do.")
        return 0

    lock = FileLock(str(lock_path), timeout=120)
    lock.acquire()
    try:
        with open(snap, "rb") as f:
            envelope = pickle.load(f)
        payload = _unwrap(envelope)
        entries = payload.get("archived_entries")
        if not isinstance(entries, list):
            raise ValueError("payload missing archived_entries list")

        n = len(entries)
        for entry in entries:
            migrate_legacy_archived_entry_in_place(entry)

        bak = snap.with_suffix(snap.suffix + ".bak")
        shutil.copy2(snap, bak)
        print(f"Backed up to {bak}")

        fd, tmp = tempfile.mkstemp(
            dir=snap.parent, prefix=".tmp_migrate_", suffix=".snapshot", text=False
        )
        try:
            with os.fdopen(fd, "wb") as tmp_f:
                pickle.dump(_wrap(payload), tmp_f, protocol=pickle.HIGHEST_PROTOCOL)
                tmp_f.flush()
                os.fsync(tmp_f.fileno())
            os.replace(tmp, snap)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

        print(f"Migrated {n} archived entries in {snap}")
        return 0
    finally:
        lock.release()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        raise SystemExit(1)
