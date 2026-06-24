# logging_config.py
import logging.config
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        # Console: RichHandler adds time/level/path itself, so keep this minimal
        "rich_console": {
            "format": "%(message)s",
            "datefmt": "[%X]",
        },
        # File: plain text, full detail, no ANSI color codes
        "detailed_file": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | "
                      "%(module)s:%(funcName)s:%(lineno)d | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },

    "handlers": {
        "console": {
            "()": "rich.logging.RichHandler",   # "()" = call this as a factory
            "console": console,                  # inject the shared instance
            "level": "INFO",
            "formatter": "rich_console",
            "rich_tracebacks": True,
            "tracebacks_show_locals": True,
            "show_time": True,
            "show_level": True,
            "show_path": True,
            "markup": True,
        },
        "file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed_file",
            "filename": str(LOG_DIR / "app.log"),
            "when": "midnight",      # roll at 00:00
            "interval": 1,           # every 1 day
            "backupCount": 30,       # keep 30 days, then delete oldest
            "encoding": "utf-8",
            "delay": True,           # don't open file until first emit
        },
    },

    "loggers": {
        # Your app's namespace — tune levels per-package here
        "myapp": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False,
        },
        # Quiet a noisy dependency
        "urllib3": {"level": "WARNING", "handlers": ["console", "file"], "propagate": False},
    },

    "root": {
        "level": "WARNING",
        "handlers": ["console", "file"],
    },
}


def setup_logging():
    logging.config.dictConfig(LOGGING_CONFIG)