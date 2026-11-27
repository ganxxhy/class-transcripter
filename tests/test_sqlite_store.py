import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agente"))
from infrastructure.sqlite_store import SQLiteClassRepository
from infrastructure.sqlite_migration import migrate_classes


class SQLiteStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "classes.sqlite3"
        self.repository = SQLiteClassRepository(self.path)

    def test_persistence_and_concurrent_append(self):
        start = datetime(2026, 1, 1)
        class_id = self.repository.crear_clase("math", "Math", "manual", start)
        self.assertNotEqual(class_id, self.repository.crear_clase("math", "Math", "manual", start))
        def append(index):
            self.repository.anadir_segmentos(class_id, [{"ini": index, "fin": index + 1, "texto": str(index)}])
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(append, range(40)))
        reopened = SQLiteClassRepository(self.path)
        self.assertEqual(len(reopened.leer(class_id)["segmentos"]), 40)
        self.assertTrue(reopened.claim_summary(class_id))
        self.assertFalse(reopened.claim_summary(class_id))
        self.assertFalse(reopened.cerrar(class_id)["en_curso"])
        reopened.eliminar(class_id)
        with self.assertRaises(FileNotFoundError):
            reopened.leer(class_id)

    def test_migration_idempotence_and_conflict(self):
        class_id = self.repository.crear_clase("math", "Math", "manual")
        self.repository.anadir_segmentos(class_id, [{"ini": 0, "fin": 2, "texto": "Hola mundo"}])
        record = self.repository.leer(class_id)
        source = self.root / "legacy"
        source.mkdir()
        file = source / (class_id + ".json")
        file.write_text(json.dumps(record), encoding="utf-8")
        target = self.root / "import.sqlite3"
        original = file.read_bytes()
        self.assertEqual(migrate_classes(source, target), 1)
        self.assertEqual(migrate_classes(source, target), 0)
        self.assertEqual(file.read_bytes(), original)
        self.assertEqual(SQLiteClassRepository(target).leer(class_id), record)
        record["aula"] = "changed"
        file.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(ValueError):
            migrate_classes(source, target)
        self.assertEqual(SQLiteClassRepository(target).leer(class_id)["aula"], "")


if __name__ == "__main__":
    unittest.main()
