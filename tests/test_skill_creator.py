"""Tests for skill-creator/scripts/skill_creator.py"""

import sys
import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skill-creator" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "_lib"))


def _get_module():
    if "skill_creator" in sys.modules:
        del sys.modules["skill_creator"]
    import skill_creator as sc
    return sc


def _run(args, monkeypatch=None):
    sc = _get_module()
    old_argv = sys.argv
    sys.argv = ["skill-creator"] + args
    try:
        sc.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv


def test_new_creates_skill_files(tmp_path):
    sc = _get_module()
    # Point repo root to tmp_path
    sc._REPO_ROOT = tmp_path

    old_argv = sys.argv
    sys.argv = ["skill-creator", "new", "my-test-skill", "--description", "A test skill"]
    try:
        sc.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv

    skill_dir = tmp_path / "my-test-skill"
    assert skill_dir.exists()
    assert (skill_dir / "SKILL.md").exists()
    assert (skill_dir / "scripts" / "main.py").exists()
    assert (skill_dir / "my-test-skill").exists()  # wrapper


def test_new_bash_skill(tmp_path):
    sc = _get_module()
    sc._REPO_ROOT = tmp_path

    old_argv = sys.argv
    sys.argv = ["skill-creator", "new", "bash-skill", "--bash"]
    try:
        sc.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv

    skill_dir = tmp_path / "bash-skill"
    assert (skill_dir / "scripts" / "main.sh").exists()
    assert not (skill_dir / "scripts" / "main.py").exists()


def test_new_invalid_name_rejected(tmp_path, capsys):
    sc = _get_module()
    sc._REPO_ROOT = tmp_path

    old_argv = sys.argv
    sys.argv = ["skill-creator", "new", "Invalid Name!"]
    try:
        sc.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv

    err = capsys.readouterr().err
    assert "Invalid skill name" in err
    assert not (tmp_path / "Invalid Name!").exists()


def test_new_duplicate_rejected(tmp_path, capsys):
    sc = _get_module()
    sc._REPO_ROOT = tmp_path

    for _ in range(2):
        old_argv = sys.argv
        sys.argv = ["skill-creator", "new", "dup-skill"]
        try:
            sc.main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv

    err = capsys.readouterr().err
    assert "already exists" in err


def test_description_with_braces_doesnt_crash(tmp_path):
    """Ensure {curly} in description doesn't cause KeyError in .format()"""
    sc = _get_module()
    sc._REPO_ROOT = tmp_path

    old_argv = sys.argv
    sys.argv = ["skill-creator", "new", "braces-skill", "--description", "Fix {bug} in {module}"]
    try:
        sc.main()  # should not raise KeyError
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv

    skill_dir = tmp_path / "braces-skill"
    assert skill_dir.exists(), "Skill should be created even with braces in description"
    content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    # Braces are escaped in the stored template ({{bug}} not {bug}), but the
    # skill creation must not raise KeyError — that's the key assertion here.
    assert "bug" in content and "module" in content


def test_validate_passes_for_complete_skill(tmp_path, capsys):
    sc = _get_module()
    sc._REPO_ROOT = tmp_path

    # Create a skill first
    old_argv = sys.argv
    sys.argv = ["skill-creator", "new", "ok-skill"]
    try:
        sc.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv

    # Now validate it
    old_argv = sys.argv
    sys.argv = ["skill-creator", "validate", "ok-skill"]
    try:
        sc.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv

    out = capsys.readouterr().out
    assert "ok-skill" in out


def test_generated_python_skill_supports_scopes_and_json(tmp_path, monkeypatch):
    sc = _get_module()
    sc._REPO_ROOT = tmp_path
    monkeypatch.setattr(sys, 'argv', ['skill-creator', 'new', 'json-skill'])
    sc.main()
    environment = dict(os.environ, PYTHONPATH=str(REPO_ROOT / '_lib'),
                       AI_SKILLS_DATA_DIR=str(tmp_path / 'data'))
    result = subprocess.run([sys.executable, '-B',
        str(tmp_path / 'json-skill/scripts/main.py'), 'example', '--json',
        '--scope', 'project', '--scope-project', str(tmp_path)],
        env=environment, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload['ok'] and payload['data'] == 'Done.'
    assert payload['scope']['kind'] == 'project'
