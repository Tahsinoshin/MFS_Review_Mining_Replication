# Pilot report: codebook v0 → v1

Results of the pilot coding round. This is the record behind [codebook v1](codebook_v1.md); the codebook itself holds only the coding rules.

| | |
|---|---|
| Set | Pilot_60: 15 random 1–3 star reviews per app (seed 20261020), excluded from the gold and analysis sets |
| Coders | Two coders (B and C), coding independently with codebook v0 |
| Coded file | `pilot-final.xlsx` (contains review text, so it is kept out of the public repository) |
| Finalized | 2026-11-01 |
| Codes | Design (D1–D12) and non-design (N1–N5) codes |

## Agreement on the primary code

Computed on the two coders' independent labels, before any discussion.

| Measure | Value |
|---|---|
| Reviews | 60 |
| Same primary code | 54 (90.0%) |
| Agreement expected by chance | 19.8% |
| **Cohen's kappa** | **0.875** ("almost perfect", Landis and Koch 1977) |

**To reproduce:** the labels are in `data/labels/pilot_labels.csv`, which holds review IDs and labels only, no review text. Run:

```
python scripts/agreement.py data/labels/pilot_labels.csv
```

The output is also saved in `logs/pilot_agreement.json`. The columns `coder_b` and `coder_c` hold each coder's independent label. In the working sheet, coder B's label for UP-P05 was later edited to D1 while the D1 vs D12 rule was being recorded; the label file keeps the independent label (D12).

The pilot recorded one primary code per review in the first pass. Secondary code, severity and evidence span were added in the final pass, so no agreement is reported for them.

## Disagreements and how they were resolved

| Review | Coder B | Coder C | Final | Rule added to v1 |
|---|---|---|---|---|
| BK-P06 | D8 | D7 | D7 | D7 vs D8 |
| NG-P06 | D8 | D7 | D7 | D7 vs D8 |
| BK-P10 | D4 | D1 | D1 | D1 vs D4 |
| BK-P12 | D6 | D2 | D6 → **D2** (see below) | D2 vs D6 |
| RK-P02 | D11 | N5 | D11 | D11 vs N5 |
| UP-P07 | D5 | D2 | D5 | D2 vs D5 |

UP-P05 (both coders D12) also produced the D1 vs D12 rule during the final pass.

## Code frequencies (final labels, n = 60)

| Code | n | | Code | n | | Code | n |
|---|---|---|---|---|---|---|---|
| D1 | 1 | | D7 | 6 | | N1 | 0 |
| D2 | 22 | | D8 | 2 | | N2 | 4 |
| D3 | 1 | | D9 | 0 | | N3 | 0 |
| D4 | 1 | | D10 | 0 | | N4 | 0 |
| D5 | 4 | | D11 | 4 | | N5 | 8 |
| D6 | 1 | | D12 | 6 | | | |

As recorded in the final pilot sheet, before the corrections listed below. These counts must not be shown to coders or put into the LLM prompt, because they could anchor the gold labels.

## Codes with no pilot reviews (D9, D10, N1, N3, N4)

**Kept in v1.** The pilot tests whether codes are clear and can be told apart, not how often they occur.
- **Zero proves little.** Zero in 60 reviews is consistent with a true prevalence of up to about 5% (rule of three), which would be about 80 reviews in the 1,600 analysis set.
- **They do occur.** Keyword searches of the 1–3 star reviews outside the pilot and gold sets match fees (about 3%), permissions or security (about 2%), scams (about 2%) and network problems (about 2%).
- **Deleting codes after seeing data would weaken the method.** The codebook is deductive (directed content analysis), so post-hoc removal would push those reviews into the wrong codes. Rare codes may be grouped at reporting time (cells under 10 reviews), and the paper will say so.

## Final labels to align with v1

These final pilot labels contradict v1's rules. They don't change the kappa above, which comes from the coders' independent labels.

| Review | Recorded | Under v1 | Rule |
|---|---|---|---|
| BK-P12 | D6 | D2 | A broken OTP box is coded by the flow it breaks |
| NG-P02, NG-P12 | secondary D6 | no secondary | Same rule |
| NG-P13 | N5 + secondary D3 | N5 | A secondary code only sits next to a D primary |
| UP-P12 | D11 | D7 | A feature that doesn't work is D7 (as RK-P08) |
| NG-P11 | D4 | D1 | A failed send is D1 |
| RK-P09 | D3 | D7 | D3 is for messages; a broken complaint feature is D7 |
| RK-P10, RK-P15 | no severity | request | New severity value |
| RK-P02 | no severity | annoyance | Every D primary gets a severity |

## Notes for the gold set

- **Seven gold reviews were shown to the coders with suggested labels,** as worked examples in annotation guide v1.0: BK-A001, A013, A015, A026, A034, A063, A078. Exclude them from the gold kappa (report kappa on the other 193) and say so in the paper.
- **BK-A034 is in the 50-review LLM holdout.** None of the seven may appear in the LLM prompt.
- **What to compute on the gold set:** kappa on the primary code over the 193 reviews, plus optional weighted kappa on severity.
