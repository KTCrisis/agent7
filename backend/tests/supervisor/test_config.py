"""Tests for supervisor configuration."""

import pytest
import yaml

from backend.app.services.supervisor.config import (
    SupervisorConfig,
    _parse_duration,
    load_config,
)


class TestParseDuration:
    def test_seconds(self):
        assert _parse_duration("2s") == 2.0

    def test_milliseconds(self):
        assert _parse_duration("500ms") == 0.5

    def test_minutes(self):
        assert _parse_duration("1m") == 60.0

    def test_hours(self):
        assert _parse_duration("2h") == 7200.0

    def test_float(self):
        assert _parse_duration("1.5s") == 1.5

    def test_invalid(self):
        with pytest.raises(ValueError, match="invalid duration"):
            _parse_duration("abc")

    def test_no_unit(self):
        with pytest.raises(ValueError, match="invalid duration"):
            _parse_duration("42")


class TestSupervisorConfig:
    def test_defaults(self):
        cfg = SupervisorConfig()
        assert cfg.mesh_url == "http://localhost:9090"
        assert cfg.agent_id == "supervisor"
        assert cfg.poll_interval == 2.0
        assert cfg.confidence_threshold == 0.8

    def test_poll_interval_string(self):
        cfg = SupervisorConfig(poll_interval="5s")
        assert cfg.poll_interval == 5.0

    def test_poll_interval_numeric(self):
        cfg = SupervisorConfig(poll_interval=3)
        assert cfg.poll_interval == 3.0

    def test_auto_catchall(self):
        cfg = SupervisorConfig(rules=[])
        assert len(cfg.rules) == 1
        assert cfg.rules[-1].name == "default"
        assert cfg.rules[-1].action == "escalate"

    def test_no_double_catchall(self):
        """If last rule is already a catch-all, don't append another."""
        from backend.app.services.supervisor.config import RuleConfig

        cfg = SupervisorConfig(rules=[
            RuleConfig(name="my-catchall", action="deny"),
        ])
        # catch-all has condition=None, so it matches. Our rule already has condition=None,
        # but the config still appends because it checks the last rule's condition.
        # Actually: our rule has condition=None, so it IS a catch-all -> no append
        assert cfg.rules[-1].name == "my-catchall"


class TestLoadConfig:
    def test_load_nested(self, tmp_path):
        config_file = tmp_path / "supervisor.yaml"
        config_file.write_text(yaml.dump({
            "supervisor": {
                "mesh_url": "http://mesh:9090",
                "poll_interval": "3s",
                "project_dirs": ["/tmp/test"],
            }
        }))
        cfg = load_config(str(config_file))
        assert cfg.mesh_url == "http://mesh:9090"
        assert cfg.poll_interval == 3.0
        assert cfg.project_dirs == ["/tmp/test"]

    def test_load_flat(self, tmp_path):
        config_file = tmp_path / "supervisor.yaml"
        config_file.write_text(yaml.dump({
            "mesh_url": "http://localhost:9090",
            "agent_id": "my-supervisor",
        }))
        cfg = load_config(str(config_file))
        assert cfg.agent_id == "my-supervisor"
