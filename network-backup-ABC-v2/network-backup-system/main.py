"""CLI chung của bản A+B+C; chạy python main.py --help."""
import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import sys
from uuid import uuid4

import yaml

from app.backup import BackupService
from app.config_service import ConfigService
from app.contracts import DeviceInfo
from app.inventory import InventoryManager
from app.logging_setup import setup_logging
from app.ospf_lab import OspfLab
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


def for_device(mapping, name):
    """Chấp nhận mapping chung hoặc {devices: {R1: {...}, R2: {...}}}."""
    if 'devices' not in mapping:
        return mapping
    if set(mapping) != {'devices'} or not isinstance(mapping['devices'], dict):
        raise ValueError('Mapping devices khong hop le.')
    value = mapping['devices'].get(name)
    if not isinstance(value, dict):
        raise ValueError(f'Thieu mapping cho {name}.')
    return value


def export_results(results, format, label):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    path = ROOT / 'reports' / f'{label}_{stamp}_{uuid4().hex[:8]}.{format}'
    saved = ReportService().export(results, path, format)
    logging.getLogger('app.cli').info(
        'report_saved task=%s format=%s', label, format)
    return saved


def selectors(parser, devices=True):
    if devices:
        parser.add_argument('--devices', nargs='+')
    parser.add_argument('--group')
    parser.add_argument('--role')
    parser.add_argument('--tag')


def cli(argv=None):
    parser = argparse.ArgumentParser(description='Network Backup System A+B+C')
    parser.add_argument(
        '--inventory', default=str(ROOT / 'inventory/devices.yaml'))
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--report', choices=['json', 'csv'], default='json')
    parser.add_argument('--summary', action='store_true',
                        help='Bang ket qua ngan; chi tiet trong report')
    sub = parser.add_subparsers(dest='command', required=True)
    selectors(sub.add_parser(
        'inventory', help='Liet ke/loc inventory, offline'), devices=False)
    for name in ('facts', 'backup', 'check'):
        selectors(sub.add_parser(name))
    for name in ('inventory-add', 'inventory-update'):
        p = sub.add_parser(name)
        p.add_argument('--file', required=True)
        if name == 'inventory-update':
            p.add_argument('--device', required=True)
    p = sub.add_parser('inventory-delete')
    p.add_argument('--device', required=True)
    p.add_argument('--confirm', action='store_true')
    p = sub.add_parser('list', help='Liet ke backup, offline')
    p.add_argument('--device', required=True)
    p = sub.add_parser(
        'diff', help='Diff da che dong nhay cam; --raw chi doc rieng')
    p.add_argument('first', type=int)
    p.add_argument('second', type=int)
    p.add_argument('--raw', action='store_true')
    p = sub.add_parser('baseline')
    p.add_argument('--device', required=True)
    p.add_argument('--backup-id', type=int, required=True)
    p = sub.add_parser('restore')
    p.add_argument('--device', required=True)
    p.add_argument('--backup-id', type=int, required=True)
    p.add_argument('--checks', required=True)
    p.add_argument('--confirm', action='store_true')
    for name in ('dry-run', 'apply'):
        p = sub.add_parser(name)
        selectors(p)
        p.add_argument('--template', required=True)
        p.add_argument('--vars', required=True)
        if name == 'apply':
            p.add_argument('--checks', required=True)
            p.add_argument('--confirm', action='store_true')
    p = sub.add_parser('scheduler')
    p.add_argument('--schedule', default=str(ROOT /
                   'config/schedule.example.yaml'))
    p = sub.add_parser(
        'ospf', help='Kich ban thuc nghiem R1/R2; restore tra ve ban truoc')
    p.add_argument('action', choices=['dry-run', 'apply', 'verify', 'restore'])
    p.add_argument('--confirm', action='store_true')
    args = parser.parse_args(argv)
    setup_logging()
    logger = logging.getLogger('app.cli')
    logger.info('cli_started task=%s', args.command)
    inventory = InventoryManager(args.inventory)
    infos = inventory.load()
    if args.command == 'inventory':
        print(json.dumps([safe_data(x) for x in inventory.filter(args.group, args.role, args.tag)],
                         indent=2, ensure_ascii=False))
        return 0
    if args.command.startswith('inventory-'):
        if args.command == 'inventory-add':
            inventory.add(DeviceInfo(**load_mapping(args.file)))
        elif args.command == 'inventory-update':
            inventory.update(args.device, load_mapping(args.file))
        else:
            if not args.confirm:
                raise ValueError('Xoa inventory can --confirm.')
            inventory.delete(args.device)
        print('Da cap nhat inventory.')
        return 0
    service = BackupService()
    if args.command == 'list':
        print(json.dumps([safe_data(x)
              for x in service.list_backups(args.device)], indent=2))
        return 0
    if args.command == 'diff':
        text = service.compare(args.first, args.second)
        if not args.raw:
            text = '\n'.join('[REDACTED sensitive config line]' if re.search(
                r'\b(password|secret|community|private[-_]key|token)\b', line, re.IGNORECASE)
                else line for line in text.splitlines())
        print(text or 'Khong co thay doi cau hinh.')
        return 0
    if args.command == 'baseline':
        service.set_baseline(args.device, args.backup_id)
        print('Da chon baseline.')
        return 0
    mutation = (args.command in {'restore', 'apply'} or
                (args.command == 'ospf' and args.action in {'apply', 'restore'}))
    if mutation and not args.confirm:
        raise ValueError('Lenh thay doi thiet bi can --confirm.')
    runner = TaskRunner(max_workers=args.workers)
    if args.command == 'scheduler':
        runner.on_results = lambda results: export_results(
            results, args.report, 'scheduled_backup')
        scheduler = BackupScheduler.from_yaml(args.schedule, infos, runner, service,
                                              max_workers=args.workers)
        print('Scheduler bat dau; Ctrl+C de dung. Bao cao tung luot: reports/.', flush=True)
        scheduler.run_forever()
        return 0
    if args.command == 'ospf':
        results = OspfLab(infos, runner, service).run(args.action)
        if args.action == 'dry-run':
            print(json.dumps(results, indent=2))
            return 0 if all(r['valid'] for r in results) else 1
        label = 'ospf_' + args.action
    else:
        chosen = [args.device] if args.command == 'restore' else getattr(
            args, 'devices', None)
        selected = infos
        if chosen:
            if set(chosen) - {info.name for info in infos}:
                raise ValueError('Thiet bi khong co trong inventory.')
            selected = [info for info in infos if info.name in chosen]
        for key in ('group', 'role', 'tag'):
            value = getattr(args, key, None)
            if value:
                selected = [info for info in selected if (value in info.tags if key == 'tag'
                                                          else getattr(info, key) == value)]
        if not selected:
            raise ValueError('Khong co thiet bi phu hop.')
        configs = ConfigService(service)
        checks = load_mapping(args.checks) if args.command in {
            'apply', 'restore'} else None
        rendered = {}
        if args.command in {'apply', 'dry-run'}:
            if not chosen and not any(getattr(args, key, None) for key in ('group', 'role', 'tag')):
                raise ValueError(
                    'Can chon --devices/--group/--role/--tag cho template.')
            variables = load_mapping(args.vars)
            rendered = {info.name: configs.render(args.template, for_device(variables, info.name))
                        for info in selected}
            previews = [configs.dry_run(info, rendered[info.name])
                        for info in selected]
            if args.command == 'dry-run':
                print(json.dumps(previews, indent=2, ensure_ascii=False))
                return 0 if all(row['valid'] for row in previews) else 1
            if not all(row['valid'] for row in previews):
                raise ValueError('Dry-run that bai; khong thay doi thiet bi.')
        if checks is not None:
            for info in selected:
                for_device(checks, info.name)
        tasks = {
            'facts': lambda d: d.get_normalized_facts(),
            'backup': lambda d: service.create_backup(d),
            'check': lambda d: service.check_changes(d),
            'restore': lambda d: service.restore(d, args.backup_id, for_device(checks, d.name)),
            'apply': lambda d: configs.apply(d, rendered[d.name], for_device(checks, d.name)),
        }
        results = runner.run(selected, args.command, tasks[args.command])
        label = args.command
    if args.summary:
        from rich.console import Console
        from rich.table import Table
        table = Table(title='KET QUA TAC VU')
        for column in ('Thiet bi', 'Tac vu', 'Ket qua', 'Backup ID', 'Loi'):
            table.add_column(column)
        for result in results:
            table.add_row(result.device, result.task, result.status,
                          str(result.data.get('backup_id',
                              result.data.get('pre_backup_id', '-'))),
                          result.error['type'] if result.error else '-')
        Console().print(table)
    else:
        print(json.dumps([safe_data(result)
              for result in results], indent=2, ensure_ascii=False))
    print('Report:', export_results(results, args.report, label))
    return 1 if any(result.status != 'success' for result in results) else 0


if __name__ == '__main__':
    try:
        sys.exit(cli())
    except KeyboardInterrupt:
        print(
            'Da dung. Neu ospf dang thay doi, dung ospf restore --confirm.', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        logging.getLogger('app.cli').error(
            'cli_failed error_type=%s', type(exc).__name__)
        print(f'Loi: {type(exc).__name__}. Kiem tra tham so va logs; khong in du lieu nhay cam.',
              file=sys.stderr)
        sys.exit(2)
