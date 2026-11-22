"""Phần C: điểm vào CLI. Chạy python main.py --help."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

import yaml

from app.backup import BackupService
from app.config_service import ConfigService
from app.inventory import InventoryManager
from app.logging_setup import setup_logging
from app.reporting import ReportService
from app.runner import TaskRunner, safe_data
from app.scheduler import BackupScheduler

ROOT = Path(__file__).resolve().parent


def load_mapping(path):
    with Path(path).open(encoding='utf-8') as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError('YAML phai la dictionary.')
    return data


def cli(argv=None):
    parser = argparse.ArgumentParser(description='Network Backup System - CLI phan C')
    parser.add_argument('--inventory', default=str(ROOT / 'inventory/devices.yaml'))
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--report', choices=['json', 'csv'], help='Xuat bao cao vao reports/')
    sub = parser.add_subparsers(dest='command', required=True)
    inventory_cmd = sub.add_parser('inventory', help='Liet ke thiet bi (offline)')
    for item in (inventory_cmd,):
        item.add_argument('--group')
        item.add_argument('--role')
        item.add_argument('--tag')
    for name in ('facts', 'backup', 'check'):
        p = sub.add_parser(name)
        p.add_argument('--devices', nargs='+', help='Ten thiet bi; mac dinh tat ca')
    p = sub.add_parser('list', help='Liet ke cac backup (offline)')
    p.add_argument('--device', required=True)
    p = sub.add_parser('diff', help='So sanh hai backup (offline)')
    p.add_argument('first', type=int)
    p.add_argument('second', type=int)
    p = sub.add_parser('baseline', help='Gan baseline (offline)')
    p.add_argument('--device', required=True)
    p.add_argument('--backup-id', type=int, required=True)
    p = sub.add_parser('restore', help='Restore thiet bi (co thay doi thiet bi)')
    p.add_argument('--device', required=True)
    p.add_argument('--backup-id', type=int, required=True)
    p.add_argument('--checks', required=True)
    p.add_argument('--confirm', action='store_true')
    for name in ('dry-run', 'apply'):
        p = sub.add_parser(name)
        p.add_argument('--devices', nargs='+', required=True)
        p.add_argument('--template', required=True)
        p.add_argument('--vars', required=True)
        if name == 'apply':
            p.add_argument('--checks', required=True)
            p.add_argument('--confirm', action='store_true')
    p = sub.add_parser('scheduler', help='Lich backup trong tien trinh')
    p.add_argument('--schedule', default=str(ROOT / 'config/schedule.example.yaml'))
    args = parser.parse_args(argv)
    setup_logging()
    inventory = InventoryManager(args.inventory)
    infos = inventory.load()
    if args.command == 'inventory':
        print(json.dumps([safe_data(x) for x in inventory.filter(args.group, args.role, args.tag)],
                         indent=2, ensure_ascii=False))
        return 0
    service = BackupService()
    if args.command == 'list':
        print(json.dumps([safe_data(x) for x in service.list_backups(args.device)], indent=2))
        return 0
    if args.command == 'diff':
        print(service.compare(args.first, args.second))
        return 0
    if args.command == 'baseline':
        service.set_baseline(args.device, args.backup_id)
        print('Da chon baseline.')
        return 0
    if args.command in {'restore', 'apply'} and not args.confirm:
        raise ValueError('Lenh thay doi thiet bi can --confirm.')
    runner = TaskRunner(max_workers=args.workers)
    if args.command == 'scheduler':
        scheduler = BackupScheduler.from_yaml(args.schedule, infos, runner, service)
        print('Scheduler bat dau; Ctrl+C de dung.', flush=True)
        scheduler.run_forever()
        return 0
    chosen = getattr(args, 'devices', None)
    if args.command == 'restore':
        chosen = [args.device]
    names = {x.name for x in infos}
    if chosen:
        missing = set(chosen) - names
        if missing:
            raise ValueError('Thiet bi khong co trong inventory: ' + ', '.join(sorted(missing)))
        selected = [x for x in infos if x.name in set(chosen)]
    else:
        selected = infos
    config_service = ConfigService(backup_service=service)
    checks = load_mapping(args.checks) if args.command in {'restore', 'apply'} else None
    if args.command in {'dry-run', 'apply'}:
        variables = load_mapping(args.vars)
        config_text = config_service.render(args.template, variables)
        previews = [config_service.dry_run(info, config_text) for info in selected]
        if args.command == 'dry-run':
            print(json.dumps(previews, ensure_ascii=False, indent=2))
            return 0 if all(x['valid'] for x in previews) else 1
        if not all(x['valid'] for x in previews):
            raise ValueError('Dry-run that bai; khong thay doi thiet bi.')
    tasks = {
        'facts': ('facts', lambda d: d.get_normalized_facts()),
        'backup': ('backup', lambda d: service.create_backup(d)),
        'check': ('check', lambda d: service.check_changes(d)),
        'restore': ('restore', lambda d: service.restore(d, args.backup_id, checks))
                           if args.command == 'restore' else None,
        'apply': ('apply', lambda d: config_service.apply(d, config_text, checks))
                           if args.command == 'apply' else None,
    }
    task, func = tasks[args.command]
    results = runner.run(selected, task, func)
    print(json.dumps([safe_data(x) for x in results], ensure_ascii=False, indent=2))
    if args.report:
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        path = ROOT / 'reports' / f'{task}_{stamp}.{args.report}'
        print('Report:', ReportService().export(results, path, args.report))
    return 1 if any(x.status != 'success' for x in results) else 0


if __name__ == '__main__':
    try:
        sys.exit(cli())
    except (ValueError, OSError, yaml.YAMLError, Exception) as exc:
        # Không in raw exception (có thể chứa đường dẫn/bí mật từ SSH).
        print(f'Loi: {type(exc).__name__}. Kiem tra tham so, file va logs.', file=sys.stderr)
        sys.exit(2)
