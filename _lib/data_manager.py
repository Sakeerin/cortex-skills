"""Allowlisted data backups, integrity-checked restore, and JSONL repair.

Manifest v1 is {"version": 1, "files": {name: {"size": int, "sha256": str}}}.
Restore checks transport integrity, not document schemas: damaged originals in
safety backups must remain restorable. Validation/conflict failures are reported
in ``issues`` with no data writes. Backup failures raise OSError or ValueError.
``changed`` records actual replacements; ``files`` records a restore's plan.
Read-only operations still acquire the shared lock, which may create its lock
file and data directory; they never write data, importer state, or backups.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import stat
import tempfile
import uuid
import zipfile
import zlib
from datetime import date, datetime, timezone
from pathlib import Path

from file_lock import data_lock


DATA_FILES = (
    "todos.jsonl", "notes.jsonl", "memory.jsonl", "cost-log.jsonl",
    "prompts.json", "budget.json", "usage-import-state.json", "model-overrides.json",
)
MAX_TOTAL_SIZE = 256 * 1024 * 1024
MAX_MANIFEST_SIZE = 64 * 1024
MANIFEST = "manifest.json"


def _report() -> dict:
    return {"issues": [], "changed": [], "backup": None, "files": [],
            "quarantine": [], "ok": True}


def _issue(report: dict, name: str, message: str, line: int | None = None) -> None:
    issue = {"file": name, "message": message, "resolved": False}
    if line is not None:
        issue["line"] = line
    report["issues"].append(issue)
    report["ok"] = False


def _unique_name(prefix: str, suffix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex}{suffix}"


def _check_path(path: Path) -> None:
    # Also reject linked ancestors (including Windows directory junctions).
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError(f"Linked paths are not allowed: {part.name}")


def _atomic_write(path: Path, content: bytes) -> None:
    _check_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".data-", suffix=".tmp",
                                     dir=path.parent)
    temp = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temp.unlink(missing_ok=True)


def _pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _finite_float(raw: str) -> float:
    result = float(raw)
    if not math.isfinite(result):
        raise ValueError("Non-finite JSON number")
    return result


def _reject_constant(raw: str) -> None:
    raise ValueError("Non-finite JSON number")


def _json(raw: bytes) -> object:
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                      parse_constant=_reject_constant, parse_float=_finite_float)


def _number(value: object) -> bool:
    return (type(value) is int and value >= 0) or (
        type(value) is float and math.isfinite(value) and value >= 0)


def _timestamp(value: object) -> bool:
    if not isinstance(value, str) or not ("T" in value or " " in value):
        return False
    try:
        datetime.fromisoformat(value)
        return True
    except ValueError:
        return False


def _event_error(name: str, obj: object) -> str | None:
    if not isinstance(obj, dict):
        return "Expected a JSON object"
    if name == "cost-log.jsonl":
        for field in ("id", "provider", "model"):
            if not isinstance(obj.get(field), str) or not obj[field].strip():
                return f"{field} must be a nonempty string"
        if not _timestamp(obj.get("timestamp")):
            return "timestamp must be a valid ISO datetime"
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            if type(obj.get(field)) is not int or obj[field] < 0:
                return f"{field} must be a nonnegative integer"
        if obj["total_tokens"] != obj["input_tokens"] + obj["output_tokens"]:
            return "total_tokens must equal input_tokens + output_tokens"
        if "cost_usd" not in obj:
            return "cost_usd is required"
        cost = obj["cost_usd"]
        if cost is None:
            if obj.get("pricing_status") != "unknown":
                return "Null cost_usd requires pricing_status unknown"
        elif not _number(cost):
            return "cost_usd must be finite and nonnegative, or unknown"
        if 'metadata' in obj:
            metadata = obj['metadata']
            if not isinstance(metadata, dict):
                return 'metadata must be an object'
            for field in ('source', 'source_file'):
                if field in metadata and not isinstance(metadata[field], str):
                    return f'metadata.{field} must be a string'
            fields = ('input_uncached_tokens', 'cache_read_tokens', 'cache_write_tokens',
                      'reasoning_tokens', 'tool_tokens')
            for field in fields:
                if field in metadata and (type(metadata[field]) is not int or metadata[field] < 0):
                    return f'metadata.{field} must be a nonnegative integer'
            tools = metadata.get('server_tool_requests', {})
            if not isinstance(tools, dict) or any(type(value) is not int or value < 0
                                                  for value in tools.values()):
                return 'metadata.server_tool_requests must contain nonnegative integers'
            input_fields = fields[:3]
            if metadata.get('cache_read_tokens', 0) + metadata.get('cache_write_tokens', 0) > obj['input_tokens']:
                return 'Cached input components exceed input_tokens'
            if (metadata.get('source') == 'session_import'
                    and all(field in metadata for field in input_fields)
                    and sum(metadata[field] for field in input_fields) != obj['input_tokens']):
                return 'Imported input components must equal input_tokens'
        return None

    identity = "key" if name == "memory.jsonl" else "id"
    if not isinstance(obj.get(identity), str) or not obj[identity].strip():
        return f"{identity} must be a nonempty string"
    # Event logs permit partial updates and tombstones, including key-only ones.
    strings = {"id", "key", "title", "content", "value"}
    for field in strings & obj.keys():
        if not isinstance(obj[field], str):
            return f"{field} must be a string"
    for field in ("deleted", "checked", "done"):
        if field in obj and type(obj[field]) is not bool:
            return f"{field} must be a boolean"
    if "tags" in obj and (not isinstance(obj["tags"], list)
                          or any(not isinstance(tag, str) for tag in obj["tags"])):
        return "tags must be a list of strings"
    if "priority" in obj and obj["priority"] not in ("low", "medium", "high", "urgent"):
        return "Invalid todo priority"
    if "project" in obj and obj["project"] is not None and not isinstance(obj["project"], str):
        return "project must be a string or null"
    for field in ("created_at", "updated_at"):
        if field in obj and not _timestamp(obj[field]):
            return f"{field} must be a valid ISO datetime"
    for field in ("date", "due_date"):
        if field not in obj or (field == "due_date" and obj[field] is None):
            continue
        try:
            date.fromisoformat(obj[field])
        except (ValueError, TypeError):
            return f"{field} must be a valid ISO date"
    return None


def validate_cost_event(event: object) -> str | None:
    """Return an integrity error shared by doctor and the usage importer."""
    return _event_error('cost-log.jsonl', event)


def _document_error(name: str, obj: object) -> str | None:
    if not isinstance(obj, dict):
        return "Expected a JSON object"
    if name == 'model-overrides.json':
        from model_registry import validate_registry
        try:
            validate_registry(obj, overrides=True)
        except ValueError as exc:
            return str(exc)
    if name == "prompts.json":
        for key, entry in obj.items():
            if (not isinstance(entry, dict) or entry.get("name") != key
                    or not isinstance(entry.get("content"), str)):
                return "Prompt entries require name matching key and string content"
    elif name == "budget.json":
        for field in ("daily", "session", "monthly"):
            if obj.get(field) is not None and not _number(obj[field]):
                return f"{field} must be nonnegative or null"
        threshold = obj.get("alert_threshold", 80)
        if not _number(threshold) or threshold > 100:
            return "alert_threshold must be between 0 and 100"
        if not _number(obj.get("session_spend", 0)):
            return "session_spend must be finite and nonnegative"
        if not _number(obj.get('session_baseline', 0)):
            return 'session_baseline must be finite and nonnegative'
    # Importer state is opaque, but must be a well-formed JSON object.
    return None


def validate_document(name: str, obj: object) -> str | None:
    """Validate managed JSON documents for both readers and data doctor."""
    return _document_error(name, obj)


def _read_member(archive: zipfile.ZipFile, name: str, size: int) -> bytes:
    # Bound decompressor output per read, even if a malicious header understates
    # the real uncompressed size. ZipFile.read() can request a huge output buffer.
    chunks = []
    total = 0
    with archive.open(name) as handle:
        while True:
            chunk = handle.read(min(64 * 1024, size - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > size:
                raise ValueError("Archive member exceeds declared size")
            chunks.append(chunk)
    if total != size:
        raise ValueError("Archive member size mismatch")
    return b"".join(chunks)


class DataManager:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir).absolute()

    def backup(self, output: Path | None = None) -> Path:
        """Snapshot only known regular files, including malformed data verbatim."""
        _check_path(self.data_dir)
        with data_lock(self.data_dir):
            _check_path(self.data_dir)
            target = (Path(output).absolute() if output is not None else
                      self.data_dir / "backups" / _unique_name("backup", ".zip"))
            _check_path(target)
            if target.exists():
                raise FileExistsError(f"Backup output already exists: {target}")
            # Never allow the backup itself to become a root-level data file.
            if target.parent == self.data_dir and target.name in DATA_FILES:
                raise ValueError("Backup output cannot be a managed data file")
            payload = {}
            total = 0
            for name in DATA_FILES:
                path = self.data_dir / name
                _check_path(path)
                if not path.exists():
                    continue
                if not path.is_file():
                    raise ValueError(f"Not a regular data file: {name}")
                with path.open("rb") as handle:
                    content = handle.read(MAX_TOTAL_SIZE - total + 1)
                total += len(content)
                if total > MAX_TOTAL_SIZE:
                    raise ValueError("Backup exceeds 256 MiB limit")
                payload[name] = content
            manifest = json.dumps({"version": 1, "files": {
                name: {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                for name, raw in payload.items()
            }}, sort_keys=True).encode("utf-8")
            if total + len(manifest) > MAX_TOTAL_SIZE:
                raise ValueError("Backup exceeds 256 MiB limit including manifest")
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(MANIFEST, manifest)
                for name, raw in payload.items():
                    archive.writestr(name, raw)
            _atomic_write(target, buffer.getvalue())
            return target

    @staticmethod
    def _read_archive(path: Path) -> dict[str, bytes]:
        with zipfile.ZipFile(path, "r") as archive:
            entries = archive.infolist()
            if len(entries) > len(DATA_FILES) + 1:
                raise ValueError("Too many archive entries")
            seen = set()
            total = 0
            for entry in entries:
                name = entry.filename
                if name not in (*DATA_FILES, MANIFEST) or entry.orig_filename != name:
                    raise ValueError("Unexpected or unsafe archive entry")
                if name in seen:
                    raise ValueError("Duplicate archive entry")
                seen.add(name)
                kind = stat.S_IFMT(entry.external_attr >> 16)
                if kind not in (0, stat.S_IFREG) or entry.is_dir() or entry.external_attr & 0x10:
                    raise ValueError("Archive entries must be regular files")
                if entry.flag_bits & 1 or entry.compress_type not in (
                        zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise ValueError("Encrypted or unsupported archive entry")
                total += entry.file_size
                if total > MAX_TOTAL_SIZE:
                    raise ValueError("Archive exceeds 256 MiB uncompressed limit")
            if MANIFEST not in seen:
                raise ValueError("Missing manifest")
            if archive.getinfo(MANIFEST).file_size > MAX_MANIFEST_SIZE:
                raise ValueError("Manifest is too large")
            manifest = _json(_read_member(archive, MANIFEST, archive.getinfo(MANIFEST).file_size))
            if (not isinstance(manifest, dict) or set(manifest) != {"version", "files"}
                    or type(manifest["version"]) is not int or manifest["version"] != 1
                    or not isinstance(manifest["files"], dict)):
                raise ValueError("Invalid manifest or unsupported version")
            records = manifest["files"]
            if set(records) != seen - {MANIFEST}:
                raise ValueError("Manifest file list does not match archive")
            payload = {}
            for name, record in records.items():
                if (not isinstance(record, dict) or set(record) != {"size", "sha256"}
                        or type(record["size"]) is not int or record["size"] < 0
                        or record["size"] != archive.getinfo(name).file_size
                        or not isinstance(record["sha256"], str)
                        or len(record["sha256"]) != 64
                        or any(c not in "0123456789abcdef" for c in record["sha256"])):
                    raise ValueError("Invalid manifest size or SHA-256")
                # Never extract paths; read and verify every member before any writes.
                raw = _read_member(archive, name, record["size"])
                if len(raw) != record["size"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
                    raise ValueError(f"Checksum mismatch: {name}")
                payload[name] = raw
            return payload

    def restore(self, archive: Path, overwrite: bool = False, dry_run: bool = False) -> dict:
        """Validate everything first; conflicts block the entire restore."""
        report = _report()
        try:
            _check_path(self.data_dir)
        except ValueError as exc:
            _issue(report, str(self.data_dir), str(exc))
            return report
        with data_lock(self.data_dir):
            try:
                _check_path(self.data_dir)
                payload = self._read_archive(Path(archive))
                report["files"] = sorted(payload)
                conflicts = []
                for name in payload:
                    path = self.data_dir / name
                    _check_path(path)
                    if path.exists():
                        if not path.is_file():
                            raise ValueError(f"Not a regular data file: {name}")
                        conflicts.append(name)
                if conflicts and not overwrite:
                    report['error_code'] = 'conflict'
                    for name in sorted(conflicts):
                        _issue(report, name, "File exists; overwrite=True is required")
                    return report
                if dry_run:
                    return report
                if conflicts:
                    report["backup"] = str(self.backup())
                for name, raw in payload.items():
                    _atomic_write(self.data_dir / name, raw)
                    report["changed"].append(name)
            except (OSError, ValueError, zipfile.BadZipFile, RuntimeError,
                    NotImplementedError, EOFError, RecursionError, zlib.error) as exc:
                report['error_code'] = ('not_found' if isinstance(exc, FileNotFoundError)
                                        else 'operation_failed' if isinstance(exc, OSError)
                                        else 'invalid_data')
                _issue(report, str(archive), str(exc))
        return report

    def doctor(self, repair: bool = False) -> dict:
        """Quarantine rejected JSONL lines; never rewrite whole JSON documents."""
        report = _report()
        repairs = {}
        try:
            _check_path(self.data_dir)
        except ValueError as exc:
            _issue(report, str(self.data_dir), str(exc))
            return report
        with data_lock(self.data_dir):
            for name in DATA_FILES:
                path = self.data_dir / name
                try:
                    _check_path(path)
                    if not path.exists():
                        continue
                    if not path.is_file():
                        raise ValueError("Not a regular data file")
                    if not name.endswith(".jsonl"):
                        error = _document_error(name, _json(path.read_bytes()))
                        if error:
                            _issue(report, name, error)
                        continue
                    valid, rejected, issues = [], [], []
                    with path.open("rb") as handle:
                        for number, raw in enumerate(handle, 1):
                            try:
                                # Blank lines are harmless and must retain their bytes.
                                text = raw.decode("utf-8")
                                error = _event_error(name, _json(raw)) if text.strip() else None
                            except (ValueError, RecursionError) as exc:
                                error = f"Invalid UTF-8 or JSON: {exc}"
                            if error:
                                _issue(report, name, error, number)
                                issues.append(report["issues"][-1])
                                rejected.append(raw)
                            else:
                                valid.append(raw)
                    if rejected:
                        repairs[name] = (b"".join(valid), b"".join(rejected), issues)
                except (OSError, ValueError, RecursionError) as exc:
                    _issue(report, name, str(exc))
            if repair and repairs:
                try:
                    _check_path(self.data_dir / "quarantine")
                    report["backup"] = str(self.backup())
                    for name, (valid, rejected, issues) in repairs.items():
                        quarantine = self.data_dir / "quarantine" / _unique_name(name, ".rejected")
                        _atomic_write(quarantine, rejected)
                        report["quarantine"].append(str(quarantine))
                        _atomic_write(self.data_dir / name, valid)
                        report["changed"].append(name)
                        for issue in issues:
                            issue["resolved"] = True
                except (OSError, ValueError) as exc:
                    _issue(report, "repair", str(exc))
            report["ok"] = not any(not issue["resolved"] for issue in report["issues"])
        return report
