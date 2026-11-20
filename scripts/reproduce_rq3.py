"""Recompute every RQ3 number (LLM-assisted coding) from the public, text-free files.

Checks each number against the value reported in the paper or saved in logs/, prints
PASS or FAIL for each, and saves everything to logs/rq3_reproduction.json.

Run from the package root:
    python scripts/reproduce_rq3.py

Inputs:
    data/labels/gold_labels.csv            human labels and consensus for the 200 gold reviews
    data/labels/llm/llm_gold_runs.csv      LLM runs on the gold reviews (tune v1, tune v2, hold-out x2)
    data/labels/llm/holdout_compare.csv    hold-out: consensus, both LLM runs, both coders
    data/labels/llm/llm_labels.csv         LLM labels for the 1,400 analysis and 200 contrast reviews
    data/labels/llm/spotcheck_checks.csv   each checker's Y/N on the LLM labels (160 random + 43 targeted)
    data/labels/llm/spotcheck_settled.csv  answers settled jointly where the checkers differed
"""
import json
import math
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agreement import cohen_kappa  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "data/labels"
LOGS = ROOT / "logs"
SEED = 20261020
SEV3 = ["blocks", "degrades", "annoyance"]
results, checks = {}, []


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def check(name, got, expected):
    ok = got == expected
    checks.append({"check": name, "got": got, "expected": expected, "pass": ok})
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {got}" + ("" if ok else f" (expected {expected})"))


def kappa(a, b, order=None):
    return cohen_kappa(list(a), list(b), order)["kappa"]


def wilson(k, n, z=1.96):
    p = k / n
    centre, half = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round(100 * (centre - half) / (1 + z * z / n), 1), round(100 * (centre + half) / (1 + z * z / n), 1)]


gold = read(LAB / "gold_labels.csv").set_index("sample_id")
runs = read(LAB / "llm/llm_gold_runs.csv")
run = {name: g.set_index("sample_id") for name, g in runs.groupby("run")}

# ---- Prompt tuning (150 tune reviews; not evidence of accuracy, the prompt was adjusted on them)
print("\nPrompt tuning, LLM vs consensus on the 150 tune reviews")
tune_ids = [i for i in gold.index if gold.loc[i, "gold_split"] == "tune"]
for name, paper in (("tune_v1", 0.839), ("tune_v2", 0.854)):
    r = run[name].loc[tune_ids, "primary_code"]
    k = kappa(r, gold.loc[tune_ids, "final_primary"])
    same = int((r.values == gold.loc[tune_ids, "final_primary"].values).sum())
    results[name] = {"n": len(tune_ids), "same": same, "kappa": round(k, 4)}
    check(f"{name} kappa", round(k, 3), paper)

# ---- Hold-out (50 reviews never seen while tuning)
print("\nHold-out, 50 reviews, frozen prompt v2")
h = read(LAB / "llm/holdout_compare.csv")
ids = list(h.sample_id)
r1, r2 = run["holdout_run1"].loc[ids], run["holdout_run2"].loc[ids]
check("holdout_compare.csv llm1/llm2 match llm_gold_runs.csv",
      bool((h.llm1.values == r1.primary_code.values).all() and (h.llm2.values == r2.primary_code.values).all()), True)
check("holdout_compare.csv final/coders match gold_labels.csv",
      bool((h.final.values == gold.loc[ids, "final_primary"].values).all()
           and (h.coder_b.values == gold.loc[ids, "coder_b"].values).all()
           and (h.coder_c.values == gold.loc[ids, "coder_c"].values).all()), True)

pairs = {}
for a, b in (("llm1", "final"), ("llm2", "final"), ("coder_b", "coder_c"), ("coder_b", "final"),
             ("coder_c", "final"), ("llm1", "coder_b"), ("llm1", "coder_c")):
    pairs[f"{a}_vs_{b}"] = {"same": int((h[a] == h[b]).sum()), "kappa": round(kappa(h[a], h[b]), 4)}
results["holdout_pairs"] = pairs
log = json.load(open(LOGS / "llm_holdout_agreement.json", encoding="utf-8"))
check("LLM vs consensus, same", pairs["llm1_vs_final"]["same"], log["same_label"])
check("LLM vs consensus, kappa (log)", pairs["llm1_vs_final"]["kappa"], log["kappa"])
check("LLM vs consensus, kappa (paper)", round(pairs["llm1_vs_final"]["kappa"], 3), 0.882)
check("LLM run 2 vs consensus, kappa", round(pairs["llm2_vs_final"]["kappa"], 3), 0.882)
check("coder B vs coder C on the same 50, kappa", round(pairs["coder_b_vs_coder_c"]["kappa"], 3), 0.671)
check("coder B vs consensus, kappa", round(pairs["coder_b_vs_final"]["kappa"], 3), 0.929)
check("coder C vs consensus, kappa", round(pairs["coder_c_vs_final"]["kappa"], 3), 0.696)
check("LLM vs coder B, kappa", round(pairs["llm1_vs_coder_b"]["kappa"], 3), 0.929)
check("LLM vs coder C, kappa", round(pairs["llm1_vs_coder_c"]["kappa"], 3), 0.742)

misses = h[h.llm1 != h.final]
design_match = int((h.llm1.str[0] == h.final.str[0]).sum())
miss_matches_a_coder = int(((misses.llm1 == misses.coder_b) | (misses.llm1 == misses.coder_c)).sum())
results["holdout_misses"] = misses[["sample_id", "final", "llm1", "llm2", "coder_b", "coder_c"]].to_dict("records")
results["holdout_design_vs_nondesign_same"] = design_match
check("design vs non-design, same of 50", design_match, 50)
check("misses whose LLM code matches one coder", f"{miss_matches_a_coder} of {len(misses)}", "5 of 5")

same_primary = int((r1.primary_code.values == r2.primary_code.values).sum())
same_sev = int((r1.severity.values == r2.severity.values).sum())
results["run_to_run"] = {"primary_same": same_primary, "severity_same": same_sev, "n": len(ids)}
check("run-to-run, same primary", same_primary, 50)
check("run-to-run, same severity", same_sev, 48)

m = h[h.final_sev.isin(SEV3) & h.llm1_sev.isin(SEV3)]
wk = kappa(m.final_sev, m.llm1_sev, SEV3)
results["holdout_severity"] = {"n": len(m), "same": int((m.final_sev == m.llm1_sev).sum()), "weighted_kappa": round(wk, 4)}
check("hold-out severity, same", f"{results['holdout_severity']['same']}/{len(m)}", "31/34")
check("hold-out severity, weighted kappa", round(wk, 3), 0.759)

rng, boot = random.Random(SEED), []
for _ in range(10_000):
    s = [rng.randrange(len(h)) for _ in range(len(h))]
    k = kappa(h.final.iloc[s], h.llm1.iloc[s])
    if k == k:  # skip the (practically impossible) undefined resample
        boot.append(k)
boot.sort()
ci = [round(boot[int(0.025 * len(boot)) - 1], 2), round(boot[int(0.975 * len(boot)) - 1], 2)]
results["holdout_kappa_bootstrap_ci95"] = {"resamples": len(boot), "seed": SEED, "ci": ci}
check("hold-out kappa, bootstrap 95% CI", ci, [0.77, 0.98])

# ---- Spot-check of the LLM labels on the 1,400 non-gold analysis reviews
print("\nSpot-check, 160 random + 43 targeted reviews")
llm = read(LAB / "llm/llm_labels.csv").set_index("sample_id")
chk = read(LAB / "llm/spotcheck_checks.csv")
settled = read(LAB / "llm/spotcheck_settled.csv").set_index("sample_id")
log_ind = json.load(open(LOGS / "llm_spotcheck_independent.json", encoding="utf-8"))
log_fin = json.load(open(LOGS / "llm_spotcheck_final.json", encoding="utf-8"))
results["spotcheck_independent"], results["spotcheck_final"] = {}, {}

for tab in ("spotcheck", "targeted"):
    t = chk[chk.tab == tab]
    d = t.llm_primary.str.startswith("D")  # severity is judged only where the LLM gave a D code
    ind = {
        "n": len(t),
        "primary_N_coder_b": int((t.coder_b_primary_ok == "N").sum()),
        "primary_N_coder_c": int((t.coder_c_primary_ok == "N").sum()),
        "primary_N_both": int(((t.coder_b_primary_ok == "N") & (t.coder_c_primary_ok == "N")).sum()),
        "primary_N_either": int(((t.coder_b_primary_ok == "N") | (t.coder_c_primary_ok == "N")).sum()),
        "primary_same_answer": int((t.coder_b_primary_ok == t.coder_c_primary_ok).sum()),
        "severity_answered_coder_b": int((d & (t.coder_b_severity_ok != "")).sum()),
        "severity_answered_coder_c": int((d & (t.coder_c_severity_ok != "")).sum()),
        "severity_N_coder_b": int((d & (t.coder_b_severity_ok == "N")).sum()),
        "severity_N_coder_c": int((d & (t.coder_c_severity_ok == "N")).sum()),
    }
    results["spotcheck_independent"][tab] = ind
    check(f"{tab}: independent checks match log", ind, log_ind[tab])

    errors, changes, sev_rows, sev_errors, by_code = [], {}, 0, [], {}
    for _, row in t.iterrows():
        i, llm_p = row.sample_id, row.llm_primary
        final_p = llm_p
        if i in settled.index and settled.loc[i, "final_primary_correct"] == "N":
            final_p = settled.loc[i, "final_primary_code"]
        wrong = final_p != llm_p
        if wrong:
            errors.append(i)
            changes[f"{llm_p}->{final_p}"] = changes.get(f"{llm_p}->{final_p}", 0) + 1
        by_code.setdefault(llm_p, [0, 0])
        by_code[llm_p][0] += 1
        by_code[llm_p][1] += wrong
        if llm_p.startswith("D") and not wrong:
            sev_rows += 1
            if i in settled.index and settled.loc[i, "final_severity_correct"] == "N":
                sev_errors.append(i)
    n = len(t)
    fin = {
        "n": n, "primary_errors": len(errors), "primary_error_pct": round(100 * len(errors) / n, 1),
        "primary_error_ci95_wilson": wilson(len(errors), n), "primary_error_ids": errors, "changes": changes,
        "severity_rows": sev_rows, "severity_errors": len(sev_errors), "severity_error_ids": sev_errors,
        "design_primary_llm": int(d.sum()),
        "design_primary_final": int(d.sum()) - sum(v for k, v in changes.items() if k[0] == "D" and k.split("->")[1][0] == "N")
                                + sum(v for k, v in changes.items() if k[0] == "N" and k.split("->")[1][0] == "D"),
        "errors_by_llm_code": {k: v for k, v in sorted(by_code.items()) if v[1]},
    }
    results["spotcheck_final"][tab] = fin
    check(f"{tab}: settled error rates match log", fin, log_fin[tab])
    if tab == "spotcheck":
        flagged = llm.loc[list(t.sample_id), "unsure"] == "True"
        err = t.sample_id.isin(errors).values
        split = {"flagged": int(flagged.sum()), "errors_flagged": int((flagged.values & err).sum()),
                 "not_flagged": int((~flagged).sum()), "errors_not_flagged": int((~flagged.values & err).sum())}
        results["unsure_flag_split"] = split
        check("unsure flag: errors among flagged", f"{split['errors_flagged']}/{split['flagged']}", "8/47")
        check("unsure flag: errors among not flagged", f"{split['errors_not_flagged']}/{split['not_flagged']}", "1/113")

check("spot-check random 160: error %", results["spotcheck_final"]["spotcheck"]["primary_error_pct"], 5.6)
check("spot-check random 160: Wilson 95% CI", results["spotcheck_final"]["spotcheck"]["primary_error_ci95_wilson"], [3.0, 10.3])
check("spot-check targeted 43: error %", results["spotcheck_final"]["targeted"]["primary_error_pct"], 2.3)

out = LOGS / "rq3_reproduction.json"
json.dump({"results": results, "checks": checks}, open(out, "w", encoding="utf-8"), indent=1, default=str)
failed = [c["check"] for c in checks if not c["pass"]]
print(f"\n{len(checks) - len(failed)} of {len(checks)} checks passed. Saved {out.relative_to(ROOT)}")
sys.exit(1 if failed else 0)
