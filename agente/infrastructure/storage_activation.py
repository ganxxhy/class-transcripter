"""Offline storage cutover. Requires all legacy writers to be stopped."""
import json
import hashlib
import os
import tempfile
from pathlib import Path

from .sqlite_migration import migrate_classes
from .sqlite_store import SQLiteClassRepository

MARKER = "sqlite-active.json"
DATABASE = "classes.sqlite3"


def active_database(data_directory):
    root = Path(data_directory)
    marker = root / MARKER
    if not marker.exists():
        return None
    with marker.open(encoding="utf-8") as stream:
        metadata = json.load(stream)
    if metadata != {"version": 1, "database": DATABASE}:
        raise ValueError("Invalid SQLite activation marker")
    database = root / DATABASE
    if not database.is_file():
        raise FileNotFoundError(database)
    SQLiteClassRepository.validate_existing(database)
    return database


def legacy_snapshot(root):
    """Fingerprint legacy inputs, including additions and removals."""
    paths = sorted((root / "clases").glob("*.json"))
    state = root / "estado.json"
    if state.exists():
        paths.append(state)
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths}


def activate_sqlite(data_directory, *, offline_confirmed=False):
    if not offline_confirmed:
        raise ValueError("Stop Estudio, MCP and all Hub instances before migration")
    root = Path(data_directory)
    existing = active_database(root)
    if existing is not None:
        return existing
    root.mkdir(parents=True, exist_ok=True)
    source = root / "clases"
    source.mkdir(exist_ok=True)
    snapshot = legacy_snapshot(root)
    state = root / "estado.json"
    database = root / DATABASE
    # Never overwrite an inactive database: it may contain newer user data.
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        candidate = Path(temporary) / DATABASE
        migrate_classes(source, candidate, state if state.exists() else None)
        repository = SQLiteClassRepository(candidate)
        expected = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(source.glob("*.json"))]
        actual = repository.listar(incluir_segmentos=True)
        if sorted(expected, key=lambda record: record["id"]) != sorted(actual, key=lambda record: record["id"]):
            raise ValueError("Class verification failed")
        completed = json.loads(state.read_text(encoding="utf-8"))["hechos"] if state.exists() else []
        if repository.leer_estado()["hechos"] != sorted(set(completed)):
            raise ValueError("Completed item verification failed")
        with repository.transaction(write=False) as connection:
            if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("SQLite integrity check failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("SQLite foreign key check failed")
        marker = Path(temporary) / MARKER
        with marker.open("w", encoding="utf-8") as stream:
            json.dump({"version": 1, "database": DATABASE}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        if legacy_snapshot(root) != snapshot:
            raise RuntimeError("Legacy data changed during migration; close the old Hub and retry")
        if database.exists():
            SQLiteClassRepository.validate_existing(database)
            previous = SQLiteClassRepository(database)
            if previous.listar(incluir_segmentos=True) != actual or previous.leer_estado() != repository.leer_estado():
                raise ValueError("Inactive database differs from the verified snapshot; preserve it for manual recovery")
        else:
            os.replace(candidate, database)
        if legacy_snapshot(root) != snapshot:
            raise RuntimeError("Legacy data changed before activation; preserve both stores for recovery")
        os.replace(marker, root / MARKER)
    return database


def ensure_sqlite(data_directory):
    """Serialize first-use migration across the desktop and MCP processes."""
    from .file_lock import FileLock
    root = Path(data_directory)
    with FileLock(str(root / ".storage.lock")).hold():
        database = activate_sqlite(root, offline_confirmed=True)
        # Keep legacy files outside the path used by old Hub versions.
        source = root / "clases"
        backup = root / "clases-json-backup"
        if source.exists():
            if backup.exists():
                # Never merge stale JSON into the active database or overwrite a backup.
                if not any(source.iterdir()):
                    source.rmdir()
                else:
                    with tempfile.TemporaryDirectory(prefix="legacy-recovery-", dir=root) as temporary:
                        # Keep a uniquely named sibling directory after the temporary context exits.
                        recovery = Path(temporary).with_name(Path(temporary).name + "-preserved")
                        source.rename(recovery)
            else:
                source.rename(backup)
        return database
