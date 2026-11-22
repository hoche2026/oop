"""Offline tests phần C (chạy sau khi pip install -r requirements.txt)."""
from dataclasses import dataclass
from pathlib import Path
import tempfile
import unittest

from app.contracts import DeviceInfo, VerificationResult
from app.runner import TaskRunner
from app.config_service import ConfigService, ConfigApplyError


INFO = DeviceInfo('R1', '127.0.0.1', 22, 'cisco_ios',
                  'lab', 'router', [], 'LAB')


class FakeDevice:
    def __init__(self, info, *, fail=False, verify_after=True):
        self.name = info.name
        self.fail = fail
        self.verify_after = verify_after
        self.connected = False
        self.disconnected = False
        self.applied = False
        self.restored = False

    def connect(self):
        if self.fail:
            raise RuntimeError('password SHOULD_NOT_LEAK')
        self.connected = True

    def disconnect(self):
        self.disconnected = True

    def push_config(self, value):
        self.applied = True
        return {'output': 'SECRET'}

    def verify_config(self, config, checks):
        passed = not self.applied or self.verify_after
        if checks.get('config_match'):
            return VerificationResult(self.restored, [], {'config_match': self.restored})
        return VerificationResult(passed, [], {'ping': passed})

    def restore_config(self, value):
        self.restored = True
        return {}


class FakeFactory:
    devices = []

    @classmethod
    def create(cls, info):
        device = FakeDevice(info, fail=info.name == 'FAIL')
        cls.devices.append(device)
        return device


class FakeStorage:
    def read_restore_point(self, backup_id):
        return 'RESTORE_POINT'

    def read_backup(self, backup_id):
        return 'ORIGINAL_CONFIG'


@dataclass
class FakeRecord:
    backup_id: int = 42


class FakeBackupService:
    storage = FakeStorage()

    def create_backup(self, device):
        return FakeRecord()

    @staticmethod
    def _validate_verification(value, checks):
        assert isinstance(value, VerificationResult)
        assert set(checks).issubset(value.checks)


class PartCTests(unittest.TestCase):
    def test_runner_isolates_failures_and_disconnects(self):
        FakeFactory.devices.clear()
        info_bad = DeviceInfo('FAIL', '127.0.0.2', 22,
                              'cisco_ios', 'lab', 'router', [], 'LAB')
        runner = TaskRunner(max_workers=2, factory=FakeFactory)
        result = runner.run([INFO, info_bad], 'demo', lambda d: {
                            'ok': True, 'output': 'sensitive'})
        self.assertEqual([x.status for x in result], ['success', 'failed'])
        self.assertEqual(result[0].data, {'ok': True})
        self.assertNotIn('SHOULD_NOT_LEAK', str(result))
        self.assertTrue(all(d.disconnected for d in FakeFactory.devices))

    def test_dry_run_and_jinja_missing_variable(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'demo.j2').write_text(
                'interface {{ interface }}', encoding='utf8')
            service = ConfigService(FakeBackupService(), folder)
            with self.assertRaises(ValueError):
                service.render('demo.j2', {})
            text = service.render('demo.j2', {'interface': 'FastEthernet0/0'})
            self.assertTrue(service.dry_run(INFO, text)['valid'])
            self.assertFalse(service.dry_run(INFO, 'reload')['valid'])

    def test_apply_success(self):
        service = ConfigService(FakeBackupService())
        device = FakeDevice(INFO)
        result = service.apply(device, 'description demo', {
                               'ping': {'target': '1.1.1.1'}})
        self.assertTrue(result['verified'])
        self.assertEqual(result['pre_backup_id'], 42)
        self.assertFalse(device.restored)

    def test_failed_verification_invokes_rollback_once(self):
        service = ConfigService(FakeBackupService())
        device = FakeDevice(INFO, verify_after=False)
        with self.assertRaises(ConfigApplyError) as result:
            service.apply(device, 'description demo', {
                          'ping': {'target': '1.1.1.1'}})
        self.assertTrue(device.restored)
        self.assertEqual(result.exception.result_data['rollback'], 'verified')
        self.assertTrue(result.exception.result_data['rollback_verified'])


if __name__ == '__main__':
    unittest.main()
