"""Central configuration for the review-mining pipeline.

Every methodological constant lives here so the scrape, cleaning and sampling
steps stay consistent and the choices are easy to report in the paper.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
STREAM_DIR = RAW_DIR / "streams"          # per (app, lang, star) checkpoints
CLEAN_DIR = DATA_DIR / "clean"
SAMPLE_DIR = DATA_DIR / "samples"
LOG_DIR = ROOT / "logs"                   # counts only, no review text: safe to publish
RESOURCE_DIR = ROOT / "resources"

RAW_CSV = RAW_DIR / "play_reviews_raw.csv"
CLEAN_CSV = CLEAN_DIR / "play_reviews_clean.csv"
EXCEL_PATH = SAMPLE_DIR / "mfs_review_samples.xlsx"
ROMANIZED_WORDS = RESOURCE_DIR / "romanized_bangla_words.txt"

SCRAPE_SUMMARY = LOG_DIR / "scrape_summary.json"
CLEAN_SUMMARY = LOG_DIR / "clean_summary.json"
SAMPLE_MANIFEST = LOG_DIR / "sample_manifest.json"

# --------------------------------------------------------------------------
# Apps (package IDs verified on Google Play, Bangladesh store, 2026-10-20)
# --------------------------------------------------------------------------
APPS = {
    "bkash": {"package": "com.bKash.customerapp", "label": "bKash", "prefix": "BK"},
    "nagad": {"package": "com.konasl.nagad", "label": "Nagad", "prefix": "NG"},
    "rocket": {"package": "com.dbbl.mbs.apps.main", "label": "Rocket", "prefix": "RK"},
    "upay": {"package": "bd.com.upay.customer", "label": "Upay", "prefix": "UP"},
}

# --------------------------------------------------------------------------
# Scraping
# --------------------------------------------------------------------------
COUNTRY = "bd"
LANGS = ["en", "bn"]              # both runs are kept and deduplicated by review ID
SCORES = [1, 2, 3, 4, 5]          # 1-3 = main set, 4-5 = contrast pool
NEGATIVE_SCORES = (1, 2, 3)
POSITIVE_SCORES = (4, 5)

WINDOW_MONTHS = 24                # same window for every app (comparability across apps)
WINDOW_END = None                 # None = scrape day (UTC). Set "YYYY-MM-DD" to reproduce a run.

PAGE_SIZE = 200                   # reviews requested per call
REQUEST_PAUSE_SEC = 1.5           # polite pause between calls
MAX_RETRIES = 5                   # per page, with exponential backoff
BACKOFF_BASE_SEC = 10

# --------------------------------------------------------------------------
# Cleaning and language tagging
# --------------------------------------------------------------------------
MIN_WORDS = 4                     # drop reviews under 4 words ...
MIN_CHARS = 15                    # ... or under 15 characters
BANGLA_RATIO_MIN = 0.80           # share of Bengali letters at or above which a review is "bangla"
LATIN_RATIO_MIN = 0.80            # share of Latin letters at or above which a review is english/romanized
ROMANIZED_MIN_HITS = 2            # romanized = at least 2 romanized-Bangla words making up ...
ROMANIZED_MIN_SHARE = 0.10        # ... at least 10% of the Latin tokens,
ROMANIZED_SINGLE_HIT_SHARE = 0.25 # or a single such word in a short review (>= 25% of tokens)
LANG_GROUPS = ["bangla", "english", "mixed", "romanized"]

# --------------------------------------------------------------------------
# Sampling
# --------------------------------------------------------------------------
SEED = 20261020                   # fixed seed; never change after samples are shared
PILOT_PER_APP = 15                # pilot 60, kept out of gold and analysis
ANALYSIS_TOTAL = 1600             # nominal 400 per app
REBALANCE_SHORTFALL = True        # an app short of 400 gives all it has; others share the rest
GOLD_PER_APP = 50                 # gold 200, drawn from inside the analysis set
GOLD_MIN_PER_LANG_GROUP = 5       # proportional allocation with this floor per language group
GOLD_HOLDOUT_TOTAL = 50           # held out for the final LLM evaluation
CONTRAST_PER_APP = 50             # contrast 200 from 4-5 stars
LANG_CHECK_PER_APP = 25           # 100 Latin-script reviews to measure romanized tagging error
