import hashlib
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.contracts import BackupError
from app.storage import BackupStorage


class BackupStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix="storage_test_", dir=Path(__file__).resolve().parents[1]
        )
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.storage = BackupStorage(self.root)

    def save(self, name="R1", config="hostname R1\n", point="hostname R1\n"):
        return self.storage.save_backup(name, "cisco_ios", config, point)

    def test_round_trip_preserves_unicode_and_line_endings(self):
        text = "hostname R1\r\n! mô tả\r\n"
        point = '{"binary_base64":"AAEC", "metadata":"mẫu"}\n'
        record = self.save(config=text, point=point)
        self.assertEqual(self.storage.read_backup(record.backup_id), text)
        self.assertEqual(self.storage.read_restore_point(
            record.backup_id), point)
        self.assertEqual(record.sha256, hashlib.sha256(
            text.encode()).hexdigest())
        self.assertFalse(Path(record.file_path).is_absolute())
        self.assertIsNotNone(datetime.fromisoformat(
            record.created_at).utcoffset())
        self.assertEqual(self.storage.get_backup(record.backup_id), record)

    def test_versions_survive_reopening_and_filter_by_device(self):
        first = self.save()
        second = self.save(config="hostname R1\n! updated\n")
        self.save(name="R2")
        reopened = BackupStorage(self.root)
        self.assertEqual(reopened.list_backups("R1"), [second, first])
        self.assertEqual(reopened.list_backups("missing"), [])
        self.assertNotEqual(first.file_path, second.file_path)
        self.assertEqual(reopened.read_backup(
            first.backup_id), "hostname R1\n")

    def test_baseline_is_reference_and_rejects_other_device(self):
        first = self.save()
        second = self.save(config="hostname R1\n! new\n")
        with self.assertRaisesRegex(BackupError, "chua co baseline"):
            self.storage.get_baseline("R1")
        self.storage.set_baseline("R1", first.backup_id)
        self.assertEqual(self.storage.get_baseline("R1"), first)
        self.storage.set_baseline("R1", second.backup_id)
        self.assertEqual(self.storage.get_baseline("R1"), second)
        with self.assertRaises(BackupError):
            self.storage.set_baseline("R2", first.backup_id)
        self.assertEqual(self.storage.read_backup(
            first.backup_id), "hostname R1\n")

    def test_tampered_or_missing_configuration_is_rejected(self):
        record = self.save()
        path = self.root / record.file_path
        path.write_bytes(b"changed")
        with self.assertRaisesRegex(BackupError, "SHA256"):
            self.storage.read_backup(record.backup_id)
        with self.assertRaises(BackupError):
            self.storage.set_baseline("R1", record.backup_id)
        path.unlink()
        with self.assertRaises(BackupError):
            self.storage.read_backup(record.backup_id)

    def test_tampered_restore_point_is_rejected(self):
        record = self.save()
        path = next((self.root / "backups/R1").glob("*.restore"))
        path.write_bytes(b"changed")
        with self.assertRaisesRegex(BackupError, "SHA256"):
            self.storage.read_restore_point(record.backup_id)

    def test_missing_ids_are_reported(self):
        for operation in (self.storage.get_backup, self.storage.read_restore_point):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(BackupError):
                    operation(12345)

    def test_invalid_names_and_empty_content_are_rejected(self):
        for name in ("../R1", "R 1", "", "R1/other", "R1\\other"):
            with self.subTest(name=name), self.assertRaises(BackupError):
                self.save(name=name)
        for kwargs in ({"config": ""}, {"point": ""}, {"point": None}):
            with self.subTest(kwargs=kwargs), self.assertRaises(BackupError):
                self.save(**kwargs)
        self.assertEqual(self.storage.list_backups("R1"), [])

    def test_database_path_cannot_escape_project(self):
        record = self.save()
        with closing(sqlite3.connect(self.storage.db_path)) as connection, connection:
            connection.execute(
                "UPDATE backups SET file_path = ? WHERE backup_id = ?",
                ("../outside.cfg", record.backup_id),
            )
        with self.assertRaisesRegex(BackupError, "ngoai thu muc"):
            self.storage.read_backup(record.backup_id)

    def test_database_failure_rolls_back_metadata_and_files(self):
        # Lỗi ở INSERT thứ hai phải rollback cả INSERT thứ nhất.
        with closing(sqlite3.connect(self.storage.db_path)) as connection, connection:
            connection.execute("""CREATE TRIGGER reject_point BEFORE INSERT ON restore_points
                BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
        with self.assertRaises(BackupError):
            self.save()
        self.assertEqual(self.storage.list_backups("R1"), [])
        self.assertEqual(list((self.root / "backups").rglob("*.cfg")), [])
        self.assertEqual(list((self.root / "backups").rglob("*.restore")), [])

    def test_file_failure_does_not_publish_metadata(self):
        from app.security import private_file
        original_open = private_file

        def fail_point(path, *args, **kwargs):
            if path.suffix == ".restore":
                raise OSError("simulated disk failure")
            return original_open(path, *args, **kwargs)

        with patch("app.storage.private_file", fail_point):
            with self.assertRaises(BackupError):
                self.save()
        self.assertEqual(self.storage.list_backups("R1"), [])
        self.assertEqual(list((self.root / "backups").rglob("*.cfg")), [])

    def test_parallel_workers_get_distinct_versions_and_intact_files(self):
        def save(index):
            text = f"hostname R1\n! version {index}\n"
            record = self.save(config=text, point=text)
            return record, text

        with ThreadPoolExecutor(max_workers=8) as pool:
            saved = list(pool.map(save, range(24)))
        self.assertEqual(len({record.backup_id for record, _ in saved}), 24)
        self.assertEqual(len({record.file_path for record, _ in saved}), 24)
        self.assertEqual(len(self.storage.list_backups("R1")), 24)
        for record, text in saved:
            self.assertEqual(self.storage.read_backup(record.backup_id), text)
            self.assertEqual(self.storage.read_restore_point(
                record.backup_id), text)


if __name__ == "__main__":
    unittest.main()
