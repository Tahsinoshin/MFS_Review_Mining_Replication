"""Run scrape -> clean/tag -> sample in one go.

Usage (from the project root):
    python scripts/run_pipeline.py              # resumes an interrupted scrape
    python scripts/run_pipeline.py --skip-scrape
"""

import argparse
import sys

import clean_tag
import draw_samples
import scrape_play


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-scrape", action="store_true", help="reuse data/raw/play_reviews_raw.csv")
    args = parser.parse_args()

    if not args.skip_scrape:
        sys.argv = [sys.argv[0]]  # scrape_play parses its own arguments
        scrape_play.main()
    clean_tag.main()
    draw_samples.main()


if __name__ == "__main__":
    main()
