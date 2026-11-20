"""Merge LLM labels and build the coders' check file: random 160 and a separate targeted tab.

Writes data/labels/llm/llm_labels_all.csv and data/labels/llm/spotcheck_160.xlsx (both ignored by git).
The `unsure` flag is kept out of the sheet so it cannot anchor the checkers.
"""
import glob, json, random
from pathlib import Path
import pandas as pd
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.datavalidation import DataValidation

SEED, N = 20261020, 160
RARE = {"D9", "D10", "N3", "D6"}
N_CONTRAST = 10
ROOT = Path(__file__).resolve().parent.parent
LLM = ROOT / "data/labels/llm"
rows = []
for s in ("analysis", "contrast"):
    for p in sorted(glob.glob(str(LLM / f"raw/*promptv2_{s}_*.json"))):
        for r in json.load(open(p, encoding="utf-8")):
            rows.append({**r, "set": s, "batch": Path(p).stem[-2:]})
df = pd.DataFrame(rows)
assert df["sample_id"].is_unique
df.to_csv(LLM / "llm_labels_all.csv", index=False, encoding="utf-8-sig")

a = df[df["set"] == "analysis"]
ids = random.Random(SEED).sample(sorted(a["sample_id"]), N)
COLS = ["sample_id", "app", "review_text", "llm_primary", "llm_secondary", "llm_severity", "llm_evidence"]
CHECKS = ["primary_correct", "correct_primary", "severity_correct", "correct_severity", "note"]


def text_of(name):
    return pd.read_csv(ROOT / "data/samples" / name, encoding="utf-8-sig")[["sample_id", "app", "text"]]


def build(frame, order, src):
    t = frame.set_index("sample_id").loc[order].reset_index().merge(src, on="sample_id", how="left")
    t = t[["sample_id", "app", "text", "primary_code", "secondary_code", "severity", "evidence_span"]]
    t.columns = COLS
    for c in CHECKS:
        t[c] = ""
    return t


src = pd.concat([text_of("analysis.csv"), text_of("contrast.csv")])
sheet = build(a, ids, src)

# Targeted check: codes unseen or nearly unseen in gold, plus a few contrast reviews.
# Reviews already in the random 160 are not repeated; they are scored from that tab.
rng = random.Random(SEED + 1)
rare = sorted(a[a["primary_code"].isin(RARE) & ~a["sample_id"].isin(ids)]["sample_id"])
extra = rng.sample(sorted(df[df["set"] == "contrast"]["sample_id"]), N_CONTRAST)
order = rare + extra
rng.shuffle(order)
targeted = build(df, order, src)

HOWTO = [
    "This file has two sheets to check: 'spotcheck' (160 reviews) and 'targeted'. Check both the same way.",
    "An AI model (LLM) coded these reviews using codebook v1. Your job is to judge whether its labels are right.",
    "",
    "For each row:",
    "1. Read review_text. Keep docs/codebook_v1.md open, and follow it as you did for the gold set.",
    "2. Look at llm_primary. Is it the code you would accept under the codebook? Choose Y or N in primary_correct.",
    "3. If N, write your code (D1-D12 or N1-N5) in correct_primary.",
    "4. Look at llm_severity. Choose Y or N in severity_correct. Leave it blank if llm_primary is an N code.",
    "5. If N, write blocks, degrades, annoyance or request in correct_severity.",
    "6. Use note for anything unclear (one line, optional).",
    "",
    "Rules:",
    "- Judge the review text only, not the star rating or what you know about the app.",
    "- A label that is a reasonable reading under the codebook is Y, even if you might have picked another one on a very close call. Mark N when the codebook points to a different code.",
    "- llm_secondary and llm_evidence are there to help you. You don't need to mark them.",
    "- Work on your own. Don't discuss reviews with the other coder until you have finished.",
    "- Fill in every row of both sheets, don't change the existing columns or the row order, and save the file with your name added.",
]

out = LLM / "spotcheck_160.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as w:
    pd.DataFrame({"How to check these sheets": HOWTO}).to_excel(w, index=False, sheet_name="instructions")
    w.sheets["instructions"].column_dimensions["A"].width = 120
    w.sheets["instructions"]["A1"].font = Font(bold=True)
    for r in w.sheets["instructions"].iter_rows(min_row=2):
        r[0].alignment = Alignment(wrap_text=True, vertical="top")
    for name, t in (("spotcheck", sheet), ("targeted", targeted)):
        t.to_excel(w, index=False, sheet_name=name)
        ws = w.sheets[name]
        ws.freeze_panes = "D2"
        for col, width in zip("ABCDEFGHIJKL", [11, 9, 60, 10, 10, 11, 35, 10, 10, 10, 10, 30]):
            ws.column_dimensions[col].width = width
        for row in ws.iter_rows(min_row=2):
            row[2].alignment = Alignment(wrap_text=True, vertical="top")
            row[6].alignment = Alignment(wrap_text=True, vertical="top")
        for c in ws[1]:
            c.font = Font(bold=True)
        yn = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
        ws.add_data_validation(yn)
        last = len(t) + 1
        yn.add(f"H2:H{last}")
        yn.add(f"J2:J{last}")
print("spotcheck", len(sheet), "targeted", len(targeted), "rare", len(rare), "contrast", len(extra))
print("missing text", int(sheet["review_text"].isna().sum() + targeted["review_text"].isna().sum()))
print("overlap", len(set(sheet["sample_id"]) & set(targeted["sample_id"])))
print("rare in 160:", sheet["llm_primary"].isin(RARE).sum())
