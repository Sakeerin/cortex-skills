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
    for command in (backup, restore, doctor):
        command.add_argument('--json', action='store_true', help='Print a machine-readable result')
    args = parser.parse_args()
    try:
        manager = DataManager(args.data_dir.expanduser() if args.data_dir else get_data_dir())
        if args.command == 'backup':
            report = {'backup': str(manager.backup(args.output))}
        elif args.command == 'restore':
            report = manager.restore(args.archive, overwrite=args.overwrite, dry_run=args.dry_run)
        else:
            report = manager.doctor(repair=args.repair)
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
            return 1
        return 0
    except (OSError, ValueError, TimeoutError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
