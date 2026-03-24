import tomllib
import tomli_w
from dataclasses import dataclass, field
from pathlib import Path

from skillmanager.models import ConflictResolution, Project, Skill, Source, SourceKind

CONFIG_DIR = Path("~/.config/skillmanager").expanduser()
REPOS_DIR = Path("~/.local/share/skillmanager/repos").expanduser()

_CONFIG_FILE = CONFIG_DIR / "config.toml"


@dataclass
class AppConfig:
    sources: list[Source] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    conflict_resolutions: list[ConflictResolution] = field(default_factory=list)


def _skill_from_dict(d: dict) -> Skill:
    return Skill(
        name=d["name"],
        rel_path=d["rel_path"],
        enabled=d.get("enabled", True),
        description=d.get("description", ""),
    )


def _source_from_dict(d: dict) -> Source:
    return Source(
        id=d["id"],
        display_name=d["display_name"],
        kind=SourceKind(d["kind"]),
        path=d["path"],
        url=d.get("url", ""),
        skills=[_skill_from_dict(s) for s in d.get("skills", [])],
        confirmed=d.get("confirmed", False),
        last_updated=d.get("last_updated", ""),
    )


def _project_from_dict(d: dict) -> Project:
    return Project(
        id=d["id"],
        display_name=d["display_name"],
        path=d["path"],
    )


def _conflict_from_dict(d: dict) -> ConflictResolution:
    return ConflictResolution(
        skill_name=d["skill_name"],
        target_id=d["target_id"],
        winner_source_id=d["winner_source_id"],
    )


def _skill_to_dict(s: Skill) -> dict:
    d: dict = {"name": s.name, "rel_path": s.rel_path, "enabled": s.enabled}
    if s.description:
        d["description"] = s.description
    return d


def _source_to_dict(s: Source) -> dict:
    return {
        "id": s.id,
        "display_name": s.display_name,
        "kind": s.kind.value,
        "path": s.path,
        "url": s.url,
        "skills": [_skill_to_dict(sk) for sk in s.skills],
        "confirmed": s.confirmed,
        "last_updated": s.last_updated,
    }


def _project_to_dict(p: Project) -> dict:
    return {"id": p.id, "display_name": p.display_name, "path": p.path}


def _conflict_to_dict(c: ConflictResolution) -> dict:
    return {
        "skill_name": c.skill_name,
        "target_id": c.target_id,
        "winner_source_id": c.winner_source_id,
    }


def load_config() -> AppConfig:
    if not _CONFIG_FILE.exists():
        return AppConfig()
    with open(_CONFIG_FILE, "rb") as f:
        data = tomllib.load(f)
    return AppConfig(
        sources=[_source_from_dict(s) for s in data.get("sources", [])],
        projects=[_project_from_dict(p) for p in data.get("projects", [])],
        conflict_resolutions=[
            _conflict_from_dict(c) for c in data.get("conflict_resolutions", [])
        ],
    )


def save_config(config: AppConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "sources": [_source_to_dict(s) for s in config.sources],
        "projects": [_project_to_dict(p) for p in config.projects],
        "conflict_resolutions": [
            _conflict_to_dict(c) for c in config.conflict_resolutions
        ],
    }
    with open(_CONFIG_FILE, "wb") as f:
        tomli_w.dump(data, f)
