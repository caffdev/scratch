Here's how to wire up Rich + Python's logging for console + daily rotating file logs.
1. The pieces

rich.logging.RichHandler — pretty, colorized console output with tracebacks
logging.handlers.TimedRotatingFileHandler — rolls over to a new file daily
logging.config.dictConfig — declarative config, the production-standard way to wire handlers/formatters/loggers

2. Dictionary-based config
python# logging_config.py
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
            "class": "rich.logging.RichHandler",
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
3. Call it once at startup
python# main.py
import logging
from logging_config import setup_logging

setup_logging()
log = logging.getLogger("myapp.main")  # child of "myapp", inherits its config

def run():
    log.debug("Detailed state — file only (console is INFO+)")
    log.info("Service started")
    log.warning("Disk at 85%%")
    try:
        1 / 0
    except ZeroDivisionError:
        log.exception("Computation failed")  # full Rich traceback on console

if __name__ == "__main__":
    run()
4. What happens, step by step

setup_logging() runs first, before any logger is used. dictConfig builds the formatters, handlers, and loggers from the dict and attaches them. Do this once, at the entry point.
You get loggers by name, never by instantiating handlers yourself. getLogger("myapp.main") is a child of "myapp", so it inherits that logger's level and handlers via the hierarchy.
A record is emitted (e.g. log.info(...)). It's checked against the logger's level (DEBUG for myapp), then passed to each attached handler.
Each handler applies its own level filter. The console handler is INFO, so DEBUG records are dropped there but still written to the file handler (DEBUG). This is the core split: terse console, verbose file.
Formatters render the record. Console uses %(message)s because RichHandler itself prints the timestamp, level, and source path with color. The file uses the full detailed_file format with module/function/line — plain text, grep-friendly, no color codes.
TimedRotatingFileHandler rolls at midnight. When the first record arrives after 00:00, it renames the current app.log to app.log.2026-06-24 and opens a fresh app.log. backupCount=30 means the 31st-oldest file is deleted on rollover.
propagate: False stops records from bubbling up to the root logger, which would otherwise double-log everything.

Key production details

rich_tracebacks=True + tracebacks_show_locals=True give you readable, syntax-highlighted exceptions with local variable values on the console. Don't enable show_locals if logs might capture secrets.
The file handler gets no Rich formatting — keep ANSI out of files. If you want structured logs for ingestion (Loki/ELK), swap detailed_file for a JSON formatter like python-json-logger.
delay=True avoids creating an empty file when a handler never fires.
Two RichHandlers in one process fight over the console. Use exactly one. If you also use rich.Console for app output, pass the same Console instance into RichHandler via a custom factory so they share state and don't garble each other.
when="midnight" uses local time by default; set utc=True on the handler if your fleet should rotate uniformly.

One caveat on the dict above: handler-level "rich.logging.RichHandler" config keys like rich_tracebacks are passed straight to the constructor, which works because dictConfig forwards unknown keys as kwargs. If you need a shared Console, you can't express that in pure dict form — use a small custom handler subclass or a () factory key instead.You said: should I be using rich.should I be using rich.Console with this? What about logs showing during Live that cause flickering10:02 AMClaude responded: Yes, use a single shared Console, and route logging away from the live region while Live is active.Yes, use a single shared Console, and route logging away from the live region while Live is active. Two issues, two fixes.
Shared Console
The problem: RichHandler creates its own Console by default. If you also do Console() for app output, you have two objects with separate state writing to the same terminal — they miscalculate width, fight over cursor position, and interleave badly.
Fix: make one Console, inject it everywhere. This breaks pure-dict config, so use a factory.
python# console.py
from rich.console import Console
console = Console()  # the one true console
python# logging_config.py — replace the console handler with a factory
from console import console

LOGGING_CONFIG = {
    # ...
    "handlers": {
        "console": {
            "()": "rich.logging.RichHandler",   # "()" = call this as a factory
            "console": console,                  # inject the shared instance
            "level": "INFO",
            "formatter": "rich_console",
            "rich_tracebacks": True,
            "tracebacks_show_locals": True,
            "markup": True,
        },
        # file handler unchanged
    },
    # ...
}
The "()" key tells dictConfig to treat the value as a callable and pass the remaining keys as kwargs, so you can hand it a live object the plain "class" form can't.
Live + logging = flicker
Live owns a region of the screen and repaints it on a refresh loop. A log record written straight to stdout in the middle of that lands inside the region, so Live overdraws it on the next frame — you see tearing/flicker, and the log line often vanishes.
The mechanism matters: Live redraws on every refresh (default 4/sec, or whenever you call update()). Any out-of-band write to the same console competes with that redraw.
There are three correct approaches, in rough order of preference:
1. Print through Live, not around it. Live exposes the console so writes are serialized above the live region instead of into it:
pythonfrom rich.live import Live
from rich.table import Table

with Live(generate_table(), console=console, refresh_per_second=4) as live:
    for item in work():
        live.console.log("processed", item)   # prints cleanly above the table
        live.update(generate_table())
live.console.print(...) / .log(...) flush above the live region without flicker because Live coordinates the cursor. But your logging calls don't go through live.console — which leads to the real fix:
2. Swap the handler's console for the duration of Live. Point the RichHandler at the same console Live is managing so log records get the same coordinated treatment. Since you already share one Console, and Live wraps that console, logging emitted to it is serialized automatically — as long as RichHandler writes via the Live-aware path. In practice the clean way is a context manager that suspends the file-only noise and lets Rich handle the rest:
pythonwith Live(table, console=console) as live:
    log.info("starting")   # RichHandler -> shared console -> Live serializes it
This works because RichHandler ultimately calls console.print, and when that console is inside a Live context, Rich buffers and reorders the output above the region. The single shared Console is what makes this hold together — with two consoles it breaks.
3. During Live, log to file only; show progress in the live region. Often the cleanest production pattern: the live display is your console feedback, so silence the console handler while it's up and let the file keep full detail.
pythonimport logging
from contextlib import contextmanager

@contextmanager
def console_quiet():
    h = next(h for h in logging.getLogger("myapp").handlers
             if h.get_name() == "console" or h.__class__.__name__ == "RichHandler")
    old = h.level
    h.setLevel(logging.CRITICAL + 1)   # mute console
    try:
        yield
    finally:
        h.setLevel(old)

with console_quiet(), Live(table, console=console) as live:
    for item in work():
        log.info("processed %s", item)   # file only; console stays clean
        live.update(render(table))
What I'd actually ship

One shared Console, injected via the "()" factory. Non-negotiable once you mix Rich logging with any other Rich output.
For long-running live displays (progress bars, dashboards): use Progress/Live as the console feedback channel and mute the console handler while it's active (approach 3). The file handler keeps logging at DEBUG the whole time, so you lose nothing for debugging.
For occasional log lines during a short Live: rely on the shared console serializing them (approaches 1–2).

One note: rich.progress.Progress handles this better than raw Live for the common case — it has built-in support for printing/logging above the bars without flicker, so if your live region is progress tracking, prefer Progress and call progress.console.log(...) or just let the shared-console RichHandler write through it.