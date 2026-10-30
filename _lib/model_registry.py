"""Validated, offline model catalog shared by context, discovery and pricing."""

from copy import deepcopy
import json
import math
from pathlib import Path

from env_loader import get
from errors import DataError, AmbiguousModelError
from file_lock import atomic_write, data_lock

PROVIDERS = ('claude', 'gemini', 'openai', 'ollama', 'mistral', 'lmstudio')
LOCAL_PROVIDERS = frozenset({'ollama', 'lmstudio'})
ROOT = Path(__file__).resolve().parents[1]


def _name(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise DataError('Model IDs and aliases must be nonempty strings without surrounding whitespace')
    if len(value) > 512 or any(ord(char) < 32 for char in value):
        raise DataError('Model IDs and aliases must not contain control characters or exceed 512 characters')
    return value.casefold()


def validate_rates(rates):
    if not isinstance(rates, dict) or not {'input', 'output'} <= rates.keys():
        raise DataError('Rates require input and output prices per million tokens')
    if set(rates) - {'input', 'output', 'cache_read', 'cache_write'}:
        raise DataError('Unknown rate fields')
    for value in rates.values():
        try:
            valid = type(value) in (float, int) and math.isfinite(value) and value >= 0
        except OverflowError:
            valid = False
        if not valid:
            raise DataError('Prices must be finite, nonnegative numbers')


def validate_registry(document, *, overrides=False):
    """Validate a versioned document, returning an independent normalized copy."""
    if not isinstance(document, dict) or type(document.get('version')) is not int or document['version'] != 1:
        raise DataError('Model registry requires version: 1')
    if set(document) - {'version', 'models', 'provider_prefixes'}:
        raise DataError('Unknown model registry fields')
    rows = document.get('models')
    if not isinstance(rows, list):
        raise DataError('Registry models must be an array')
    prefixes = document.get('provider_prefixes', {})
    if not isinstance(prefixes, dict) or (overrides and prefixes):
        raise DataError('Only the bundled registry may define provider_prefixes')
    for prefix, provider in prefixes.items():
        _name(prefix)
        if provider not in PROVIDERS:
            raise DataError(f'Unknown provider in prefix map: {provider}')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'provider', 'id', 'context_window', 'aliases', 'match_suffix', 'rates'}:
            raise DataError('Each model requires provider, id, context_window, aliases, match_suffix, and rates')
        provider = row['provider']
        if provider not in PROVIDERS:
            raise DataError(f'Unsupported model provider: {provider}')
        if type(row['context_window']) is not int or row['context_window'] < 0:
            raise DataError('context_window must be a nonnegative integer (0 means unknown)')
        if type(row['match_suffix']) is not bool or not isinstance(row['aliases'], list):
            raise DataError('match_suffix must be boolean and aliases must be an array')
        for identifier in [row['id'], *row['aliases']]:
            key = provider, _name(identifier)
            if key in seen:
                raise DataError(f'Duplicate model ID or alias: {provider}/{identifier}')
            seen.add(key)
        if row['rates'] is not None:
            validate_rates(row['rates'])
            if provider in LOCAL_PROVIDERS and any(row['rates'].values()):
                raise DataError('Local provider token rates must be zero')
    return deepcopy(document)


def _read(path):
    try:
        with path.open(encoding='utf-8-sig') as handle:
            return json.load(handle)
    except (ValueError, UnicodeError) as exc:
        raise DataError(f'Invalid model data in {path}: {exc}') from exc


def _signature(path):
    try:
        stat = path.stat()
        return str(path), stat.st_mtime_ns, stat.st_size, stat.st_ino
    except FileNotFoundError:
        return str(path), None


class ModelRegistry:
    def __init__(self, builtin_path=None, override_path=None, rate_path=None):
        self.builtin_path = Path(builtin_path) if builtin_path is not None else ROOT / 'model-registry.json'
        base = Path(get('AI_SKILLS_DATA_DIR', str(Path.home() / '.ai-skills-data'))).expanduser()
        self.override_path = (Path(override_path).expanduser() if override_path is not None
                              else Path(get('AI_MODEL_REGISTRY', str(base / 'model-overrides.json'))).expanduser())
        self.rate_path = Path(rate_path) if rate_path is not None else ROOT / 'cost-rates.json'
        self._cached_signature = None
        self._cached = None

    def signature(self):
        return tuple(_signature(path) for path in (self.builtin_path, self.rate_path, self.override_path))

    def _overrides(self):
        if not self.override_path.exists():
            return {'version': 1, 'models': []}
        return validate_registry(_read(self.override_path), overrides=True)

    def _load(self):
        signature = self.signature()
        if self._cached is not None and self._cached_signature == signature:
            return self._cached
        bundled = validate_registry(_read(self.builtin_path))
        rows = {(row['provider'], _name(row['id'])): row for row in bundled['models']}
        legacy = _read(self.rate_path) if self.rate_path.exists() else {}
        if not isinstance(legacy, dict):
            raise DataError('cost-rates.json must be a model-to-rates object')
        legacy = {_name(name): rates for name, rates in legacy.items()}
        for name, rates in legacy.items():
            validate_rates(rates)
            for row in rows.values():
                if _name(row['id']) == name and row['provider'] not in LOCAL_PROVIDERS:
                    row['rates'] = deepcopy(rates)
        overrides = self._overrides()
        for row in overrides['models']:
            rows[row['provider'], _name(row['id'])] = row
        combined = {'version': 1, 'models': list(rows.values()),
                    'provider_prefixes': bundled.get('provider_prefixes', {})}
        validate_registry(combined)
        self._cached = combined, legacy, overrides
        self._cached_signature = signature
        return self._cached

    def list_models(self, provider=None):
        if provider is not None and provider not in PROVIDERS:
            raise ValueError(f'Unsupported provider: {provider}')
        rows = self._load()[0]['models']
        return deepcopy(sorted((row for row in rows if provider is None or row['provider'] == provider),
                               key=lambda row: (PROVIDERS.index(row['provider']), row['id'])))

    def names(self, provider):
        return [row['id'] for row in self.list_models(provider)]

    def resolve(self, model, provider=None):
        if not model:
            return None
        return self._resolve(model, provider, self._load()[0]['models'])

    @staticmethod
    def _resolve(model, provider, rows):
        if provider is not None and provider not in PROVIDERS:
            raise ValueError(f'Unsupported provider: {provider}')
        if not model:
            return None
        name = _name(model)
        matches = []
        for row in rows:
            if provider is not None and row['provider'] != provider:
                continue
            for candidate in [row['id'], *row['aliases']]:
                candidate = _name(candidate)
                exact = name == candidate
                suffix = row['match_suffix'] and (name.startswith(candidate + '-') or name.startswith(candidate + ':'))
                if exact or suffix:
                    matches.append(((int(exact), len(candidate)), row))
        if not matches:
            return None
        rank = max(item[0] for item in matches)
        best = [row for score, row in matches if score == rank]
        if len({(row['provider'], _name(row['id'])) for row in best}) > 1:
            raise AmbiguousModelError(f'Ambiguous model {model}; specify --provider')
        return deepcopy(best[0])

    def infer_provider(self, model):
        if not model:
            return 'unknown'
        catalog = self._load()[0]
        try:
            row = self._resolve(model, None, catalog['models'])
        except DataError:
            raise
        except ValueError:
            return 'unknown'
        if row:
            return row['provider']
        prefixes = catalog.get('provider_prefixes', {})
        return self._provider_hint(model, prefixes)

    @staticmethod
    def _provider_hint(model, prefixes):
        return next((prefixes[key] for key in sorted(prefixes, key=len, reverse=True)
                     if model.casefold().startswith(key.casefold())), 'unknown')

    def rate(self, model, provider=None):
        catalog, legacy, overrides = self._load()
        if provider in LOCAL_PROVIDERS:
            return {'input': 0.0, 'output': 0.0}
        row = self._resolve(model, provider, catalog['models'])
        # Explicit user models take priority over the compatibility overlay.
        if row and any(item['provider'] == row['provider'] and _name(item['id']) == _name(row['id'])
                       for item in overrides['models']):
            return deepcopy(row['rates'])
        # Legacy prices may describe more-specific snapshots/custom IDs.
        name = _name(model)
        for key in sorted(legacy, key=len, reverse=True):
            if name == key or name.startswith(key + '-') or name.startswith(key + ':'):
                try:
                    legacy_model = self._resolve(key, None, catalog['models'])
                except AmbiguousModelError:
                    legacy_model = self._resolve(key, provider, catalog['models']) if provider else None
                    if legacy_model is None:
                        continue
                owner = (legacy_model['provider'] if legacy_model else
                         self._provider_hint(key, catalog.get('provider_prefixes', {})))
                if provider is None or owner in {'unknown', provider}:
                    return deepcopy(legacy[key])
        return deepcopy(row['rates']) if row else None

    def export(self, overrides_only=False):
        return self._overrides() if overrides_only else {'version': 1, 'models': self.list_models()}

    def rate_table(self):
        """Legacy provider-agnostic view; new consumers should call rate(model, provider)."""
        combined, legacy, overrides = self._load()
        rates = {row['id'].casefold(): row['rates'] for row in combined['models'] if row['rates'] is not None}
        rates.update(legacy)
        for row in overrides['models']:
            key = row['id'].casefold()
            if row['rates'] is None:
                rates.pop(key, None)
            else:
                rates[key] = row['rates']
        return deepcopy(rates)

    def status(self):
        combined, legacy, overrides = self._load()
        return {'version': 1, 'models': len(combined['models']), 'overrides': len(overrides['models']),
                'legacy_prices': len(legacy), 'registry_scope': 'global',
                'builtin_path': str(self.builtin_path), 'override_path': str(self.override_path),
                'legacy_rates_path': str(self.rate_path)}

    def set_model(self, provider, model, **changes):
        if provider not in PROVIDERS:
            raise ValueError(f'Unsupported provider: {provider}')
        if set(changes) - {'context_window', 'aliases', 'match_suffix', 'rates'}:
            raise ValueError('Model identity cannot be changed by metadata updates')
        _name(model)
        self._check_write_path()
        with data_lock(self.override_path.parent):
            original = self._overrides()
            existing = next((row for row in self.list_models(provider) if _name(row['id']) == _name(model)), None)
            row = existing or {'provider': provider, 'id': model, 'context_window': 0,
                               'aliases': [], 'match_suffix': True, 'rates': None}
            row.update(changes)
            candidate = {'version': 1, 'models': [item for item in original['models']
                         if (item['provider'], _name(item['id'])) != (provider, _name(model))] + [row]}
            validate_registry(candidate, overrides=True)
            effective = [item for item in self.list_models() if
                         (item['provider'], _name(item['id'])) != (provider, _name(model))] + [row]
            validate_registry({'version': 1, 'models': effective})
            atomic_write(self.override_path, json.dumps(candidate, indent=2, ensure_ascii=False).encode('utf-8'))
            self._cached_signature = None
            return deepcopy(row)

    def remove_model(self, provider, model):
        if provider not in PROVIDERS:
            raise ValueError(f'Unsupported provider: {provider}')
        self._check_write_path()
        with data_lock(self.override_path.parent):
            document = self._overrides()
            rows = [row for row in document['models']
                    if (row['provider'], _name(row['id'])) != (provider, _name(model))]
            if len(rows) == len(document['models']):
                raise FileNotFoundError(f'No user override for {provider}/{model}; bundled models cannot be removed')
            document['models'] = rows
            # Removing an override can re-expose a bundled alias; validate before replacing.
            bundled = ModelRegistry(self.builtin_path, override_path=self.override_path, rate_path=self.rate_path)
            base = validate_registry(_read(bundled.builtin_path))
            merged = {(row['provider'], _name(row['id'])): row for row in base['models']}
            merged.update({(row['provider'], _name(row['id'])): row for row in rows})
            validate_registry({'version': 1, 'models': list(merged.values())})
            atomic_write(self.override_path, json.dumps(document, indent=2).encode('utf-8'))
            self._cached_signature = None

    def _check_write_path(self):
        if self.override_path.resolve() in {self.builtin_path.resolve(), self.rate_path.resolve()}:
            raise ValueError('User registry cannot overwrite bundled catalog or legacy rates')


_registries = {}


def get_registry(*, rate_path=None):
    candidate = ModelRegistry(rate_path=rate_path)
    key = tuple(str(path.resolve()) for path in (candidate.builtin_path, candidate.override_path, candidate.rate_path))
    if key not in _registries:
        _registries[key] = candidate
    return _registries[key]
