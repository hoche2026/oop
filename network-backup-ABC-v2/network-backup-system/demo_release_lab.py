"""Kiểm thử vòng đời backup/diff/baseline/restore trên R1, không dùng ID mẫu."""
import argparse
from dataclasses import asdict
import json

from app.backup import BackupService
from app.config_service import ConfigService
from app.contracts import BackupError
from app.inventory import InventoryManager
from app.logging_setup import setup_logging
from app.runner import TaskRunner, safe_data
from main import export_results


def lifecycle(device, service):
    before = service.create_backup(device)
    previous_baseline = None
    try:
        previous_baseline = service.storage.get_baseline(device.name).backup_id
    except BackupError:
        pass
    service.set_baseline(device.name, before.backup_id)
    needs_cleanup = False
    changed = False
    try:
        config = 'interface FastEthernet1/0\n description OOP_LIFECYCLE_TEST\n'
        applied = ConfigService(service).apply(device, config, {
            'interface_descriptions': {'FastEthernet1/0': 'OOP_LIFECYCLE_TEST'},
        })
        needs_cleanup = True
        after = service.create_backup(device)
        diff_found = bool(service.compare(before.backup_id, after.backup_id))
        drift = service.check_changes(device)
        changed = drift['changed']
        if not diff_found or not changed:
            raise ValueError('Khong phat hien thay doi thu.')
        # Khong tu lap restore neu chinh lenh restore bi timeout/that bai.
        needs_cleanup = False
        restore = service.restore(device, before.backup_id, {
            'config_match': True,
            'interfaces': {'FastEthernet0/0': {
                'ip_address': device.host, 'status': 'up', 'protocol': 'up'}},
            'ping': {'source': device.host, 'target': '192.168.241.2', 'min_success_percent': 100},
        })
        final_drift = service.check_changes(device)
        if final_drift['changed']:
            raise ValueError('Cau hinh con sai lech sau restore.')
        return {'before_backup_id': before.backup_id, 'after_backup_id': after.backup_id,
                'diff_detected': diff_found, 'drift_detected': changed,
                'restored': True, 'drift_after_restore': False,
                'restore_verification': restore['verification'],
                'pre_restore_backup_id': restore['pre_backup_id']}
    finally:
        # Nếu bước chính thất bại sau thay đổi, vẫn thử cứu hộ đúng một lần.
        try:
            if needs_cleanup:
                service.restore(device, before.backup_id,
                                {'config_match': True})
        finally:
            if previous_baseline is not None:
                service.set_baseline(device.name, previous_baseline)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    if not args.confirm:
        parser.error(
            'Demo thay doi description R1 roi khoi phuc; can --confirm.')
    setup_logging()
    service = BackupService()
    infos = [info for info in InventoryManager(
        'inventory/devices.yaml').load() if info.name == 'R1']
    if len(infos) != 1:
        raise ValueError('Can dung mot R1 trong inventory.')
    results = TaskRunner(max_workers=1).run(
        infos, 'lifecycle_R1', lambda d: lifecycle(d, service))
    print(json.dumps([safe_data(result) for result in results], indent=2))
    print('Report:', export_results(results, 'json', 'lifecycle_R1'))
    return 0 if all(result.status == 'success' for result in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
