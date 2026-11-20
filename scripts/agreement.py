"""Inter-coder agreement (Cohen's kappa) for a text-free labels file.

Reads a CSV with one row per review and one column per coder, and reports
observed agreement, chance agreement, Cohen's kappa with its Landis and Koch
band, each coder's code counts and every disagreement. Rows where either coder
left the label blank are skipped and counted.

Usage (from the project root):
    python scripts/agreement.py data/labels/pilot_labels.csv
    python scripts/agreement.py data/labels/gold_labels.csv --exclude BK-A001 BK-A013
    python scripts/agreement.py FILE --a sev_b --b sev_c --ordinal blocks degrades annoyance
    python scripts/agreement.py FILE --json logs/pilot_agreement.json

--ordinal gives linearly weighted kappa over the listed order (for severity);
labels outside that list are skipped.
"""

import argparse
from collections import Counter
from pathlib import Path

import pandas as pd

from common import CSV_ENCODING, table, utc_now, write_json

# Upper bound of each band (Landis and Koch 1977); above 0.80 is "almost perfect", below 0 "poor".
LANDIS_KOCH = [(0.20, "slight"), (0.40, "fair"), (0.60, "moderate"), (0.80, "substantial")]


def cohen_kappa(a: list[str], b: list[str], order: list[str] | None = None) -> dict:
    """Cohen's kappa for two equal-length label lists.

    With `order`, labels are treated as ordinal and agreement is weighted
    linearly (1 for the same label, 0 for the two ends of the scale).
    """
    if len(a) != len(b) or not a:
        raise ValueError("need two non-empty label lists of equal length")
    labels = order or sorted(set(a) | set(b))
    pos = {lab: i for i, lab in enumerate(labels)}
    k, n = len(labels), len(a)

    def weight(x, y):
        if order is None or k == 1:
            return 1.0 if x == y else 0.0
        return 1.0 - abs(pos[x] - pos[y]) / (k - 1)

    observed = sum(weight(x, y) for x, y in zip(a, b)) / n
    pa, pb = Counter(a), Counter(b)
    chance = sum(pa[x] / n * pb[y] / n * weight(x, y) for x in labels for y in labels)
    kappa = float("nan") if chance == 1 else (observed - chance) / (1 - chance)
    return {"n": n, "observed": observed, "chance": chance, "kappa": kappa}


def landis_koch(kappa: float) -> str:
    if kappa != kappa:  # NaN
        return "undefined"
    if kappa < 0:
        return "poor"
    for upper, band in LANDIS_KOCH:
        if kappa <= upper:
            return band
    return "almost perfect"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("labels", help="CSV with one row per review")
    parser.add_argument("--a", default="coder_b", help="first coder's column (default: coder_b)")
    parser.add_argument("--b", default="coder_c", help="second coder's column (default: coder_c)")
    parser.add_argument("--id", default="sample_id", help="row identifier column (default: sample_id)")
    parser.add_argument("--exclude", nargs="*", default=[], help="row IDs to leave out of the calculation")
    parser.add_argument("--ordinal", nargs="+", metavar="LABEL", help="ordered labels for weighted kappa")
    parser.add_argument("--json", help="also save the result to this JSON file")
    args = parser.parse_args()

    df = pd.read_csv(args.labels, dtype=str, keep_default_na=False, encoding=CSV_ENCODING)
    for col in (args.id, args.a, args.b):
        if col not in df.columns:
            raise SystemExit(f"Column '{col}' not found. Columns: {', '.join(df.columns)}")
    df[args.a] = df[args.a].str.strip()
    df[args.b] = df[args.b].str.strip()

    unknown = sorted(set(args.exclude) - set(df[args.id]))
    if unknown:
        raise SystemExit(f"--exclude IDs not in the file: {', '.join(unknown)}")
    excluded = df[args.id].isin(args.exclude)
    blank = (df[args.a] == "") | (df[args.b] == "")
    off_scale = pd.Series(False, index=df.index)
    if args.ordinal:
        off_scale = ~df[args.a].isin(args.ordinal) | ~df[args.b].isin(args.ordinal)
    used = df[~excluded & ~blank & ~off_scale]

    result = cohen_kappa(used[args.a].tolist(), used[args.b].tolist(), args.ordinal)
    band = landis_koch(result["kappa"])
    agree = int((used[args.a] == used[args.b]).sum())

    print(f"File: {args.labels}")
    print(f"Columns: {args.a} vs {args.b}" + (f" (linearly weighted over {' < '.join(args.ordinal)})"
                                             if args.ordinal else ""))
    print(f"Rows: {len(df)} total, {int(excluded.sum())} excluded, {int((blank & ~excluded).sum())} blank, "
          f"{int((off_scale & ~blank & ~excluded).sum())} off-scale, {result['n']} used")
    print(f"Same label: {agree} of {result['n']} ({agree / result['n']:.1%})")
    print(f"Observed agreement: {result['observed']:.3f}   Chance agreement: {result['chance']:.3f}")
    print(f"Cohen's kappa: {result['kappa']:.3f} ({band}, Landis and Koch 1977)")

    labels = args.ordinal or sorted(set(used[args.a]) | set(used[args.b]))
    ca, cb = Counter(used[args.a]), Counter(used[args.b])
    print("\nLabel counts per coder:\n" + table(
        [{"label": lab, args.a: ca[lab], args.b: cb[lab]} for lab in labels], ["label", args.a, args.b]))

    disagreements = used[used[args.a] != used[args.b]]
    print(f"\nDisagreements ({len(disagreements)}):")
    for _, row in disagreements.iterrows():
        print(f"  {row[args.id]}: {row[args.a]} vs {row[args.b]}")

    if args.json:
        write_json(Path(args.json), {
            "computed_utc": utc_now().isoformat(),
            "file": args.labels, "columns": [args.a, args.b], "excluded": sorted(args.exclude),
            "ordinal_order": args.ordinal, "rows_total": len(df), "rows_used": result["n"],
            "same_label": agree, "observed_agreement": round(result["observed"], 4),
            "chance_agreement": round(result["chance"], 4), "kappa": round(result["kappa"], 4),
            "landis_koch_band": band,
            "label_counts": {args.a: dict(ca), args.b: dict(cb)},
            "disagreements": [{"id": r[args.id], args.a: r[args.a], args.b: r[args.b]}
                              for _, r in disagreements.iterrows()],
        })
        print(f"\nSaved {args.json}")


if __name__ == "__main__":
    main()
