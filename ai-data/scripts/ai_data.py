#!/usr/bin/env python3
"""Back up, restore and inspect AI Skills data."""

import argparse
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '_lib'))
from data_manager import DataManager  # noqa: E402
from env_loader import get_data_dir  # noqa: E402
from cli import command, set_result, CLIError, DATA_ERROR, CONFLICT, NOT_FOUND, FAILURE  # noqa: E402
from data_scope import current_scope  # noqa: E402


@command(scoped=True)
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, help='Override AI_SKILLS_DATA_DIR')
    sub = parser.add_subparsers(dest='command', required=True)
    backup = sub.add_parser('backup', help='Create a ZIP archive with checksums')
    backup.add_argument('--output', type=Path)
    restore = sub.add_parser('restore', help='Validate and restore a backup')
    restore.add_argument('archive', type=Path)
    restore.add_argument('--overwrite', action='store_true', help='Replace files after a safety backup')
    restore.add_argument('--dry-run', action='store_true', help='Validate and preview only')
    doctor = sub.add_parser('doctor', help='Check data syntax and schemas')
    doctor.add_argument('--repair', action='store_true', help='Back up and quarantine invalid JSONL lines')
    for subcommand in (backup, restore, doctor):
        subcommand.add_argument('--json', action='store_true', help='Print a machine-readable result')
    args = parser.parse_args()
    try:
        manager = DataManager(current_scope().directory(args.data_dir.expanduser()) if args.data_dir else get_data_dir())
        if args.command == 'backup':
            report = {'backup': str(manager.backup(args.output))}
        elif args.command == 'restore':
            report = manager.restore(args.archive, overwrite=args.overwrite, dry_run=args.dry_run)
        else:
            report = manager.doctor(repair=args.repair)
        set_result(report)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        elif args.command == 'backup':
            print(f"Backup: {report['backup']}")
        elif args.command == 'restore':
            if report['ok']:
                print(('Would restore: ' if args.dry_run else 'Restored: ') + ', '.join(report['files']))
            for issue in report['issues']:
                print(f"Error: {issue['file']}: {issue['message']}", file=sys.stderr)
            if report.get('backup'):
                print(f"Safety backup: {report['backup']}")
        else:
            issues = report['issues']
            print(f"Data doctor: {len(issues)} issue(s); {len(report['changed'])} file(s) repaired")
            for issue in issues:
                line = f":{issue['line']}" if issue.get('line') else ''
                print(f"  {issue['file']}{line}: {issue['message']}")
            if report.get('backup'):
                print(f"Safety backup: {report['backup']}")
        if args.command != 'backup' and not report.get('ok', True):
            conflict = report.get('error_code') == 'conflict'
            exit_code = {'conflict': CONFLICT, 'not_found': NOT_FOUND,
                         'operation_failed': FAILURE}.get(report.get('error_code'), DATA_ERROR)
            raise CLIError('Restore conflicts with existing data' if conflict
                           else 'Data validation failed; see report issues',
                           exit_code)
        return 0
    except ValueError as exc:
        raise CLIError(str(exc), DATA_ERROR) from exc


if __name__ == '__main__':
    raise SystemExit(main())
