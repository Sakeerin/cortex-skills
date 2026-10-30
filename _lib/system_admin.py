"""Offline installation and skill health checks for the central CLI."""

import ast
from pathlib import Path
import re
import shutil
import sys

from ai_provider import detect, get_model
from data_manager import DataManager
from env_loader import get_data_dir
from model_registry import get_registry

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SKILLS = {
    'todo': 'tasks', 'notes': 'notes', 'memory': 'memory', 'prompt-lib': 'prompt_lib',
    'ai-cost': 'ai_cost', 'ai-data': 'ai_data', 'token-budget': 'token_budget',
    'daily-report': 'daily_report', 'ai-provider': 'ai_provider', 'ai-context': 'ai_context',
    'ai-model-list': 'ai_model_list', 'ai-session-log': 'ai_session_log',
    'project-brief': 'project_brief', 'git-summary': 'git_summary',
    'env-check': 'env_check', 'skill-creator': 'skill_creator',
}
SCOPED_SKILLS = frozenset({'todo', 'notes', 'memory', 'prompt-lib', 'ai-cost',
                          'ai-data', 'token-budget', 'daily-report'})
_NAME = re.compile(r'^[a-z][a-z0-9-]*$')


def skill_path(name):
    if not _NAME.fullmatch(name):
        raise ValueError('Skill names must contain lowercase letters, numbers and hyphens')
    path = ROOT / name
    if not path.is_dir() or path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise FileNotFoundError(f'Skill not found: {name}')
    return path


def list_skills():
    return [{'name': folder.name, 'path': str(folder),
             'python_cli': folder.name in PYTHON_SKILLS,
             'scoped': folder.name in SCOPED_SKILLS}
            for folder in sorted(ROOT.iterdir())
            if _NAME.fullmatch(folder.name) and folder.is_dir() and not folder.is_symlink()
            and folder.resolve().is_relative_to(ROOT.resolve()) and _regular_in_tree(folder / 'SKILL.md')]


def _regular_in_tree(path):
    return path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT.resolve())


def validate_skill(name):
    folder = skill_path(name)
    errors, warnings = [], []
    document = folder / 'SKILL.md'
    if not _regular_in_tree(document):
        errors.append('Missing or linked SKILL.md')
    else:
        text = document.read_text(encoding='utf-8')
        if not text.startswith('---') or '\n---' not in text[3:]:
            errors.append('Missing or incomplete SKILL.md frontmatter')
        for section in ('## Usage', '## When to Use'):
            if section not in text:
                warnings.append(f'Missing section: {section}')
    scripts = list((folder / 'scripts').glob('*.py')) + list((folder / 'scripts').glob('*.sh'))
    if scripts and not (folder / name).is_file():
        errors.append('Missing shell wrapper')
    if name in PYTHON_SKILLS and not (folder / 'scripts' / (PYTHON_SKILLS[name] + '.py')).is_file():
        errors.append('Missing Python entrypoint')
    for script in sorted(scripts):
        if not _regular_in_tree(script):
            errors.append(f'{script.name}: not a regular file inside the installation')
            continue
        try:
            if script.suffix == '.py':
                ast.parse(script.read_text(encoding='utf-8-sig'), filename=str(script))
        except (SyntaxError, UnicodeError, OSError) as exc:
            errors.append(f'{script.name}: {exc}')
    return {'name': name, 'valid': not errors, 'errors': errors, 'warnings': warnings}


def status():
    registry = get_registry()
    model = get_model()
    provider = detect()
    row = registry.resolve(model, provider if provider != 'unknown' else None)
    return {'python': sys.version.split()[0], 'executable': sys.executable,
            'installation': str(ROOT), 'data_dir': str(get_data_dir()),
            'provider': provider, 'model': model,
            'context_window': row['context_window'] if row else None,
            'registry': registry.status(), 'skills': len(list_skills()),
            'tools': {name: shutil.which(name) is not None for name in ('git', 'bash')}}


def doctor(repair=False):
    checks = []
    checks.append({'name': 'python', 'ok': sys.version_info >= (3, 11), 'message': sys.version.split()[0]})
    required = ['cortex.py', 'model-registry.json', '_lib/cli.py', '_lib/model_registry.py',
                '_lib/data_scope.py', '_lib/system_admin.py', '_lib/data_manager.py',
                '_lib/cost_tracker.py', '_lib/usage_importer.py', '_lib/env_loader.py',
                '_lib/file_lock.py', '_lib/errors.py', '_lib/ai_provider.py']
    for name in required:
        checks.append({'name': name, 'ok': (ROOT / name).is_file(), 'message': 'Required runtime file'})
    registry = None
    try:
        registry = get_registry().status()
        checks.append({'name': 'registry', 'ok': True, 'message': f"{registry['models']} registered models"})
    except (OSError, ValueError) as exc:
        checks.append({'name': 'registry', 'ok': False, 'message': str(exc)})
    skills = []
    names = set(PYTHON_SKILLS) | {row['name'] for row in list_skills()}
    for name in sorted(names):
        try:
            skills.append(validate_skill(name))
        except (OSError, ValueError) as exc:
            skills.append({'name': name, 'valid': False, 'errors': [str(exc)], 'warnings': []})
    data = DataManager(get_data_dir()).doctor(repair=repair)
    return {'ok': all(item['ok'] for item in checks) and all(row['valid'] for row in skills) and data['ok'],
            'checks': checks, 'registry': registry, 'skills': skills, 'data': data,
            'repair': repair}
