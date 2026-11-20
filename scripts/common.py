"""Small helpers shared by the pipeline scripts."""

import json
import logging
import sys
from datetime import date, datetime, timezone

from dateutil.relativedelta import relativedelta

import config

CSV_ENCODING = "utf-8-sig"  # BOM so Excel opens Bangla text correctly


def setup_logging(step: str) -> logging.Logger:
    """Log to the console and to logs/<step>_<timestamp>.log."""
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = config.LOG_DIR / f"{step}_{stamp}.log"

    logger = logging.getLogger(step)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(log_path, encoding="utf-8")):
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    logger.info("Log file: %s", log_path.relative_to(config.ROOT))
    return logger


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def review_window(window_end: str | None = None) -> tuple[datetime, datetime]:
    """Return [start, end) of the review window as UTC datetimes.

    The end is midnight UTC of the scrape day (or config.WINDOW_END), and the
    start is exactly WINDOW_MONTHS calendar months earlier.
    """
    end_day = date.fromisoformat(window_end) if window_end else utc_now().date()
    end = datetime(end_day.year, end_day.month, end_day.day, tzinfo=timezone.utc)
    start = end - relativedelta(months=config.WINDOW_MONTHS)
    return start, end


def write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def table(rows: list[dict], columns: list[str]) -> str:
    """Render a list of dicts as a fixed-width text table for the logs."""
    widths = {c: max(len(str(c)), *(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    line = "  ".join(str(c).rjust(widths[c]) for c in columns)
    out = [line, "-" * len(line)]
    for r in rows:
        out.append("  ".join(str(r.get(c, "")).rjust(widths[c]) for c in columns))
    return "\n".join(out)
