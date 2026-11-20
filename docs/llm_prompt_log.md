# LLM coding: prompt and run log

Model: Claude Opus 5.5 (`claude-opus-5-5`) through Claude Code subagents on a subscription, no API. No temperature setting exists. Batch size 50. Each batch goes to a fresh subagent that sees only the prompt file and one batch file (`sample_id`, `text`). Batches: `scripts/llm_batches.py`, seed 20261020. Raw outputs: `data/labels/llm/raw/` (not shared, because they hold evidence spans quoted from reviews; the text-free versions are in `data/labels/llm/`, see `scripts/make_public_labels.py`). Prompts: `docs/llm_coding_prompt_v1.md` (v1) and `docs/llm_coding_prompt.md` (v2).

## Prompt versions

| Version | Date | sha256 (first 12) | Change |
|---|---|---|---|
| v1 | 2026-11-07 | 0548fd11681b | Built from codebook v1 Sections 1-7. Removed the pilot-basis column and coder-only wording; added output format and app prefixes. |
| v2 | 2026-11-07 | 63943d7a3297 | Added Section 8: four clarifications taken from rule notes on tune rows (N2 vs D5, D7 vs N5, D11 vs D2, D3 vs D11). No review examples. |

**Frozen: v2 on 2026-11-07, after 2 of 3 allowed tune rounds** (tune kappa v1 0.839, v2 0.854; no holdout labels or notes seen). No change after this point.

## Runs

| Date | Batch | Prompt | Output file | Notes |
|---|---|---|---|---|
| 2026-11-07 | tune_01 | v1 | 2026-11-07_claude-opus-5-5_promptv1_tune_01.json | Round 1 |
| 2026-11-07 | tune_02 | v1 | 2026-11-07_claude-opus-5-5_promptv1_tune_02.json | Round 1 |
| 2026-11-07 | tune_03 | v1 | 2026-11-07_claude-opus-5-5_promptv1_tune_03.json | Round 1 |
| 2026-11-07 | tune_01 | v2 | 2026-11-07_claude-opus-5-5_promptv2_tune_01.json | Round 2 |
| 2026-11-07 | tune_02 | v2 | 2026-11-07_claude-opus-5-5_promptv2_tune_02.json | Round 2 |
| 2026-11-07 | tune_03 | v2 | 2026-11-07_claude-opus-5-5_promptv2_tune_03.json | Round 2 |
| 2026-11-07 | holdout_01 run 1 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_holdout_run1.json | Holdout test |
| 2026-11-07 | holdout_01 run 2 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_holdout_run2.json | Holdout test |
| 2026-11-07 | analysis_01 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_01.json | Wave 1 |
| 2026-11-07 | analysis_02 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_02.json | Wave 1 |
| 2026-11-07 | analysis_03 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_03.json | Wave 1 |
| 2026-11-07 | analysis_04 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_04.json | Wave 1 |
| 2026-11-07 | analysis_05 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_05.json | Wave 1 |
| 2026-11-07 | analysis_06 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_06.json | Wave 1 |
| 2026-11-07 | analysis_07 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_07.json | Wave 1 |
| 2026-11-07 | analysis_08 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_08.json | Wave 1 |
| 2026-11-07 | analysis_09 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_09.json | Wave 2 |
| 2026-11-07 | analysis_10 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_10.json | Wave 2 |
| 2026-11-07 | analysis_11 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_11.json | Wave 2 |
| 2026-11-07 | analysis_12 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_12.json | Wave 2 |
| 2026-11-07 | analysis_13 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_13.json | Wave 2 |
| 2026-11-07 | analysis_14 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_14.json | Wave 2 |
| 2026-11-07 | analysis_15 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_15.json | Wave 2 |
| 2026-11-07 | analysis_16 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_16.json | Wave 2 |
| 2026-11-07 | analysis_17 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_17.json | Wave 2 |
| 2026-11-07 | analysis_18 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_18.json | Wave 2 |
| 2026-11-07 | analysis_19 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_19.json | Wave 2 |
| 2026-11-07 | analysis_20 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_20.json | Wave 2 |
| 2026-11-07 | analysis_21 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_21.json | Wave 3 |
| 2026-11-07 | analysis_22 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_22.json | Wave 3 |
| 2026-11-07 | analysis_23 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_23.json | Wave 3 |
| 2026-11-07 | analysis_24 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_24.json | Wave 3 |
| 2026-11-07 | analysis_25 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_25.json | Wave 3 |
| 2026-11-07 | analysis_26 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_26.json | Wave 3 |
| 2026-11-07 | analysis_27 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_27.json | Wave 3 |
| 2026-11-07 | analysis_28 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_analysis_28.json | Wave 3 |
| 2026-11-07 | contrast_01 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_contrast_01.json | Wave 3 |
| 2026-11-07 | contrast_02 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_contrast_02.json | Wave 3 |
| 2026-11-07 | contrast_03 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_contrast_03.json | Wave 3 |
| 2026-11-07 | contrast_04 | v2 (frozen) | 2026-11-07_claude-opus-5-5_promptv2_contrast_04.json | Wave 3 |
