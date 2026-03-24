import pytest
from pathlib import Path
from skillmanager.config import AppConfig, load_config, save_config
from skillmanager.models import ConflictResolution, Project, Skill, Source, SourceKind


def test_load_config_missing_file_returns_empty(tmp_path, monkeypatch):
    import skillmanager.config as cfg
    monkeypatch.setattr(cfg, "_CONFIG_FILE", tmp_path / "nonexistent.toml")
    result = load_config()
    assert result == AppConfig()


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    import skillmanager.config as cfg
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr(cfg, "_CONFIG_FILE", config_file)
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)

    source = Source(
        id="src1",
        display_name="My Source",
        kind=SourceKind.REMOTE,
        path="/tmp/repo",
        url="https://example.com/repo.git",
        skills=[Skill(name="my-skill", rel_path="my-skill", enabled=True)],
        confirmed=True,
        last_updated="2024-01-01T00:00:00",
    )
    project = Project(id="proj1", display_name="My Project", path="/tmp/project")
    conflict = ConflictResolution(
        skill_name="my-skill", target_id="personal", winner_source_id="src1"
    )
    original = AppConfig(
        sources=[source],
        projects=[project],
        conflict_resolutions=[conflict],
    )

    save_config(original)
    loaded = load_config()

    assert len(loaded.sources) == 1
    assert loaded.sources[0].id == "src1"
    assert loaded.sources[0].display_name == "My Source"
    assert loaded.sources[0].kind == SourceKind.REMOTE
    assert loaded.sources[0].url == "https://example.com/repo.git"
    assert loaded.sources[0].confirmed is True
    assert len(loaded.sources[0].skills) == 1
    assert loaded.sources[0].skills[0].name == "my-skill"

    assert len(loaded.projects) == 1
    assert loaded.projects[0].id == "proj1"
    assert loaded.projects[0].path == "/tmp/project"

    assert len(loaded.conflict_resolutions) == 1
    assert loaded.conflict_resolutions[0].skill_name == "my-skill"
    assert loaded.conflict_resolutions[0].winner_source_id == "src1"


def test_local_source_kind(tmp_path, monkeypatch):
    import skillmanager.config as cfg
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr(cfg, "_CONFIG_FILE", config_file)
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)

    source = Source(
        id="local1",
        display_name="Local Source",
        kind=SourceKind.LOCAL,
        path="/some/local/path",
    )
    save_config(AppConfig(sources=[source]))
    loaded = load_config()
    assert loaded.sources[0].kind == SourceKind.LOCAL


def test_empty_config_saves_and_loads(tmp_path, monkeypatch):
    import skillmanager.config as cfg
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr(cfg, "_CONFIG_FILE", config_file)
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)

    save_config(AppConfig())
    loaded = load_config()
    assert loaded == AppConfig()
