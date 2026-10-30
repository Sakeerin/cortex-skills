"""Storage namespaces shared by every data-backed skill.

Global storage retains the original layout. Project/session namespaces never
inherit data from their parents, so a read cannot accidentally cross scopes.
"""

from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path


@dataclass(frozen=True)
class DataScope:
    kind: str = 'global'
    project: str | None = None
    session: str | None = None

    def as_dict(self):
        return {'kind': self.kind, 'project': self.project, 'session': self.session}

    def directory(self, root: Path) -> Path:
        if self.kind == 'global':
            return root
        # Compact 128-bit identifiers keep nested session paths usable on
        # Windows without requiring system-wide long-path configuration.
        parts = ['scopes', 'p-' + _digest(self.project)]
        if self.kind == 'session':
            parts += ['s-' + _digest(self.session)]
        target = root
        for part in parts:
            target = target / part
            if target.is_symlink() or (hasattr(target, 'is_junction') and target.is_junction()):
                raise ValueError(f'Scope directory cannot be a link: {target}')
        if not target.resolve().is_relative_to(root.resolve()):
            raise ValueError('Scope directory escapes the data root')
        return target


_active_scope: ContextVar[DataScope | None] = ContextVar('ai_skills_scope', default=None)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]


def project_root(path: Path) -> Path:
    """Use the nearest Git root, including worktrees (.git can be a file)."""
    path = path.expanduser().resolve()
    for candidate in (path, *path.parents):
        if (candidate / '.git').exists():
            return candidate
    return path


def resolve_scope(kind=None, project=None, session=None) -> DataScope:
    from env_loader import get

    kind = kind or get('AI_SKILLS_SCOPE', 'global')
    if kind not in {'global', 'project', 'session'}:
        raise ValueError('Scope must be global, project, or session')
    if kind == 'global':
        if project is not None or session is not None:
            raise ValueError('--scope-project/--scope-session require a non-global --scope')
        return DataScope()
    if kind == 'project' and session is not None:
        raise ValueError('--scope-session requires --scope session')
    location = Path(project or get('AI_SKILLS_PROJECT_DIR') or Path.cwd()).expanduser()
    if not location.is_dir():
        raise ValueError(f'Project directory not found: {location}')
    canonical = os.path.normcase(str(project_root(location)))
    if kind == 'session':
        session = session if session is not None else get('AI_SKILLS_SESSION_ID')
        if not session or not session.strip() or len(session) > 1024 or any(ord(c) < 32 for c in session):
            raise ValueError('Session scope requires --scope-session ID or AI_SKILLS_SESSION_ID')
    else:
        session = None
    return DataScope(kind, canonical, session)


def current_scope() -> DataScope:
    active = _active_scope.get()
    return active if active is not None else resolve_scope()


def set_scope(scope: DataScope):
    return _active_scope.set(scope)


def reset_scope(token):
    _active_scope.reset(token)
