from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from skillmanager.operations import (
    OperationResult,
    clone_repo,
    detect_skills,
    make_dest_path,
    make_slug,
    validate_local_path,
)


def test_make_slug_url_with_git():
    assert make_slug("https://github.com/user/my-repo.git") == "my-repo"


def test_make_slug_url_without_git():
    assert make_slug("https://github.com/user/my-repo") == "my-repo"


def test_make_slug_local_path():
    assert make_slug("/home/user/skills") == "skills"


def test_make_slug_trailing_slash():
    assert make_slug("/home/user/skills/") == "skills"


def test_make_slug_empty():
    assert make_slug("") == "repo"


def test_make_dest_path_no_conflict(tmp_path):
    dest = make_dest_path("https://github.com/user/myrepo.git", tmp_path)
    assert dest == tmp_path / "myrepo"


def test_make_dest_path_avoids_conflict(tmp_path):
    (tmp_path / "myrepo").mkdir()
    dest = make_dest_path("https://github.com/user/myrepo.git", tmp_path)
    assert dest.parent == tmp_path
    assert dest.name.startswith("myrepo-")
    assert len(dest.name) > len("myrepo-")


def test_clone_repo_success(tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = clone_repo("https://example.com/repo.git", tmp_path / "repo")
    assert result.success is True
    mock_run.assert_called_once_with(
        ["git", "clone", "https://example.com/repo.git", str(tmp_path / "repo")],
        capture_output=True,
        text=True,
    )


def test_clone_repo_failure(tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Repository not found."
    with patch("subprocess.run", return_value=mock_result):
        result = clone_repo("https://example.com/bad.git", tmp_path / "repo")
    assert result.success is False
    assert "Repository not found" in result.message


def test_clone_repo_git_not_found(tmp_path):
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = clone_repo("https://example.com/repo.git", tmp_path / "repo")
    assert result.success is False
    assert "git not found" in result.message


def test_clone_repo_unexpected_error(tmp_path):
    with patch("subprocess.run", side_effect=PermissionError("denied")):
        result = clone_repo("https://example.com/repo.git", tmp_path / "repo")
    assert result.success is False
    assert "denied" in result.message


def test_validate_local_path_exists(tmp_path):
    result = validate_local_path(str(tmp_path))
    assert result.success is True


def test_validate_local_path_missing():
    result = validate_local_path("/nonexistent/path/xyz_abc_123")
    assert result.success is False
    assert "does not exist" in result.message


def test_validate_local_path_file(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hello")
    result = validate_local_path(str(f))
    assert result.success is False
    assert "not a directory" in result.message


def test_validate_local_path_expands_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = validate_local_path("~")
    assert result.success is True


# --- detect_skills tests ---

def test_detect_skills_finds_subdir_with_md(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "README.md").write_text("# skill")
    results = detect_skills(tmp_path)
    names = [r[0] for r in results]
    assert "my-skill" in names


def test_detect_skills_enabled_by_default(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "README.md").write_text("# skill")
    results = detect_skills(tmp_path)
    enabled = {r[0]: r[1] for r in results}
    assert enabled["my-skill"] is True


def test_detect_skills_default_disabled_folders(tmp_path):
    for name in ("docs", "tests", ".github", "flowchart"):
        d = tmp_path / name
        d.mkdir()
        (d / "README.md").write_text("# doc")
    results = detect_skills(tmp_path)
    enabled = {r[0]: r[1] for r in results}
    for name in ("docs", "tests", ".github", "flowchart"):
        assert enabled[name] is False, f"{name} should default to unchecked"


def test_detect_skills_excludes_root(tmp_path):
    (tmp_path / "README.md").write_text("# root")
    results = detect_skills(tmp_path)
    assert results == []


def test_detect_skills_requires_md_at_any_depth(tmp_path):
    skill_dir = tmp_path / "deep-skill"
    skill_dir.mkdir()
    nested = skill_dir / "sub"
    nested.mkdir()
    (nested / "page.md").write_text("# page")
    results = detect_skills(tmp_path)
    names = [r[0] for r in results]
    assert "deep-skill" in names


def test_detect_skills_ignores_dirs_without_md(tmp_path):
    no_md = tmp_path / "no-md-dir"
    no_md.mkdir()
    (no_md / "script.py").write_text("# python")
    results = detect_skills(tmp_path)
    names = [r[0] for r in results]
    assert "no-md-dir" not in names


def test_detect_skills_only_direct_children(tmp_path):
    """Only direct subdirs of source root are returned as candidates."""
    skill_dir = tmp_path / "skill-a"
    skill_dir.mkdir()
    child = skill_dir / "child"
    child.mkdir()
    (child / "README.md").write_text("# child")
    results = detect_skills(tmp_path)
    names = [r[0] for r in results]
    assert "skill-a" in names
    assert "child" not in names
