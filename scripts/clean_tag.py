"""Clean the raw reviews, redact personal data, tag language.

Input : data/raw/play_reviews_raw.csv   (from scrape_play.py)
Output: data/clean/play_reviews_clean.csv
        logs/clean_summary.json         (per-step counts for the paper's method section)

Steps, in order (each step's removals are counted per app and polarity):
  1. keep reviews inside the review window recorded by the scrape run
  2. drop empty texts
  3. drop reviews under 4 words or 15 characters
  4. drop duplicate texts within an app (case/spacing/punctuation-insensitive),
     keeping the earliest review
  5. redact phone numbers, NID/account numbers, transaction IDs and e-mails
     (review text and developer reply)
  6. tag each review as bangla, english, mixed or romanized

The original wording is kept (no translation), apart from collapsing runs of
whitespace and the redaction placeholders.

Usage (from the project root):
    python scripts/clean_tag.py
"""

import re
from datetime import datetime

import pandas as pd

import config
from common import CSV_ENCODING, read_json, setup_logging, table, write_json
from textproc import dedup_key, normalize_whitespace, redact, romanized_words, tag_language, word_count

PLACEHOLDER_RE = re.compile(r"\[(?:PHONE|TRX_ID|ID_NUMBER|EMAIL|NAME)\]")
CLEAN_COLUMNS = [
    "review_id", "app", "score", "polarity", "review_at_utc", "app_version", "thumbs_up",
    "text", "word_count", "char_count", "lang_group", "bengali_share", "romanized_hits",
    "pii_in_text", "has_reply", "reply_text", "replied_at_utc", "pii_in_reply", "lang_params",
]


def format_counts(counts: dict) -> str:
    return ";".join(f"{k}:{v}" for k, v in sorted(counts.items()))


def count_by_group(df: pd.DataFrame) -> dict:
    counts = df.groupby(["app", "polarity"]).size()
    return {f"{app}/{pol}": int(counts.get((app, pol), 0))
            for app in config.APPS for pol in ("negative", "positive")}


def main() -> None:
    logger = setup_logging("clean")
    df = pd.read_csv(config.RAW_CSV, dtype=str, keep_default_na=False, encoding=CSV_ENCODING)
    df["score"] = df["score"].astype(int)
    df["thumbs_up"] = df["thumbs_up"].astype(int)
    df["polarity"] = df["score"].map(lambda s: "negative" if s in config.NEGATIVE_SCORES else "positive")
    logger.info("Loaded %d raw reviews from %s", len(df), config.RAW_CSV.relative_to(config.ROOT))

    run = read_json(config.SCRAPE_SUMMARY)["run"]
    start = datetime.fromisoformat(run["window_start_utc"]).strftime("%Y-%m-%d %H:%M:%S")
    end = datetime.fromisoformat(run["window_end_utc"]).strftime("%Y-%m-%d %H:%M:%S")

    flow = [("raw (unique review IDs)", count_by_group(df))]

    df = df[(df["review_at_utc"] >= start) & (df["review_at_utc"] < end)].copy()
    flow.append(("inside review window", count_by_group(df)))

    df["text"] = df["text"].map(normalize_whitespace)
    df = df[df["text"] != ""].copy()
    flow.append(("non-empty text", count_by_group(df)))

    # Length filter first, so the duplicate count below reflects substantive repeats
    # rather than thousands of identical one-liners such as "bad app".
    df["word_count"] = df["text"].map(word_count)
    df["char_count"] = df["text"].str.len()
    df = df[(df["word_count"] >= config.MIN_WORDS) & (df["char_count"] >= config.MIN_CHARS)].copy()
    flow.append((f">= {config.MIN_WORDS} words and >= {config.MIN_CHARS} characters", count_by_group(df)))

    df["_key"] = df["text"].map(dedup_key)
    df = df.sort_values(["app", "review_at_utc", "review_id"])
    df = df.drop_duplicates(["app", "_key"], keep="first").drop(columns="_key")
    flow.append(("after removing duplicate texts", count_by_group(df)))

    text_red = df["text"].map(redact)
    df["text"] = text_red.map(lambda r: r[0])
    df["pii_in_text"] = text_red.map(lambda r: format_counts(r[1]))
    df["reply_text"] = df["reply_text"].map(normalize_whitespace)
    reply_red = df["reply_text"].map(lambda t: redact(t, is_reply=True))
    df["reply_text"] = reply_red.map(lambda r: r[0])
    df["pii_in_reply"] = reply_red.map(lambda r: format_counts(r[1]))
    df["has_reply"] = df["reply_text"] != ""

    tags = pd.DataFrame([tag_language(PLACEHOLDER_RE.sub(" ", t)) for t in df["text"]], index=df.index)
    df = pd.concat([df, tags], axis=1)

    df = df.sort_values(["app", "review_at_utc", "review_id"], ascending=[True, False, True])
    df = df[CLEAN_COLUMNS].reset_index(drop=True)
    config.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.CLEAN_CSV, index=False, encoding=CSV_ENCODING)
    logger.info("Wrote %d clean reviews to %s", len(df), config.CLEAN_CSV.relative_to(config.ROOT))

    # ---- reporting -------------------------------------------------------
    groups = [f"{a}/{p}" for a in config.APPS for p in ("negative", "positive")]
    flow_rows = [{"step": step, **counts, "total": sum(counts.values())} for step, counts in flow]
    logger.info("Cleaning flow (negative = 1-3 stars, positive = 4-5 stars):\n%s",
                table(flow_rows, ["step", *groups, "total"]))

    lang_rows = []
    for app in config.APPS:
        for pol in ("negative", "positive"):
            sub = df[(df["app"] == app) & (df["polarity"] == pol)]
            counts = sub["lang_group"].value_counts()
            lang_rows.append({"app": app, "polarity": pol, "n": len(sub),
                              **{g: int(counts.get(g, 0)) for g in [*config.LANG_GROUPS, "other"]}})
    logger.info("Language groups of clean reviews:\n%s",
                table(lang_rows, ["app", "polarity", "n", *config.LANG_GROUPS, "other"]))

    pii_types = {}
    for col in ("pii_in_text", "pii_in_reply"):
        for cell in df[col]:
            for part in filter(None, cell.split(";")):
                label, n = part.split(":")
                key = f"{col.removeprefix('pii_in_')}:{label}"
                pii_types[key] = pii_types.get(key, 0) + int(n)
    logger.info("Redactions: %s", pii_types or "none")
    logger.info("Reviews with at least one redaction: %d", int((df["pii_in_text"] != "").sum()))

    write_json(config.CLEAN_SUMMARY, {
        "input": str(config.RAW_CSV.relative_to(config.ROOT)),
        "output": str(config.CLEAN_CSV.relative_to(config.ROOT)),
        "window_utc": [start, end],
        "rules": {"min_words": config.MIN_WORDS, "min_chars": config.MIN_CHARS,
                  "bangla_ratio_min": config.BANGLA_RATIO_MIN, "latin_ratio_min": config.LATIN_RATIO_MIN,
                  "romanized_min_hits": config.ROMANIZED_MIN_HITS,
                  "romanized_min_share": config.ROMANIZED_MIN_SHARE,
                  "romanized_single_hit_share": config.ROMANIZED_SINGLE_HIT_SHARE,
                  "romanized_word_list_size": len(romanized_words())},
        "flow": flow_rows,
        "language_groups": lang_rows,
        "redactions": pii_types,
        "reviews_with_redaction": int((df["pii_in_text"] != "").sum()),
    })
    logger.info("Wrote %s", config.CLEAN_SUMMARY.relative_to(config.ROOT))


if __name__ == "__main__":
    main()
