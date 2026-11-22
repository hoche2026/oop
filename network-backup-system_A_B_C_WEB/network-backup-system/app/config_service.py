"""Phần C: render và áp cấu hình có backup + rollback một lần."""
import re
from dataclasses import asdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError
from app.backup import BackupService
from app.contracts import VerificationResult

PROJECT_DIR = Path(__file__).resolve().parents[1]


class ConfigApplyError(Exception):
    def __init__(self, message, result_data):
        super().__init__(message)
        self.result_data = result_data


class ConfigService:
    def __init__(self, backup_service=None, templates_dir=None):
        self.backups = backup_service if backup_service is not None else BackupService()
        self.templates_dir = Path(templates_dir or PROJECT_DIR / 'templates').resolve()
        self.env = Environment(loader=FileSystemLoader(str(self.templates_dir)),
                               undefined=StrictUndefined, autoescape=False,
                               keep_trailing_newline=True)

    def render(self, template_name, variables):
        if (not isinstance(template_name, str) or not template_name
                or Path(template_name).name != template_name or '\\' in template_name):
            raise ValueError('Ten template khong hop le.')
        if not isinstance(variables, dict):
            raise ValueError('Variables phai la dictionary.')
        try:
            result = self.env.get_template(template_name).render(**variables)
        except TemplateError as exc:
            raise ValueError('Khong render duoc template (kiem tra bien/ten file).') from exc
        if not result.strip():
            raise ValueError('Template sinh cau hinh rong.')
        return result

    def dry_run(self, device_info, config_text):
        if not isinstance(config_text, str) or not config_text.strip():
            raise ValueError('Cau hinh rong.')
        lines = [line.strip() for line in config_text.splitlines()
                 if line.strip() and not line.lstrip().startswith(('!', '#'))]
        if not lines:
            raise ValueError('Khong co lenh de ap dung.')
        errors = []
        if device_info.platform == 'mikrotik_routeros':
            if any(not line.startswith('/') for line in lines):
                errors.append('MikroTik yeu cau moi dong bat dau bang /.')
        elif device_info.platform == 'cisco_ios':
            forbidden = {'configure terminal', 'conf t', 'end', 'write memory', 'wr', 'reload'}
            if any(line.lower() in forbidden for line in lines):
                errors.append('Cisco: khong chen lenh EXEC vao config.')
        else:
            errors.append('Platform chua duoc ho tro.')
        return {'device': device_info.name, 'platform': device_info.platform,
                'valid': not errors, 'errors': errors, 'commands_count': len(lines),
                'preview': config_text, 'note': 'Kiem tra cu phap co ban; chua ket noi/kiem tra thiet bi.'}

    def apply(self, device, config_text, checks):
        """Thiết bị đã nối. Xác minh bắt buộc; lỗi áp/verify thì rollback đúng một lần."""
        if not isinstance(checks, dict) or not checks:
            raise ValueError('Can checks khong rong (interfaces hoac ping).')
        if not isinstance(config_text, str) or not config_text.strip():
            raise ValueError('Cau hinh rong.')
        # Preflight trước khi có tác động; chỉ cần cấu trúc hợp lệ, không đòi đã đạt.
        preflight = device.verify_config(config_text, checks)
        self.backups._validate_verification(preflight, checks)
        pre = self.backups.create_backup(device)
        result_data = {'device': device.name, 'pre_backup_id': pre.backup_id,
                       'applied': False, 'verified': False, 'rollback': 'not_needed'}
        try:
            device.push_config(config_text)
            result_data['applied'] = True
            verification = device.verify_config(config_text, checks)
            self.backups._validate_verification(verification, checks)
            result_data['verification'] = asdict(verification)
            if not verification.passed:
                raise ValueError('Xac minh sau ap cau hinh khong dat.')
            result_data['verified'] = True
            return result_data
        except Exception as exc:
            result_data['rollback'] = 'failed'
            result_data['failure_stage'] = 'apply_or_verify'
            try:
                point = self.backups.storage.read_restore_point(pre.backup_id)
                device.restore_config(point)
                result_data['rollback'] = 'restore_invoked'
                # Không khẳng định rollback thành công chỉ vì lệnh restore đã trả về.
                result_data['rollback_verified'] = False
            except Exception as rollback_exc:
                result_data['rollback_error_type'] = type(rollback_exc).__name__
            raise ConfigApplyError('Ap cau hinh that bai; xem trang thai rollback.', result_data) from exc
