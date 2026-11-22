"""Adapter dành riêng cho giao diện Web; KHÔNG thay đổi API A/B/C.

Mọi thao tác SSH chỉ chạy khi người dùng bấm nút. Không chứa mật khẩu,
không tiết lộ raw output/config trong báo cáo.
"""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import threading

from app.backup import BackupService
from app.config_service import ConfigService
from app.contracts import DeviceInfo
from app.inventory import InventoryManager
from app.reporting import ReportService
from app.runner import TaskRunner, safe_data
from app.scheduler import BackupScheduler, load_schedule

ROOT = Path(__file__).resolve().parents[1]


class WebController:
    def __init__(self, inventory_path=None, workers=4, backup_service=None, runner=None):
        self.inventory = InventoryManager(inventory_path or ROOT / 'inventory/devices.yaml')
        self.backups = backup_service if backup_service is not None else BackupService()
        self.runner = runner if runner is not None else TaskRunner(max_workers=workers)
        self.configs = ConfigService(backup_service=self.backups)
        self.reports = ReportService()

    def devices(self, group=None, role=None, tag=None):
        return self.inventory.filter(group=group or None, role=role or None, tag=tag or None)

    def selected(self, names):
        if not names:
            raise ValueError('Phải chọn ít nhất một thiết bị.')
        all_devices = self.inventory.load()
        name_set = set(names)
        if len(name_set) != len(names) or not name_set.issubset({x.name for x in all_devices}):
            raise ValueError('Tên thiết bị không hợp lệ hoặc bị trùng.')
        return [x for x in all_devices if x.name in name_set]

    def add_device(self, fields):
        self.inventory.add(InventoryManager._parse_device(fields))

    def update_device(self, name, fields):
        self.inventory.update(name, fields)

    def delete_device(self, name):
        self.inventory.delete(name)

    def run_task(self, names, task):
        funcs = {
            'facts': lambda d: d.get_normalized_facts(),
            'backup': lambda d: self.backups.create_backup(d),
            'check': lambda d: self.backups.check_changes(d),
        }
        if task not in funcs:
            raise ValueError('Tác vụ không hỗ trợ.')
        return self.runner.run(self.selected(names), task, funcs[task])

    def history(self, device_name):
        self.selected([device_name])
        return self.backups.list_backups(device_name)

    def diff(self, first, second):
        return self.backups.compare(first, second)

    def baseline(self, name, backup_id):
        self.selected([name])
        return self.backups.set_baseline(name, backup_id)

    def restore(self, name, backup_id, checks):
        if not isinstance(checks, dict) or not checks:
            raise ValueError('Phải cung cấp điều kiện xác minh.')
        return self.runner.run(self.selected([name]), 'restore',
                               lambda device: self.backups.restore(device, backup_id, checks))

    def preview(self, names, template, variables):
        text = self.configs.render(template, variables)
        return text, [self.configs.dry_run(info, text) for info in self.selected(names)]

    def apply(self, names, template, variables, checks):
        if not isinstance(checks, dict) or not checks:
            raise ValueError('Phải cung cấp điều kiện xác minh.')
        text, previews = self.preview(names, template, variables)
        if not all(p['valid'] for p in previews):
            raise ValueError('Dry-run không đạt; chưa áp dụng cấu hình.')
        return self.runner.run(self.selected(names), 'apply',
                               lambda device: self.configs.apply(device, text, checks))

    def report(self, results, fmt):
        if fmt not in ('csv', 'json'):
            raise ValueError('Định dạng báo cáo không hợp lệ.')
        now = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        return Path(self.reports.export(results, ROOT / 'reports' / f'web_{now}.{fmt}', fmt))

    def schedule(self, path):
        # B tự kiểm tra YAML, C cung cấp runner.
        entries = load_schedule(path)
        return BackupScheduler(entries, self.inventory.load(), self.runner, self.backups)


def launch_scheduler(scheduler):
    """Chạy lịch trong một luồng riêng, dừng qua scheduler.stop()."""
    worker = threading.Thread(target=scheduler.run_forever,
                              name='web-backup-scheduler', daemon=True)
    worker.start()
    return worker


def clean_table(data):
    return [safe_data(asdict(x)) for x in data]
