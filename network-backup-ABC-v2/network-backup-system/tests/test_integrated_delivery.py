"""Integration probes with fake devices; no SSH or actual credentials."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.backup import BackupService
from app.contracts import DeviceInfo
from app.reporting import ReportService
from app.runner import TaskRunner
from app.scheduler import BackupScheduler, ScheduleEntry
from app.storage import BackupStorage
from test_backup import FakeDevice


class OfflineFactory:
    @staticmethod
    def create(info):
        device = FakeDevice(info.name, info.platform)
        device.connect = lambda: None
        device.disconnect = lambda: None
        return device


class IntegratedDeliveryTests(unittest.TestCase):
    def test_diff_is_excluded_from_runner_and_both_report_formats(self):
        marker = 'DUMMY_SECRET_IN_DIFF_ONLY'
        info = DeviceInfo('R1', '192.0.2.1', 22, 'cisco_ios',
                          'lab', 'router', [], 'LAB')
        with tempfile.TemporaryDirectory() as folder:
            backup = BackupService(BackupStorage(folder))
            device = OfflineFactory.create(info)
            baseline = backup.create_backup(device)
            backup.set_baseline(info.name, baseline.backup_id)
            device.config += f'username lab secret 0 {marker}\n'
            drift = backup.check_changes(device)
            self.assertTrue(drift['changed'])
            self.assertIn(marker, drift['diff'])
            results = TaskRunner(factory=OfflineFactory).run(
                [info], 'check', lambda connected: {
                    **drift, 'nested': {'diff': drift['diff'], 'preview': marker},
                },
            )
            self.assertEqual(results[0].status, 'success')
            self.assertTrue(results[0].data['changed'])
            self.assertNotIn('diff', results[0].data)
            with patch('app.reporting.PROJECT_DIR', Path(folder)):
                for format in ('json', 'csv'):
                    with self.subTest(format=format):
                        path = Path(folder) / 'reports' / f'result.{format}'
                        ReportService().export(results, path, format)
                        self.assertNotIn(
                            marker, path.read_text(encoding='utf-8-sig'))

    def test_scheduler_runner_storage_save_two_rounds(self):
        infos = [DeviceInfo(name, host, 22, 'cisco_ios', 'lab', 'router', [], 'LAB')
                 for name, host in [('R1', '192.0.2.1'), ('R2', '192.0.2.2')]]
        with tempfile.TemporaryDirectory() as folder:
            backups = BackupService(BackupStorage(folder))
            clock = [0]
            scheduler = BackupScheduler(
                [ScheduleEntry(info.name, 1) for info in infos], infos,
                TaskRunner(factory=OfflineFactory), backups, clock=lambda: clock[0],
            )
            try:
                for tick in (1, 2):
                    clock[0] = tick
                    futures = scheduler.run_pending()
                    self.assertEqual(set(futures), {'R1', 'R2'})
                    for future in futures.values():
                        self.assertEqual(future.result(timeout=5)[
                                         0].status, 'success')
            finally:
                scheduler.close()
            for info in infos:
                records = backups.list_backups(info.name)
                self.assertEqual(len(records), 2)
                self.assertNotEqual(records[0].file_path, records[1].file_path)
                for record in records:
                    self.assertIn(
                        info.name, backups.read_backup(record.backup_id))
                    self.assertTrue(
                        backups.storage.read_restore_point(record.backup_id))


if __name__ == '__main__':
    unittest.main()
