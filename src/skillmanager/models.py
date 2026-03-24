from dataclasses import dataclass, field
from enum import Enum


class SourceKind(Enum):
    REMOTE = "remote"
    LOCAL = "local"


@dataclass
class Skill:
    name: str
    rel_path: str
    enabled: bool = True


@dataclass
class Source:
    id: str
    display_name: str
    kind: SourceKind
    path: str
    url: str = ""
    skills: list[Skill] = field(default_factory=list)
    confirmed: bool = False
    last_updated: str = ""


@dataclass
class Project:
    id: str
    display_name: str
    path: str


@dataclass
class SymlinkTarget:
    target_id: str
    skills_dir: str


@dataclass
class ConflictResolution:
    skill_name: str
    target_id: str
    winner_source_id: str
