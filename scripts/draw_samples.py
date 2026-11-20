"""Draw the fixed-seed working samples and export them to Excel.

Sets, drawn per app from data/clean/play_reviews_clean.csv:
  Pilot       15 random 1-3 star reviews per app (60). Kept out of every other set.
  Analysis    random 1-3 star reviews, pilot excluded: 1,600 in total, nominally
              400 per app. An app with fewer than 400 left contributes all it has and
              the shortfall is shared equally by the other apps (REBALANCE_SHORTFALL).
  Gold        50 per app (200) drawn from inside the analysis set, stratified by
              language group: proportional, with at least 5 per group when available.
              Split into 150 "tune" and 50 "holdout" reviews for the LLM step.
  Contrast    50 random 4-5 star reviews per app (200).
  Lang check  25 random Latin-script (english/romanized) 1-3 star reviews per app (100),
              for measuring the romanized-tagging error rate by hand.

Drawing the analysis set first and nesting the gold set inside it keeps the analysis
set a random sample within each app (needed for the RQ1 frequencies) while the gold set is
still random, stratified and pilot-free. Each draw uses its own seed derived from
SEED, so changing one set's size never changes another set.

Outputs:
  data/samples/mfs_review_samples.xlsx   one sheet per set + README + Summary
  data/samples/<set>.csv                 the same sets as CSV
  data/samples/sample_membership.csv     IDs and set membership only (no text)
  logs/sample_manifest.json              seed, sizes, allocation, input checksum

Usage (from the project root):
    python scripts/draw_samples.py
"""

import hashlib

import numpy as np
import pandas as pd

import config
from common import CSV_ENCODING, read_json, setup_logging, table, utc_now, write_json
from excel_export import add_lang_check_tools, new_workbook, write_frame, write_info_sheet

DRAW_KEYS = {"pilot": 1, "analysis": 2, "gold": 3, "holdout": 4, "contrast": 5, "lang_check": 6}
APP_INDEX = {app: i for i, app in enumerate(config.APPS)}
BASE_COLUMNS = ["sample_id", "review_id", "app", "score", "review_date_utc", "app_version",
                "lang_group", "text", "word_count", "thumbs_up", "has_reply"]


# --------------------------------------------------------------------------
# Random draws and allocation
# --------------------------------------------------------------------------

def rng_for(purpose: str, app: str | None = None) -> np.random.Generator:
    return np.random.default_rng([config.SEED, DRAW_KEYS[purpose], APP_INDEX.get(app, 99)])


def draw(pool: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Simple random sample without replacement, independent of the pool's row order."""
    pool = pool.sort_values("review_id")
    picked = rng.choice(len(pool), size=min(n, len(pool)), replace=False)
    return pool.iloc[picked]


def largest_remainder(quotas: dict, total: int, rng: np.random.Generator) -> dict:
    """Round fractional quotas to integers that sum to total (ties broken at random)."""
    alloc = {k: int(np.floor(q)) for k, q in quotas.items()}
    keys = list(quotas)
    tiebreak = dict(zip(keys, rng.permutation(len(keys))))
    order = sorted(keys, key=lambda k: (-(quotas[k] - alloc[k]), tiebreak[k]))
    for k in order[: total - sum(alloc.values())]:
        alloc[k] += 1
    return alloc


def allocate_analysis(available: dict) -> dict:
    """Split ANALYSIS_TOTAL across apps, capped by what each app has."""
    nominal = config.ANALYSIS_TOTAL // len(available)
    if not config.REBALANCE_SHORTFALL:
        return {a: min(nominal, n) for a, n in available.items()}

    alloc, open_apps, remaining = {}, list(available), config.ANALYSIS_TOTAL
    while open_apps:
        share = remaining / len(open_apps)
        short = [a for a in open_apps if available[a] <= share]
        if not short:
            break
        for a in short:  # these apps give everything they have
            alloc[a] = available[a]
            remaining -= available[a]
            open_apps.remove(a)
    for i, a in enumerate(open_apps):  # equal shares; any remainder goes to the first apps
        alloc[a] = remaining // len(open_apps) + (1 if i < remaining % len(open_apps) else 0)
    return {a: alloc[a] for a in available}


def allocate_strata(counts: dict, n: int, floor: int, rng: np.random.Generator) -> dict:
    """Proportional allocation of n across strata, with a floor per stratum.

    A stratum whose proportional share falls below the floor gets the floor (or all of
    its reviews if it has fewer); the rest is shared proportionally by the others.
    """
    counts = {g: c for g, c in counts.items() if c > 0}
    if sum(counts.values()) <= n:
        return dict(counts)
    fixed, free, n_left = {}, dict(counts), n
    while True:
        total_free = sum(free.values())
        quotas = {g: n_left * c / total_free for g, c in free.items()}
        below = [g for g in free if g in config.LANG_GROUPS and quotas[g] < min(floor, free[g])]
        if not below:
            break
        for g in below:
            fixed[g] = min(floor, counts[g])
            n_left -= fixed[g]
            del free[g]
    return {**fixed, **largest_remainder(quotas, n_left, rng)}


# --------------------------------------------------------------------------
# Building the sets
# --------------------------------------------------------------------------

def with_ids(df: pd.DataFrame, app: str, tag: str, width: int) -> pd.DataFrame:
    df = df.copy()
    prefix = config.APPS[app]["prefix"]
    df.insert(0, "sample_id", [f"{prefix}-{tag}{i:0{width}d}" for i in range(1, len(df) + 1)])
    return df


def order_rows(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(["app", "sample_id"], key=lambda s: s.map(APP_INDEX) if s.name == "app" else s)


def main() -> None:
    logger = setup_logging("sample")
    clean = pd.read_csv(config.CLEAN_CSV, dtype=str, keep_default_na=False, encoding=CSV_ENCODING)
    for col in ("score", "word_count", "thumbs_up", "romanized_hits"):
        clean[col] = clean[col].astype(int)
    clean["bengali_share"] = clean["bengali_share"].astype(float)
    clean["has_reply"] = clean["has_reply"] == "True"
    clean["review_date_utc"] = pd.to_datetime(clean["review_at_utc"])
    checksum = hashlib.sha256(config.CLEAN_CSV.read_bytes()).hexdigest()
    logger.info("Loaded %d clean reviews (sha256 %s...)", len(clean), checksum[:12])

    negative = clean[clean["polarity"] == "negative"]
    positive = clean[clean["polarity"] == "positive"]

    # ---- pilot -------------------------------------------------------------
    pilot_parts, rest_pools = [], {}
    for app in config.APPS:
        pool = negative[negative["app"] == app]
        pilot = draw(pool, config.PILOT_PER_APP, rng_for("pilot", app))
        pilot_parts.append(with_ids(pilot, app, "P", 2))
        rest_pools[app] = pool[~pool["review_id"].isin(pilot["review_id"])]
    pilot = pd.concat(pilot_parts)

    # ---- analysis (pilot excluded) ------------------------------------------
    available = {app: len(rest_pools[app]) for app in config.APPS}
    allocation = allocate_analysis(available)
    analysis_parts = []
    for app in config.APPS:
        sample = draw(rest_pools[app], allocation[app], rng_for("analysis", app))
        analysis_parts.append(with_ids(sample, app, "A", 3))
    analysis = pd.concat(analysis_parts)

    # ---- gold (inside analysis, stratified by language group) ----------------
    gold_parts, strata_log = [], {}
    for app in config.APPS:
        rng = rng_for("gold", app)
        pool = analysis[analysis["app"] == app]
        counts = pool["lang_group"].value_counts().to_dict()
        alloc = allocate_strata(counts, config.GOLD_PER_APP, config.GOLD_MIN_PER_LANG_GROUP, rng)
        strata_log[app] = {"available_in_analysis": {g: int(c) for g, c in counts.items()}, "allocated": alloc}
        for group, n in sorted(alloc.items()):
            gold_parts.append(draw(pool[pool["lang_group"] == group], n, rng))
    gold = pd.concat(gold_parts)  # rows keep their analysis sample_id

    # ---- gold tune / holdout split ------------------------------------------
    gold_sizes = gold["app"].value_counts().to_dict()
    holdout_quota = {a: config.GOLD_HOLDOUT_TOTAL * gold_sizes[a] / len(gold) for a in config.APPS}
    holdout_alloc = largest_remainder(holdout_quota, config.GOLD_HOLDOUT_TOTAL, rng_for("holdout"))
    holdout_ids = set()
    for app in config.APPS:
        picked = draw(gold[gold["app"] == app], holdout_alloc[app], rng_for("holdout", app))
        holdout_ids.update(picked["review_id"])
    gold["gold_split"] = np.where(gold["review_id"].isin(holdout_ids), "holdout", "tune")
    analysis["in_gold"] = analysis["review_id"].isin(gold["review_id"])

    # ---- contrast and language check ------------------------------------------
    contrast = pd.concat([
        with_ids(draw(positive[positive["app"] == app], config.CONTRAST_PER_APP, rng_for("contrast", app)), app, "C", 2)
        for app in config.APPS
    ])
    latin = negative[negative["lang_group"].isin(["english", "romanized"])]
    lang_check = pd.concat([
        with_ids(draw(latin[latin["app"] == app], config.LANG_CHECK_PER_APP, rng_for("lang_check", app)), app, "L", 2)
        for app in config.APPS
    ])
    lang_check["manual_lang_group"] = ""
    lang_check["note"] = ""

    # ---- integrity checks -------------------------------------------------------
    pilot_ids, analysis_ids, gold_ids = set(pilot["review_id"]), set(analysis["review_id"]), set(gold["review_id"])
    checks = {
        "pilot and analysis are disjoint": not pilot_ids & analysis_ids,
        "gold is inside analysis": gold_ids <= analysis_ids,
        "pilot and gold are disjoint": not pilot_ids & gold_ids,
        "no duplicate reviews within a set": all(not s["review_id"].duplicated().any()
                                                 for s in (pilot, analysis, gold, contrast, lang_check)),
        "pilot/analysis/gold are 1-3 stars": all(s["score"].isin(config.NEGATIVE_SCORES).all()
                                                 for s in (pilot, analysis, gold)),
        "contrast is 4-5 stars": contrast["score"].isin(config.POSITIVE_SCORES).all(),
        "analysis matches its allocation": len(analysis) == sum(allocation.values()),
        f"gold has {config.GOLD_PER_APP * len(config.APPS)} reviews": len(gold) == config.GOLD_PER_APP * len(config.APPS),
        f"holdout has {config.GOLD_HOLDOUT_TOTAL} reviews": len(holdout_ids) == config.GOLD_HOLDOUT_TOTAL,
    }
    for name, ok in checks.items():
        logger.info("check %-40s %s", name, "OK" if ok else "FAILED")
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise SystemExit(f"Sample checks failed: {failed}. Nothing was written.")
    if len(analysis) < config.ANALYSIS_TOTAL:
        logger.warning("Analysis set has %d reviews, below the target of %d (not enough clean reviews)",
                       len(analysis), config.ANALYSIS_TOTAL)

    sets = {
        "pilot": order_rows(pilot)[BASE_COLUMNS],
        "gold": order_rows(gold)[BASE_COLUMNS + ["gold_split"]],
        "analysis": order_rows(analysis)[BASE_COLUMNS + ["in_gold"]],
        "contrast": order_rows(contrast)[BASE_COLUMNS],
        "lang_check": order_rows(lang_check)[["sample_id", "review_id", "app", "score", "lang_group",
                                              "bengali_share", "romanized_hits", "text",
                                              "manual_lang_group", "note"]],
    }

    # ---- CSV outputs -----------------------------------------------------------------
    config.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in sets.items():
        df.to_csv(config.SAMPLE_DIR / f"{name}.csv", index=False, encoding=CSV_ENCODING)
    membership = pd.concat([
        sets["pilot"][["sample_id", "review_id", "app"]].assign(set="pilot"),
        sets["analysis"][["sample_id", "review_id", "app", "in_gold"]].assign(set="analysis"),
        sets["contrast"][["sample_id", "review_id", "app"]].assign(set="contrast"),
    ]).merge(sets["gold"][["review_id", "gold_split"]], on="review_id", how="left")
    membership["in_gold"] = membership["in_gold"].fillna(False).astype(bool)
    membership["gold_split"] = membership["gold_split"].fillna("")
    membership[["sample_id", "review_id", "app", "set", "in_gold", "gold_split"]].to_csv(
        config.SAMPLE_DIR / "sample_membership.csv", index=False, encoding=CSV_ENCODING)

    # ---- summary tables ------------------------------------------------------------------
    size_rows = []
    for app in config.APPS:
        g = sets["gold"][sets["gold"]["app"] == app]
        size_rows.append({
            "app": app,
            "clean 1-3* pool": int((negative["app"] == app).sum()),
            "clean 4-5* pool": int((positive["app"] == app).sum()),
            "pilot": int((sets["pilot"]["app"] == app).sum()),
            "analysis": int((sets["analysis"]["app"] == app).sum()),
            "gold": len(g),
            "gold tune": int((g["gold_split"] == "tune").sum()),
            "gold holdout": int((g["gold_split"] == "holdout").sum()),
            "contrast": int((sets["contrast"]["app"] == app).sum()),
            "lang check": int((sets["lang_check"]["app"] == app).sum()),
        })
    size_rows.append({k: ("total" if k == "app" else sum(r[k] for r in size_rows)) for k in size_rows[0]})
    size_cols = list(size_rows[0])

    groups = [*config.LANG_GROUPS, "other"]
    lang_rows, star_rows = [], []
    frames = {"1-3* pool": negative, "pilot": sets["pilot"], "gold": sets["gold"],
              "analysis": sets["analysis"], "contrast": sets["contrast"]}
    for set_name, df in frames.items():
        for app in config.APPS:
            sub = df[df["app"] == app]
            lc = sub["lang_group"].value_counts()
            sc = sub["score"].value_counts()
            lang_rows.append({"set": set_name, "app": app, "n": len(sub), **{g: int(lc.get(g, 0)) for g in groups}})
            star_rows.append({"set": set_name, "app": app, "n": len(sub),
                              **{f"{s}*": int(sc.get(s, 0)) for s in config.SCORES}})

    logger.info("Sample sizes:\n%s", table(size_rows, size_cols))
    logger.info("Language groups by set:\n%s", table(lang_rows, ["set", "app", "n", *groups]))
    logger.info("Analysis allocation (available after pilot -> drawn): %s",
                {a: f"{available[a]} -> {allocation[a]}" for a in config.APPS})

    # ---- Excel workbook --------------------------------------------------------------------
    scrape = read_json(config.SCRAPE_SUMMARY)
    clean_summary = read_json(config.CLEAN_SUMMARY)
    run = scrape["run"]
    created = utc_now()
    sheet_names = {
        "pilot": f"Pilot_{len(sets['pilot'])}", "gold": f"Gold_{len(sets['gold'])}",
        "analysis": f"Analysis_{len(sets['analysis'])}", "contrast": f"Contrast_{len(sets['contrast'])}",
        "lang_check": f"Lang_check_{len(sets['lang_check'])}",
    }
    store_rows = pd.DataFrame([
        {"app": a, "package": m.get("package"), "title": m.get("title"), "developer": m.get("developer"),
         "installs": m.get("installs"), "rating": round(m["rating"], 2) if m.get("rating") else None,
         "ratings": m.get("ratings"), "version": m.get("current_version"), "last updated": m.get("last_updated_utc")}
        for a, m in scrape["app_store_metadata"].items()
    ])

    wb = new_workbook()
    write_info_sheet(wb, "README", [
        ("title", "TTT: Taka, Trust and Trouble- Exploring User-Reported Design Problems in Bangladeshi Mobile Financial Apps "
                  "(review samples)"),
        ("kv", [
            ("Generated (UTC)", created.strftime("%Y-%m-%d %H:%M")),
            ("Source", "Public Google Play reviews; store country bd; Play language settings en and bn"),
            ("Apps", ", ".join(f"{s['label']} ({s['package']})" for s in config.APPS.values())),
            ("Review window (UTC)", f"{run['window_start_utc'][:10]} to {run['window_end_utc'][:10]} "
                                    f"(last {config.WINDOW_MONTHS} months, end date excluded)"),
            ("Scraped (UTC)", f"{run['run_started_utc'][:16]} to {run['run_finished_utc'][:16]}"),
            ("Scraper", f"google-play-scraper {run['google_play_scraper']}, Python {run['python']}"),
            ("Random seed", config.SEED),
            ("Clean dataset", f"{len(clean)} reviews; sha256 {checksum}"),
        ]),
        ("section", "Sheets"),
        ("kv", [
            ("Summary", "Sample sizes, language and star mix per set and app, store metadata, cleaning flow."),
            (sheet_names["pilot"], f"{config.PILOT_PER_APP} random 1-3 star reviews per app for the codebook pilot "
                                   "(codebook development). Not part of any other set."),
            (sheet_names["gold"], f"{config.GOLD_PER_APP} per app, drawn from inside the analysis set, stratified by "
                                  f"language group (proportional, at least {config.GOLD_MIN_PER_LANG_GROUP} per group "
                                  "when available). gold_split: 'tune' for prompt tuning, 'holdout' for the final "
                                  "LLM evaluation. sample_id matches the Analysis sheet."),
            (sheet_names["analysis"], "Random 1-3 star reviews, pilot excluded; includes the gold set (in_gold = TRUE). "
                                      "Coded with LLM assistance."),
            (sheet_names["contrast"], f"{config.CONTRAST_PER_APP} random 4-5 star reviews per app, used only to check "
                                      "that design codes concentrate in negative reviews."),
            (sheet_names["lang_check"], f"{config.LANG_CHECK_PER_APP} random Latin-script 1-3 star reviews per app. "
                                        "Fill manual_lang_group to measure the romanized-tagging error rate "
                                        "(the formulas beside the table update live)."),
        ]),
        ("section", "Columns"),
        ("kv", [
            ("sample_id", "Stable short ID: app prefix (BK, NG, RK, UP) + set letter (P pilot, A analysis, "
                          "C contrast, L language check) + number. Use it in coding sheets and the decision log."),
            ("review_id", "Google Play review ID. Share IDs, not text, in the public replication package."),
            ("score", "Star rating (1-5)."),
            ("review_date_utc", "Date and time of the review (UTC)."),
            ("app_version", "App version the review was written on, when Google Play reports it."),
            ("lang_group", "bangla, english, mixed, or romanized (automatic tag; see Notes)."),
            ("text", "Review text with personal data redacted; otherwise original wording, not translated."),
            ("word_count", "Whitespace-separated words in the review."),
            ("thumbs_up", "How many users marked the review helpful."),
            ("has_reply", "TRUE if the developer replied (reply text is in data/clean, not shown here so "
                          "coding is based on the review text only)."),
        ]),
        ("section", "Notes"),
        ("text", "Cleaning: duplicate review IDs and duplicate texts within an app were removed (earliest kept), "
                 f"and reviews under {config.MIN_WORDS} words or {config.MIN_CHARS} characters were dropped."),
        ("text", "Redaction placeholders: [PHONE] Bangladeshi mobile number, [ID_NUMBER] any run of 8+ digits "
                 "(NID, account, card), [TRX_ID] transaction ID, [EMAIL] e-mail address. Personal names in reviews "
                 "cannot be detected automatically: if you see one while coding, note it in the decision log."),
        ("text", f"Language tag: bangla if at least {config.BANGLA_RATIO_MIN:.0%} of letters are Bengali script; "
                 f"english or romanized if at least {config.LATIN_RATIO_MIN:.0%} are Latin; mixed otherwise. "
                 f"Latin-script reviews are romanized when at least {config.ROMANIZED_MIN_HITS} of their words "
                 f"(and at least {config.ROMANIZED_MIN_SHARE:.0%} of them) are in "
                 "resources/romanized_bangla_words.txt, or when a single listed word makes up at least "
                 f"{config.ROMANIZED_SINGLE_HIT_SHARE:.0%} of a short review."),
        ("text", "Ethics: this workbook contains review text. Keep it in private storage and do not "
                 "commit it to a public repository."),
    ])
    write_info_sheet(wb, "Summary", [
        ("title", "Summary"),
        ("section", "Sample sizes per app"),
        ("table", pd.DataFrame(size_rows, columns=size_cols)),
        ("section", "Language groups per set and app"),
        ("table", pd.DataFrame(lang_rows)),
        ("section", "Star ratings per set and app"),
        ("table", pd.DataFrame(star_rows)),
        ("section", "Cleaning flow (negative = 1-3 stars, positive = 4-5 stars)"),
        ("table", pd.DataFrame(clean_summary["flow"])),
        ("section", "Google Play listing at scrape time"),
        ("table", store_rows),
    ])
    for key, df in sets.items():
        write_frame(wb, sheet_names[key], df, table_name=f"tbl_{key}")
    add_lang_check_tools(wb, sheet_names["lang_check"], sets["lang_check"], [*config.LANG_GROUPS, "other"])
    wb.save(config.EXCEL_PATH)
    logger.info("Wrote %s", config.EXCEL_PATH.relative_to(config.ROOT))

    write_json(config.SAMPLE_MANIFEST, {
        "created_utc": created.isoformat(),
        "seed": config.SEED,
        "input": {"file": str(config.CLEAN_CSV.relative_to(config.ROOT)), "rows": len(clean), "sha256": checksum},
        "settings": {"pilot_per_app": config.PILOT_PER_APP, "analysis_total": config.ANALYSIS_TOTAL,
                     "rebalance_shortfall": config.REBALANCE_SHORTFALL, "gold_per_app": config.GOLD_PER_APP,
                     "gold_min_per_lang_group": config.GOLD_MIN_PER_LANG_GROUP,
                     "gold_holdout_total": config.GOLD_HOLDOUT_TOTAL, "contrast_per_app": config.CONTRAST_PER_APP,
                     "lang_check_per_app": config.LANG_CHECK_PER_APP},
        "analysis_available_after_pilot": available,
        "analysis_allocation": allocation,
        "gold_strata": strata_log,
        "gold_holdout_allocation": holdout_alloc,
        "sizes": size_rows,
        "language_groups": lang_rows,
        "star_ratings": star_rows,
        "checks": {k: bool(v) for k, v in checks.items()},
    })
    logger.info("Wrote %s", config.SAMPLE_MANIFEST.relative_to(config.ROOT))


if __name__ == "__main__":
    main()
