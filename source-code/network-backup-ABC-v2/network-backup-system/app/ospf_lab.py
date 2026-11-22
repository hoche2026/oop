"""Kịch bản OSPF R1/R2: chuẩn bị -> push cả hai -> hội tụ -> verify.

Mọi thay đổi chỉ thực thi qua run('apply') hoặc run('restore') của CLI đã
yêu cầu --confirm. State cứu hộ được lưu trước lần push đầu tiên.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

from app.backup import BackupService
from app.config_service import ConfigService
from app.contracts import VerificationError
from app.security import write_private


def lab_plan():
    """Trả cấu hình và điều kiện kiểm tra OSPF riêng cho R1 và R2."""
    plans = {}
    for name, local, peer, address, peer_address in (
        ('R1', '10.255.1.1', '10.255.2.2', '10.10.12.1', '10.10.12.2'),
        ('R2', '10.255.2.2', '10.255.1.1', '10.10.12.2', '10.10.12.1'),
    ):
        plans[name] = {
            'variables': {'router_id': local, 'link_ip': address},
            'checks': {
                'interfaces': {
                    'FastEthernet1/0': {'ip_address': address, 'status': 'up', 'protocol': 'up'},
                    'Loopback101': {'ip_address': local, 'status': 'up', 'protocol': 'up'},
                },
                'interface_descriptions': {'Loopback101': 'OOP_OSPF_LAB'},
                'config_lines': ['router ospf 10', f'router-id {local}'],
                'ospf_neighbors': [peer], 'ospf_routes': [peer + '/32'],
                'ping': {'source': local, 'target': peer, 'min_success_percent': 100},
            },
        }
    return plans


class OspfLab:
    """Điều phối thực nghiệm OSPF hai router với bản sao và state cứu hộ."""

    def __init__(self, infos, runner, backups=None, project_dir=None,
                 timeout=90, interval=3, clock=time.monotonic, sleep=time.sleep):
        self.infos = [info for info in infos if info.name in {'R1', 'R2'}]
        if {info.name for info in self.infos} != {'R1', 'R2'} or len(self.infos) != 2:
            raise ValueError('OSPF lab can dung hai thiet bi R1/R2.')
        if any(info.platform != 'cisco_ios' or info.role != 'router' for info in self.infos):
            raise ValueError('R1/R2 phai la Cisco IOS router.')
        self.runner = runner
        self.backups = backups if backups is not None else BackupService()
        self.configs = ConfigService(self.backups)
        self.root = Path(project_dir or Path(__file__).resolve().parents[1])
        self.state_path = self.root / 'data/ospf_state.json'
        self.timeout, self.interval = timeout, interval
        self.clock, self.sleep = clock, sleep
        self.plans = lab_plan()

    def _config(self, name):
        return self.configs.render('cisco_ospf.j2', self.plans[name]['variables'])

    def _state(self):
        state = json.loads(self.state_path.read_text(encoding='utf-8'))
        expected = {info.name: {'host': info.host, 'port': info.port}
                    for info in self.infos}
        if state.get('endpoints') != expected or set(state.get('backups', {})) != {'R1', 'R2'}:
            raise ValueError(
                'State OSPF khong khop inventory; khong khoi phuc.')
        # Kiểm tra cả hai mục tiêu trước khi thay đổi bất kỳ router nào.
        for info in self.infos:
            record = self.backups.storage.get_backup(
                state['backups'][info.name])
            if record.device_name != info.name or record.platform != info.platform:
                raise ValueError('Ban sao OSPF khong khop thiet bi.')
            self.backups.read_backup(record.backup_id)
            self.backups.storage.read_restore_point(record.backup_id)
        return state

    def _save(self, state):
        write_private(self.state_path, json.dumps(state, indent=2))

    def _wait_verify(self, device):
        end = self.clock() + self.timeout
        while True:
            result = device.verify_config(self._config(
                device.name), self.plans[device.name]['checks'])
            self.backups._validate_verification(
                result, self.plans[device.name]['checks'])
            if result.passed:
                return {'verified': True, 'verification': asdict(result)}
            if self.clock() >= end:
                error = VerificationError(
                    'OSPF chua hoi tu trong thoi gian cho.')
                error.result_data = {'verification': asdict(result)}
                raise error
            self.sleep(min(self.interval, max(0, end - self.clock())))

    def run(self, action):
        """Thực hiện từng pha OSPF, lưu cứu hộ trước push và giữ kết quả lỗi."""
        if action == 'dry-run':
            return [self.configs.dry_run(info, self._config(info.name)) for info in self.infos]
        if action == 'verify':
            return self.runner.run(self.infos, 'ospf_verify', self._wait_verify)
        if action == 'restore':
            state = self._state()
            results = self._restore(state)
            if all(result.status == 'success' for result in results):
                self.state_path.unlink()
            return results
        if action != 'apply':
            raise ValueError('Hanh dong OSPF khong hop le.')
        if self.state_path.exists():
            raise ValueError(
                'Da co state OSPF. Dung ospf verify hoac ospf restore truoc.')

        def prepare(device):
            """Lưu bản sao trước thay đổi và từ chối ghi đè tài nguyên lab có sẵn."""
            text = device.backup_config()
            if re.search(r'^router ospf 10\s*$', text, re.MULTILINE) or re.search(
                    r'^interface Loopback101\s*$', text, re.MULTILINE):
                raise ValueError(
                    'OSPF 10/Loopback101 da ton tai; khong ghi de.')
            return asdict(self.backups.create_backup(device))

        prepared = self.runner.run(self.infos, 'ospf_prepare', prepare)
        if any(result.status != 'success' for result in prepared):
            return prepared
        state = {
            'created_at': datetime.now(timezone.utc).isoformat(), 'phase': 'prepared',
            'endpoints': {info.name: {'host': info.host, 'port': info.port} for info in self.infos},
            'backups': {result.device: result.data['backup_id'] for result in prepared},
        }
        self._save(state)

        def push(device):
            """Áp cấu hình OSPF đã sinh và trả ID bản sao trước thao tác."""
            result = device.push_config(self._config(device.name))
            if not isinstance(result, dict) or result.get('applied') is False:
                raise ValueError('OSPF push khong thanh cong.')
            return {'applied': True, 'pre_backup_id': state['backups'][device.name]}

        # Lưu trạng thái trước push, để Ctrl+C/tắt tiến trình vẫn có đường cứu hộ.
        state['phase'] = 'applying'
        self._save(state)
        applied = self.runner.run(self.infos, 'ospf_apply', push)
        verified = []
        if all(result.status == 'success' for result in applied):
            verified = self.runner.run(
                self.infos, 'ospf_verify', self._wait_verify)
        if verified and all(result.status == 'success' for result in verified):
            state['phase'] = 'verified'
            self._save(state)
            return prepared + applied + verified
        restored = self._restore(state)
        state['phase'] = 'rolled_back' if all(
            r.status == 'success' for r in restored) else 'rollback_failed'
        self._save(state)
        # Giữ các kết quả apply/verify thất bại kể cả khi khôi phục thành công.
        return prepared + applied + verified + restored

    def _restore(self, state):
        return self.runner.run(self.infos, 'ospf_restore', lambda device: self.backups.restore(
            device, state['backups'][device.name], {'config_match': True}))
