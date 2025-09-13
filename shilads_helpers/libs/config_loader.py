"""Configuration loading utilities for shilads-helpers."""

import copy
import os
from typing import Any
import logging

import yaml

LOG = logging.getLogger(__name__)

ConfigType = dict[str, Any]


def load_configs(*path_configs: str) -> dict[str, Any]:
    """Load and merge YAML configuration files.
    
    Args:
        *path_configs: Paths to YAML configuration files
        
    Returns:
        Merged configuration dictionary
        
    Raises:
        TypeError: If a config file doesn't contain a dict
        ValueError: If no configs are loaded
    """
    def merge(orig_conf: Any, new_conf: Any):
        """Recursively merge configuration dictionaries."""
        if isinstance(orig_conf, dict):
            result = copy.deepcopy(orig_conf)
            for k, v in new_conf.items():
                if k in orig_conf:
                    result[k] = merge(orig_conf[k], v)
                else:
                    result[k] = v
            return result
        else:
            return copy.deepcopy(new_conf)

    result = {}
    for path in list(path_configs):
        LOG.info("loading config from %s", path)
        if os.path.isfile(path):
            with open(path, "r") as f:
                c = yaml.safe_load(f)
                if not isinstance(c, dict):
                    raise TypeError(f"YAML config file {path} must be a dict")
                result = merge(result, c)
        else:
            LOG.warning("Skipping missing config file %s", repr(path))
    if not result:
        raise ValueError("No configs loaded")
    return result


def load_default_configs() -> dict[str, Any]:
    """Load default and local configuration files.
    
    Looks for config files in the following order:
    1. config/default.yaml (base configuration)
    2. config/local.yaml (local overrides, not committed to git)
    
    Returns:
        Merged configuration from default.yaml and local.yaml
    """
    # Get the project root directory (shilads-helpers)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up two levels: libs -> src -> project_root
    project_root = os.path.dirname(os.path.dirname(current_dir))
    config_dir = os.path.join(project_root, "config")
    
    default_config_path = os.path.join(config_dir, "default.yaml")
    local_config_path = os.path.join(config_dir, "local.yaml")
    
    return load_configs(default_config_path, local_config_path)


def load_all_configs() -> dict[str, Any]:
    """Load and merge all YAML configuration files in the config directory.
    
    Loads files in alphabetical order, with later files overriding earlier ones.
    Skips files that don't have .yaml or .yml extensions.
    
    Returns:
        Merged configuration from all YAML files in config/
    """
    # Get the project root directory (shilads-helpers)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up two levels: libs -> src -> project_root
    project_root = os.path.dirname(os.path.dirname(current_dir))
    config_dir = os.path.join(project_root, "config")
    
    if not os.path.exists(config_dir):
        raise ValueError(f"Config directory not found: {config_dir}")
    
    # Find all YAML files in the config directory
    yaml_files = []
    for filename in sorted(os.listdir(config_dir)):
        if filename.endswith(('.yaml', '.yml')):
            yaml_files.append(os.path.join(config_dir, filename))
    
    if not yaml_files:
        raise ValueError("No YAML files found in config directory")
    
    LOG.info("Loading configs from: %s", yaml_files)
    return load_configs(*yaml_files)


def get_config(key: str, config: dict[str, Any] = None) -> Any:
    """Get a configuration value by dot-separated key.
    
    Args:
        key: Dot-separated path to config value (e.g., "app.logging.level")
        config: Configuration dict (if None, loads default configs)
        
    Returns:
        Configuration value
        
    Raises:
        KeyError: If key not found in configuration
    """
    if config is None:
        config = load_default_configs()
    
    keys = key.split('.')
    value = config
    for k in keys:
        if not isinstance(value, dict):
            raise KeyError(f"Cannot access {k} in non-dict value at {'.'.join(keys[:keys.index(k)])}")
        if k not in value:
            raise KeyError(f"Key {key} not found in configuration")
        value = value[k]
    return value