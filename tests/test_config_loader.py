"""Tests for config loader functionality."""

import os
import pytest
import tempfile
import yaml

from shilads_helpers.libs.config_loader import load_configs, load_default_configs, get_config


def test_load_single_config():
    """Test loading a single config file."""
    config_data = {
        "app": {"name": "test-app"},
        "logging": {"level": "DEBUG"}
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    try:
        result = load_configs(temp_path)
        assert result == config_data
    finally:
        os.unlink(temp_path)


def test_load_multiple_configs_merge():
    """Test loading and merging multiple config files."""
    config1 = {
        "app": {"name": "test-app", "version": "1.0"},
        "logging": {"level": "INFO"}
    }
    config2 = {
        "app": {"version": "2.0"},  # This should override
        "logging": {"verbose": True}  # This should be added
    }
    
    expected = {
        "app": {"name": "test-app", "version": "2.0"},
        "logging": {"level": "INFO", "verbose": True}
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f1:
        yaml.dump(config1, f1)
        temp_path1 = f1.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f2:
        yaml.dump(config2, f2)
        temp_path2 = f2.name
    
    try:
        result = load_configs(temp_path1, temp_path2)
        assert result == expected
    finally:
        os.unlink(temp_path1)
        os.unlink(temp_path2)


def test_load_missing_file():
    """Test that missing files are skipped with warning."""
    config_data = {"app": {"name": "test-app"}}
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    try:
        # Load existing file and non-existing file
        result = load_configs(temp_path, "nonexistent.yaml")
        assert result == config_data
    finally:
        os.unlink(temp_path)


def test_no_configs_loaded():
    """Test that ValueError is raised when no configs are loaded."""
    with pytest.raises(ValueError, match="No configs loaded"):
        load_configs("nonexistent1.yaml", "nonexistent2.yaml")


def test_invalid_yaml_type():
    """Test that TypeError is raised for non-dict YAML."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("just a string, not a dict")
        temp_path = f.name
    
    try:
        with pytest.raises(TypeError, match="must be a dict"):
            load_configs(temp_path)
    finally:
        os.unlink(temp_path)


def test_get_config():
    """Test getting config values by dot-separated key."""
    config = {
        "app": {
            "name": "test-app",
            "database": {
                "host": "localhost",
                "port": 5432
            }
        },
        "logging": {"level": "INFO"}
    }
    
    assert get_config("app.name", config) == "test-app"
    assert get_config("app.database.host", config) == "localhost"
    assert get_config("app.database.port", config) == 5432
    assert get_config("logging.level", config) == "INFO"
    
    with pytest.raises(KeyError):
        get_config("nonexistent.key", config)
    
    with pytest.raises(KeyError):
        get_config("app.database.nonexistent", config)


def test_load_default_configs_integration():
    """Test loading default configs (integration test)."""
    # First create the default config files
    project_root = os.path.dirname(os.path.dirname(__file__))
    config_dir = os.path.join(project_root, "config")
    
    default_config = {
        "app": {
            "name": "shilads-helpers",
            "version": "1.0.0"
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    }
    
    default_config_path = os.path.join(config_dir, "default.yaml")
    
    # Only test if default.yaml exists
    if os.path.exists(default_config_path):
        config = load_default_configs()
        assert isinstance(config, dict)
        assert "app" in config or "logging" in config  # At least one section should exist