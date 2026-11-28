"""Import legacy class files without modifying or deleting the originals."""
import json
from pathlib import Path
from .sqlite_store import SQLiteClassRepository


def migrate_classes(source_directory, database_path, state_path=None):
    """Import an offline snapshot. Stop the agent and Hub before invoking."""
    source = Path(source_directory)
    if not source.is_dir():
        raise FileNotFoundError(source)
    records = []
    for path in sorted(source.glob("*.json")):
        with path.open(encoding="utf-8") as stream:
            record = json.load(stream)
        if not isinstance(record, dict) or record.get("id") != path.stem:
            raise ValueError(f"Invalid class record: {path.name}")
        if not isinstance(record.get("segmentos"), list):
            raise ValueError(f"Invalid segments: {path.name}")
        records.append(record)
    completed = []
    if state_path is not None:
        with Path(state_path).open(encoding="utf-8") as stream:
            state = json.load(stream)
        completed = state["hechos"]
        if not isinstance(completed, list) or not all(isinstance(key, str) for key in completed):
            raise ValueError("Invalid completed items")
    repository = SQLiteClassRepository(database_path)
    return repository.import_records(records, completed)
