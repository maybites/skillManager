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
