#!/usr/bin/env python3
"""Central offline administration CLI for cortex-skills."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '_lib'))

from cli import command, set_result, CLIError, DATA_ERROR, NOT_FOUND, USAGE  # noqa: E402
from data_scope import current_scope  # noqa: E402
from errors import DataError  # noqa: E402
from file_lock import atomic_write, data_lock  # noqa: E402
from model_registry import get_registry, PROVIDERS, validate_registry  # noqa: E402
from system_admin import PYTHON_SKILLS, SCOPED_SKILLS, doctor, list_skills, status, validate_skill  # noqa: E402

PROXIES = {'provider': 'ai-provider', 'data': 'ai-data', 'cost': 'ai-cost',
           'budget': 'token-budget', 'context': 'ai-context', 'usage': 'ai-cost'}


def forward(skill, arguments):
    """Run the existing handler under ONE scope/result/exception boundary."""
    if skill not in PYTHON_SKILLS:
        raise CLIError(f'No Python CLI for skill: {skill}', NOT_FOUND)
    if skill not in SCOPED_SKILLS and current_scope().kind != 'global':
        raise CLIError(f'{skill} does not support storage scope; use --scope global', USAGE)
    path = ROOT / skill / 'scripts' / (PYTHON_SKILLS[skill] + '.py')
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise FileNotFoundError(f'Skill entrypoint missing: {path}')
    spec = importlib.util.spec_from_file_location('cortex_skill_' + skill.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    original = sys.argv
    try:
        spec.loader.exec_module(module)
        sys.argv = [str(path), *arguments]
        # The public main is decorated for standalone use. The central boundary
        # already supplies JSON, scope and exit handling, so avoid double wrapping.
        return module.main.__wrapped__()
    finally:
        sys.argv = original


def cmd_status(_args):
    report = status()
    set_result(report)
    print(f"cortex-skills: {report['installation']}")
    print(f"Python: {report['python']} | Skills: {report['skills']}")
    print(f"Provider: {report['provider']} | Model: {report['model']}")
    print(f"Data: {report['data_dir']}")
    print(f"Registry: {report['registry']['models']} models, {report['registry']['overrides']} user overrides")


def cmd_doctor(args):
    report = doctor(repair=args.repair)
    set_result(report)
    for check in report['checks']:
        print(f"{'OK' if check['ok'] else 'FAIL'} {check['name']}: {check['message']}")
    for row in report['skills']:
        if not row['valid']:
            print(f"FAIL skill {row['name']}: {'; '.join(row['errors'])}")
    print(f"Data doctor: {len(report['data']['issues'])} issue(s), {len(report['data']['changed'])} repaired file(s)")
    for issue in report['data']['issues']:
        print(f"  {issue['file']}: {issue['message']}")
    if not report['ok']:
        raise CLIError('System doctor found unresolved issues; inspect data', DATA_ERROR)


def cmd_skills(args):
    if args.skills_command == 'list':
        rows = list_skills()
        set_result(rows)
        for row in rows:
            print(f"{row['name']:<18} python:{row['python_cli']} scope:{row['scoped']}")
        return
    names = [row['name'] for row in list_skills()] if args.all else [args.name]
    if not args.all and not args.name:
        raise ValueError('Provide a skill name or --all')
    if args.all and args.name:
        raise ValueError('Provide either a skill name or --all, not both')
    rows = [validate_skill(name) for name in names]
    set_result(rows)
    for row in rows:
        print(f"{'OK' if row['valid'] else 'FAIL'} {row['name']}")
        for message in row['errors'] + row['warnings']:
            print(f'  {message}')
    if any(not row['valid'] for row in rows):
        raise CLIError('Skill validation failed', DATA_ERROR)


def cmd_models(args):
    registry = get_registry()
    action = args.models_command
    if action in {'set', 'remove'} and current_scope().kind != 'global':
        raise ValueError('The central model registry is global; use --scope global to modify it')
    if action == 'list':
        rows = registry.list_models(args.provider)
        if args.query:
            query = args.query.casefold()
            rows = [row for row in rows if any(query in name.casefold() for name in [row['id'], *row['aliases']])]
        set_result(rows)
        for row in rows:
            print(f"{row['provider']:<10} {row['id']:<30} context:{row['context_window'] or 'unknown'} "
                  f"rates:{row['rates'] if row['rates'] is not None else 'unknown'}")
    elif action == 'show':
        row = registry.resolve(args.model, args.provider)
        if row is None:
            raise CLIError(f'Model not found: {args.model}', NOT_FOUND)
        set_result(row)
        print(json.dumps(row, indent=2, ensure_ascii=False))
    elif action == 'set':
        changes = {}
        for flag, field in [('context', 'context_window'), ('alias', 'aliases')]:
            value = getattr(args, flag)
            if value is not None:
                changes[field] = value
        if args.clear_aliases:
            if args.alias:
                raise ValueError('--clear-aliases cannot be combined with --alias')
            changes['aliases'] = []
        if args.exact:
            changes['match_suffix'] = False
        if args.allow_suffix:
            changes['match_suffix'] = True
        supplied = {key: getattr(args, key) for key in ('input', 'output', 'cache_read', 'cache_write')
                    if getattr(args, key) is not None}
        if args.unpriced and supplied:
            raise ValueError('--unpriced cannot be combined with rate options')
        if supplied:
            if not {'input', 'output'} <= supplied.keys():
                raise ValueError('Provide both --input and --output per million tokens')
            changes['rates'] = supplied
        elif args.unpriced:
            changes['rates'] = None
        if not changes:
            raise ValueError('Provide model metadata to set (context, aliases, pricing, or matching)')
        try:
            row = registry.set_model(args.provider, args.model, **changes)
        except DataError as exc:
            # Distinguish an already-corrupt file from invalid proposed metadata.
            registry.status()
            raise CLIError(str(exc), USAGE) from exc
        set_result(row)
        print(f"Saved user model: {row['provider']}/{row['id']}")
    elif action == 'remove':
        registry.remove_model(args.provider, args.model)
        set_result({'provider': args.provider, 'id': args.model, 'removed_override': True})
        print(f'Removed user override: {args.provider}/{args.model}')
    elif action == 'validate':
        report = registry.status()
        set_result(report)
        print(f"Registry valid: {report['models']} models, {report['overrides']} user overrides")
    else:
        document = registry.export(overrides_only=args.overrides_only)
        validate_registry(document, overrides=True)
        if args.output:
            with data_lock(args.output.parent):
                if args.output.exists():
                    raise FileExistsError(f'Export already exists: {args.output}')
                atomic_write(args.output, json.dumps(document, indent=2, ensure_ascii=False).encode('utf-8'))
            set_result({'output': str(args.output), 'models': len(document['models'])})
            print(f'Exported registry: {args.output}')
        else:
            set_result(document)
            print(json.dumps(document, indent=2, ensure_ascii=False))


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'Also: cortex provider|data|cost|budget|context <args>; cortex usage import <args>; '
        'cortex run <python-skill> <args>. Use <command> --help for details.'), allow_abbrev=False)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status', help='Show offline runtime, scope and registry status').set_defaults(func=cmd_status)
    p_doctor = sub.add_parser('doctor', help='Check installation, registry, skills, and selected data (offline)')
    p_doctor.add_argument('--repair', action='store_true', help='Back up and quarantine corrupt selected-scope JSONL data only')
    p_doctor.set_defaults(func=cmd_doctor)
    skills = sub.add_parser('skills', help='List or validate installed skills').add_subparsers(dest='skills_command', required=True)
    skills.add_parser('list').set_defaults(func=cmd_skills)
    validate = skills.add_parser('validate')
    validate.add_argument('name', nargs='?')
    validate.add_argument('--all', action='store_true')
    validate.set_defaults(func=cmd_skills)
    models = sub.add_parser('models', help='Manage the central offline model registry').add_subparsers(dest='models_command', required=True)
    listing = models.add_parser('list')
    listing.add_argument('--provider', choices=PROVIDERS)
    listing.add_argument('--query')
    show = models.add_parser('show')
    show.add_argument('model')
    show.add_argument('--provider', choices=PROVIDERS)
    setting = models.add_parser('set', help='Create or replace a global user override')
    setting.add_argument('model')
    setting.add_argument('--provider', choices=PROVIDERS, required=True)
    setting.add_argument('--context', type=int)
    setting.add_argument('--alias', action='append', help='Replace aliases (repeatable)')
    setting.add_argument('--clear-aliases', action='store_true')
    matching = setting.add_mutually_exclusive_group()
    matching.add_argument('--exact', action='store_true', help='Disable snapshot/tag suffix matching')
    matching.add_argument('--allow-suffix', action='store_true')
    for option in ('input', 'output', 'cache-read', 'cache-write'):
        setting.add_argument('--' + option, type=float, help='USD per million tokens')
    setting.add_argument('--unpriced', action='store_true')
    remove = models.add_parser('remove', help='Remove a user entry/override; bundled definitions remain')
    remove.add_argument('model')
    remove.add_argument('--provider', choices=PROVIDERS, required=True)
    models.add_parser('validate')
    exporting = models.add_parser('export')
    exporting.add_argument('--output', type=Path)
    exporting.add_argument('--overrides-only', action='store_true')
    for child in (listing, show, setting, remove, exporting):
        child.set_defaults(func=cmd_models)
    models.choices['validate'].set_defaults(func=cmd_models)
    return parser


@command(scoped=True)
def main():
    arguments = sys.argv[1:]
    if arguments and arguments[0] in PROXIES:
        group, rest = arguments[0], arguments[1:]
        if group == 'usage':
            if rest in (['--help'], ['-h']):
                print('usage: cortex usage import [options]\nImport local usage; use cortex usage import --help for options.')
                return 0
            if not rest or rest[0] != 'import':
                raise ValueError('Usage: cortex usage import [options]')
        return forward(PROXIES[group], rest)
    if arguments and arguments[0] == 'run':
        if arguments[1:] in (['--help'], ['-h']):
            print('usage: cortex run SKILL [arguments]\nPython skills: ' + ', '.join(PYTHON_SKILLS))
            return 0
        if len(arguments) < 2:
            raise ValueError('Usage: cortex run SKILL [arguments]')
        if arguments[1].startswith('-'):
            raise ValueError('Usage: cortex run SKILL [arguments]')
        return forward(arguments[1], arguments[2:])
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
