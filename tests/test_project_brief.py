"""Integration tests for project-brief/scripts/project_brief.py"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "project-brief" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "_lib"))


def _get_module():
    if "project_brief" in sys.modules:
        del sys.modules["project_brief"]
    import project_brief as pb
    return pb


def _run(args, cwd=None):
    pb = _get_module()
    old_argv = sys.argv
    old_cwd = Path.cwd()
    sys.argv = ["project-brief"] + args
    if cwd:
        import os
        os.chdir(cwd)
    try:
        pb.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv
        if cwd:
            import os
            os.chdir(old_cwd)


def test_init_creates_brief_md(tmp_path):
    _run(["init"], cwd=tmp_path)
    brief = tmp_path / "BRIEF.md"
    assert brief.exists()
    content = brief.read_text()
    assert "## Stack" in content
    assert "## Domain Glossary" in content
    assert tmp_path.name in content  # project name = dir name


def test_init_skips_if_exists(tmp_path, capsys):
    _run(["init"], cwd=tmp_path)
    _run(["init"], cwd=tmp_path)
    out = capsys.readouterr().out
    assert "already exists" in out


def test_validate_empty_brief(tmp_path, capsys):
    _run(["init"], cwd=tmp_path)
    # Validate should warn about empty/template sections
    _run(["validate"], cwd=tmp_path)
    out = capsys.readouterr().out
    # Should either report warnings or confirm valid
    assert "Stack" in out or "✅" in out or "⚠" in out


def test_inject_outputs_context(tmp_path, capsys):
    _run(["init"], cwd=tmp_path)
    _run(["inject"], cwd=tmp_path)
    out = capsys.readouterr().out
    assert "PROJECT CONTEXT" in out
    assert "## Stack" in out


def test_find_brief_traverses_up(tmp_path):
    # Create BRIEF.md in parent, run from subdir
    brief = tmp_path / "BRIEF.md"
    brief.write_text("# Project Brief: Test\n\n## Stack\n- Python\n\n## Domain Glossary\n- term\n\n## Conventions\n- conv\n\n## Key Files\n- main.py\n")
    # Create a fake .git dir to stop traversal
    (tmp_path / ".git").mkdir()
    subdir = tmp_path / "src" / "app"
    subdir.mkdir(parents=True)

    pb = _get_module()
    import os
    old_cwd = os.getcwd()
    os.chdir(subdir)
    try:
        found = pb.find_brief()
        assert found == brief
    finally:
        os.chdir(old_cwd)
