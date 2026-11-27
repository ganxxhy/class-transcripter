"""Import legacy class files without modifying or deleting the originals."""
import json
from pathlib import Path
from .sqlite_store import SQLiteClassRepository


def migrate_classes(source_directory, database_path):
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
    repository = SQLiteClassRepository(database_path)
    return repository.import_records(records)
