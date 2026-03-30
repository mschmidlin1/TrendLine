"""
Probe whether the TrendLine log coordination lock can be acquired immediately.

Uses the same path as LockingFileHandler in src.base.tl_logger (logs.txt.lock next to
the log file). While the app is actively logging, the lock may be held only briefly;
a "held" result can occasionally appear due to timing.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from filelock import FileLock, Timeout  # noqa: E402
from src.configs import LOG_FILE, LOG_PATH  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check if the log filelock can be acquired without waiting."
    )
    parser.add_argument(
        "--lock-path",
        metavar="PATH",
        help="Override lock file path (default: from src.configs LOG_PATH/LOG_FILE + .lock)",
    )
    args = parser.parse_args()

    if args.lock_path:
        lock_path = args.lock_path
    else:
        lock_path = os.path.join(LOG_PATH, LOG_FILE) + ".lock"

    lock = FileLock(lock_path)
    try:
        lock.acquire(timeout=0)
    except Timeout:
        print(f"Log lock is held: {lock_path}", file=sys.stderr)
        return 1

    try:
        print(f"Log lock is free: {lock_path}")
    finally:
        lock.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
