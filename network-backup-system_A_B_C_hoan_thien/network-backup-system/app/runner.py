"""Phần C: điều phối độc lập theo thiết bị; quản lý vòng đời SSH."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from time import perf_counter
import logging

from app.devices.factory import DeviceFactory


@dataclass
class TaskResult:
    device: str
    task: str
    status: str
    started_at: str
    duration_seconds: float
    data: dict = field(default_factory=dict)
    error: dict | None = None


def safe_data(value):
    """Chỉ giữ metadata, không xuất raw output/config/credentials của thiết bị."""
    sensitive = {'output', 'config', 'config_text', 'restore_point', 'password',
                 'secret', 'token', 'binary_base64', 'private_key'}
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {str(k): safe_data(v) for k, v in value.items()
                if str(k).lower() not in sensitive}
    if isinstance(value, (list, tuple)):
        return [safe_data(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(type(value).__name__)


class TaskRunner:
    def __init__(self, max_workers=4, factory=None, logger=None):
        if type(max_workers) is not int or max_workers < 1:
            raise ValueError('max_workers phai la so nguyen duong.')
        self.max_workers = max_workers
        self.factory = factory if factory is not None else DeviceFactory
        self.logger = logger or logging.getLogger(__name__)

    def _one(self, info, task_name, task_callable):
        start = datetime.now(timezone.utc).astimezone().isoformat()
        tick = perf_counter()
        device = None
        data = {}
        error = None
        try:
            device = self.factory.create(info)
            device.connect()
            result = task_callable(device)
            data = safe_data(result)
            if not isinstance(data, dict):
                data = {'result': data}
            status = 'success'
        except Exception as exc:
            status = 'failed'
            error = {'type': type(exc).__name__, 'message': 'Tac vu that bai; xem log va thiet bi.'}
            if hasattr(exc, 'result_data'):
                data = safe_data(exc.result_data)
            for attr in ('pre_backup_id', 'backup_id', 'stage'):
                if hasattr(exc, attr):
                    data[attr] = safe_data(getattr(exc, attr))
            self.logger.error('task_failed device=%s task=%s error_type=%s',
                              info.name, task_name, type(exc).__name__)
        finally:
            if device is not None:
                try:
                    device.disconnect()
                except Exception as exc:
                    self.logger.error('disconnect_failed device=%s error_type=%s',
                                      info.name, type(exc).__name__)
                    if error is None:
                        status = 'failed'
                        error = {'type': type(exc).__name__, 'message': 'Khong dong duoc ket noi.'}
        result = TaskResult(info.name, task_name, status, start,
                            round(perf_counter() - tick, 4), data, error)
        self.logger.info('task_completed device=%s task=%s status=%s',
                         info.name, task_name, status)
        return result

    def run(self, device_infos, task_name, task_callable):
        infos = list(device_infos)
        if len({info.name for info in infos}) != len(infos):
            raise ValueError('Danh sach thiet bi co ten trung.')
        if not infos:
            return []
        results = [None] * len(infos)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(self._one, info, task_name, task_callable): index
                for index, info in enumerate(infos)
            }
            for future in as_completed(future_map):
                results[future_map[future]] = future.result()
        return results
