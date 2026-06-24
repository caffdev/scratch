"""Logging bootstrap.

Loads an external YAML config, validates it, injects the shared Console
(Option A: patch the parsed dict after load), applies optional env-var
overrides, and falls back to a safe basicConfig if anything goes wrong.
"""
from __future__ import annotations

import logging
import logging.config
import os
from pathlib import Path

import yaml

from console import console

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "logging.yaml"

# Keys we require to exist before we trust the dict enough to hand it to dictConfig.
_REQUIRED_TOP_KEYS = ("version", "handlers", "loggers")


def _validate(config: dict) -> None:
    """Raise ValueError if the parsed config is missing essentials."""
    if not isinstance(config, dict):
        raise ValueError("Config root must be a mapping")
    missing = [k for k in _REQUIRED_TOP_KEYS if k not in config]
    if missing:
        raise ValueError(f"Config missing required keys: {missing}")
    if "console" not in config["handlers"]:
        raise ValueError("Config missing 'console' handler")
    if "file" not in config["handlers"]:
        raise ValueError("Config missing 'file' handler")


def _inject_shared_console(config: dict) -> None:
    """Rewrite the class-based RichHandler into the () factory form so we can
    pass the live shared Console instance (Option A)."""
    ch = config["handlers"]["console"]
    ch.pop("class", None)
    ch["()"] = "rich.logging.RichHandler"
    ch["console"] = console


def _resolve_log_path(config: dict) -> None:
    """Make the file handler path absolute (relative to BASE_DIR) and ensure
    its parent directory exists — so logs don't land wherever the CWD happens
    to be at launch."""
    fh = config["handlers"]["file"]
    fname = Path(fh["filename"])
    if not fname.is_absolute():
        fname = BASE_DIR / fname
    fname.parent.mkdir(parents=True, exist_ok=True)
    fh["filename"] = str(fname)


def _apply_env_overrides(config: dict) -> None:
    """LOG_LEVEL bumps both the console handler and the app logger."""
    if level := os.getenv("LOG_LEVEL"):
        level = level.upper()
        config["handlers"]["console"]["level"] = level
        if "myapp" in config["loggers"]:
            config["loggers"]["myapp"]["level"] = level


def setup_logging(config_path: str | os.PathLike | None = None) -> None:
    config_path = Path(config_path or os.getenv("LOG_CONFIG", DEFAULT_CONFIG))
    try:
        config = yaml.safe_load(config_path.read_text())
        _validate(config)
        _apply_env_overrides(config)
        _resolve_log_path(config)
        _inject_shared_console(config)
        logging.config.dictConfig(config)
        logging.getLogger("myapp").debug(
            "Logging configured from %s", config_path
        )
    except (FileNotFoundError, yaml.YAMLError, ValueError, KeyError) as e:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        )
        logging.getLogger(__name__).warning(
            "Falling back to basicConfig; failed to load %s: %s", config_path, e
        )