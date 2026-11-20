# Replication package: TTT: Taka, Trust and Trouble

Replication package for the paper **"TTT: Taka, Trust and Trouble- Exploring User-Reported Design Problems
in Bangladeshi Mobile Financial Apps"**, submitted to the DESIGNING 2027 workshop at ICSE 2027.

The study codes negative Google Play reviews of four Bangladeshi mobile financial service (MFS) apps by
the design problem they report. Two human coders labelled a pilot set and a gold set, and an LLM coded
the rest after it was validated against the gold set. This package lets you:

- recompute every reported agreement figure and the RQ1 tables from text-free label files, with one
  command each;
- read the codebook, the coder guide and the exact LLM prompt;
- see the code that collected, cleaned and sampled the reviews, and re-collect them by review ID.

**No review text is included** (see [Data ethics](#data-ethics)).

| App | Google Play package |
|---|---|
| bKash | `com.bKash.customerapp` |
| Nagad | `com.konasl.nagad` |
| Rocket | `com.dbbl.mbs.apps.main` |
| Upay | `bd.com.upay.customer` |

Reviews: Google Play Bangladesh store, 2024-10-20 to 2026-10-20 (UTC, end date excluded), scraped on
2026-10-20.

## Contents

```
docs/
  codebook_v1.md              codebook: 12 design (D1-D12) and 5 non-design (N1-N5) codes, severity, rules
  gold_annotation_guide.md    instructions given to the two gold-set coders
  pilot_report.md             pilot agreement and how the pilot turned codebook v0 into v1
  llm_coding_prompt.md        frozen LLM prompt v2, used for every reported LLM label (sha256 63943d7a3297...)
  llm_coding_prompt_v1.md     prompt v1, used only in the first tuning round (sha256 0548fd11681b...)
  llm_prompt_log.md           model, prompt versions and the date and batch of every LLM run
data/
  samples/sample_membership.csv   every sampled review: sample_id, Google Play review_id, app, set, gold split
  labels/pilot_labels.csv         pilot (60): both coders' independent codes and the final code
  labels/gold_labels.csv          gold (200): both coders' independent primary, secondary and severity, and consensus
  labels/final_labels_1600.csv    final label of each of the 1,600 analysis reviews (200 human + 1,400 LLM)
  labels/llm/llm_labels.csv       LLM labels for the 1,400 non-gold analysis and 200 contrast reviews
  labels/llm/llm_gold_runs.csv    LLM labels on the gold reviews: tuning rounds v1 and v2, hold-out runs 1 and 2
  labels/llm/holdout_compare.csv  hold-out (50): consensus, both LLM runs, both coders
  labels/llm/spotcheck_checks.csv     spot-check: the LLM's codes and each checker's independent Y/N
  labels/llm/spotcheck_settled.csv    spot-check rows settled jointly, with the agreed answer
logs/                         saved outputs of each step (counts and statistics only)
resources/                    romanized Bangla word list used for language tagging
scripts/                      all code (see below)
tests/                        unit tests
```

Sample IDs are an app prefix (BK, NG, RK, UP), a set letter (P pilot, A analysis, C contrast,
L language check) and a number. Gold reviews keep their analysis (A) ID. Coders are named B and C.

## Setup

Tested with Python 3.12.10 on Windows (any Python 3.10+ should work).

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Versions used: google-play-scraper 1.2.7, pandas 3.0.6, numpy 2.5.4, openpyxl 3.1.5,
python-dateutil 2.9.0.post0, scipy 1.18.1.

## Reproducing the results

Run every command from the package root. None of them needs review text.

| Paper result | Command | Expected output |
|---|---|---|
| Pilot, coder vs coder, κ = 0.875 (54/60) | `python scripts/agreement.py data/labels/pilot_labels.csv` | `Cohen's kappa: 0.875` (as `logs/pilot_agreement.json`) |
| Gold, coder vs coder, κ = 0.665 (137/193) | `python scripts/agreement.py data/labels/gold_labels.csv --exclude BK-A001 BK-A013 BK-A015 BK-A026 BK-A034 BK-A063 BK-A078` | `Cohen's kappa: 0.665` (as `logs/gold_agreement.json`) |
| Gold severity, weighted κ = 0.249 (n = 103) | `python scripts/agreement.py data/labels/gold_labels.csv --a coder_b_severity --b coder_c_severity --ordinal blocks degrades annoyance --exclude BK-A001 BK-A013 BK-A015 BK-A026 BK-A034 BK-A063 BK-A078` | `Cohen's kappa: 0.249` (as `logs/gold_agreement_severity.json`) |
| Hold-out, LLM vs consensus, κ = 0.882 (45/50) | `python scripts/agreement.py data/labels/llm/holdout_compare.csv --a final --b llm1` | `Cohen's kappa: 0.882` (as `logs/llm_holdout_agreement.json`) |
| RQ3 and Table III: tuning κ 0.839 → 0.854; hold-out κ, its bootstrap CI and the coder comparison; run-to-run 50/50 and 48/50; severity weighted κ 0.759; spot-check 5.6% (95% CI 3.0–10.3%) and 2.3%; `unsure`-flag split | `python scripts/reproduce_rq3.py` | `29 of 29 checks passed`; details in `logs/rq3_reproduction.json` |
| RQ1 and Table I: codes by app, design share 72.9%, χ² tests and Cramér's V, severity by code and app, contrast odds ratio 6.42 | `python scripts/llm_analysis.py` | Rewrites `data/labels/final_labels_1600.csv` and `logs/analysis_tables.md/.json` byte for byte (`git status` shows no change) |
| Unit tests | `python -m unittest discover -s tests -v` | 31 tests, OK |

Notes:

- The seven gold reviews excluded from κ (all bKash) had been shown to the coders as labelled examples
  in an earlier version of the coder guide. They keep their consensus labels everywhere else.
- Severity κ uses the ordered scale blocks > degrades > annoyance. Rows where either coder gave an N
  code (no severity) or `request` (off the ordered scale) are skipped, which leaves 103 of 193.
- The RQ2 coverage figures follow from `logs/analysis_tables.md`. The top five design codes (D2, D7,
  D12, D5, D8) hold 972 of 1,166 design reviews (83.4%) and 722 of 802 blocking reviews (90.0%).
- The RQ2 design responses (Table II) are hypotheses written by the authors, not computed results.

## Steps that need review text

These steps produced the label files above. They need review text, which is not shared, so the
package includes their code and outputs but they can't be re-run from the package alone.

1. **Scrape** (`scripts/scrape_play.py`, google-play-scraper 1.2.7). For each app, Play language
   setting (`en`, `bn`) and star rating (1–5), it pages through reviews newest first until it passes the
   start of the window. Usernames and avatars are never stored. Set `WINDOW_END = "2026-10-20"` in
   `scripts/config.py` to use the same window. Reviews that were deleted or edited after 2026-10-20
   can't be recovered, so a new scrape won't match exactly.
2. **Clean and tag** (`scripts/clean_tag.py`). Drops reviews under 4 words or 15 characters and
   duplicate texts within an app. Redacts phone numbers, ID and account numbers, transaction IDs and
   e-mail addresses. Tags each review `bangla`, `english`, `mixed` or `romanized`. Counts per step are
   in `logs/clean_summary.json`.
3. **Sample** (`scripts/draw_samples.py`, seed 20261020). Draws the pilot (60), analysis (1,600; Upay
   contributes all 247 of its eligible reviews and the other apps 451 each), gold (200, inside the
   analysis set, stratified by language), contrast (200 four- and five-star reviews) and a language-check
   set. With the same cleaned file (sha256 in `logs/sample_manifest.json`) the draw is identical. To
   rebuild the exact samples from a new scrape, match on `review_id` in
   `data/samples/sample_membership.csv`. `scripts/run_pipeline.py` runs steps 1–3.
4. **LLM coding.**
   - **Model and access.** Claude Opus 5.5 (`claude-opus-5-5`, Anthropic), run on 2026-11-07 through
     Claude Code on a subscription, not through the API.
   - **Batches.** `scripts/llm_batches.py` writes blind batches of 50 reviews holding only `sample_id`
     and redacted text, shuffled with the study seed. Each batch went to a fresh Claude Code subagent
     with the prompt in `docs/`.
   - **Tuning.** Prompt v1 and then v2 were tried on the 150 tune reviews (`scripts/llm_compare.py`).
     v2 was frozen before the 50 hold-out reviews were coded.
   - **Validation.** `scripts/llm_validate.py` checked every output: IDs, legal codes, and evidence spans
     found word for word in the review.
   - **Spot-check.** `scripts/llm_spotcheck.py` built the check sheets: 160 random reviews and 43
     targeted ones.
   - **Public files.** `scripts/make_public_labels.py` produced the text-free files in
     `data/labels/llm/`, dropping evidence spans, review text and free-text notes.

   **The LLM run can't be repeated identically.** Claude Code exposes no temperature or other sampling
   setting, so none was fixed and its value is unknown. The effort setting was not recorded. The package
   therefore ships the LLM's outputs, not a way to regenerate them. Stability was checked by running the
   frozen prompt twice on the hold-out: the same primary code on 50 of 50 reviews, and the same severity
   on 48 of 50.

## Data ethics

- **No review text is shared.** That covers the raw and cleaned reviews, the sample files, the LLM's
  evidence spans and the coders' free-text notes. The package holds only review IDs, labels and
  aggregate counts.
- **Why.** Reviews are written by identifiable people, many describe financial losses or locked
  accounts, and Google Play's terms restrict redistributing its content. Sharing only IDs also respects
  a reviewer's later choice to delete a review.
- **Personal data in the study.** Usernames were never collected. Phone, ID and transaction numbers and
  e-mail addresses were redacted before any coding, and coders and the LLM saw only redacted text.
- **One exception.** The codebook and the LLM prompt quote a few words from some pilot reviews and from
  reviews outside every sample, each with an English gloss, as coding examples. The prompt is published
  exactly as it was used, so it can be checked against its sha256. No gold or analysis review is quoted.

## Licence

- **Code** (`scripts/`, `tests/`): MIT licence, see [LICENSE](LICENSE).
- **Data and documents** (`data/`, `logs/`, `docs/`, `resources/`): CC BY 4.0, see
  [LICENSE-DATA.md](LICENSE-DATA.md).

## Citation

If you use this package, please cite the paper: "TTT: Taka, Trust and Trouble- Exploring
User-Reported Design Problems in Bangladeshi Mobile Financial Apps", DESIGNING 2027 workshop at
ICSE 2027.
