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

    def test_completed_items(self):
        source = self.root / "legacy"
        source.mkdir()
        state = self.root / "estado.json"
        state.write_text(json.dumps({"hechos": ["b", "a", "a"]}), encoding="utf-8")
        self.assertEqual(migrate_classes(source, self.path, state), 0)
        self.assertEqual(self.repository.leer_estado(), {"hechos": ["a", "b"]})
        self.assertEqual(self.repository.marcar_hecho("a", False), {"hechos": ["b"]})
        self.assertEqual(self.repository.marcar_hecho("c", True), {"hechos": ["b", "c"]})

    def test_verified_activation(self):
        from infrastructure.storage_activation import activate_sqlite, active_database
        root = self.root / "activation"
        source = root / "clases"
        source.mkdir(parents=True)
        class_id = self.repository.crear_clase("math", "Math", "manual")
        record = self.repository.leer(class_id)
        original = source / (class_id + ".json")
        original.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(ValueError):
            activate_sqlite(root)
        self.assertIsNone(active_database(root))
        database = activate_sqlite(root, offline_confirmed=True)
        self.assertEqual(active_database(root), database)
        self.assertEqual(SQLiteClassRepository(database).leer(class_id), record)
        self.assertEqual(json.loads(original.read_text(encoding="utf-8")), record)
        self.assertEqual(activate_sqlite(root, offline_confirmed=True), database)

    def test_invalid_snapshot_does_not_activate(self):
        from infrastructure.storage_activation import activate_sqlite, active_database
        root = self.root / "invalid"
        source = root / "clases"
        source.mkdir(parents=True)
        (source / "bad.json").write_text("invalid", encoding="utf-8")
        with self.assertRaises(ValueError):
            activate_sqlite(root, offline_confirmed=True)
        self.assertIsNone(active_database(root))
        self.assertFalse((root / "classes.sqlite3").exists())

    def test_empty_activation_and_retry(self):
        from infrastructure.storage_activation import activate_sqlite
        root = self.root / "empty"
        database = activate_sqlite(root, offline_confirmed=True)
        (root / "sqlite-active.json").unlink()
        self.assertEqual(activate_sqlite(root, offline_confirmed=True), database)
        self.assertEqual(SQLiteClassRepository(database).listar(), [])

    def test_invalid_existing_database(self):
        import sqlite3
        path = self.root / "invalid.sqlite3"
        sqlite3.connect(path).close()
        with self.assertRaises(ValueError):
            SQLiteClassRepository.validate_existing(path)

    def test_independent_process_writers(self):
        import subprocess
        class_id = self.repository.crear_clase("math", "Math", "manual")
        agent = str(Path(__file__).resolve().parents[1] / "agente")
        script = "import sys; sys.path.insert(0, sys.argv[1]); from infrastructure.sqlite_store import SQLiteClassRepository; r=SQLiteClassRepository(sys.argv[2]); [r.anadir_segmentos(sys.argv[3], [{'ini': i, 'fin': i+1, 'texto': 'word'}]) for i in range(20)]"
        processes = [subprocess.Popen([sys.executable, "-c", script, agent, str(self.path), class_id]) for _ in range(3)]
        for process in processes:
            self.assertEqual(process.wait(timeout=60), 0)
        self.assertEqual(self.repository.listar()[0]["n_segmentos"], 60)

    def test_mandatory_storage_preserves_legacy_backup(self):
        from infrastructure.storage_activation import ensure_sqlite
        root = self.root / "mandatory"
        source = root / "clases"
        source.mkdir(parents=True)
        class_id = self.repository.crear_clase("math", "Math", "manual")
        record = self.repository.leer(class_id)
        filename = class_id + ".json"
        (source / filename).write_text(json.dumps(record), encoding="utf-8")
        database = ensure_sqlite(root)
        self.assertFalse(source.exists())
        self.assertEqual(json.loads((root / "clases-json-backup" / filename).read_text(encoding="utf-8")), record)
        self.assertEqual(SQLiteClassRepository(database).leer(class_id), record)
        self.assertEqual(ensure_sqlite(root), database)


if __name__ == "__main__":
    unittest.main()
