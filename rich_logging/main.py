"""Application entry point.

Configures logging from the external YAML, then runs the worker. Console logging
is muted automatically while the worker's Live display is on screen; the file
handler captures everything at DEBUG the whole time.
"""
from __future__ import annotations

import logging

from console import console
from logging_setup import setup_logging
from worker import run_jobs


def main() -> None:
    setup_logging()  # reads logging.yaml (or $LOG_CONFIG), falls back if broken
    log = logging.getLogger("myapp.main")

    console.rule("[bold blue]Rich Logging Demo")
    log.info("Application starting")
    log.debug("This DEBUG line goes to the file but not the console (console=INFO)")

    try:
        run_jobs(n_jobs=4)
    except Exception:
        # Rich traceback on console, full detail in the file.
        log.exception("Unhandled error while running jobs")
        raise

    log.info("Application shutting down cleanly")
    console.rule("[bold blue]Done")


if __name__ == "__main__":
    main()