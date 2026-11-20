"""Build the text-free LLM and spot-check label files from the private working files.

This script documents how the public files in data/labels/llm/ were made. It needs
the private files (LLM outputs with evidence spans, spot-check workbooks with review
text), which are not part of this package, so readers cannot run it.

Usage (from the private project root):
    python scripts/make_public_labels.py [--out PATH_TO_PACKAGE]

Inputs (private):
    data/labels/llm/llm_labels_all.csv                    LLM labels, 1,400 analysis + 200 contrast
    data/labels/llm/raw/*_promptv1_tune_*.json            prompt v1 on the 150 tune reviews
    data/labels/llm/raw/*_promptv2_tune_*.json            prompt v2 on the 150 tune reviews
    data/labels/llm/raw/*_promptv2_holdout_run[12].json   frozen prompt v2, hold-out, two runs
    data/labels/llm/spotcheck_returned/*.xlsx             each checker's Y/N answers
    data/labels/llm/spotcheck_settle_final.xlsx           answers settled jointly

Outputs (public, no review text, no evidence spans, no free-text notes):
    data/labels/llm/llm_labels.csv        primary, secondary, severity, unsure, set, batch
    data/labels/llm/llm_gold_runs.csv     the four LLM runs on the gold reviews
    data/labels/llm/spotcheck_checks.csv  LLM codes and each checker's Y/N, 160 random + 43 targeted
    data/labels/llm/spotcheck_settled.csv the 21 rows settled jointly and their final answers
"""
import argparse
import glob
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
YN = {"", "Y", "N"}


def read_csv(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(ROOT), help="private project root (default: this folder)")
    ap.add_argument("--out", default=str(ROOT), help="package root to write into (default: this folder)")
    args = ap.parse_args()
    src, out = Path(args.src) / "data/labels/llm", Path(args.out) / "data/labels/llm"
    out.mkdir(parents=True, exist_ok=True)

    # 1. LLM labels for the 1,400 analysis and 200 contrast reviews, without evidence spans
    llm = read_csv(src / "llm_labels_all.csv")
    cols = ["sample_id", "primary_code", "secondary_code", "severity", "unsure", "set", "batch"]
    llm[cols].to_csv(out / "llm_labels.csv", index=False, encoding="utf-8", lineterminator="\n")

    # 2. LLM runs on the gold reviews (tuning and hold-out), without evidence spans
    runs = [("tune_v1", "v1", "*_promptv1_tune_*.json"), ("tune_v2", "v2", "*_promptv2_tune_*.json"),
            ("holdout_run1", "v2", "*_promptv2_holdout_run1.json"), ("holdout_run2", "v2", "*_promptv2_holdout_run2.json")]
    rows = []
    for run, prompt, pattern in runs:
        for p in sorted(glob.glob(str(src / "raw" / pattern))):
            for r in json.load(open(p, encoding="utf-8")):
                rows.append({"run": run, "prompt": prompt, "sample_id": r["sample_id"],
                             "primary_code": r["primary_code"], "secondary_code": r["secondary_code"] or "",
                             "severity": r["severity"] or "", "unsure": str(bool(r["unsure"]))})
    pd.DataFrame(rows).to_csv(out / "llm_gold_runs.csv", index=False, encoding="utf-8", lineterminator="\n")

    # 3. Spot-check: each checker's independent answers. The returned files were misnamed:
    #    spot-check_author_a.xlsx is coder B and spot-check_author_b.xlsx is coder C.
    b_file = src / "spotcheck_returned/spot-check_author_a.xlsx"
    c_file = src / "spotcheck_returned/spot-check_author_b.xlsx"
    checks = []
    for tab in ("spotcheck", "targeted"):
        b = pd.read_excel(b_file, sheet_name=tab, dtype=str, engine="openpyxl").fillna("")
        c = pd.read_excel(c_file, sheet_name=tab, dtype=str, engine="openpyxl").fillna("")
        assert list(b.sample_id) == list(c.sample_id)
        t = pd.DataFrame({
            "tab": tab, "sample_id": b.sample_id,
            "llm_primary": b.llm_primary, "llm_secondary": b.llm_secondary, "llm_severity": b.llm_severity,
            "coder_b_primary_ok": b.primary_correct_author_a.str.strip(),
            "coder_b_severity_ok": b.severity_correct_author_a.str.strip(),
            "coder_c_primary_ok": c.primary_correct_author_b.str.strip(),
            "coder_c_severity_ok": c.severity_correct_author_b.str.strip(),
        })
        for col in t.columns[5:]:
            assert set(t[col]) <= YN, (tab, col, set(t[col]))
        checks.append(t)
    checks = pd.concat(checks, ignore_index=True)
    ref = llm.set_index("sample_id")
    assert (ref.loc[checks.sample_id, "primary_code"].values == checks.llm_primary.values).all()
    checks.to_csv(out / "spotcheck_checks.csv", index=False, encoding="utf-8", lineterminator="\n")

    # 4. Rows settled jointly, in the order of the settle sheet (no review text, evidence or notes)
    s = pd.read_excel(src / "spotcheck_settle_final.xlsx", sheet_name="settle", dtype=str).fillna("")
    keep = ["sample_id", "sheet", "to_settle", "final_primary_correct", "final_primary_code",
            "final_severity_correct", "final_severity"]
    s[keep].to_csv(out / "spotcheck_settled.csv", index=False, encoding="utf-8", lineterminator="\n")

    print(f"llm_labels {len(llm)}, llm_gold_runs {len(rows)}, spotcheck_checks {len(checks)}, spotcheck_settled {len(s)}")


if __name__ == "__main__":
    main()
