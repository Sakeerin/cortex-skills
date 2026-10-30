"""Common Python CLI contract: global flags, JSON envelopes and exit codes."""

import argparse
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from contextvars import ContextVar
from functools import wraps
import io
import json
from pathlib import Path
import subprocess
import sys

from data_scope import DataScope, reset_scope, resolve_scope, set_scope
from errors import DataError

SUCCESS = 0
FAILURE = 1
USAGE = 2
NOT_FOUND = 3
CONFLICT = 4
DATA_ERROR = 5
UNAVAILABLE = 6

_NAMES = {FAILURE: 'operation_failed', USAGE: 'invalid_arguments', NOT_FOUND: 'not_found',
          CONFLICT: 'conflict', DATA_ERROR: 'invalid_data', UNAVAILABLE: 'unavailable'}
_UNSET = object()
_result = ContextVar('cli_result', default=_UNSET)
_json = ContextVar('cli_json', default=False)


class CLIError(Exception):
    def __init__(self, message, exit_code=FAILURE):
        super().__init__(message)
        self.exit_code = exit_code


def set_result(data):
    """Attach structured data without changing the existing human formatter."""
    _result.set(data)


def json_mode():
    return _json.get()


def _common_arguments(argv, scoped):
    # Do not consume option-like literal values following the POSIX separator.
    split = argv.index('--') if '--' in argv else len(argv)
    head, tail = argv[:split], argv[split:]
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument('--json', action='store_true')
    if scoped:
        parser.add_argument('--scope', choices=['global', 'project', 'session'])
        parser.add_argument('--scope-project', metavar='PATH')
        parser.add_argument('--scope-session', metavar='ID')
    options, rest = parser.parse_known_args(head)
    scope = (resolve_scope(options.scope, options.scope_project, options.scope_session)
             if scoped and not any(flag in rest for flag in ('-h', '--help')) else DataScope())
    return options.json, scope, rest + tail


def command(*, scoped=False):
    """Wrap a main() while keeping direct in-process callers backwards compatible.

    Normal callers still observe SystemExit for failures; successful main calls
    return zero. CLI entry points therefore use raise SystemExit(main()).
    """
    def decorate(main):
        @wraps(main)
        def run():
            original_argv = sys.argv
            argv = original_argv[1:]
            before_separator = argv[:argv.index('--')] if '--' in argv else argv
            machine = '--json' in before_separator
            stdout, stderr = io.StringIO(), io.StringIO()
            scope = DataScope()
            token = None
            result_token = _result.set(_UNSET)
            json_token = _json.set(machine)
            code, message = SUCCESS, None
            try:
                with redirect_stdout(stdout) if machine else nullcontext(), redirect_stderr(stderr):
                    try:
                        machine, scope, rest = _common_arguments(argv, scoped)
                        token = set_scope(scope)
                        sys.argv = [original_argv[0], *rest]
                        if '-h' in rest or '--help' in rest:
                            print('Common options: --json' + (
                                ' --scope {global,project,session} --scope-project PATH --scope-session ID'
                                if scoped else ''))
                        returned = main()
                        code = returned if type(returned) is int else SUCCESS
                    except CLIError as exc:
                        code, message = exc.exit_code, str(exc)
                    except SystemExit as exc:
                        code = exc.code if type(exc.code) is int else (SUCCESS if exc.code is None else FAILURE)
                        if isinstance(exc.code, str):
                            message = exc.code
                    except FileNotFoundError as exc:
                        code, message = NOT_FOUND, str(exc)
                    except FileExistsError as exc:
                        code, message = CONFLICT, str(exc)
                    except (DataError, json.JSONDecodeError, UnicodeError) as exc:
                        code, message = DATA_ERROR, str(exc)
                    except ValueError as exc:
                        code, message = USAGE, str(exc)
                    except (TimeoutError, ConnectionError) as exc:
                        code, message = UNAVAILABLE, str(exc)
                    except OSError as exc:
                        code, message = FAILURE, str(exc)
                    except subprocess.CalledProcessError as exc:
                        code, message = UNAVAILABLE, f'External command failed (status {exc.returncode})'
                    except Exception as exc:
                        code, message = FAILURE, f'{type(exc).__name__}: {exc}'
                diagnostics = stderr.getvalue().strip()
                if message is None and code:
                    message = diagnostics or 'Command failed'
                if machine:
                    data = _result.get()
                    if data is _UNSET:
                        rendered = stdout.getvalue().strip()
                        try:
                            data = json.loads(rendered) if rendered else None
                        except ValueError:
                            data = {'text': stdout.getvalue()}
                    try:
                        # Validate before writing any bytes so encoding failures
                        # still produce one complete machine-readable document.
                        json.dumps(data, allow_nan=False, default=_json_default)
                    except (TypeError, ValueError) as exc:
                        code, message, data = FAILURE, f'Invalid command result: {exc}', None
                    envelope = {
                        'schema_version': 1, 'ok': code == SUCCESS, 'exit_code': code,
                        'scope': scope.as_dict(), 'data': data,
                        'error': {'code': _NAMES.get(code, 'operation_failed'), 'message': message} if code else None,
                        'warnings': diagnostics.splitlines() if not code and diagnostics else [],
                    }
                    print(json.dumps(envelope, ensure_ascii=False, allow_nan=False, default=_json_default))
                else:
                    if diagnostics:
                        print(diagnostics, file=sys.stderr)
                    if message and message != diagnostics:
                        print(f'Error: {message}', file=sys.stderr)
                if code:
                    raise SystemExit(code)
                return SUCCESS
            finally:
                sys.argv = original_argv
                if token is not None:
                    reset_scope(token)
                _result.reset(result_token)
                _json.reset(json_token)
        return run
    return decorate


def _json_default(value):
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f'Unsupported JSON result type: {type(value).__name__}')
