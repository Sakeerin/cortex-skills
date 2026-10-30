"""Import recorded Claude/Gemini usage without storing transcript contents."""

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys

from cost_tracker import CostTracker
from data_manager import DataManager, validate_cost_event
from env_loader import get
from file_lock import atomic_write, data_lock


def _signature(path):
    stat = path.stat()
    return [stat.st_mtime_ns, stat.st_size, stat.st_ino]


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError('token counts must be nonnegative integers')
    return value


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError('missing usage timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('usage timestamp must include timezone')
    return parsed.isoformat()


def _jsonl_rows(path, warnings):
    with path.open('rb') as handle:
        for index, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield index, json.loads(line.decode('utf-8-sig'))
            except (UnicodeError, ValueError):
                warnings.append(f'{path}:{index}: incomplete or invalid JSON; retry on next import')


def _normalize(provider, row, session, path):
    message = row.get('message')
    message = message if isinstance(message, dict) else row
    role = row.get('type') or message.get('role') or row.get('role')
    if role not in {'assistant', 'gemini', 'model'}:
        return None
    usage = message.get('usage') if provider == 'claude' else row.get('usageMetadata')
    if not usage:
        usage = row.get('usage') if provider == 'claude' else row.get('tokens')
    if not isinstance(usage, dict) or not usage:
        return None
    if provider == 'claude':
        uncached = _count(usage.get('input_tokens', 0))
        cached = _count(usage.get('cache_read_input_tokens', 0))
        written = _count(usage.get('cache_creation_input_tokens', 0))
        output = _count(usage.get('output_tokens', 0))
        thoughts = 0
        tool = 0
        server_tools = usage.get('server_tool_use') or {}
        if not isinstance(server_tools, dict):
            raise ValueError('server_tool_use must be an object')
        server_tools = {key: _count(value) for key, value in server_tools.items()}
        input_tokens = uncached + cached + written
    else:
        input_tokens = _count(usage.get('promptTokenCount', usage.get('input', 0)))
        cached = _count(usage.get('cachedContentTokenCount', usage.get('cached', 0)))
        written = 0
        thoughts = _count(usage.get('thoughtsTokenCount', usage.get('thoughts', 0)))
        tool = _count(usage.get('toolUsePromptTokenCount', usage.get('tool', 0)))
        output = _count(usage.get('candidatesTokenCount', usage.get('output', 0))) + thoughts
        if cached > input_tokens:
            raise ValueError('cached input exceeds total input')
        uncached = input_tokens - cached
        server_tools = {}
    model = message.get('model') or row.get('model')
    if not isinstance(model, str) or not model.strip():
        raise ValueError('usage has no model name')
    timestamp = _timestamp(row.get('timestamp') or row.get('createTime'))
    session = row.get('sessionId') or row.get('session_id') or session
    identity = message.get('id') or row.get('id') or row.get('uuid')
    identity = identity or f'{timestamp}:{model}'
    key = json.dumps([provider, str(session), str(identity)], separators=(',', ':'))
    return {
        'id': 'import-' + hashlib.sha256(key.encode()).hexdigest(),
        'timestamp': timestamp, 'provider': provider, 'model': model,
        'session_id': str(session), 'input_tokens': input_tokens,
        'output_tokens': output, 'total_tokens': input_tokens + output,
        'metadata': {
            'source': 'session_import', 'source_file': str(path.resolve()),
            'input_uncached_tokens': uncached, 'cache_read_tokens': cached,
            'cache_write_tokens': written, 'reasoning_tokens': thoughts,
            'tool_tokens': tool,
            'server_tool_requests': server_tools,
        },
    }


def _merge(left, right):
    """Streaming records can repeat a request with increasing token totals."""
    result = dict(right)
    left_meta = left.get('metadata') or {}
    right_meta = right['metadata']
    # Pick one coherent input snapshot: cached input can replace uncached input,
    # so independently taking maxima for each component would count it twice.
    def input_rank(event):
        meta = event.get('metadata') or {}
        return event['input_tokens'], meta.get('cache_read_tokens', 0) + meta.get('cache_write_tokens', 0)
    input_owner = max((left, right), key=input_rank)
    input_meta = input_owner.get('metadata') or {}
    result['input_tokens'] = input_owner['input_tokens']
    result['output_tokens'] = max(left['output_tokens'], right['output_tokens'])
    result['total_tokens'] = result['input_tokens'] + result['output_tokens']
    result['metadata'] = dict(right_meta)
    for key in ('cache_read_tokens', 'cache_write_tokens'):
        result['metadata'][key] = input_meta.get(key, 0)
    result['metadata']['input_uncached_tokens'] = (
        result['input_tokens'] - result['metadata']['cache_read_tokens']
        - result['metadata']['cache_write_tokens'])
    for key in ('reasoning_tokens', 'tool_tokens'):
        result['metadata'][key] = max(left_meta.get(key, 0), right_meta.get(key, 0))
    tools = dict(left_meta.get('server_tool_requests', {}))
    for key, count in right_meta.get('server_tool_requests', {}).items():
        tools[key] = max(tools.get(key, 0), count)
    result['metadata']['server_tool_requests'] = tools
    # Preserve first provenance so replaying identical copied files is a no-op.
    result['metadata']['source_file'] = left_meta.get('source_file', right_meta['source_file'])
    result['timestamp'] = left['timestamp']
    return result


def _price(event, tracker):
    meta = event['metadata']
    rate = tracker.get_rate(event['model'], event['provider'])
    known = tracker.has_rate(event['model'], event['provider'])
    for field, key in (('cache_read_tokens', 'cache_read'), ('cache_write_tokens', 'cache_write')):
        if meta[field] and key not in rate:
            known = False
    # Tool-use prompt accounting is provider-specific; retain it without inventing a price.
    if meta['tool_tokens'] or any(meta.get('server_tool_requests', {}).values()):
        known = False
    if known:
        amount = (meta['input_uncached_tokens'] * rate['input']
                  + event['output_tokens'] * rate['output']
                  + meta['cache_read_tokens'] * rate.get('cache_read', 0)
                  + meta['cache_write_tokens'] * rate.get('cache_write', 0)) / 1_000_000
        known = math.isfinite(amount) and amount >= 0
    event['cost_usd'] = round(amount, 6) if known else None
    event['pricing_status'] = 'estimated' if known else 'unknown'
    return event


class UsageImporter:
    def __init__(self, tracker: CostTracker):
        self.tracker = tracker
        self.state_path = tracker.data_dir / 'usage-import-state.json'

    def _files(self, provider, source):
        if source is not None:
            root = Path(source).expanduser()
        elif provider == 'claude':
            root = Path(get('AI_CLAUDE_SESSION_DIR', str(Path.home() / '.claude/projects'))).expanduser()
        else:
            root = Path(get('AI_GEMINI_SESSION_DIR', str(Path.home() / '.gemini/tmp'))).expanduser()
        if root.is_file():
            return [root] if not root.is_symlink() else []
        if not root.exists():
            if source is not None:
                raise ValueError(f'Session source not found: {root}')
            return []
        suffixes = {'.jsonl'} if provider == 'claude' else {'.json', '.jsonl'}
        return sorted(path for path in root.rglob('*') if path.is_file() and not path.is_symlink()
                      and path.suffix in suffixes
                      and (provider == 'claude' or source is not None
                           or path.name.startswith('session-')))

    def _read(self, provider, path, warnings):
        records = []
        if path.suffix == '.json':
            with path.open(encoding='utf-8-sig') as handle:
                document = json.load(handle)
            if not isinstance(document, dict):
                raise ValueError('session document must be an object')
            session = document.get('sessionId') or document.get('session_id') or path.stem
            rows = document.get('messages', [])
            if not isinstance(rows, list):
                raise ValueError('messages must be an array')
            lines = enumerate(rows, 1)
        else:
            session = path.stem
            lines = _jsonl_rows(path, warnings)
        for index, row in lines:
            if not isinstance(row, dict):
                continue
            session = row.get('sessionId') or row.get('session_id') or session
            try:
                event = _normalize(provider, row, session, path)
                if event is not None:
                    records.append(event)
            except (TypeError, ValueError) as exc:
                warnings.append(f'{path}:{index}: {exc}')
        return records

    def import_usage(self, provider=None, source=None, dry_run=False):
        if provider not in (None, 'claude', 'gemini'):
            raise ValueError('Usage import supports claude and gemini')
        if source is not None and provider is None:
            raise ValueError('--source requires --provider')
        if dry_run:
            return self._import(provider, source, True)
        with data_lock(self.tracker.data_dir):
            return self._import(provider, source, False)

    def _import(self, provider, source, dry_run):
        result = {'imported': 0, 'updated': 0, 'duplicates': 0, 'unpriced': 0,
                  'files_scanned': 0, 'files_unchanged': 0, 'warnings': [],
                  'backup': None, 'dry_run': dry_run}
        log_path = self.tracker.log_path
        events = []
        if log_path.exists():
            for line in log_path.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    try:
                        event = json.loads(line)
                        error = validate_cost_event(event)
                        if error:
                            raise ValueError(error)
                        events.append(event)
                    except ValueError as exc:
                        raise ValueError('Invalid cost log; run ai-data doctor before importing') from exc
        indexes = {event['id']: index for index, event in enumerate(events)}
        old_signature = _signature(log_path) if log_path.exists() else None
        rate_signature = _signature(self.tracker.rate_path) if self.tracker.rate_path.exists() else None
        state = {}
        if self.state_path.exists():
            try:
                state = json.loads(self.state_path.read_text(encoding='utf-8'))
            except (ValueError, UnicodeError):
                pass
        if not isinstance(state, dict) or state.get('log_signature') != old_signature or state.get('rate_signature') != rate_signature:
            state = {}
        previous_files = state.get('files', {})
        if not isinstance(previous_files, dict):
            previous_files = {}
        files = dict(previous_files)
        candidates = {}
        for name in ([provider] if provider else ['claude', 'gemini']):
            for path in self._files(name, source):
                key = name + ':' + str(path.resolve())
                try:
                    signature = _signature(path)
                    if previous_files.get(key) == signature:
                        result['files_unchanged'] += 1
                        continue
                    warning_count = len(result['warnings'])
                    records = self._read(name, path, result['warnings'])
                    result['files_scanned'] += 1
                    for event in records:
                        identity = event['id']
                        if identity in candidates:
                            result['duplicates'] += 1
                            event = _merge(candidates[identity], event)
                        candidates[identity] = event
                    if len(result['warnings']) == warning_count and _signature(path) == signature:
                        files[key] = signature
                except (OSError, ValueError, UnicodeError) as exc:
                    result['warnings'].append(f'{path}: {exc}')
                    files.pop(key, None)
        for identity, event in candidates.items():
            index = indexes.get(identity)
            if index is not None:
                event = _merge(events[index], event)
            event = _price(event, self.tracker)
            result['unpriced'] += event['cost_usd'] is None
            if index is None:
                indexes[identity] = len(events)
                events.append(event)
                result['imported'] += 1
            elif event != events[index]:
                events[index] = event
                result['updated'] += 1
            else:
                result['duplicates'] += 1
        if dry_run:
            return result
        if result['imported'] or result['updated']:
            if log_path.exists():
                result['backup'] = str(DataManager(self.tracker.data_dir).backup())
            content = ''.join(json.dumps(event, ensure_ascii=False) + '\n' for event in events)
            atomic_write(log_path, content.encode('utf-8'))
            self.tracker.invalidate_events()
        new_state = {'version': 1, 'files': files, 'rate_signature': rate_signature,
                     'log_signature': _signature(log_path) if log_path.exists() else None}
        if new_state != state:
            atomic_write(self.state_path, json.dumps(new_state, indent=2).encode('utf-8'))
        # Importing historical sessions deliberately does not alter the live session budget.
        return result


def sync_usage(tracker):
    """Best-effort local import for reporting commands; diagnostics go to stderr."""
    if get('AI_USAGE_AUTO_IMPORT', '1').lower() in {'0', 'false', 'no', 'off'}:
        return None
    try:
        report = UsageImporter(tracker).import_usage()
        if report['imported'] or report['updated']:
            print(f"Usage import: {report['imported']} new, {report['updated']} updated", file=sys.stderr)
        for warning in report['warnings'][:5]:
            print(f'Usage import warning: {warning}', file=sys.stderr)
        return report
    except (OSError, ValueError, TimeoutError) as exc:
        print(f'Usage import warning: {exc}', file=sys.stderr)
        return None
