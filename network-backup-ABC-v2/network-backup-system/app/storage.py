"""Lưu phiên bản cấu hình và restore point, không giao tiếp với thiết bị."""

import hashlib
import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.contracts import BackupError
from app.security import private_dir, private_file


PROJECT_DIR = Path(__file__).resolve().parents[1]


def _resolve_path(path):
    resolved = Path(path).resolve()
    # Windows có thể trả đường dẫn extended-length khi thư mục đang được tạo.
    # Chuẩn hóa prefix trước khi so sánh với thư mục dự án.
    if os.name == "nt":
        value = str(resolved)
        if value.startswith("\\\\?\\UNC\\"):
            resolved = Path("\\\\" + value[8:])
        elif value.startswith("\\\\?\\"):
            resolved = Path(value[4:])
    return resolved


@dataclass(frozen=True)
class BackupRecord:
    """Metadata công khai theo hợp đồng B; đường dẫn tương đối với dự án."""

    backup_id: int
    device_name: str
    platform: str
    created_at: str
    file_path: str
    sha256: str


class BackupStorage:
    """Mỗi thao tác mở connection riêng, dùng được từ nhiều worker.

    Hai file được ghi xong trước khi commit metadata trong một transaction.
    Chỉ các phiên bản có metadata đã commit mới được trả về cho bên gọi.
    """

    def __init__(self, project_dir=None):
        self.project_dir = _resolve_path(project_dir or PROJECT_DIR)
        self.db_path = self._safe_path("data/app.db")
        try:
            private_dir(self.db_path.parent)
            with private_file(self.db_path):
                pass
            with self._connection() as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.executescript("""
                    CREATE TABLE IF NOT EXISTS backups (
                        backup_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_name TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        file_path TEXT NOT NULL UNIQUE,
                        sha256 TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_backups_device_time
                        ON backups(device_name, created_at, backup_id);
                    CREATE TABLE IF NOT EXISTS restore_points (
                        backup_id INTEGER PRIMARY KEY
                            REFERENCES backups(backup_id),
                        file_path TEXT NOT NULL UNIQUE,
                        sha256 TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS baselines (
                        device_name TEXT PRIMARY KEY,
                        backup_id INTEGER NOT NULL REFERENCES backups(backup_id)
                    );
                """)
        except OSError as exc:
            raise BackupError("Khong tao duoc thu muc database.") from exc

    def _safe_path(self, relative_path):
        path = Path(relative_path)
        if path.is_absolute():
            raise BackupError("Duong dan ban sao phai la duong dan tuong doi.")
        resolved = _resolve_path(self.project_dir / path)
        if not resolved.is_relative_to(self.project_dir):
            raise BackupError("Duong dan nam ngoai thu muc du an.")
        return resolved

    @contextmanager
    def _connection(self):
        connection = None
        try:
            connection = sqlite3.connect(self.db_path, timeout=30)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                yield connection
        except sqlite3.Error as exc:
            raise BackupError("Thao tac SQLite that bai.") from exc
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _record(row):
        if row is None:
            raise BackupError("Khong tim thay ban sao.")
        return BackupRecord(**dict(row))

    def save_backup(self, device_name, platform, config_text, restore_point):
        """Lưu nguyên hai chuỗi UTF-8 và liên kết chúng với cùng backup_id.

        restore_point phải do A.create_restore_point() cung cấp; tầng này
        không phân tích hoặc sửa gói phục hồi theo từng nền tảng.
        """
        if not isinstance(device_name, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]+", device_name
        ):
            raise BackupError("Ten thiet bi khong hop le.")
        if not isinstance(platform, str) or not platform.strip():
            raise BackupError("Thieu platform cua thiet bi.")
        if not isinstance(config_text, str) or not config_text.strip():
            raise BackupError("Cau hinh phai la chuoi khong rong.")
        if not isinstance(restore_point, str) or not restore_point.strip():
            raise BackupError("Restore point phai la chuoi khong rong.")

        now = datetime.now(timezone.utc)
        # UUID tránh trùng tên ngay cả khi nhiều worker có cùng microsecond.
        stem = f"{device_name}_{now:%Y%m%d_%H%M%S_%f}_{uuid4().hex}"
        config_path = f"backups/{device_name}/{stem}.cfg"
        point_path = f"backups/{device_name}/{stem}.restore"
        created_files = []
        try:
            config_bytes = config_text.encode("utf-8")
            point_bytes = restore_point.encode("utf-8")
            for relative_path, content in (
                (config_path, config_bytes), (point_path, point_bytes)
            ):
                path = self._safe_path(relative_path)
                private_dir(self.project_dir / "backups")
                private_dir(path.parent)
                with private_file(path, exclusive=True) as stream:
                    created_files.append(path)
                    stream.write(content)

            config_hash = hashlib.sha256(config_bytes).hexdigest()
            point_hash = hashlib.sha256(point_bytes).hexdigest()
            with self._connection() as connection:
                cursor = connection.execute(
                    """INSERT INTO backups
                       (device_name, platform, created_at, file_path, sha256)
                       VALUES (?, ?, ?, ?, ?)""",
                    (device_name, platform, now.isoformat(),
                     config_path, config_hash),
                )
                backup_id = cursor.lastrowid
                connection.execute(
                    "INSERT INTO restore_points VALUES (?, ?, ?)",
                    (backup_id, point_path, point_hash),
                )
            return BackupRecord(
                backup_id, device_name, platform, now.isoformat(),
                config_path, config_hash,
            )
        except (OSError, UnicodeError, BackupError) as exc:
            for path in created_files:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    # Không che lỗi gốc; file mồ côi không có metadata.
                    pass
            if isinstance(exc, BackupError):
                raise
            raise BackupError("Khong ghi duoc file ban sao.") from exc

    def get_backup(self, backup_id):
        """Tra metadata theo ID; phát sinh BackupError nếu không tồn tại."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM backups WHERE backup_id = ?", (backup_id,)
            ).fetchone()
        return self._record(row)

    def list_backups(self, device_name):
        """Trả phiên bản mới nhất trước; không có phiên bản thì trả []."""
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT * FROM backups WHERE device_name = ?
                   ORDER BY created_at DESC, backup_id DESC""", (device_name,)
            ).fetchall()
        return [self._record(row) for row in rows]

    def _read_verified(self, file_path, expected_hash):
        try:
            content = self._safe_path(file_path).read_bytes()
            if hashlib.sha256(content).hexdigest() != expected_hash:
                raise BackupError(
                    "Ma bam SHA256 khong khop; ban sao da bi thay doi.")
            return content.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise BackupError("Khong doc duoc file ban sao UTF-8.") from exc

    def read_backup(self, backup_id):
        """Đọc văn bản cấu hình và kiểm tra SHA256 trước khi trả dữ liệu."""
        record = self.get_backup(backup_id)
        return self._read_verified(record.file_path, record.sha256)

    def read_restore_point(self, backup_id):
        """Đọc gói phục hồi nguyên bản sau khi kiểm tra SHA256."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT file_path, sha256 FROM restore_points WHERE backup_id = ?",
                (backup_id,),
            ).fetchone()
        if row is None:
            raise BackupError("Khong tim thay restore point cua ban sao.")
        return self._read_verified(row["file_path"], row["sha256"])

    def set_baseline(self, device_name, backup_id):
        # Kiểm tra cả hai file trước khi chấp nhận bản chuẩn.
        """Chọn bản sao đúng chủ sở hữu và còn toàn vẹn làm cấu hình chuẩn."""
        record = self.get_backup(backup_id)
        if record.device_name != device_name:
            raise BackupError("Ban sao khong thuoc thiet bi duoc chon.")
        self.read_backup(backup_id)
        self.read_restore_point(backup_id)
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO baselines(device_name, backup_id) VALUES (?, ?)
                   ON CONFLICT(device_name) DO UPDATE SET backup_id=excluded.backup_id""",
                (device_name, backup_id),
            )

    def get_baseline(self, device_name):
        """Tra baseline của thiết bị; báo lỗi rõ khi chưa được chọn."""
        with self._connection() as connection:
            row = connection.execute(
                """SELECT b.* FROM backups b JOIN baselines s
                   ON b.backup_id = s.backup_id WHERE s.device_name = ?""",
                (device_name,),
            ).fetchone()
        if row is None:
            raise BackupError("Thiet bi chua co baseline.")
        return self._record(row)
