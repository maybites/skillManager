import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OperationResult:
    success: bool
    message: str = ""


def make_slug(url_or_path: str) -> str:
    """Return the last path segment, stripping .git suffix."""
    seg = url_or_path.rstrip("/").rsplit("/", 1)[-1]
    return seg.removesuffix(".git") if seg else "repo"


def make_dest_path(url_or_path: str, repos_dir: Path) -> Path:
    """Return a non-conflicting clone destination path inside repos_dir."""
    slug = make_slug(url_or_path)
    dest = repos_dir / slug
    if not dest.exists():
        return dest
    return repos_dir / f"{slug}-{uuid.uuid4().hex[:8]}"


def clone_repo(url: str, dest: Path) -> OperationResult:
    """Run git clone synchronously. Suitable for asyncio.to_thread."""
    try:
        result = subprocess.run(
            ["git", "clone", url, str(dest)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return OperationResult(success=True, message="Cloned successfully.")
        return OperationResult(
            success=False,
            message=result.stderr.strip() or "Clone failed.",
        )
    except FileNotFoundError:
        return OperationResult(success=False, message="git not found in PATH.")
    except Exception as e:
        return OperationResult(success=False, message=str(e))


_UNCHECKED_BY_DEFAULT = frozenset({"docs", "tests", ".github", "flowchart"})


def detect_skills(source_path: str | Path) -> list[tuple[str, bool]]:
    """Return (rel_path, enabled_by_default) for each direct subdirectory of
    source_path that contains at least one .md file at any depth."""
    root = Path(source_path)
    results: list[tuple[str, bool]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if any(child.rglob("*.md")):
            enabled = child.name not in _UNCHECKED_BY_DEFAULT
            results.append((child.name, enabled))
    return results


def add_project(path: str) -> OperationResult:
    """Validate project path exists and auto-create .claude/skills/ inside it."""
    p = Path(path).expanduser()
    if not p.exists():
        return OperationResult(success=False, message=f"Path does not exist: {p}")
    if not p.is_dir():
        return OperationResult(success=False, message=f"Path is not a directory: {p}")
    skills_dir = p / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return OperationResult(success=True)


def validate_local_path(path: str) -> OperationResult:
    """Check that a local path exists and is a directory."""
    p = Path(path).expanduser()
    if not p.exists():
        return OperationResult(success=False, message=f"Path does not exist: {p}")
    if not p.is_dir():
        return OperationResult(success=False, message=f"Path is not a directory: {p}")
    return OperationResult(success=True)


def create_symlink(src: Path, dst: Path) -> OperationResult:
    """Create symlink dst -> src, auto-creating dst.parent if missing."""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(src, dst)
        return OperationResult(success=True)
    except OSError as e:
        return OperationResult(success=False, message=str(e))


def remove_symlink(dst: Path) -> OperationResult:
    """Remove a symlink at dst."""
    try:
        os.unlink(dst)
        return OperationResult(success=True)
    except OSError as e:
        return OperationResult(success=False, message=str(e))


def git_pull(repo_path: Path) -> OperationResult:
    """Run git pull in repo_path. Returns combined stdout+stderr as message."""
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode == 0:
            return OperationResult(success=True, message=output or "Already up to date.")
        return OperationResult(success=False, message=output or "git pull failed.")
    except FileNotFoundError:
        return OperationResult(success=False, message="git not found in PATH.")
    except Exception as e:
        return OperationResult(success=False, message=str(e))


def scan_broken_symlinks(target_dirs: list[Path]) -> list[Path]:
    """Return paths of broken symlinks in target_dirs.
    Broken = os.path.lexists(p) is True AND os.path.exists(p) is False."""
    broken: list[Path] = []
    for target_dir in target_dirs:
        if not target_dir.exists():
            continue
        for entry in target_dir.iterdir():
            if os.path.lexists(str(entry)) and not os.path.exists(str(entry)):
                broken.append(entry)
    return broken
