"""An unusable log directory must never make the package unimportable.

Regression: ``audit.py`` used to call ``default_log_dir().mkdir(...)`` at module
import time without a guard. On a read-only home, a sandboxed ``%LOCALAPPDATA%``
or a container without a writable state dir, ``import portal_mcp_server`` raised
``PermissionError`` — which also took down the ``portal`` credential CLI a user
would need in order to fix the problem. Start-up must degrade, not crash; the
audit *write* path keeps its documented fail-closed guarantee instead.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from portal_mcp_server import audit
from portal_mcp_server import paths


def _file_as_log_dir(tmp_path: Path) -> Path:
    """A regular file where a directory is expected: ``mkdir`` always fails."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("occupied\n")
    return blocker


def test_ensure_log_dir_creates_directory(tmp_path, monkeypatch):
    target = tmp_path / "logs"
    monkeypatch.setenv("PORTAL_LOG_DIR", str(target))
    directory, error = paths.ensure_log_dir()
    assert error is None
    assert directory == target and directory.is_dir()


def test_ensure_log_dir_reports_error_instead_of_raising(tmp_path, monkeypatch):
    blocker = _file_as_log_dir(tmp_path)
    monkeypatch.setenv("PORTAL_LOG_DIR", str(blocker))
    directory, error = paths.ensure_log_dir()
    assert directory == blocker
    assert error is not None and "log directory" in error


def test_package_imports_when_log_dir_is_unusable(tmp_path):
    """The actual crash: import must succeed, and say why logging is off."""
    blocker = _file_as_log_dir(tmp_path)
    env = dict(os.environ, PORTAL_LOG_DIR=str(blocker))
    proc = subprocess.run(
        [sys.executable, "-c",
         "import portal_mcp_server; "
         "from portal_mcp_server import audit; "
         "print(audit._log_dir_error is not None)"],
        cwd=str(Path(__file__).resolve().parent.parent),
        env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().endswith("True")


def test_audit_log_fails_closed_and_names_the_knob(monkeypatch):
    """Default posture is unchanged: a state-changing op is refused, but the
    error names PORTAL_LOG_DIR so it is fixable."""
    monkeypatch.delenv("PORTAL_AUDIT_FAIL_OPEN", raising=False)
    monkeypatch.setattr(audit, "_log_dir_error", "boom: read-only state dir")
    with pytest.raises(RuntimeError) as exc:
        audit.audit_log("web01", "rm -rf /tmp/x", 0)
    assert "PORTAL_LOG_DIR" in str(exc.value)
    assert "PORTAL_AUDIT_FAIL_OPEN" in str(exc.value)


def test_audit_log_fail_open_still_records_history(monkeypatch):
    monkeypatch.setenv("PORTAL_AUDIT_FAIL_OPEN", "1")
    monkeypatch.setattr(audit, "_log_dir_error", "boom: read-only state dir")
    audit.audit_log("web01", "echo hi", 0, operation="exec")
    assert any(e.get("command") == "echo hi" for e in audit.get_history(10))
