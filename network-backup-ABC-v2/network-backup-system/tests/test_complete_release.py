"""Regression/integration tests; real services and device verification, fake I/O."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.backup import BackupService
from app.comparison import comparison_lines
from app.config_service import ConfigService, ConfigApplyError
from app.contracts import DeviceInfo, VerificationError, VerificationResult
from app.devices.cisco_ios import CiscoIOSDevice
from app.devices.mikrotik import MikroTikDevice
from app.ospf_lab import OspfLab
from app.runner import TaskRunner
from app.storage import BackupStorage
from app.verification import required_criteria
from test_backup import FakeDevice


def info(name='R1', platform='cisco_ios'):
    return DeviceInfo(name, '192.0.2.1' if name == 'R1' else '192.0.2.2', 22,
                      platform, 'lab', 'router', [], 'LAB')


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ, {'LAB_USERNAME': 'dummy', 'LAB_PASSWORD': 'dummy'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.cisco = CiscoIOSDevice(info())
        self.config = ('version 15.2\nhostname R1\ninterface FastEthernet1/0\n'
                       ' description ACTUAL\n ip address 10.10.12.1 255.255.255.252\nend\n')
        self.cisco.backup_config = lambda: self.config

    def test_description_checks_real_value_and_missing_interface(self):
        for value, expected in [('ACTUAL', True), ('WRONG', False), ('', False)]:
            with self.subTest(value=value):
                self.assertEqual(self.cisco.verify_config('', {
                    'interface_descriptions': {'FastEthernet1/0': value}}).passed, expected)
        self.assertFalse(self.cisco.verify_config('', {
            'interface_descriptions': {'FastEthernet9/9': ''}}).passed)

    def test_full_config_match_detects_extra_commands(self):
        self.assertTrue(self.cisco.verify_config(
            self.config, {'config_match': True}).passed)
        self.assertFalse(self.cisco.verify_config(
            self.config + 'extra\n', {'config_match': True}).passed)

    def test_config_line_and_absence_are_independent_criteria(self):
        checks = {'config_lines': ['hostname R1'],
                  'config_absent': ['hostname R2']}
        result = self.cisco.verify_config('', checks)
        self.assertTrue(result.passed)
        self.assertEqual(set(result.checks), required_criteria(checks))

    def test_ospf_requires_exact_neighbor_full_and_ospf_route(self):
        output = {'show ip ospf neighbor':
                  'Neighbor ID Pri State Dead Time Address Interface\n'
                  '10.255.2.2 1 FULL/DR 00:00:35 10.10.12.2 FastEthernet1/0\n',
                  'show ip route 10.255.2.2 255.255.255.255':
                  'Routing entry for 10.255.2.2/32\n Known via "ospf 10", distance 110\n'}
        self.cisco.send_command = lambda command: output[command]
        checks = {'ospf_neighbors': ['10.255.2.2'],
                  'ospf_routes': ['10.255.2.2/32']}
        self.assertTrue(self.cisco.verify_config('', checks).passed)
        output['show ip ospf neighbor'] = output['show ip ospf neighbor'].replace(
            'FULL/DR', '2WAY/DROTHER')
        self.assertFalse(self.cisco.verify_config('', checks).passed)
        output['show ip ospf neighbor'] = '110.255.2.2 1 FULL/DR 00:00:35 X Ethernet0\n'
        self.assertFalse(self.cisco.verify_config('', checks).passed)
        output['show ip route 10.255.2.2 255.255.255.255'] = 'Routing entry for 10.255.2.2/32\n Known via "static"\n'
        self.assertFalse(self.cisco.verify_config(
            '', {'ospf_routes': ['10.255.2.2/32']}).passed)

    def test_invalid_ospf_and_injected_interface_rejected_before_io(self):
        self.cisco.send_command = lambda command: self.fail(
            'Unexpected device I/O')
        for checks in ({'ospf_neighbors': ['not-an-ip']}, {'ospf_routes': ['1.2.3.4/24']},
                       {'interface_descriptions': {'Ethernet0\nreload': 'x'}},
                       {'config_match': False}, {'config_lines': []}):
            with self.subTest(checks=checks), self.assertRaises(VerificationError):
                self.cisco.verify_config('', checks)

    def test_mikrotik_comment_actual_value(self):
        device = MikroTikDevice(info('MT1', 'mikrotik_routeros'))
        device._read_rows = lambda command: [
            {'name': 'ether1', 'comment': 'ACTUAL'}]
        self.assertTrue(device.verify_config(
            '', {'interface_comments': {'ether1': 'ACTUAL'}}).passed)
        self.assertFalse(device.verify_config(
            '', {'interface_comments': {'ether1': 'WRONG'}}).passed)
        with self.assertRaises(VerificationError):
            device.verify_config('', {'ospf_neighbors': ['1.1.1.1']})

    def test_missing_extended_coverage_is_not_accepted(self):
        with self.assertRaises(VerificationError):
            BackupService._validate_verification(
                VerificationResult(True, [], {'ping': True}), {'config_match': True})

    def test_generated_headers_ignored_but_body_comments_preserved(self):
        first = '# 2026-11-12 01:00:00 by RouterOS 7.24.6\n/system identity set name=MT1\n'
        second = first.replace('01:00:00', '02:00:00')
        self.assertEqual(comparison_lines(first), comparison_lines(second))
        self.assertNotEqual(comparison_lines(
            first), comparison_lines(first + '# my comment\n'))
        self.assertEqual(comparison_lines('Building configuration...\n\nCurrent configuration : 50 bytes\n'
                                          '! Last configuration change at 1\n' + self.config),
                         comparison_lines(self.config))


class StatefulDevice(FakeDevice):
    def __init__(self, name, registry, *, fail_push=False, fail_rollback=False, fail_verify=False):
        super().__init__(name)
        self.host = '192.168.241.21' if name == 'R1' else '192.168.241.22'
        self.config = f'version 15.2\nhostname {name}\ninterface FastEthernet1/0\nend\n'
        self.original = self.config
        self.registry = registry
        self.fail_push, self.fail_rollback, self.fail_verify = fail_push, fail_rollback, fail_verify
        self.restore_count = 0
        self.events = registry['events']

    def connect(self):
        pass

    def disconnect(self):
        pass

    def push_config(self, config):
        self.events.append(('push', self.name))
        self.config += config
        if self.fail_push:
            raise RuntimeError('simulated partial failure')
        return {'applied': True}

    def verify_config(self, config, checks):
        self.events.append(('verify', self.name))
        if checks.get('config_match'):
            passed = comparison_lines(config) == comparison_lines(self.config)
        elif checks.get('ospf_neighbors'):
            passed = all('router ospf 10' in d.config for d in self.registry['devices'].values(
            )) and not self.fail_verify
        elif checks.get('interface_descriptions'):
            passed = all('description ' + value in self.config
                         for value in checks['interface_descriptions'].values())
        else:
            passed = self.config == self.original
        return VerificationResult(passed, [], {key: passed for key in required_criteria(checks)})

    def restore_config(self, point):
        self.restore_count += 1
        self.events.append(('restore', self.name))
        if self.fail_rollback:
            raise RuntimeError('restore failure')
        return super().restore_config(point)


class ReleaseIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.backups = BackupService(BackupStorage(self.root))
        self.registry = {'events': [], 'devices': {}}
        for name in ('R1', 'R2'):
            self.registry['devices'][name] = StatefulDevice(
                name, self.registry)
        registry = self.registry

        class Factory:
            @staticmethod
            def create(info):
                return registry['devices'][info.name]

        self.runner = TaskRunner(factory=Factory())
        self.lab = OspfLab([info('R1'), info('R2')], self.runner, self.backups,
                           project_dir=self.root, timeout=0)

    def test_apply_failure_restores_and_verifies_old_configuration_once(self):
        device = self.registry['devices']['R1']
        with self.assertRaises(ConfigApplyError) as caught:
            ConfigService(self.backups).apply(device, 'description changed\n',
                                              {'ping': {'target': '192.0.2.1'}})
        data = caught.exception.result_data
        self.assertEqual(data['rollback'], 'verified')
        self.assertTrue(data['rollback_verified'])
        self.assertEqual(device.restore_count, 1)
        self.assertEqual(device.config, device.original)
        self.assertTrue(self.backups.read_backup(data['pre_backup_id']))

    def test_rollback_failure_remains_failed_and_preserves_rescue(self):
        device = self.registry['devices']['R1']
        device.fail_rollback = True
        with self.assertRaises(ConfigApplyError) as caught:
            ConfigService(self.backups).apply(device, 'description changed\n',
                                              {'ping': {'target': '192.0.2.1'}})
        self.assertFalse(caught.exception.result_data['rollback_verified'])
        self.assertEqual(device.restore_count, 1)
        self.assertTrue(self.backups.read_backup(
            caught.exception.result_data['pre_backup_id']))

    def test_release_demo_covers_baseline_diff_and_full_restore(self):
        from demo_release_lab import lifecycle
        device = self.registry['devices']['R1']
        result = lifecycle(device, self.backups)
        self.assertTrue(result['diff_detected'])
        self.assertTrue(result['drift_detected'])
        self.assertFalse(result['drift_after_restore'])
        self.assertEqual(device.config, device.original)
        self.assertEqual(device.restore_count, 1)

    def test_release_demo_does_not_repeat_failed_primary_restore(self):
        from demo_release_lab import lifecycle
        from app.contracts import RestoreError
        device = self.registry['devices']['R1']
        with patch.object(self.backups, 'restore', side_effect=RestoreError('timeout')) as restore:
            with self.assertRaises(RestoreError):
                lifecycle(device, self.backups)
        self.assertEqual(restore.call_count, 1)

    def test_ospf_applies_both_before_verify_and_restores_original(self):
        results = self.lab.run('apply')
        self.assertTrue(all(result.status == 'success' for result in results))
        events = self.registry['events']
        first_verify = next(i for i, event in enumerate(
            events) if event[0] == 'verify')
        self.assertEqual(
            {event[1] for event in events[:first_verify] if event[0] == 'push'}, {'R1', 'R2'})
        self.assertEqual(json.loads(self.lab.state_path.read_text())[
                         'phase'], 'verified')
        results = self.lab.run('restore')
        self.assertTrue(all(result.status == 'success' for result in results))
        self.assertFalse(self.lab.state_path.exists())
        self.assertTrue(
            all(d.config == d.original for d in self.registry['devices'].values()))

    def test_partial_push_failure_rolls_back_both_and_keeps_original_failure(self):
        self.registry['devices']['R2'].fail_push = True
        results = self.lab.run('apply')
        self.assertTrue(any(result.status == 'failed' for result in results))
        self.assertTrue(
            all(d.config == d.original for d in self.registry['devices'].values()))
        self.assertEqual(json.loads(self.lab.state_path.read_text())[
                         'phase'], 'rolled_back')

    def test_ospf_verify_timeout_rolls_back_without_reporting_success(self):
        self.registry['devices']['R2'].fail_verify = True
        results = self.lab.run('apply')
        self.assertTrue(any(
            result.task == 'ospf_verify' and result.status == 'failed' for result in results))
        self.assertTrue(
            all(d.config == d.original for d in self.registry['devices'].values()))

    def test_existing_process_is_not_overwritten(self):
        self.registry['devices']['R2'].config += 'router ospf 10\n'
        results = self.lab.run('apply')
        self.assertTrue(any(result.status == 'failed' for result in results))
        self.assertFalse(
            any(event[0] == 'push' for event in self.registry['events']))
        self.assertFalse(self.lab.state_path.exists())

    def test_state_write_failure_prevents_push(self):
        with patch.object(self.lab, '_save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.lab.run('apply')
        self.assertFalse(
            any(event[0] == 'push' for event in self.registry['events']))

    def test_inventory_changed_prevents_restore(self):
        self.lab.run('apply')
        state = json.loads(self.lab.state_path.read_text())
        state['endpoints']['R1']['host'] = '192.0.2.99'
        self.lab.state_path.write_text(json.dumps(state))
        with self.assertRaises(ValueError):
            self.lab.run('restore')
        self.assertFalse(
            any(event[0] == 'restore' for event in self.registry['events']))

    @unittest.skipUnless(os.name == 'posix', 'POSIX modes')
    def test_backup_database_and_new_files_are_private(self):
        record = self.backups.create_backup(self.registry['devices']['R1'])
        files = [self.root / record.file_path, self.root / record.file_path.replace('.cfg', '.restore'),
                 self.root / 'data/app.db']
        for path in files:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        for path in [self.root / 'backups', self.root / 'backups/R1', self.root / 'data']:
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)


if __name__ == '__main__':
    unittest.main()
