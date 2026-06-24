"""A worker that drives a Rich Live display while emitting logs.

Demonstrates the production pattern: the live region IS the console feedback,
so the console log handler is muted while Live is active (logs still go to file
at full DEBUG detail). This avoids flicker from out-of-band writes into the
live region.
"""
from __future__ import annotations

import logging
import random
import time
from contextlib import contextmanager

from rich.live import Live
from rich.table import Table

from console import console

log = logging.getLogger("myapp.worker")


@contextmanager
def console_quiet(logger_name: str = "myapp"):
    """Temporarily mute the RichHandler (console) so Live owns the screen.
    File handler keeps logging at its own level the whole time."""
    handlers = logging.getLogger(logger_name).handlers
    rich_handlers = [h for h in handlers if h.__class__.__name__ == "RichHandler"]
    saved = [(h, h.level) for h in rich_handlers]
    for h, _ in saved:
        h.setLevel(logging.CRITICAL + 1)
    try:
        yield
    finally:
        for h, lvl in saved:
            h.setLevel(lvl)


def _render(rows: list[tuple[str, str, int]]) -> Table:
    table = Table(title="Job Progress")
    table.add_column("Task", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")
    table.add_column("Items", justify="right", style="green")
    for name, status, n in rows:
        table.add_row(name, status, str(n))
    return table


def run_jobs(n_jobs: int = 4) -> None:
    log.info("Starting %d jobs", n_jobs)
    rows = [(f"job-{i}", "pending", 0) for i in range(n_jobs)]

    # Console handler muted here; the Live table is the user-facing feedback.
    with console_quiet(), Live(_render(rows), console=console, refresh_per_second=8) as live:
        for i in range(n_jobs):
            name = f"job-{i}"
            rows[i] = (name, "running", 0)
            live.update(_render(rows))
            log.debug("Job %s started", name)  # file only while Live is up

            total = random.randint(20, 50)
            for done in range(1, total + 1):
                rows[i] = (name, "running", done)
                if done % 10 == 0:
                    live.update(_render(rows))
                    log.debug("Job %s progress %d/%d", name, done, total)
                time.sleep(0.01)

            if random.random() < 0.25:
                rows[i] = (name, "[red]failed[/red]", total)
                live.update(_render(rows))
                log.warning("Job %s failed after %d items", name, total)
            else:
                rows[i] = (name, "[green]done[/green]", total)
                live.update(_render(rows))
                log.info("Job %s completed (%d items)", name, total)

    # Back outside Live — console logging is live again.
    log.info("All jobs finished")