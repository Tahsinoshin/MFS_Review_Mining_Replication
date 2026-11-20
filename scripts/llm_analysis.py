"""Build final labels for the 1,600 analysis reviews and the RQ1/RQ2/contrast tables.

Final labels: the 200 gold reviews use the human final labels; the other 1,400 use the
LLM labels, except the reviews the spot-check settled as wrong, which use the settled answer.
Inputs (text-free): data/labels/llm/llm_labels.csv, data/labels/gold_labels.csv,
data/labels/llm/spotcheck_settled.csv.
Outputs: data/labels/final_labels_1600.csv, logs/analysis_tables.md, logs/analysis_tables.json.
Run from the package root: python scripts/llm_analysis.py
"""
import json
import pandas as pd

LLM = "data/labels/llm/llm_labels.csv"
GOLD = "data/labels/gold_labels.csv"
SETTLED = "data/labels/llm/spotcheck_settled.csv"
APPS = {"BK": "bKash", "NG": "Nagad", "RK": "Rocket", "UP": "Upay"}
SEV = ["blocks", "degrades", "annoyance", "request"]
RARE = 10

llm = pd.read_csv(LLM, dtype=str).fillna("")
llm = llm.rename(columns={"primary_code": "primary", "secondary_code": "secondary"})
llm["source"] = "llm"

# Settled spot-check answers
s = pd.read_csv(SETTLED, dtype=str).fillna("")
fixes = []
for _, r in s.iterrows():
    i = llm.index[llm.sample_id == r.sample_id]
    assert len(i) == 1, r.sample_id
    i = i[0]
    old = llm.loc[i, ["primary", "secondary", "severity"]].tolist()
    if r.final_primary_correct == "N":
        llm.loc[i, "primary"] = r.final_primary_code
        if r.final_primary_code.startswith("N"):
            llm.loc[i, ["secondary", "severity"]] = ["", ""]
    if llm.loc[i, "primary"].startswith("D") and r.final_severity_correct == "N":
        llm.loc[i, "severity"] = r.final_severity
    new = llm.loc[i, ["primary", "secondary", "severity"]].tolist()
    if new != old:
        llm.loc[i, "source"] = "llm_corrected"
        fixes.append({"sample_id": r.sample_id, "old": old, "new": new})

gold = pd.read_csv(GOLD, dtype=str).fillna("")
gold = pd.DataFrame({"sample_id": gold.sample_id, "primary": gold.final_primary,
                     "secondary": gold.final_secondary, "severity": gold.final_severity,
                     "set": "analysis", "source": "gold_human"})
cols = ["sample_id", "primary", "secondary", "severity", "set", "source"]
allr = pd.concat([llm[cols], gold[cols]], ignore_index=True)
allr["app"] = allr.sample_id.str[:2].map(APPS)
allr["design"] = allr.primary.str.startswith("D")
assert allr.sample_id.is_unique
a = allr[allr.set == "analysis"].copy()
c = allr[allr.set == "contrast"].copy()
assert len(a) == 1600 and len(c) == 200
a.to_csv("data/labels/final_labels_1600.csv", index=False, encoding="utf-8")

order = [f"D{i}" for i in range(1, 13)] + [f"N{i}" for i in range(1, 6)]
apps = list(APPS.values())
out = {"fixes": fixes, "sources": a.source.value_counts().to_dict()}
md = ["# Analysis tables (final labels, n = 1,600 negative reviews)", "",
      f"Sources: {out['sources']}. Corrections from the settled spot-check: {len(fixes)}.", ""]

def pct(x, n):
    return f"{x} ({x / n * 100:.1f}%)" if n else "0"

# RQ1/RQ2: code by app
t = pd.crosstab(a.primary, a.app).reindex(index=order, columns=apps, fill_value=0)
t["Total"] = t.sum(axis=1)
n_app = a.app.value_counts().reindex(apps)
out["code_by_app"] = t.to_dict()
md += ["## Primary code by app (count, % of app)", "",
       "| Code | " + " | ".join(apps) + " | Total |", "|---" * (len(apps) + 2) + "|"]
for code, row in t.iterrows():
    md.append(f"| {code} | " + " | ".join(pct(row[x], n_app[x]) for x in apps) + f" | {pct(row.Total, 1600)} |")
md.append(f"| n | " + " | ".join(str(n_app[x]) for x in apps) + " | 1600 |")

# Design share by app
dsh = a.groupby("app").design.agg(["sum", "count"]).reindex(apps)
out["design_share"] = {k: [int(v["sum"]), int(v["count"])] for k, v in dsh.iterrows()}
out["design_share"]["Total"] = [int(a.design.sum()), len(a)]
md += ["", "## Design vs non-design share", "", "| App | Design | Non-design | n |", "|---|---|---|---|"]
for k, (dn, n) in out["design_share"].items():
    md.append(f"| {k} | {pct(dn, n)} | {pct(n - dn, n)} | {n} |")

# Grouped table + chi-square (app x code, rare codes grouped)
tot = a.primary.value_counts()
rare = [x for x in order if tot.get(x, 0) < RARE]
g = a.primary.where(~a.primary.isin(rare), a.primary.str[0].map({"D": "D-other", "N": "N-other"}))
gt = pd.crosstab(g, a.app)[apps]
out["rare_grouped"] = rare
try:
    from scipy.stats import chi2_contingency
    chi, p, dof, exp = chi2_contingency(gt)
    v = (chi / (gt.values.sum() * (min(gt.shape) - 1))) ** 0.5
    chi2, p2, dof2, _ = chi2_contingency(dsh.assign(non=dsh["count"] - dsh["sum"])[["sum", "non"]])
    out["chi2_code_by_app"] = {"chi2": round(chi, 1), "dof": int(dof), "p": float(p), "cramers_v": round(v, 3),
                               "min_expected": round(float(exp.min()), 1)}
    out["chi2_design_by_app"] = {"chi2": round(chi2, 1), "dof": int(dof2), "p": float(p2)}
    md += ["", f"Rare codes grouped (< {RARE} reviews): {', '.join(rare)}.",
           f"App x code (grouped): chi2 = {chi:.1f}, df = {dof}, p = {p:.2g}, Cramer's V = {v:.3f}, min expected = {exp.min():.1f}.",
           f"App x design share: chi2 = {chi2:.1f}, df = {dof2}, p = {p2:.2g}."]
except ImportError:
    md += ["", "scipy not installed: no chi-square."]

# Severity
d = a[a.design]
st = pd.crosstab(d.primary, d.severity).reindex(index=[x for x in order if x.startswith("D")], columns=SEV, fill_value=0)
sa = pd.crosstab(d.app, d.severity).reindex(index=apps, columns=SEV, fill_value=0)
out["severity_by_code"] = st.to_dict(); out["severity_by_app"] = sa.to_dict()
out["severity_missing_on_design"] = int((d.severity == "").sum())
md += ["", "## Severity of design reviews (exploratory)", "", "| Code | " + " | ".join(SEV) + " | n |", "|---" * 6 + "|"]
for code, row in st.iterrows():
    n = row.sum()
    md.append(f"| {code} | " + " | ".join(pct(row[x], n) for x in SEV) + f" | {n} |")
md += ["", "| App | " + " | ".join(SEV) + " | n |", "|---" * 6 + "|"]
for k, row in sa.iterrows():
    n = row.sum()
    md.append(f"| {k} | " + " | ".join(pct(row[x], n) for x in SEV) + f" | {n} |")
md.append(f"\nDesign reviews with no severity: {out['severity_missing_on_design']}.")

# Contrast: negative (1-3 star) vs positive (4-5 star), same apps
cn = c.design.sum()
out["contrast"] = {"negative_design": [int(a.design.sum()), 1600], "positive_design": [int(cn), 200],
                   "positive_by_code": c.primary.value_counts().to_dict()}
md += ["", "## Contrast check", "", f"Design share: negative {pct(int(a.design.sum()), 1600)}, positive (4-5 star) {pct(int(cn), 200)}.",
       f"Positive-review codes: {c.primary.value_counts().to_dict()}."]
try:
    from scipy.stats import fisher_exact
    tab = [[int(a.design.sum()), 1600 - int(a.design.sum())], [int(cn), 200 - int(cn)]]
    orr, pf = fisher_exact(tab)
    out["contrast"]["fisher"] = {"odds_ratio": round(orr, 2), "p": float(pf)}
    md.append(f"Fisher exact: odds ratio = {orr:.2f}, p = {pf:.2g}.")
except ImportError:
    pass

json.dump(out, open("logs/analysis_tables.json", "w"), indent=1, default=int)
open("logs/analysis_tables.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\n".join(md))
