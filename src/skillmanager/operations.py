import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skillmanager.models import Project, Source


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

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)


def extract_skill_description(skill_dir: Path) -> str:
    """Extract the description from YAML frontmatter of the first .md file in skill_dir.

    Looks for SKILL.md first, then falls back to the first .md file found.
    Returns empty string if no description is found.
    """
    candidates = [skill_dir / "SKILL.md"]
    candidates.extend(sorted(skill_dir.glob("*.md")))
    for md_file in candidates:
        if not md_file.is_file():
            continue
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _FRONTMATTER_RE.match(text)
        if not m:
            continue
        for line in m.group(1).splitlines():
            line = line.strip()
            if line.lower().startswith("description:"):
                value = line.split(":", 1)[1].strip().strip("\"'")
                if value:
                    return value
        break  # found frontmatter but no description — stop looking
    return ""


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


def find_owning_source(link_path: Path, sources: "list[Source]") -> "Source | None":
    """Return the Source whose skill is symlinked at link_path, or None.

    Resolves the symlink target and compares against each confirmed source's
    skill paths. Returns the first matching Source, or None if not found.
    """
    if not os.path.lexists(str(link_path)):
        return None
    try:
        raw = os.readlink(str(link_path))
        target = Path(raw) if Path(raw).is_absolute() else link_path.parent / raw
        real_target = target.resolve()
    except OSError:
        return None
    for src in sources:
        if not getattr(src, "confirmed", False):
            continue
        for sk in getattr(src, "skills", []):
            sk_path = (Path(src.path) / sk.rel_path).resolve()
            if real_target == sk_path:
                return src
    return None


def validate_project_paths(projects: "list[Project]") -> set[str]:
    """Return IDs of projects whose paths no longer exist on disk."""
    return {p.id for p in projects if not Path(p.path).exists()}


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


def find_source_symlinks(source: "Source", target_dirs: list[Path]) -> list[Path]:
    """Return symlink paths across all target_dirs that point into source's skill folders."""
    source_root = Path(source.path).resolve()
    result: list[Path] = []
    for target_dir in target_dirs:
        if not target_dir.exists():
            continue
        for entry in target_dir.iterdir():
            if not os.path.islink(str(entry)):
                continue
            try:
                raw = os.readlink(str(entry))
                target = Path(raw) if Path(raw).is_absolute() else entry.parent / raw
                real_target = target.resolve()
            except OSError:
                continue
            # Check if the symlink resolves into this source's directory
            try:
                real_target.relative_to(source_root)
                result.append(entry)
            except ValueError:
                pass
    return result


def copy_skill(src: Path, dst: Path) -> OperationResult:
    """Copy skill directory src to dst using shutil.copytree."""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(src), str(dst))
        return OperationResult(success=True)
    except OSError as e:
        return OperationResult(success=False, message=str(e))
    except Exception as e:
        return OperationResult(success=False, message=str(e))


def remove_copy(dst: Path) -> OperationResult:
    """Remove a copied skill directory at dst using shutil.rmtree."""
    try:
        if dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(str(dst))
        return OperationResult(success=True)
    except OSError as e:
        return OperationResult(success=False, message=str(e))


def is_copy(path: Path) -> bool:
    """Return True if path exists, is a directory, and is not a symlink."""
    return path.exists() and path.is_dir() and not path.is_symlink()


def compute_drift(source_skill: Path, copied_skill: Path) -> bool:
    """Return True if file content SHA-256 hashes differ between source and copy.

    Walks both trees, compares sorted file lists and per-file hashes.
    """
    import hashlib

    def _file_hashes(root: Path) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for file in sorted(root.rglob("*")):
            if not file.is_file():
                continue
            rel = str(file.relative_to(root))
            h = hashlib.sha256(file.read_bytes()).hexdigest()
            hashes[rel] = h
        return hashes

    src_hashes = _file_hashes(source_skill)
    dst_hashes = _file_hashes(copied_skill)
    return src_hashes != dst_hashes


def remove_source_repo(source_path: str) -> OperationResult:
    """Delete a cloned remote repo directory using shutil.rmtree."""
    p = Path(source_path)
    if not p.exists():
        return OperationResult(success=True, message="Directory already absent.")
    try:
        shutil.rmtree(str(p))
        return OperationResult(success=True)
    except Exception as e:
        return OperationResult(success=False, message=str(e))
