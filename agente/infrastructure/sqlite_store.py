"""Experimental SQLite repository preserving the legacy class record contract."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


class SQLiteClassRepository:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS classes (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS segments (class_id TEXT NOT NULL REFERENCES classes(id) ON DELETE CASCADE, position INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(class_id, position))")
            connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")
            connection.execute("INSERT OR IGNORE INTO schema_migrations VALUES (1)")
            connection.execute("CREATE TABLE IF NOT EXISTS completed_items (item_key TEXT PRIMARY KEY)")

    @staticmethod
    def validate_existing(path):
        path = Path(path).resolve()
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if not {"classes", "segments", "completed_items", "schema_migrations"}.issubset(tables):
                raise ValueError("Invalid SQLite schema")
            if connection.execute("SELECT version FROM schema_migrations").fetchall() != [(1,)]:
                raise ValueError("Unsupported SQLite schema version")
        finally:
            connection.close()

    @contextmanager
    def transaction(self, write=True):
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _encode(value):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)

    @staticmethod
    def _validate_id(class_id):
        if not class_id or "/" in class_id or chr(92) in class_id or ".." in class_id:
            raise ValueError("Invalid class ID")

    def _read(self, connection, class_id):
        self._validate_id(class_id)
        row = connection.execute("SELECT payload FROM classes WHERE id = ?", (class_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(class_id)
        record = json.loads(row[0])
        record["segmentos"] = [json.loads(row[0]) for row in connection.execute(
            "SELECT payload FROM segments WHERE class_id = ? ORDER BY position", (class_id,))]
        return record

    def _append(self, connection, class_id, segments):
        start = connection.execute("SELECT COALESCE(MAX(position) + 1, 0) FROM segments WHERE class_id = ?", (class_id,)).fetchone()[0]
        connection.executemany("INSERT INTO segments VALUES (?, ?, ?)",
                               ((class_id, start + index, self._encode(segment)) for index, segment in enumerate(segments)))

    def _insert(self, connection, record):
        payload = dict(record)
        class_id = payload["id"]
        self._validate_id(class_id)
        segments = payload.pop("segmentos", [])
        connection.execute("INSERT INTO classes VALUES (?, ?)", (class_id, self._encode(payload)))
        self._append(connection, class_id, segments)

    def crear_clase(self, asignatura, nombre, modo, inicio=None, aula=""):
        start = inicio or datetime.now()
        base_id = f"{start:%Y-%m-%d_%H%M%S}_{asignatura}"
        with self.transaction() as connection:
            class_id = base_id
            suffix = 1
            while connection.execute("SELECT 1 FROM classes WHERE id = ?", (class_id,)).fetchone():
                class_id = f"{base_id}_{suffix}"
                suffix += 1
            self._insert(connection, {
                "id": class_id, "asignatura": asignatura, "nombre_asignatura": nombre,
                "aula": aula, "modo": modo, "fecha": f"{start:%Y-%m-%d}",
                "inicio": start.isoformat(timespec="seconds"), "fin": None,
                "en_curso": True, "segmentos": [], "estado_resumen": "pendiente",
                "resumen": None, "error_resumen": None,
            })
        return class_id

    def leer(self, cid):
        with self.transaction(write=False) as connection:
            return self._read(connection, cid)

    def _update(self, connection, class_id, fields):
        record = self._read(connection, class_id)
        if fields.get("id", class_id) != class_id:
            raise ValueError("Cannot change class ID")
        record.update(fields)
        payload = dict(record)
        segments = payload.pop("segmentos")
        connection.execute("UPDATE classes SET payload = ? WHERE id = ?", (self._encode(payload), class_id))
        if "segmentos" in fields:
            connection.execute("DELETE FROM segments WHERE class_id = ?", (class_id,))
            self._append(connection, class_id, segments)
        return record

    def actualizar(self, cid, **campos):
        with self.transaction() as connection:
            return self._update(connection, cid, campos)

    def anadir_segmentos(self, cid, segmentos):
        if not segmentos:
            return
        self._validate_id(cid)
        with self.transaction() as connection:
            if not connection.execute("SELECT 1 FROM classes WHERE id = ?", (cid,)).fetchone():
                raise FileNotFoundError(cid)
            self._append(connection, cid, segmentos)

    def cerrar(self, cid, fin=None):
        return self.actualizar(cid, fin=(fin or datetime.now()).isoformat(timespec="seconds"), en_curso=False)

    def listar(self, incluir_segmentos=False):
        with self.transaction(write=False) as connection:
            records = []
            for class_id, payload in connection.execute("SELECT id, payload FROM classes ORDER BY id DESC"):
                if incluir_segmentos:
                    record = self._read(connection, class_id)
                else:
                    record = json.loads(payload)
                    count = words = duration = 0
                    for (segment_payload,) in connection.execute("SELECT payload FROM segments WHERE class_id = ? ORDER BY position", (class_id,)):
                        segment = json.loads(segment_payload)
                        count += 1
                        words += len(segment["texto"].split())
                        duration = int(segment["fin"])
                    record.update(n_segmentos=count, palabras=words, duracion_s=duration)
                records.append(record)
            return records

    def eliminar(self, cid):
        self._validate_id(cid)
        with self.transaction() as connection:
            if not connection.execute("DELETE FROM classes WHERE id = ?", (cid,)).rowcount:
                raise FileNotFoundError(cid)

    @contextmanager
    def summary_job(self, cid, *, retry_completed=False, log=print):
        """Serialize local jobs and recover abandoned states under OS locks."""
        import hashlib
        import time
        from infrastructure.file_lock import try_file_lock
        self._validate_id(cid)
        directory = self.path.parent / "summary-locks"
        key = hashlib.sha256(cid.encode("utf-8")).hexdigest()
        with try_file_lock(str(directory / (key + ".lock"))) as owned:
            if not owned:
                yield False
                return
            record = self.leer(cid)
            if record.get("en_curso") or (record.get("estado_resumen") == "listo" and not retry_completed):
                yield False
                return
            self.actualizar(cid, estado_resumen="en_cola", error_resumen=None)
            log(f"Resumen en cola: {cid}")
            while True:
                with try_file_lock(str(directory / "queue.lock")) as ready:
                    if ready:
                        log(f"Iniciando resumen: {cid}")
                        yield True
                        return
                time.sleep(0.5)

    def claim_summary(self, cid):
        with self.transaction() as connection:
            if self._read(connection, cid).get("estado_resumen") == "generando":
                return False
            self._update(connection, cid, {"estado_resumen": "generando", "error_resumen": None})
            return True

    def import_records(self, records, completed_items=()):
        """Import a snapshot atomically; reject conflicting records rather than overwrite."""
        imported = 0
        with self.transaction() as connection:
            for record in records:
                class_id = record["id"]
                try:
                    existing = self._read(connection, class_id)
                except FileNotFoundError:
                    self._insert(connection, record)
                    imported += 1
                else:
                    if existing != record:
                        raise ValueError(f"Conflicting class: {class_id}")
            connection.executemany("INSERT OR IGNORE INTO completed_items VALUES (?)", ((key,) for key in completed_items))
        return imported

    def leer_estado(self):
        with self.transaction(write=False) as connection:
            return {"hechos": [row[0] for row in connection.execute(
                "SELECT item_key FROM completed_items ORDER BY item_key")]}

    def marcar_hecho(self, clave, hecho):
        with self.transaction() as connection:
            if hecho:
                connection.execute("INSERT OR IGNORE INTO completed_items VALUES (?)", (clave,))
            else:
                connection.execute("DELETE FROM completed_items WHERE item_key = ?", (clave,))
            return {"hechos": [row[0] for row in connection.execute(
                "SELECT item_key FROM completed_items ORDER BY item_key")]}

    def clases_abiertas_huerfanas(self):
        return [record["id"] for record in self.listar() if record.get("en_curso")]
