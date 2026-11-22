"""Đối chiếu sau restore OSPF bằng lệnh chỉ đọc; không gọi restore/push."""
import json

from app.contracts import VerificationError
from app.inventory import InventoryManager
from app.logging_setup import setup_logging
from app.ospf_lab import OspfLab
from app.runner import TaskRunner, safe_data
from main import export_results


def recheck(lab):
    state = lab._state()  # Kiểm tra đúng endpoint, chủ sở hữu và hash hai bản.

    def check(device):
        backup_id = state['backups'][device.name]
        original = lab.backups.read_backup(backup_id)
        result = device.verify_config(original, {'config_match': True})
        lab.backups._validate_verification(result, {'config_match': True})
        if not result.passed:
            raise VerificationError(
                'Cau hinh van khac ban truoc OSPF; giu state.')
        return {'backup_id': backup_id, 'config_match': True,
                'operation': 'read_only_recheck'}

    return lab.runner.run(lab.infos, 'ospf_restore_recheck', check)


def main():
    setup_logging()
    infos = InventoryManager('inventory/devices.yaml').load()
    lab = OspfLab(infos, TaskRunner())
    results = recheck(lab)
    print(json.dumps([safe_data(result) for result in results], indent=2))
    print('Report:', export_results(results, 'json', 'ospf_restore_recheck'))
    success = all(result.status == 'success' for result in results)
    if success:
        lab.state_path.unlink()
        print('PASS: R1/R2 khop ban truoc OSPF. Da dong state, giu nguyen backups.')
    else:
        print('FAIL: giu nguyen state/backups; khong tu lap restore.')
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
