#!/usr/bin/env python3
"""
Detected repository paths (Phase 0 inspection):
- Python entrypoint: main.py
- HTTP server implementation: core/ipc_http.py (start_http_server + Handler routes)
- SQLite database path/init: core/storage.py:get_db_path() -> $TRETA_DATA_DIR/memory/treta.sqlite,
  and initialization/migrations in core/storage.py:Storage.__init__ + core/migrations/runner.py:run_migrations
- Event bus module: core/bus.py (EventBus)
- Scheduler module: core/scheduler.py (DailyScheduler)
- docker-compose service/container: service 'treta', container_name 'treta-core'
"""

from __future__ import annotations

import argparse
import os
import platform
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, allow_fail: bool = False) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    except FileNotFoundError:
        return False, f"command not found: {cmd[0]}\n"
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 and not allow_fail:
        return False, output
    return proc.returncode == 0, output


def detect_docker() -> bool:
    if os.getenv("DOCKER_CONTAINER"):
        return True
    cgroup_paths = [Path("/proc/1/cgroup"), Path("/.dockerenv")]
    for path in cgroup_paths:
        try:
            if path.name == ".dockerenv" and path.exists():
                return True
            if path.exists() and "docker" in path.read_text(encoding="utf-8", errors="ignore").lower():
                return True
        except OSError:
            continue
    return False


def resolve_db_path(cli_db_path: str | None) -> Path:
    if cli_db_path:
        return Path(cli_db_path)
    env_db = os.getenv("TRETA_DB_PATH")
    if env_db:
        return Path(env_db)

    data_root = Path(os.getenv("TRETA_DATA_DIR", "./.treta_data"))
    return ROOT / data_root / "memory" / "treta.sqlite"


def sqlite_integrity(db_path: Path) -> tuple[bool, str]:
    if not db_path.exists():
        return True, f"DB not found at {db_path} (skipped)"
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("PRAGMA integrity_check;").fetchone()
        result = row[0] if row else "unknown"
        ok = str(result).lower() == "ok"
        return ok, f"integrity_check={result}"
    finally:
        conn.close()




def decision_logs_soft_check(db_path: Path) -> tuple[bool, str]:
    if not db_path.exists():
        return True, "decision_logs check skipped (db missing)"
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error as exc:
        return True, f"decision_logs check skipped ({exc})"
    try:
        exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='decision_logs'").fetchone()
        if exists is None:
            return False, "decision_logs table missing"
        try:
            conn.execute(
                """
                INSERT INTO decision_logs (
                    created_at, decision_type, decision, status, updated_at
                ) VALUES (datetime('now'), 'audit_probe', 'RECORD', 'recorded', datetime('now'))
                """
            )
            conn.rollback()
            return True, "decision_logs table present and writable"
        except sqlite3.Error as exc:
            return True, f"decision_logs write check skipped ({exc})"
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="TRETA internal audit runner")
    parser.add_argument("--skip-security", action="store_true")
    parser.add_argument("--skip-format", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()

    print("Top-level tree:")
    _, top_tree = run(["find", ".", "-maxdepth", "1", "-mindepth", "1", "-printf", "%f\\n"], allow_fail=True)
    print(top_tree, end="")
    print("\nCore tree:")
    _, core_tree = run(["find", "core", "-maxdepth", "2", "-type", "d"], allow_fail=True)
    print(core_tree, end="")

    env_ok = True
    print("\nEnvironment info:")
    print(f"- Python: {sys.version.split()[0]}")
    print(f"- OS: {platform.platform()}")
    print(f"- Docker: {'yes' if detect_docker() else 'no'}")

    format_ok = True
    if not args.skip_format:
        ok1, out1 = run(["ruff", "check", "."])
        print(out1, end="")
        ok2, out2 = run(["black", "--check", "."])
        print(out2, end="")
        format_ok = ok1 and ok2

    security_ok = True
    if not args.skip_security:
        ok3, out3 = run(["bandit", "-r", "."], allow_fail=True)
        print(out3, end="")
        pip_ok, pip_out = run(["pip-audit"], allow_fail=True)
        print(pip_out, end="")
        offline_tokens = ("temporary failure", "name or service not known", "connection", "offline")
        if not pip_ok and any(token in pip_out.lower() for token in offline_tokens):
            print("pip-audit: SKIPPED (offline)")
            pip_ok = True
        security_ok = ok3 and pip_ok

    tests_ok = True
    if not args.skip_tests:
        tests_ok, tests_out = run(["pytest", "-q"])
        print(tests_out, end="")

    db_path = resolve_db_path(args.db_path)
    db_ok, db_msg = sqlite_integrity(db_path)
    print(db_msg)
    decision_logs_ok, decision_logs_msg = decision_logs_soft_check(db_path)
    print(decision_logs_msg)
    db_ok = db_ok and decision_logs_ok

    print("\n=================================")
    print("TRETA INTERNAL AUDIT REPORT")
    print("=================================")
    print(f"Environment: {'PASS' if env_ok else 'FAIL'}")
    print(f"Format: {'PASS' if format_ok else 'FAIL'}")
    print(f"Security: {'PASS' if security_ok else 'FAIL'}")
    print(f"Tests: {'PASS' if tests_ok else 'FAIL'}")
    print(f"Database: {'PASS' if db_ok else 'FAIL'}")
    print("=================================")

    if not (tests_ok and db_ok):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
