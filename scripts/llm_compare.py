"""Compare LLM output with final gold labels for ONE split, tune by default.

Usage: python scripts/llm_compare.py <tag> [tune|holdout] [--detail]
<tag> matches raw files, e.g. promptv1_tune. --detail prints disagreements with
rule notes; it is refused for holdout so holdout notes are never read while tuning.
"""
import csv, glob, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
args = [a for a in sys.argv[1:] if not a.startswith("--")]
tag, split = args[0], (args[1] if len(args) > 1 else "tune")
detail = "--detail" in sys.argv
if detail and split != "tune":
    sys.exit("--detail is for tune rows only")

with open(ROOT / "data/labels/gold_labels.csv", encoding="utf-8-sig", newline="") as f:
    gold = {r["sample_id"]: r for r in csv.DictReader(f) if (r["gold_split"] == "tune") == (split == "tune")}
llm = {}
for p in sorted(glob.glob(str(ROOT / f"data/labels/llm/raw/*{tag}*.json"))):
    for r in json.load(open(p, encoding="utf-8")):
        llm[r["sample_id"]] = r
ids = [i for i in gold if i in llm]
a = [llm[i]["primary_code"] for i in ids]
b = [gold[i]["final_primary"] for i in ids]
n = len(ids)
po = sum(x == y for x, y in zip(a, b)) / n
ca, cb = Counter(a), Counter(b)
pe = sum(ca[c] * cb[c] for c in set(a) | set(b)) / n / n
print(f"n={n} agree={sum(x == y for x, y in zip(a, b))} pct={po:.3f} kappa={(po - pe) / (1 - pe):.3f}")
print("code  gold llm  precision recall")
for c in sorted(set(a) | set(b), key=lambda s: (s[0], int(s[1:]))):
    tp = sum(x == y == c for x, y in zip(a, b))
    print(f"{c:4} {cb[c]:4} {ca[c]:3}  {tp / ca[c] if ca[c] else 0:.2f}  {tp / cb[c] if cb[c] else 0:.2f}")
if detail:
    print("confusions (gold->llm):", Counter((y, x) for x, y in zip(a, b) if x != y).most_common())
    for i in ids:
        if llm[i]["primary_code"] != gold[i]["final_primary"]:
            g = gold[i]
            print(i, "gold", g["final_primary"], "llm", llm[i]["primary_code"], "unsure", llm[i]["unsure"], "| B", g["coder_b"], "C", g["coder_c"], "| note:", g["rule_note"])
