"""Lịch interval trong tiến trình; runner của C sở hữu phiên thiết bị."""

import logging
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import TIMEOUT_MAX, Event, Lock

import yaml

from app.contracts import BackupError, DeviceInfo


@dataclass(frozen=True)
class ScheduleEntry:
    """Một lịch interval gắn với tên thiết bị trong inventory."""
    device: str
    interval_seconds: float


def _positive_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        return False


class _ScheduleLoader(yaml.SafeLoader):
    """Từ chối khóa lặp thay vì âm thầm dùng giá trị cuối."""


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise BackupError("Khoa YAML phai la chuoi va khong duoc lap.")
        result[key] = loader.construct_object(value_node)
    return result


_ScheduleLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping
)


def load_schedule(file_path):
    """Đọc YAML {schedules: [{device: R1, interval_seconds: 300}]}.

    Kiểm tra tên có trong inventory tại BackupScheduler.__init__().
    """
    try:
        with Path(file_path).open(encoding="utf-8") as stream:
            data = yaml.load(stream, Loader=_ScheduleLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise BackupError("Khong doc duoc file lich YAML.") from exc
    if not isinstance(data, dict) or set(data) != {"schedules"}:
        raise BackupError("YAML chi ho tro khoa schedules.")
    rows = data["schedules"]
    if not isinstance(rows, list) or not rows:
        raise BackupError("schedules phai la danh sach khong rong.")
    entries = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"device", "interval_seconds"}:
            raise BackupError("Moi lich can device va interval_seconds.")
        entries.append(ScheduleEntry(row["device"], row["interval_seconds"]))
    return _validate_entries(entries)


def _validate_entries(entries):
    entries = tuple(entries)
    if not entries:
        raise BackupError("Can it nhat mot lich sao luu.")
    names = set()
    for entry in entries:
        if (
            not isinstance(entry, ScheduleEntry)
            or not isinstance(entry.device, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]+", entry.device)
            or not _positive_number(entry.interval_seconds)
        ):
            raise BackupError(
                "Ten thiet bi hoac interval_seconds khong hop le.")
        if entry.device in names:
            raise BackupError("Moi thiet bi chi duoc khai bao mot lich.")
        names.add(entry.device)
    return entries


class BackupScheduler:
    """Gọi run([DeviceInfo], 'backup', create_backup) theo từng thiết bị.

    Runner.run phải chờ các worker của lượt đó hoàn tất trước khi trả về.
    Một Future đang chờ/chạy giữ chỗ thiết bị, kể cả khi thread pool đã đầy.
    Lượt đầu sau một interval; bỏ lượt quá hạn, không dồn việc để chạy bù.
    """

    def __init__(self, entries, device_infos, runner, backup_service, *,
                 max_workers=4, clock=time.monotonic, logger=None):
        entries = _validate_entries(entries)
        infos = {}
        for info in device_infos:
            if not isinstance(info, DeviceInfo) or info.name in infos:
                raise BackupError(
                    "Inventory can DeviceInfo va ten khong trung.")
            infos[info.name] = info
        if any(entry.device not in infos for entry in entries):
            raise BackupError(
                "Lich tham chieu thiet bi khong co trong inventory.")
        if type(max_workers) is not int or max_workers < 1:
            raise BackupError("max_workers phai la so nguyen duong.")
        if not callable(getattr(runner, "run", None)) or not callable(
            getattr(backup_service, "create_backup", None)
        ):
            raise BackupError(
                "Can runner.run va backup_service.create_backup.")
        self._entries = entries
        self._infos = infos
        self._runner = runner
        self._service = backup_service
        self._clock = clock
        self._logger = logger if logger is not None else logging.getLogger(
            __name__)
        now = clock()
        self._next_due = {e.device: now + e.interval_seconds for e in entries}
        self._active = {}
        self._lock = Lock()
        self._stop = Event()
        self._closed = False
        self._pool = ThreadPoolExecutor(max_workers=max_workers,
                                        thread_name_prefix="backup-schedule")

    @classmethod
    def from_yaml(cls, file_path, device_infos, runner, backup_service, **kwargs):
        """Đọc và kiểm tra lịch YAML trước khi tạo scheduler."""
        return cls(load_schedule(file_path), device_infos, runner, backup_service, **kwargs)

    def _execute(self, info):
        try:
            result = self._runner.run([info], "backup", self._backup_connected)
            self._logger.info("Scheduled runner finished device=%s", info.name)
            return result
        except Exception as exc:
            # Chỉ log loại lỗi, không log phản hồi SSH/cấu hình/mật khẩu.
            self._logger.error("Scheduled runner failed device=%s error_type=%s",
                               info.name, type(exc).__name__)
            raise

    def _backup_connected(self, device):
        try:
            return self._service.create_backup(device)
        except Exception as exc:
            self._logger.error("Scheduled backup failed device=%s error_type=%s",
                               device.name, type(exc).__name__)
            raise

    def run_pending(self):
        """Không chờ SSH; trả dict tên -> Future cho các lượt vừa gửi.

        future.result() giữ nguyên kết quả/ngoại lệ runner để C báo cáo.
        Lỗi một thiết bị không ngăn gửi việc cho thiết bị khác.
        """
        submitted = {}
        with self._lock:
            if self._closed or self._stop.is_set():
                return submitted
            now = self._clock()
            for entry in self._entries:
                name = entry.device
                if now < self._next_due[name]:
                    continue
                self._next_due[name] = now + entry.interval_seconds
                previous = self._active.get(name)
                if previous is not None and not previous.done():
                    self._logger.warning(
                        "Scheduled backup skipped busy device=%s", name)
                    continue
                try:
                    future = self._pool.submit(
                        self._execute, self._infos[name])
                except Exception as exc:
                    self._logger.error("Scheduled submit failed device=%s error_type=%s",
                                       name, type(exc).__name__)
                    continue
                self._active[name] = future
                submitted[name] = future
                self._logger.info("Scheduled backup submitted device=%s", name)
        return submitted

    def stop(self):
        """Ngừng nhận lượt mới và đánh thức vòng lặp; không ngắt SSH đang chạy."""
        with self._lock:
            self._stop.set()

    def close(self):
        """Dừng lịch, hủy lượt chưa chạy và chờ lượt đang chạy kết thúc."""
        with self._lock:
            self._stop.set()
            self._closed = True
        self._pool.shutdown(wait=True, cancel_futures=True)

    def run_forever(self, poll_seconds=1.0):
        """Chạy trên luồng hiện tại; stop() từ luồng khác hoặc Ctrl+C để dừng."""
        if not _positive_number(poll_seconds) or poll_seconds > TIMEOUT_MAX:
            raise BackupError(
                "poll_seconds phai duong va khong vuot threading.TIMEOUT_MAX.")
        try:
            while not self._stop.is_set():
                self.run_pending()
                self._stop.wait(poll_seconds)
        except KeyboardInterrupt:
            self.stop()
        finally:
            self.close()
