"""Data maintenance tests use temporary files and a scoped shared-lock double."""

import hashlib
import importlib.util
import json
import os
import stat
import struct
import sys
import types
import warnings
import zipfile
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

import pytest


@pytest.fixture
def dm(monkeypatch):
    # The shared lock is supplied separately. Mock only its public contract, never
    # install an unlocked fallback in production or touch a user's data directory.
    lock = RLock()
    calls = []
    active = []

    @contextmanager
    def data_lock(directory):
        with lock:
            calls.append((directory, len(active)))
            active.append(directory)
            try:
                yield
            finally:
                active.pop()

    monkeypatch.setitem(sys.modules, "file_lock", types.SimpleNamespace(data_lock=data_lock))
    path = Path(__file__).resolve().parents[1] / "_lib" / "data_manager.py"
    spec = importlib.util.spec_from_file_location("isolated_data_manager", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.lock_calls = calls
    module.active_locks = active
    return module


@pytest.fixture
def manager(tmp_path, dm):
    root = tmp_path / "data"
    root.mkdir()
    return dm.DataManager(root)


def encoded(obj):
    return json.dumps(obj).encode("utf-8")


def cost(**changes):
    entry = {"id": "usage-1", "provider": "openai", "model": "example", "timestamp": "2026-10-30T08:00:00Z",
             "input_tokens": 12, "output_tokens": 4, "total_tokens": 16, "cost_usd": 0.03}
    return {**entry, **changes}


def make_archive(path, files=None, *, manifest=None, extra=()):
    files = files if files is not None else {"todos.jsonl": b'{"id":"a","title":"Task"}\n'}
    if manifest is None:
        manifest = {"version": 1, "files": {
            name: {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in files.items()
        }}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", encoded(manifest))
            for name, raw in files.items():
                archive.writestr(name, raw)
            for name, raw in extra:
                archive.writestr(name, raw)
    return path


def tree(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_backup_allowlist_manifest_and_roundtrip(manager, tmp_path, dm):
    files = {
        "todos.jsonl": b'{"id":"a","title":"Task"}\r\n',
        "notes.jsonl": b'{"id":"n","content":"Note"}\n',
        "memory.jsonl": b'{"key":"stack","value":"Python"}\n',
        "cost-log.jsonl": encoded(cost()) + b"\n",
        "prompts.json": encoded({"test": {"name": "test", "content": "Hello"}}),
        "budget.json": encoded({"daily": None, "monthly": 10, "session": 2,
                                "alert_threshold": 90, "session_spend": 0.5}),
        "usage-import-state.json": b'{"version":1,"imports":{}}',
    }
    for name, raw in files.items():
        (manager.data_dir / name).write_bytes(raw)
    for name in (".env", "credentials.json", "config.json", "session.json", "unknown.jsonl"):
        (manager.data_dir / name).write_bytes(b"secret")
    (manager.data_dir / "sessions").mkdir()
    (manager.data_dir / "sessions" / "todos.jsonl").write_bytes(b"secret")
    archive_path = manager.backup()
    assert archive_path.parent == manager.data_dir / "backups"
    assert archive_path.suffix == ".zip"
    with zipfile.ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == set(files) | {"manifest.json"}
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["version"] == 1
        for name, raw in files.items():
            assert archive.read(name) == raw
            assert manifest["files"][name] == {
                "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    destination = dm.DataManager(tmp_path / "restored")
    report = destination.restore(archive_path)
    assert report["ok"] and report["issues"] == []
    assert set(report["files"]) == set(files) == set(report["changed"])
    assert report["backup"] is None
    assert tree(destination.data_dir) == files
    assert destination.doctor()["ok"]


def test_backup_unique_explicit_output_and_no_clobber(manager, tmp_path):
    first = manager.backup()
    second = manager.backup()
    assert first != second and first.exists() and second.exists()
    explicit = tmp_path / "exports" / "copy.zip"
    assert manager.backup(explicit) == explicit
    before = explicit.read_bytes()
    with pytest.raises(FileExistsError):
        manager.backup(explicit)
    assert explicit.read_bytes() == before
    with pytest.raises(ValueError):
        manager.backup(manager.data_dir / "prompts.json")


def test_restore_conflict_refuses_entire_plan(manager, tmp_path):
    existing = manager.data_dir / "todos.jsonl"
    existing.write_bytes(b"original")
    archive = make_archive(tmp_path / "data.zip", {"todos.jsonl": b"new", "notes.jsonl": b"new"})
    before = tree(manager.data_dir)
    report = manager.restore(archive)
    assert not report["ok"] and report["changed"] == [] and report["backup"] is None
    assert report["files"] == ["notes.jsonl", "todos.jsonl"]
    assert report["issues"][0]["file"] == "todos.jsonl"
    assert tree(manager.data_dir) == before


@pytest.mark.parametrize("existing", [False, True])
def test_restore_dry_run_no_writes(tmp_path, dm, existing):
    manager = dm.DataManager(tmp_path / "destination")
    if existing:
        manager.data_dir.mkdir()
        (manager.data_dir / "todos.jsonl").write_bytes(b"old")
    archive = make_archive(tmp_path / "data.zip")
    before = tree(tmp_path)
    report = manager.restore(archive, overwrite=True, dry_run=True)
    assert report["ok"] and report["files"] == ["todos.jsonl"]
    assert report["changed"] == [] and report["backup"] is None
    assert tree(tmp_path) == before
    if not existing:
        assert not manager.data_dir.exists()


def test_overwrite_safety_backup_precedes_writes(manager, tmp_path, dm, monkeypatch):
    original = b"malformed original\xff\n"
    (manager.data_dir / "todos.jsonl").write_bytes(original)
    archive = make_archive(tmp_path / "data.zip")
    real_write = dm._atomic_write
    writes = []

    def checked_write(path, raw):
        assert dm.active_locks == [manager.data_dir] * len(dm.active_locks)
        assert dm.active_locks
        if path.name == "todos.jsonl":
            backups = list((manager.data_dir / "backups").glob("*.zip"))
            assert len(backups) == 1
            with zipfile.ZipFile(backups[0]) as snapshot:
                assert snapshot.read("todos.jsonl") == original
        writes.append(path)
        real_write(path, raw)

    monkeypatch.setattr(dm, "_atomic_write", checked_write)
    report = manager.restore(archive, overwrite=True)
    assert report["ok"] and report["backup"]
    assert writes[0] == Path(report["backup"])
    assert dm.lock_calls == [(manager.data_dir, 0), (manager.data_dir, 1)]
    monkeypatch.setattr(dm, "_atomic_write", real_write)
    undo = manager.restore(Path(report["backup"]), overwrite=True)
    assert undo["ok"] and (manager.data_dir / "todos.jsonl").read_bytes() == original


@pytest.mark.parametrize("action", ["restore", "repair"])
def test_backup_failure_prevents_mutation(manager, tmp_path, monkeypatch, action):
    (manager.data_dir / "todos.jsonl").write_bytes(b"bad\n")
    archive = make_archive(tmp_path / "data.zip")

    def fail_backup(*args, **kwargs):
        raise OSError("No backup space")

    monkeypatch.setattr(manager, "backup", fail_backup)
    before = tree(manager.data_dir)
    report = (manager.restore(archive, overwrite=True) if action == "restore"
              else manager.doctor(repair=True))
    assert not report["ok"] and report["changed"] == [] and report["backup"] is None
    assert tree(manager.data_dir) == before
    assert not (manager.data_dir / "quarantine").exists()


@pytest.mark.parametrize("name", [
    "../todos.jsonl", "..\\todos.jsonl", "/todos.jsonl", "C:/todos.jsonl",
    "sessions/todos.jsonl", "todos.jsonl/", "TODOS.JSONL", "todos.jsonl:stream",
    "credentials.json", ".env", "config.json", "backups/old.zip", "./todos.jsonl",
])
def test_restore_rejects_unsafe_or_secret_entries(manager, tmp_path, name):
    archive = make_archive(tmp_path / "attack.zip", {name: b"secret"})
    before = tree(tmp_path)
    report = manager.restore(archive, overwrite=True)
    assert not report["ok"] and report["issues"] and report["changed"] == []
    assert tree(tmp_path) == before


@pytest.mark.parametrize("duplicate", ["todos.jsonl", "manifest.json"])
def test_restore_rejects_duplicate_entries(manager, tmp_path, duplicate):
    archive = make_archive(tmp_path / "attack.zip", extra=[(duplicate, b"duplicate")])
    report = manager.restore(archive)
    assert not report["ok"] and "Duplicate" in report["issues"][0]["message"]
    assert tree(manager.data_dir) == {}


@pytest.mark.parametrize("kind", [stat.S_IFLNK, stat.S_IFDIR, stat.S_IFIFO, stat.S_IFCHR])
def test_restore_rejects_non_regular_zip_entries(manager, tmp_path, kind):
    entry = zipfile.ZipInfo("todos.jsonl")
    entry.create_system = 3
    entry.external_attr = (kind | 0o600) << 16
    archive = make_archive(tmp_path / "attack.zip", {}, extra=[(entry, b"target")])
    report = manager.restore(archive)
    assert not report["ok"] and tree(manager.data_dir) == {}


@pytest.mark.parametrize("mutation", [
    "version", "bool_version", "missing_file", "extra_file", "size", "negative_size",
    "bool_size", "hash", "bad_hash_format", "record_shape", "files_shape",
])
def test_restore_validates_manifest_before_any_writes(manager, tmp_path, mutation):
    files = {"notes.jsonl": b"first", "todos.jsonl": b"second"}
    manifest = {"version": 1, "files": {
        name: {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        for name, raw in files.items()}}
    record = manifest["files"]["todos.jsonl"]
    if mutation == "version":
        manifest["version"] = 2
    elif mutation == "bool_version":
        manifest["version"] = True
    elif mutation == "missing_file":
        del manifest["files"]["todos.jsonl"]
    elif mutation == "extra_file":
        manifest["files"][".env"] = record
    elif mutation == "size":
        record["size"] += 1
    elif mutation == "negative_size":
        record["size"] = -1
    elif mutation == "bool_size":
        record["size"] = True
    elif mutation == "hash":
        record["sha256"] = "0" * 64
    elif mutation == "bad_hash_format":
        record["sha256"] = "x" * 64
    elif mutation == "record_shape":
        manifest["files"]["todos.jsonl"] = []
    elif mutation == "files_shape":
        manifest["files"] = []
    archive = make_archive(tmp_path / "attack.zip", files, manifest=manifest)
    report = manager.restore(archive, overwrite=True)
    assert not report["ok"] and report["changed"] == [] and tree(manager.data_dir) == {}


@pytest.mark.parametrize("contents", [b"garbage", b"[]", b'{"version":1,"version":1,"files":{}}'])
def test_restore_invalid_manifest_or_zip(manager, tmp_path, contents):
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", contents)
    report = manager.restore(path)
    assert not report["ok"] and tree(manager.data_dir) == {}
    path.write_bytes(contents)
    assert not manager.restore(path)["ok"]


def test_restore_requires_manifest(manager, tmp_path):
    path = tmp_path / "missing.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("todos.jsonl", b"data")
    assert not manager.restore(path)["ok"]
    assert tree(manager.data_dir) == {}


def test_restore_rejects_crc_corruption(manager, tmp_path):
    path = make_archive(tmp_path / "crc.zip")
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("todos.jsonl")
        offset = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
    raw = bytearray(path.read_bytes())
    raw[offset + info.compress_size - 1] ^= 0xFF
    path.write_bytes(raw)
    assert not manager.restore(path)["ok"]
    assert tree(manager.data_dir) == {}


@pytest.mark.parametrize("attack", ["encrypted", "compression", "nul_name", "local_name"])
def test_restore_rejects_header_attacks(manager, tmp_path, attack):
    path = make_archive(tmp_path / "headers.zip")
    raw = bytearray(path.read_bytes())
    central = raw.index(b"PK\x01\x02", raw.index(b"PK\x01\x02") + 4)
    with zipfile.ZipFile(path) as archive:
        local = archive.getinfo("todos.jsonl").header_offset
    if attack == "encrypted":
        struct.pack_into("<H", raw, central + 8, 1)
        struct.pack_into("<H", raw, local + 6, 1)
    elif attack == "compression":
        struct.pack_into("<H", raw, central + 10, 99)
        struct.pack_into("<H", raw, local + 8, 99)
    elif attack == "nul_name":
        raw[central + 46 + 5] = 0
    else:
        raw[local + 30] = ord("X")
    path.write_bytes(raw)
    report = manager.restore(path)
    assert not report["ok"] and report["changed"] == []
    assert tree(manager.data_dir) == {}


def test_restore_and_backup_enforce_total_limit(manager, tmp_path, dm, monkeypatch):
    path = make_archive(tmp_path / "big.zip", {"todos.jsonl": b"x" * 5000})
    monkeypatch.setattr(dm, "MAX_TOTAL_SIZE", 4096)
    assert not manager.restore(path)["ok"]
    assert tree(manager.data_dir) == {}
    (manager.data_dir / "todos.jsonl").write_bytes(b"x" * 5000)
    with pytest.raises(ValueError, match="limit"):
        manager.backup()
    assert not (manager.data_dir / "backups").exists()


def test_restore_manifest_size_limit(manager, tmp_path, dm, monkeypatch):
    path = make_archive(tmp_path / "big-manifest.zip")
    monkeypatch.setattr(dm, "MAX_MANIFEST_SIZE", 8)
    assert not manager.restore(path)["ok"]
    assert tree(manager.data_dir) == {}


def test_doctor_partial_events_and_unknown_prices(manager):
    files = {
        "todos.jsonl": [
            {"id": "t", "title": "Task", "priority": "urgent", "checked": False,
             "tags": ["dev"], "project": None, "due_date": None},
            {"id": "t", "checked": True}, {"id": "t", "priority": "low"},
            {"id": "t", "deleted": True},
        ],
        "notes.jsonl": [{"id": "n", "content": "Note", "date": "2026-10-30"},
                        {"id": "n", "done": True}, {"id": "n", "deleted": True}],
        "memory.jsonl": [{"key": "stack", "value": "Python"},
                         {"key": "stack", "tags": ["dev"]},
                         {"key": "stack", "deleted": True}],
        "cost-log.jsonl": [cost(), cost(cost_usd=None, pricing_status="unknown")],
    }
    for name, events in files.items():
        (manager.data_dir / name).write_bytes(b"\n".join(map(encoded, events)) + b"\n")
    before = tree(manager.data_dir)
    report = manager.doctor(repair=True)
    assert report["ok"] and report["issues"] == [] and report["backup"] is None
    assert tree(manager.data_dir) == before


def test_importer_state_and_cache_metadata_are_accepted(manager):
    metadata = {"source": "session_import", "source_file": "/sessions/example.jsonl",
                "input_uncached_tokens": 2, "cache_read_tokens": 8, "cache_write_tokens": 2,
                "reasoning_tokens": 1, "tool_tokens": 0}
    (manager.data_dir / "cost-log.jsonl").write_bytes(
        encoded(cost(cost_usd=None, pricing_status="unknown", metadata=metadata)) + b"\n"
        + encoded(cost(pricing_status="estimated", metadata=metadata)) + b"\n")
    state = {"version": 1, "files": {"openai:/sessions/example.jsonl": [123456, 100, 42]},
             "rate_signature": None, "log_signature": [123457, 200, 43]}
    (manager.data_dir / "usage-import-state.json").write_bytes(encoded(state))
    before = tree(manager.data_dir)
    assert manager.doctor(repair=True)["ok"]
    assert tree(manager.data_dir) == before


@pytest.mark.parametrize("change", [
    {"provider": ""}, {"model": None}, {"timestamp": "bad"},
    {"timestamp": "2026-10-30"}, {"timestamp": "2026-02-30T01:02:03Z"},
    {"input_tokens": -1}, {"input_tokens": True}, {"output_tokens": 1.5},
    {"total_tokens": "16"}, {"total_tokens": 99}, {"cost_usd": -1},
    {"cost_usd": float("nan")}, {"cost_usd": float("inf")},
    {"cost_usd": True}, {"cost_usd": None},
    {"cost_usd": None, "pricing_status": "known"},
])
def test_doctor_rejects_bad_costs(manager, change):
    path = manager.data_dir / "cost-log.jsonl"
    path.write_bytes(encoded(cost(**change)) + b"\n")
    report = manager.doctor()
    assert not report["ok"] and report["changed"] == []
    assert report["issues"][0]["file"] == path.name
    assert report["issues"][0]["line"] == 1


@pytest.mark.parametrize(("name", "event"), [
    ("todos.jsonl", []), ("todos.jsonl", {}), ("todos.jsonl", {"id": 1}),
    ("todos.jsonl", {"id": "x", "title": 3}),
    ("todos.jsonl", {"id": "x", "checked": 1}),
    ("todos.jsonl", {"id": "x", "priority": "invalid"}),
    ("todos.jsonl", {"id": "x", "tags": "tag"}),
    ("todos.jsonl", {"id": "x", "tags": [5]}),
    ("todos.jsonl", {"id": "x", "project": []}),
    ("todos.jsonl", {"id": "x", "due_date": "2026-02-30"}),
    ("notes.jsonl", {"id": "x", "done": "yes"}),
    ("notes.jsonl", {"id": "x", "created_at": 0}),
    ("memory.jsonl", {"id": "x", "value": "No key"}),
    ("memory.jsonl", {"key": "x", "value": []}),
    ("memory.jsonl", {"key": "x", "deleted": "true"}),
])
def test_doctor_validates_event_fields(manager, name, event):
    (manager.data_dir / name).write_bytes(encoded(event) + b"\n")
    report = manager.doctor()
    assert not report["ok"] and report["issues"][0]["line"] == 1


def test_repair_quarantines_raw_bad_lines_and_preserves_events(manager, dm, monkeypatch):
    good = [b' {"id":"a", "title":"Task"} \r\n', b"\n",
            b'{"id":"a","checked":true}\n', b'{"id":"a","deleted":true}']
    bad = [b"not-json\r\n", b'{"id":"bad","title":"\xff"}\n', b"[]\n"]
    original = good[0] + bad[0] + good[1] + bad[1] + good[2] + bad[2] + good[3]
    path = manager.data_dir / "todos.jsonl"
    path.write_bytes(original)
    before = tree(manager.data_dir)
    diagnosis = manager.doctor()
    assert not diagnosis["ok"] and diagnosis["backup"] is None
    assert [issue["line"] for issue in diagnosis["issues"]] == [2, 4, 6]
    assert tree(manager.data_dir) == before
    real_write = dm._atomic_write

    def checked_write(target, raw):
        assert dm.active_locks
        if target == path:
            assert path.read_bytes() == original
            assert list((manager.data_dir / "backups").glob("*.zip"))
            quarantines = list((manager.data_dir / "quarantine").iterdir())
            assert len(quarantines) == 1 and quarantines[0].read_bytes() == b"".join(bad)
        real_write(target, raw)

    monkeypatch.setattr(dm, "_atomic_write", checked_write)
    report = manager.doctor(repair=True)
    assert report["ok"] and report["changed"] == ["todos.jsonl"]
    assert all(issue["resolved"] for issue in report["issues"])
    assert path.read_bytes() == b"".join(good)
    assert Path(report["quarantine"][0]).read_bytes() == b"".join(bad)
    with zipfile.ZipFile(report["backup"]) as archive:
        assert archive.read("todos.jsonl") == original
    assert manager.doctor(repair=True)["backup"] is None


def test_repeated_repairs_use_unique_quarantines(manager):
    path = manager.data_dir / "notes.jsonl"
    path.write_bytes(b"bad\n")
    first = manager.doctor(repair=True)
    path.write_bytes(b"other-bad\n")
    second = manager.doctor(repair=True)
    assert first["backup"] != second["backup"]
    assert first["quarantine"] != second["quarantine"]
    assert Path(first["quarantine"][0]).read_bytes() == b"bad\n"
    assert Path(second["quarantine"][0]).read_bytes() == b"other-bad\n"


@pytest.mark.parametrize(("name", "raw"), [
    ("prompts.json", b"{broken"), ("prompts.json", b"[]"),
    ("prompts.json", b'{"x":{"name":"other","content":"test"}}'),
    ("prompts.json", b'{"x":{"name":"x","content":5}}'),
    ("prompts.json", b'{"x":"test"}'), ("prompts.json", b"\xff"),
    ("budget.json", b'{"daily":-1}'), ("budget.json", b'{"session":true}'),
    ("budget.json", b'{"monthly":"1"}'), ("budget.json", b'{"alert_threshold":101}'),
    ("budget.json", b'{"alert_threshold":-1}'), ("budget.json", b'{"session_spend":-1}'),
    ("budget.json", b'{"session_spend":NaN}'), ("budget.json", b'{"session_spend":1e999}'),
    ("budget.json", b'{"daily":1,"daily":2}'),
    ("usage-import-state.json", b"[1]"),
])
def test_doctor_never_mutates_invalid_whole_documents(manager, name, raw):
    (manager.data_dir / name).write_bytes(raw)
    before = tree(manager.data_dir)
    report = manager.doctor(repair=True)
    assert not report["ok"] and report["changed"] == [] and report["backup"] is None
    assert report["issues"][0]["file"] == name
    assert report["issues"][0]["resolved"] is False
    assert tree(manager.data_dir) == before


def test_doctor_reports_documents_unresolved_while_repairing_jsonl(manager):
    (manager.data_dir / "notes.jsonl").write_bytes(b"bad\n")
    (manager.data_dir / "budget.json").write_bytes(b"malformed")
    report = manager.doctor(repair=True)
    assert not report["ok"] and report["changed"] == ["notes.jsonl"]
    assert report["backup"] and (manager.data_dir / "budget.json").read_bytes() == b"malformed"
    assert {issue["file"]: issue["resolved"] for issue in report["issues"]} == {
        "notes.jsonl": True, "budget.json": False}


def test_atomic_write_fsync_unique_temps_and_cleanup(manager, dm, monkeypatch):
    path = manager.data_dir / "notes.jsonl"
    path.write_bytes(b"old")
    real_replace = os.replace
    real_fsync = os.fsync
    temps = []
    synced = []

    def fsync(fd):
        synced.append(fd)
        real_fsync(fd)

    def replace(source, destination):
        assert synced
        assert source.parent == path.parent and source.name != "notes.tmp"
        temps.append(source)
        real_replace(source, destination)

    monkeypatch.setattr(dm.os, "fsync", fsync)
    monkeypatch.setattr(dm.os, "replace", replace)
    dm._atomic_write(path, b"one")
    dm._atomic_write(path, b"two")
    assert temps[0] != temps[1] and not any(temp.exists() for temp in temps)
    assert path.read_bytes() == b"two"

    def fail_replace(*args):
        raise OSError("Injected rename failure")

    monkeypatch.setattr(dm.os, "replace", fail_replace)
    with pytest.raises(OSError):
        dm._atomic_write(path, b"three")
    assert path.read_bytes() == b"two" and list(manager.data_dir.glob("*.tmp")) == []


def test_empty_doctor_is_read_only(tmp_path, dm):
    manager = dm.DataManager(tmp_path / "missing")
    assert manager.doctor(repair=True)["ok"]
    assert not manager.data_dir.exists()


def test_real_shared_lock_nested_backup_and_read_only_state(manager, tmp_path, dm, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "_lib" / "file_lock.py"
    if not path.exists():
        pytest.skip("Shared lock supplied by a separate repository task")
    spec = importlib.util.spec_from_file_location("isolated_shared_lock", path)
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    monkeypatch.setattr(dm, "data_lock", shared.data_lock)
    (manager.data_dir / "todos.jsonl").write_bytes(b"broken\n")
    (manager.data_dir / "usage-import-state.json").write_bytes(b'{"version":1,"files":{}}')
    archive = make_archive(tmp_path / "incoming.zip")
    before = tree(manager.data_dir)
    report = manager.restore(archive, overwrite=True, dry_run=True)
    assert report["ok"] and report["changed"] == [] and report["backup"] is None
    after = tree(manager.data_dir)
    after.pop(".ai-skills.lock", None)
    assert after == before
    report = manager.doctor(repair=True)
    assert report["ok"] and report["backup"] and report["changed"] == ["todos.jsonl"]
    assert manager.restore(archive, overwrite=True)["ok"]


@pytest.mark.parametrize("location", ["todos.jsonl", "backups", "quarantine"])
def test_linked_local_paths_are_not_followed(manager, tmp_path, location):
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "private.json"
    target.write_bytes(b"secret")
    link = manager.data_dir / location
    try:
        link.symlink_to(target if location.endswith("jsonl") else outside,
                        target_is_directory=not location.endswith("jsonl"))
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode or privileges")
    if location == "todos.jsonl":
        with pytest.raises(ValueError):
            manager.backup()
        assert not manager.doctor(repair=True)["ok"]
        archive = make_archive(tmp_path / "data.zip")
        assert not manager.restore(archive, overwrite=True)["ok"]
    elif location == "backups":
        with pytest.raises(ValueError):
            manager.backup()
    else:
        (manager.data_dir / "notes.jsonl").write_bytes(b"bad\n")
        assert not manager.doctor(repair=True)["ok"]
        assert (manager.data_dir / "notes.jsonl").read_bytes() == b"bad\n"
    assert tree(outside) == {"private.json": b"secret"}
