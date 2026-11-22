"""Exercise public CLI, scheduler reports and log privacy with fake I/O."""
from contextlib import redirect_stdout
import io
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import main
from app.backup import BackupService
from app.logging_setup import PrivateRotatingHandler, setup_logging
from app.runner import TaskRunner
from app.scheduler import BackupScheduler
from app.storage import BackupStorage
from test_integrated_delivery import OfflineFactory


class CliReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'inventory').mkdir()
        original = Path(main.__file__).parent
        shutil.copy(original / 'inventory/devices.yaml',
                    self.root / 'inventory/devices.yaml')
        self.original = original
        self.patches = [patch.object(main, 'ROOT', self.root),
                        patch('app.reporting.PROJECT_DIR', self.root),
                        patch.object(main, 'setup_logging')]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def run_cli(self, args):
        with redirect_stdout(io.StringIO()) as stream:
            code = main.cli(args)
        return code, stream.getvalue()

    def test_inventory_filter_and_per_device_template_are_offline(self):
        with patch('app.runner.DeviceFactory.create', side_effect=AssertionError('Unexpected SSH')):
            code, output = self.run_cli(['inventory', '--role', 'switch'])
            self.assertEqual(code, 0)
            self.assertEqual([row['name']
                             for row in json.loads(output)], ['SW1'])
            variables = self.root / 'vars.yaml'
            variables.write_text('devices:\n  R1:\n    interface: FastEthernet1/0\n    description: FIRST\n'
                                 '  R2:\n    interface: FastEthernet1/0\n    description: SECOND\n')
            code, output = self.run_cli(['dry-run', '--devices', 'R1', 'R2', '--template',
                                        'cisco_interface.j2', '--vars', str(variables)])
            previews = json.loads(output)
            self.assertEqual(code, 0)
            self.assertIn('FIRST', previews[0]['preview'])
            self.assertIn('SECOND', previews[1]['preview'])

    def test_apply_and_ospf_require_confirmation_before_ssh(self):
        with patch('app.runner.DeviceFactory.create', side_effect=AssertionError('Unexpected SSH')):
            with self.assertRaises(ValueError):
                self.run_cli(['ospf', 'apply'])
            with self.assertRaises(ValueError):
                self.run_cli(['restore', '--device', 'R1',
                             '--backup-id', '1', '--checks', 'unused.yaml'])

    def test_scheduler_cli_exports_actual_two_round_results(self):
        service = BackupService(BackupStorage(self.root))
        schedule = self.root / 'schedule.yaml'
        schedule.write_text(
            'schedules:\n  - device: R1\n    interval_seconds: 1\n')
        original_constructor = BackupScheduler.from_yaml
        clock = [0]

        def build(path, infos, runner, backups, **kwargs):
            scheduler = original_constructor(
                path, infos, runner, backups, clock=lambda: clock[0], **kwargs)

            def two_rounds():
                try:
                    for tick in (1, 2):
                        clock[0] = tick
                        for future in scheduler.run_pending().values():
                            future.result(timeout=5)
                finally:
                    scheduler.close()

            scheduler.run_forever = two_rounds
            return scheduler

        with patch.object(main, 'BackupService', return_value=service), \
                patch.object(main, 'TaskRunner', side_effect=lambda **kw: TaskRunner(factory=OfflineFactory, **kw)), \
                patch.object(main.BackupScheduler, 'from_yaml', side_effect=build):
            code, output = self.run_cli(
                ['--report', 'json', 'scheduler', '--schedule', str(schedule)])
        self.assertEqual(code, 0)
        files = list((self.root / 'reports').glob('scheduled_backup_*.json'))
        self.assertEqual(len(files), 2)
        ids = {json.loads(file.read_text())[
            0]['data']['backup_id'] for file in files}
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(service.list_backups('R1')), 2)
        if os.name == 'posix':
            self.assertTrue(
                all(file.stat().st_mode & 0o777 == 0o600 for file in files))

    def test_rotated_log_has_actor_and_private_modes(self):
        logger = logging.getLogger('app')
        previous = list(logger.handlers)
        logger.handlers = []
        try:
            with patch('app.logging_setup.PROJECT_DIR', self.root), \
                    patch('app.logging_setup.getpass.getuser', return_value='lab_user'):
                setup_logging()
                handler = logger.handlers[0]
                handler.maxBytes = 120
                for index in range(8):
                    logger.info(
                        'device=R1 task=backup status=success index=%s', index)
                for item in logger.handlers:
                    item.flush()
                logs = list((self.root / 'logs').glob('operations.log*'))
                self.assertGreater(len(logs), 1)
                self.assertTrue(
                    all('actor=lab_user' in file.read_text() for file in logs))
                if os.name == 'posix':
                    self.assertTrue(
                        all(file.stat().st_mode & 0o777 == 0o600 for file in logs))
        finally:
            for handler in logger.handlers:
                handler.close()
            logger.handlers = previous


if __name__ == '__main__':
    unittest.main()
