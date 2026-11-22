"""Kiểm thử adapter Web offline; không yêu cầu cài Streamlit hay thiết bị thật."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.contracts import DeviceInfo
from app.web_backend import WebController


class FakeBackup:
    def list_backups(self, name):
        return []

    def create_backup(self, device):
        return {'backup_id': 7}

    def check_changes(self, device):
        return {'changed': False}


class FakeRunner:
    def run(self, items, name, fn):
        return [(name, info.name) for info in items]


class WebBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'inventory.yaml'
        self.path.write_text('devices: []\n', encoding='utf-8')
        self.ctrl = WebController(self.path, backup_service=FakeBackup(), runner=FakeRunner())
        self.r1 = dict(name='R1', host='192.0.2.11', port=22, platform='cisco_ios',
                       group='lab', role='router', tags=['core'], credential_profile='LAB')

    def test_inventory_crud_and_filters(self):
        self.ctrl.add_device(self.r1)
        self.assertEqual([x.name for x in self.ctrl.devices(group='lab', tag='core')], ['R1'])
        self.ctrl.update_device('R1', {'host': '192.0.2.12'})
        self.assertEqual(self.ctrl.devices()[0].host, '192.0.2.12')
        self.ctrl.delete_device('R1')
        self.assertEqual(self.ctrl.devices(), [])

    def test_selection_refuses_missing_or_duplicate(self):
        self.ctrl.add_device(self.r1)
        with self.assertRaises(ValueError): self.ctrl.selected([])
        with self.assertRaises(ValueError): self.ctrl.selected(['R2'])
        with self.assertRaises(ValueError): self.ctrl.selected(['R1', 'R1'])
        self.assertEqual(self.ctrl.selected(['R1'])[0].name, 'R1')

    def test_run_task_dispatch(self):
        self.ctrl.add_device(self.r1)
        self.assertEqual(self.ctrl.run_task(['R1'], 'backup'), [('backup', 'R1')])
        self.assertEqual(self.ctrl.run_task(['R1'], 'facts'), [('facts', 'R1')])
        with self.assertRaises(ValueError): self.ctrl.run_task(['R1'], 'erase')

    def test_template_preview_uses_c_config_service(self):
        self.ctrl.add_device(self.r1)
        text, result = self.ctrl.preview(['R1'], 'cisco_interface.j2',
                                         {'interface': 'FastEthernet1/0', 'description': 'test'})
        self.assertIn('interface FastEthernet1/0', text)
        self.assertTrue(result[0]['valid'])

    def test_restore_requires_checks(self):
        self.ctrl.add_device(self.r1)
        with self.assertRaises(ValueError): self.ctrl.restore('R1', 1, {})


if __name__ == '__main__':
    unittest.main()
