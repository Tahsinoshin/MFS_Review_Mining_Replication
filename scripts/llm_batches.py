"""Build blind batch files for LLM-assisted coding.

Each batch holds only sample_id and text: no labels, split, in_gold, score or
app columns. Order is shuffled with the study seed, batch size 50 everywhere.
Output goes to data/labels/llm/batches/ (ignored by git).
"""
import csv
import json
import random
from pathlib import Path

SEED = 20261020
SIZE = 50
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "labels" / "llm" / "batches"


def read(name):
    with open(ROOT / "data" / "samples" / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(prefix, rows):
    rows = list(rows)
    random.Random(SEED).shuffle(rows)
    n = 0
    for i in range(0, len(rows), SIZE):
        n += 1
        part = [{"sample_id": r["sample_id"], "text": r["text"]} for r in rows[i:i + SIZE]]
        path = OUT / f"{prefix}_{n:02d}.json"
        path.write_text(json.dumps(part, ensure_ascii=False, indent=0), encoding="utf-8")
    print(prefix, len(rows), "reviews", n, "batches")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gold = read("gold.csv")
    gold_ids = {r["sample_id"] for r in gold}
    write("tune", [r for r in gold if r["gold_split"] == "tune"])
    write("holdout", [r for r in gold if r["gold_split"] != "tune"])
    write("analysis", [r for r in read("analysis.csv") if r["sample_id"] not in gold_ids])
    write("contrast", read("contrast.csv"))


if __name__ == "__main__":
    main()
