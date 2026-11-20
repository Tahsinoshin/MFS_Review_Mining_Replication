"""Scrape public Google Play reviews of the four MFS apps.

For every app x language setting (en, bn) x star rating (1-5) the script pages
through reviews sorted newest-first until it passes the start of the review
window, then merges all streams and deduplicates by review ID.

Each finished stream is checkpointed under data/raw/streams/, so an
interrupted run resumes where it stopped. Usernames and avatars are never
stored.

Usage (from the project root):
    python scripts/scrape_play.py                 # all apps, resumes finished streams
    python scripts/scrape_play.py --apps upay     # selected apps only
    python scripts/scrape_play.py --force         # discard checkpoints and re-scrape
"""

import argparse
import json
import platform
import shutil
import socket
import time
from datetime import datetime, timezone
from importlib.metadata import version

import pandas as pd
from google_play_scraper import Sort
from google_play_scraper import app as app_details
from google_play_scraper.constants.regex import Regex
from google_play_scraper.constants.request import Formats
from google_play_scraper.utils.request import post

import config
from common import CSV_ENCODING, read_json, review_window, setup_logging, table, utc_now, write_json

RUN_FILE = config.STREAM_DIR / "_run.json"
STREAM_COLUMNS = [
    "review_id", "app", "package", "lang_param", "star_filter", "score", "review_at_utc",
    "text", "thumbs_up", "app_version", "reply_text", "replied_at_utc", "scraped_at_utc",
]
RAW_COLUMNS = [
    "review_id", "app", "package", "score", "review_at_utc", "text", "thumbs_up",
    "app_version", "reply_text", "replied_at_utc", "lang_params", "scraped_at_utc",
]


# --------------------------------------------------------------------------
# Low-level fetching
# --------------------------------------------------------------------------
# google_play_scraper.reviews() swallows every request error and reports it as
# "no more pages", which would silently truncate a stream. We call the same
# endpoint through the library's request helpers instead, so errors surface and
# can be retried. This relies on library internals: keep the version pinned.

def fetch_page(package: str, lang: str, score: int, token: str | None) -> tuple[list, str | None]:
    url = Formats.Reviews.build(lang=lang, country=config.COUNTRY)
    body = Formats.Reviews.build_body(package, Sort.NEWEST.value, config.PAGE_SIZE, score, "null", token)
    dom = post(url, body, {"content-type": "application/x-www-form-urlencoded"})
    envelope = json.loads(Regex.REVIEWS.findall(dom)[0])
    inner = envelope[0][2]
    if inner is None:  # Play sends no data block when the filter matches nothing
        return [], None
    data = json.loads(inner)
    items = data[0] if data and data[0] else []
    next_token = _get(data, -2, -1)
    return items, next_token if isinstance(next_token, str) else None


def fetch_with_retry(package, lang, score, token, logger) -> tuple[list, str | None, int]:
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            items, next_token = fetch_page(package, lang, score, token)
            return items, next_token, attempt
        except Exception as exc:  # network errors, rate limits, malformed responses
            if attempt == config.MAX_RETRIES:
                raise RuntimeError(f"giving up after {attempt + 1} attempts: {exc!r}") from exc
            wait = config.BACKOFF_BASE_SEC * 2 ** attempt
            logger.warning("    request failed (%r); retry %d/%d in %ds",
                           exc, attempt + 1, config.MAX_RETRIES, wait)
            time.sleep(wait)


def _get(obj, *path):
    for key in path:
        try:
            obj = obj[key]
        except (IndexError, KeyError, TypeError):
            return None
    return obj


def _iso(ts) -> str | None:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ts else None


def parse_review(item, app_key, package, lang, score, scraped_at) -> dict:
    return {
        "review_id": item[0],
        "app": app_key,
        "package": package,
        "lang_param": lang,
        "star_filter": score,
        "score": _get(item, 2),
        "review_at_utc": _iso(_get(item, 5, 0)),
        "text": _get(item, 4) or "",
        "thumbs_up": _get(item, 6) or 0,
        "app_version": _get(item, 10),
        "reply_text": _get(item, 7, 1),
        "replied_at_utc": _iso(_get(item, 7, 2, 0)),
        "scraped_at_utc": scraped_at,
    }


# --------------------------------------------------------------------------
# Streams
# --------------------------------------------------------------------------

def stream_paths(app_key, lang, score):
    stem = f"{app_key}__{lang}__{score}star"
    return config.STREAM_DIR / f"{stem}.csv", config.STREAM_DIR / f"{stem}.json"


def scrape_stream(app_key, package, lang, score, start, end, logger) -> dict:
    """Page newest-first through one (app, lang, star) stream and checkpoint it."""
    start_ts, end_ts = start.timestamp(), end.timestamp()
    started = utc_now()
    scraped_at = started.strftime("%Y-%m-%d %H:%M:%S")
    rows, seen = [], set()
    token, pages, retries = None, 0, 0
    after_window = 0

    while True:
        items, token, n_retry = fetch_with_retry(package, lang, score, token, logger)
        retries += n_retry
        pages += 1
        if not items:
            stop_reason = "no more reviews"
            break

        new_ids = 0
        page_ts = []
        for item in items:
            rid = item[0]
            if rid in seen:
                continue
            seen.add(rid)
            new_ids += 1
            ts = _get(item, 5, 0)
            if ts is None:
                continue
            page_ts.append(ts)
            if ts >= end_ts:
                after_window += 1
            elif ts >= start_ts:
                rows.append(parse_review(item, app_key, package, lang, score, scraped_at))

        if page_ts and min(page_ts) < start_ts:
            stop_reason = "reached window start"
            break
        if new_ids == 0:
            stop_reason = "page repeated, no new IDs"
            break
        if token is None:
            stop_reason = "no more reviews"
            break
        time.sleep(config.REQUEST_PAUSE_SEC)

    csv_path, meta_path = stream_paths(app_key, lang, score)
    pd.DataFrame(rows, columns=STREAM_COLUMNS).to_csv(csv_path, index=False, encoding=CSV_ENCODING)
    meta = {
        "app": app_key, "package": package, "lang_param": lang, "star": score,
        "window_start_utc": start.isoformat(), "window_end_utc": end.isoformat(),
        "reviews_in_window": len(rows), "reviews_seen": len(seen), "after_window_end": after_window,
        "pages": pages, "retries": retries, "stop_reason": stop_reason,
        "started_utc": started.isoformat(), "finished_utc": utc_now().isoformat(),
    }
    write_json(meta_path, meta)
    return meta


def resolve_window(logger):
    """Reuse the window of an interrupted run so resumed streams stay consistent."""
    if RUN_FILE.exists():
        run = read_json(RUN_FILE)
        start = datetime.fromisoformat(run["window_start_utc"])
        end = datetime.fromisoformat(run["window_end_utc"])
        logger.info("Resuming run started %s (window kept from that run)", run["run_started_utc"])
        return start, end, run
    start, end = review_window(config.WINDOW_END)
    run = {"run_started_utc": utc_now().isoformat(),
           "window_start_utc": start.isoformat(), "window_end_utc": end.isoformat()}
    write_json(RUN_FILE, run)
    return start, end, run


def fetch_app_metadata(logger) -> dict:
    meta = {}
    for app_key, spec in config.APPS.items():
        try:
            d = app_details(spec["package"], lang="en", country=config.COUNTRY)
            meta[app_key] = {
                "package": spec["package"], "title": d.get("title"), "developer": d.get("developer"),
                "installs": d.get("installs"), "real_installs": d.get("realInstalls"),
                "rating": d.get("score"), "ratings": d.get("ratings"), "reviews": d.get("reviews"),
                "current_version": d.get("version"), "last_updated_utc": _iso(d.get("updated")),
            }
        except Exception as exc:  # metadata is context only; never block the scrape on it
            logger.warning("Could not fetch store metadata for %s: %r", app_key, exc)
            meta[app_key] = {"package": spec["package"], "error": repr(exc)}
        time.sleep(config.REQUEST_PAUSE_SEC)
    return meta


# --------------------------------------------------------------------------
# Merge
# --------------------------------------------------------------------------

def merge_streams(logger) -> pd.DataFrame:
    frames = []
    for app_key in config.APPS:
        for lang in config.LANGS:
            for score in config.SCORES:
                csv_path, _ = stream_paths(app_key, lang, score)
                frames.append(pd.read_csv(csv_path, dtype=str, keep_default_na=False, encoding=CSV_ENCODING))
    df = pd.concat(frames, ignore_index=True)

    mismatched = df[df["score"] != df["star_filter"]]
    if len(mismatched):
        logger.warning("%d rows whose star rating differs from the stream filter (kept, rating as reported)",
                       len(mismatched))

    lang_params = df.groupby("review_id")["lang_param"].agg(lambda s: "|".join(sorted(set(s))))
    merged = df.drop_duplicates("review_id", keep="first").set_index("review_id")
    merged["lang_params"] = lang_params
    merged = merged.reset_index()

    for col in ("score", "thumbs_up"):
        merged[col] = pd.to_numeric(merged[col]).astype("int64")
    merged = merged.sort_values(["app", "review_at_utc", "review_id"], ascending=[True, False, True])
    return merged[RAW_COLUMNS].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apps", nargs="+", choices=list(config.APPS), default=list(config.APPS))
    parser.add_argument("--force", action="store_true",
                        help="discard the selected apps' checkpoints and re-scrape them "
                             "(with all apps selected, the review window is recomputed too)")
    args = parser.parse_args()

    logger = setup_logging("scrape")
    socket.setdefaulttimeout(60)  # the library opens URLs without a timeout
    if args.force and config.STREAM_DIR.exists():
        if set(args.apps) == set(config.APPS):
            shutil.rmtree(config.STREAM_DIR)
        else:  # keep the run's window so every app shares the same one
            for app_key in args.apps:
                for path in config.STREAM_DIR.glob(f"{app_key}__*"):
                    path.unlink()
    config.STREAM_DIR.mkdir(parents=True, exist_ok=True)

    start, end, run = resolve_window(logger)
    logger.info("Review window (UTC): %s to %s (%d months, end exclusive)",
                start.date(), end.date(), config.WINDOW_MONTHS)

    for app_key in args.apps:
        package = config.APPS[app_key]["package"]
        for lang in config.LANGS:
            for score in config.SCORES:
                csv_path, meta_path = stream_paths(app_key, lang, score)
                if csv_path.exists() and meta_path.exists():
                    meta = read_json(meta_path)
                    logger.info("%-6s lang=%s %d-star: checkpoint found, %d reviews (skipped)",
                                app_key, lang, score, meta["reviews_in_window"])
                    continue
                logger.info("%-6s lang=%s %d-star: scraping ...", app_key, lang, score)
                meta = scrape_stream(app_key, package, lang, score, start, end, logger)
                logger.info("%-6s lang=%s %d-star: %d reviews in window, %d pages, %d retries (%s)",
                            app_key, lang, score, meta["reviews_in_window"], meta["pages"],
                            meta["retries"], meta["stop_reason"])
                time.sleep(config.REQUEST_PAUSE_SEC)

    missing = [f"{a}/{l}/{s}" for a in config.APPS for l in config.LANGS for s in config.SCORES
               if not stream_paths(a, l, s)[0].exists()]
    if missing:
        logger.info("Streams still missing (%d), so the merged file was not written yet: %s",
                    len(missing), ", ".join(missing))
        return

    df = merge_streams(logger)
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.RAW_CSV, index=False, encoding=CSV_ENCODING)
    logger.info("Wrote %d unique reviews to %s", len(df), config.RAW_CSV.relative_to(config.ROOT))

    # Counts per app, per star and per language setting
    by_star = df.pivot_table(index="app", columns="score", values="review_id", aggfunc="count", fill_value=0)
    by_lang = df.pivot_table(index="app", columns="lang_params", values="review_id", aggfunc="count", fill_value=0)
    star_rows = [{"app": a, **{f"{s}*": int(by_star.loc[a].get(s, 0)) for s in config.SCORES},
                  "1-3*": int(sum(by_star.loc[a].get(s, 0) for s in config.NEGATIVE_SCORES)),
                  "total": int(by_star.loc[a].sum())} for a in config.APPS]
    lang_cols = sorted(by_lang.columns)
    lang_rows = [{"app": a, **{c: int(by_lang.loc[a].get(c, 0)) for c in lang_cols}} for a in config.APPS]
    logger.info("Unique reviews by app and star rating:\n%s",
                table(star_rows, ["app", *[f"{s}*" for s in config.SCORES], "1-3*", "total"]))
    logger.info("Unique reviews by app and Play language setting (en|bn = returned by both):\n%s",
                table(lang_rows, ["app", *lang_cols]))

    streams = [read_json(stream_paths(a, l, s)[1]) for a in config.APPS for l in config.LANGS for s in config.SCORES]
    write_json(config.SCRAPE_SUMMARY, {
        "run": {**run, "run_finished_utc": utc_now().isoformat(), "window_months": config.WINDOW_MONTHS,
                "country": config.COUNTRY, "langs": config.LANGS, "page_size": config.PAGE_SIZE,
                "request_pause_sec": config.REQUEST_PAUSE_SEC, "python": platform.python_version(),
                "google_play_scraper": version("google-play-scraper"), "pandas": version("pandas")},
        "app_store_metadata": fetch_app_metadata(logger),
        "unique_reviews": int(len(df)),
        "by_app_and_star": star_rows,
        "by_app_and_lang_param": lang_rows,
        "streams": streams,
    })
    logger.info("Wrote %s", config.SCRAPE_SUMMARY.relative_to(config.ROOT))


if __name__ == "__main__":
    main()
