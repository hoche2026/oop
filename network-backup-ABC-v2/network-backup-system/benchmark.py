"""Đo thật thời gian backup thủ công/tự động; không sinh số liệu mẫu."""
import argparse
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.backup import BackupService
from app.comparison import comparison_lines
from app.inventory import InventoryManager
from app.logging_setup import setup_logging
from app.runner import TaskRunner
from app.security import write_private

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    for mode in ('manual', 'auto'):
        p = sub.add_parser(mode)
        p.add_argument('--devices', nargs='+', required=True)
    p = sub.add_parser('compare')
    p.add_argument('--manual-file', required=True)
    p.add_argument('--backup-id', type=int, required=True)
    args = parser.parse_args()
    setup_logging()
    service = BackupService()
    if args.mode == 'compare':
        manual = Path(args.manual_file).read_text(encoding='utf-8')
        automatic = service.read_backup(args.backup_id)
        same = comparison_lines(manual) == comparison_lines(automatic)
        print(json.dumps({'backup_id': args.backup_id,
              'same_normalized_config': same}))
        return 0 if same else 1
    infos = InventoryManager(ROOT / 'inventory/devices.yaml').load()
    selected = [info for info in infos if info.name in args.devices]
    if set(args.devices) != {info.name for info in selected}:
        raise ValueError('Ten thiet bi khong hop le.')
    if args.mode == 'manual':
        input('Mo terminal SSH khac de backup thu cong. Enter khi san sang bat dau: ')
        start = perf_counter()
        input('Thuc hien backup cung danh sach thiet bi; Enter khi hoan tat: ')
        duration = perf_counter() - start
        success_count = ''  # Chưa xác minh, không tự điền đạt.
    else:
        start = perf_counter()
        results = TaskRunner().run(selected, 'benchmark_backup', service.create_backup)
        duration = perf_counter() - start
        success_count = sum(result.status == 'success' for result in results)
        print(json.dumps([{'device': result.device, 'status': result.status,
                           'backup_id': result.data.get('backup_id')} for result in results], indent=2))
    row = {'mode': args.mode, 'task': 'backup', 'devices': ','.join(args.devices),
           'elapsed_seconds': round(duration, 4), 'success_count': success_count,
           'device_count': len(selected), 'created_at': datetime.now(timezone.utc).isoformat(),
           'accuracy': 'not_measured'}
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    path = ROOT / 'reports' / f'benchmark_{args.mode}_{uuid4().hex}.csv'
    write_private(path, '\ufeff' + buffer.getvalue())
    print(json.dumps(row, indent=2))
    print('Report:', path)
    return 1 if args.mode == 'auto' and success_count != len(selected) else 0


if __name__ == '__main__':
    raise SystemExit(main())
