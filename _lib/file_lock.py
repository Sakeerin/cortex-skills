"""Cross-process data-directory locks and atomic file replacement (stdlib only)."""

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import tempfile
import threading
import time


class _LockState:
    def __init__(self):
        self.mutex = threading.RLock()
        self.depth = 0


_registry = {}
_registry_guard = threading.Lock()


@contextmanager
def data_lock(data_dir: Path, timeout: float = 15):
    """Serialize cooperating writers; nested calls in the same thread are safe."""
    directory = Path(data_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    key = os.path.normcase(str(directory))
    with _registry_guard:
        state = _registry.setdefault(key, _LockState())
    with state.mutex:
        if state.depth:
            state.depth += 1
            try:
                yield
            finally:
                state.depth -= 1
            return
        lock_path = directory / '.ai-skills.lock'
        if lock_path.is_symlink():
            raise ValueError(f'Refusing symlink lock: {lock_path}')
        with lock_path.open('a+b') as handle:
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b'\0')
                handle.flush()
            deadline = time.monotonic() + timeout
            while True:
                try:
                    handle.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f'Data directory is busy: {directory}') from exc
                    time.sleep(0.05)
            state.depth = 1
            try:
                yield
            finally:
                state.depth = 0
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_write(path: Path, content: bytes) -> None:
    """Flush a unique sibling temp file before replacing the destination."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f'Refusing to overwrite symlink: {path}')
    fd, name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
