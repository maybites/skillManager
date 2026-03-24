import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from skillmanager.models import Skill, Source, SourceKind
from skillmanager.operations import (
    OperationResult,
    add_project,
    clone_repo,
    create_symlink,
    detect_skills,
    find_owning_source,
    git_pull,
    make_dest_path,
    make_slug,
    remove_symlink,
    scan_broken_symlinks,
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


# --- add_project tests ---

def test_add_project_creates_skills_dir(tmp_path):
    result = add_project(str(tmp_path))
    assert result.success is True
    assert (tmp_path / ".claude" / "skills").is_dir()


def test_add_project_missing_path():
    result = add_project("/nonexistent/path/xyz_abc_123")
    assert result.success is False
    assert "does not exist" in result.message


def test_add_project_file_path(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hello")
    result = add_project(str(f))
    assert result.success is False
    assert "not a directory" in result.message


def test_add_project_idempotent(tmp_path):
    add_project(str(tmp_path))
    result = add_project(str(tmp_path))
    assert result.success is True
    assert (tmp_path / ".claude" / "skills").is_dir()


# --- detect_skills tests ---

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


# --- create_symlink tests ---

def test_create_symlink_creates_link(tmp_path):
    src = tmp_path / "skill-dir"
    src.mkdir()
    dst = tmp_path / "target" / "skills" / "skill-dir"
    result = create_symlink(src, dst)
    assert result.success is True
    assert dst.is_symlink()
    assert os.path.realpath(dst) == os.path.realpath(src)


def test_create_symlink_auto_creates_parent(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "a" / "b" / "c" / "skill"
    result = create_symlink(src, dst)
    assert result.success is True
    assert dst.is_symlink()


def test_create_symlink_fails_if_dst_exists(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"
    dst.mkdir()  # already exists as a directory
    result = create_symlink(src, dst)
    assert result.success is False
    assert result.message != ""


# --- remove_symlink tests ---

def test_remove_symlink_removes_link(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "link"
    os.symlink(src, dst)
    result = remove_symlink(dst)
    assert result.success is True
    assert not dst.exists()


def test_remove_symlink_fails_if_missing(tmp_path):
    dst = tmp_path / "nonexistent"
    result = remove_symlink(dst)
    assert result.success is False
    assert result.message != ""


# --- git_pull tests ---


def test_git_pull_success(tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Already up to date.\n"
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = git_pull(tmp_path)
    assert result.success is True
    assert "up to date" in result.message
    mock_run.assert_called_once_with(
        ["git", "pull"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )


def test_git_pull_failure(tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "error: failed to merge"
    with patch("subprocess.run", return_value=mock_result):
        result = git_pull(tmp_path)
    assert result.success is False
    assert "failed to merge" in result.message


def test_git_pull_git_not_found(tmp_path):
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = git_pull(tmp_path)
    assert result.success is False
    assert "git not found" in result.message


def test_git_pull_unexpected_error(tmp_path):
    with patch("subprocess.run", side_effect=PermissionError("denied")):
        result = git_pull(tmp_path)
    assert result.success is False
    assert "denied" in result.message


# --- scan_broken_symlinks tests ---


def test_scan_broken_symlinks_finds_broken(tmp_path):
    target_dir = tmp_path / "skills"
    target_dir.mkdir()
    nonexistent = tmp_path / "nonexistent-target"
    link = target_dir / "broken-link"
    os.symlink(nonexistent, link)
    assert os.path.lexists(str(link))
    assert not os.path.exists(str(link))

    broken = scan_broken_symlinks([target_dir])
    assert link in broken


def test_scan_broken_symlinks_ignores_valid(tmp_path):
    target_dir = tmp_path / "skills"
    target_dir.mkdir()
    src = tmp_path / "real-skill"
    src.mkdir()
    link = target_dir / "good-link"
    os.symlink(src, link)

    broken = scan_broken_symlinks([target_dir])
    assert link not in broken


def test_scan_broken_symlinks_ignores_missing_dir(tmp_path):
    nonexistent_dir = tmp_path / "nonexistent-dir"
    broken = scan_broken_symlinks([nonexistent_dir])
    assert broken == []


def test_scan_broken_symlinks_multiple_dirs(tmp_path):
    dir_a = tmp_path / "dir_a"
    dir_a.mkdir()
    dir_b = tmp_path / "dir_b"
    dir_b.mkdir()

    # broken link in dir_a
    bad_target = tmp_path / "gone"
    bad_link = dir_a / "bad"
    os.symlink(bad_target, bad_link)

    # good link in dir_b
    good_src = tmp_path / "real"
    good_src.mkdir()
    good_link = dir_b / "good"
    os.symlink(good_src, good_link)

    broken = scan_broken_symlinks([dir_a, dir_b])
    assert bad_link in broken
    assert good_link not in broken


# --- find_owning_source tests ---


def _make_source(tmp_path: Path, src_id: str, skill_name: str) -> Source:
    src_dir = tmp_path / src_id / skill_name
    src_dir.mkdir(parents=True)
    return Source(
        id=src_id,
        display_name=src_id,
        kind=SourceKind.LOCAL,
        path=str(tmp_path / src_id),
        skills=[Skill(name=skill_name, rel_path=skill_name)],
        confirmed=True,
    )


def test_find_owning_source_finds_match(tmp_path):
    src_a = _make_source(tmp_path, "source_a", "my-skill")
    src_b = _make_source(tmp_path, "source_b", "my-skill")
    link = tmp_path / "skills" / "my-skill"
    link.parent.mkdir(parents=True)
    os.symlink(tmp_path / "source_a" / "my-skill", link)

    result = find_owning_source(link, [src_a, src_b])
    assert result is not None
    assert result.id == "source_a"  # type: ignore[union-attr]


def test_find_owning_source_no_link(tmp_path):
    src_a = _make_source(tmp_path, "source_a", "my-skill")
    link = tmp_path / "nonexistent"
    result = find_owning_source(link, [src_a])
    assert result is None


def test_find_owning_source_unowned_link(tmp_path):
    src_a = _make_source(tmp_path, "source_a", "my-skill")
    # link points to a directory not owned by any source
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    link = tmp_path / "skills" / "my-skill"
    link.parent.mkdir(parents=True)
    os.symlink(other_dir, link)

    result = find_owning_source(link, [src_a])
    assert result is None


def test_find_owning_source_empty_sources(tmp_path):
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    link = tmp_path / "skills" / "my-skill"
    link.parent.mkdir(parents=True)
    os.symlink(other_dir, link)

    result = find_owning_source(link, [])
    assert result is None


def test_find_owning_source_unconfirmed_ignored(tmp_path):
    src_a = _make_source(tmp_path, "source_a", "my-skill")
    src_a.confirmed = False
    link = tmp_path / "skills" / "my-skill"
    link.parent.mkdir(parents=True)
    os.symlink(tmp_path / "source_a" / "my-skill", link)

    result = find_owning_source(link, [src_a])
    assert result is None
