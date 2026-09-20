"""Test safe DB refresh: backup + schema recreation."""

import shutil
import subprocess
from pathlib import Path

from jobradar.db import Database
from jobradar.models import JobRecord


def test_db_init_creates_schema(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    assert db_path.exists()
    assert db.count_jobs() == 0


def test_db_backup_and_restore(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/1")
    db.upsert_job(job)
    assert db.count_jobs() == 1
    backup_path = tmp_path / "test.db.backup"
    shutil.copy(db_path, backup_path)
    db_path.unlink()
    assert not db_path.exists()
    db2 = Database(db_path)
    assert db2.count_jobs() == 0
    shutil.copy(backup_path, db_path)
    db3 = Database(db_path)
    assert db3.count_jobs() == 1


def test_fresh_db_backup_script_exists():
    script_path = Path(__file__).parents[1] / "scripts" / "fresh_db_backup.sh"
    assert script_path.exists(), "scripts/fresh_db_backup.sh should exist"
    content = script_path.read_text()
    assert "BACKUP_PATH" in content
    assert "cp" in content
    assert "rm" in content


def test_db_refresh_workflow(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "jobradar.db"))
    db_path = tmp_path / "jobradar.db"
    db = Database(db_path)
    job = JobRecord(company="OldCo", title="Old Job", url="https://example.com/old")
    db.upsert_job(job)
    assert db.count_jobs() == 1
    backup_path = tmp_path / "jobradar.db.backup_test"
    shutil.copy(db_path, backup_path)
    db_path.unlink()
    db_new = Database(db_path)
    assert db_new.count_jobs() == 0
    shutil.copy(backup_path, db_path)
    db_restored = Database(db_path)
    assert db_restored.count_jobs() == 1
    restored_job = db_restored.list_jobs()[0]
    assert restored_job.company == "OldCo"


def test_db_init_command(tmp_path, monkeypatch):
    db_path = tmp_path / "cli_test.db"
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(db_path))
    result = subprocess.run(
        ["python3", "-m", "jobradar", "db-init"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0
    assert "initialized" in result.stdout
    assert db_path.exists()


def test_db_refresh_command_creates_backup(tmp_path, monkeypatch):
    """db-refresh creates timestamped backup before wiping."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(db_path))
    db = Database(db_path)
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/1")
    db.upsert_job(job)
    assert db.count_jobs() == 1
    
    result = subprocess.run(
        ["python3", "-m", "jobradar", "db-refresh"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0
    assert "backing up" in result.stdout
    assert "backup saved" in result.stdout
    assert "db refresh complete" in result.stdout
    
    db_new = Database(db_path)
    assert db_new.count_jobs() == 0
    
    backup_files = list(tmp_path.glob("test.db.backup_*"))
    assert len(backup_files) == 1
    backup_path = backup_files[0]
    db_backup = Database(backup_path)
    assert db_backup.count_jobs() == 1


def test_db_refresh_command_no_db_fails(tmp_path, monkeypatch):
    """db-refresh fails gracefully if no DB exists."""
    db_path = tmp_path / "nonexistent.db"
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(db_path))
    result = subprocess.run(
        ["python3", "-m", "jobradar", "db-refresh"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "error: no DB" in result.stdout


def test_db_refresh_command_no_backup_requires_confirmation(tmp_path, monkeypatch):
    """db-refresh --no-backup requires interactive YES confirmation."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(db_path))
    db = Database(db_path)
    job = JobRecord(company="TestCo", title="Engineer", url="https://example.com/1")
    db.upsert_job(job)
    
    result = subprocess.run(
        ["python3", "-m", "jobradar", "db-refresh", "--no-backup"],
        input="NO\n",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "aborted" in result.stdout
    assert db_path.exists()
    db_check = Database(db_path)
    assert db_check.count_jobs() == 1


def test_db_refresh_preserves_backup_on_multiple_runs(tmp_path, monkeypatch):
    """Multiple db-refresh calls create separate timestamped backups."""
    import time
    
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(db_path))
    
    db = Database(db_path)
    job1 = JobRecord(company="TestCo1", title="Engineer", url="https://example.com/1")
    db.upsert_job(job1)
    
    subprocess.run(
        ["python3", "-m", "jobradar", "db-refresh"],
        capture_output=True,
        text=True,
        check=True,
    )
    
    time.sleep(1.1)
    
    db2 = Database(db_path)
    job2 = JobRecord(company="TestCo2", title="Engineer", url="https://example.com/2")
    db2.upsert_job(job2)
    
    subprocess.run(
        ["python3", "-m", "jobradar", "db-refresh"],
        capture_output=True,
        text=True,
        check=True,
    )
    
    backup_files = sorted(tmp_path.glob("test.db.backup_*"))
    assert len(backup_files) >= 2, "Multiple backups should exist"
