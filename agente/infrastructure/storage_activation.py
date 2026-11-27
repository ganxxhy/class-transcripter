"""Offline storage cutover. Requires all legacy writers to be stopped."""
import json
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
    return database


def activate_sqlite(data_directory, *, offline_confirmed=False):
    if not offline_confirmed:
        raise ValueError("Stop Estudio, MCP and all Hub instances before migration")
    root = Path(data_directory)
    existing = active_database(root)
    if existing is not None:
        return existing
    source = root / "clases"
    state = root / "estado.json"
    database = root / DATABASE
    if database.exists():
        raise FileExistsError("Existing inactive database; review it before retrying")
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
        os.replace(candidate, database)
        os.replace(marker, root / MARKER)
    return database
