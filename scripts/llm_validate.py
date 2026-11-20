"""Check raw LLM outputs against their batch files (IDs, order, coding rules, spans)."""
import glob, json, re, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODES = {f"D{i}" for i in range(1, 13)} | {f"N{i}" for i in range(1, 6)}
SEV = {"blocks", "degrades", "annoyance", "request"}
norm = lambda s: " ".join(unicodedata.normalize("NFC", s).split())
total = 0
for p in sorted(glob.glob(str(ROOT / "data/labels/llm/raw/*promptv2_[ac]*.json"))):
    name = re.search(r"(analysis|contrast)_\d+", p).group(0)
    src = json.load(open(ROOT / f"data/labels/llm/batches/{name}.json", encoding="utf-8"))
    out = json.load(open(p, encoding="utf-8"))
    text = {r["sample_id"]: r["text"] for r in src}
    bad, spans = [], 0
    for r in out:
        c, s, v = r["primary_code"], r["secondary_code"], r["severity"]
        if c not in CODES or (c[0] == "N" and (s or v)) or (c[0] == "D" and v not in SEV) or (s and (s not in CODES or s[0] != "D" or s == c)):
            bad.append(r["sample_id"])
        spans += sum(1 for x in (r["evidence_span"] or "").split(" | ") if x.strip() and norm(x) not in norm(text[r["sample_id"]]))
    ok = [r["sample_id"] for r in out] == list(text)
    total += len(out)
    if not ok or bad or spans:
        print(name, "ids ok", ok, "rule errors", bad, "spans off", spans)
print("reviews checked", total)
