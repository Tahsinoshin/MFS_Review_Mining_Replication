# Gold-set annotation guide

For the coders who annotate the 200-review gold set.
Version 1.0 · 2026-11-01 · Use together with [codebook v1](codebook_v1.md).

## Your task

Code each of the 200 reviews in your coding file **on your own**, using codebook v1. A second coder codes the same reviews separately. We then measure how often you agree (Cohen's kappa) and settle the final labels together in a meeting.

## Before you start

- Read codebook v1 once from start to finish. Pay most attention to Section 3 (how to code) and Section 7 (boundary rules).
- Keep the codebook open while you code.
- Open only **your own** coding file. The lead gives each coder a separate copy.

## Ground rules

1. **Work alone.** Don't discuss any review with the other coder until both of you have submitted.
2. **Don't open the other coder's file.**
3. **No outside help.** Don't use translation tools, chatbots or web searches to interpret a review. If you can't understand one, mark it unsure.
4. **Change only your coding columns.** Leave the review text and the other columns as they are.
5. **Take breaks.** Code in sessions of about 50 reviews. The whole set takes roughly 3–4 hours.
6. **Keep the data private.** Don't copy review text outside the file.

## Columns to fill for every review

| Column | What to enter |
|---|---|
| `primary_code` | One code: D1–D12, or N1–N5 if there's no design issue |
| `secondary_code` | A second D code, only if there's a second, separate design problem. Blank otherwise, and always blank when the primary is an N code |
| `severity` | blocks / degrades / annoyance / request. Blank when the primary is an N code |
| `evidence_span` | Exact words copied from the review, in the original script. Primary first, then ` \| ` and the secondary's words |
| `unsure` | `x` if you're not sure |
| `note` | One short line on why (optional) |

Ignore all other columns. They're used later in the analysis.

## Coding one review in 6 steps

1. **Read the review twice.** Use only the text, not the stars or the developer's reply.
2. **No clear problem?** If it's vague, praise only, off-topic, or just "this app is a scam", the code is **N5**. Copy the evidence and move on.
3. **Design test:** could the provider fix this by changing the app (its screens, flows or messages)?
   - Yes: a **D code**.
   - No: an **N code**. N1 fees, N2 support, agents or provider policy, N3 outside fraud, N4 mobile network.
4. **Primary code:** the main complaint. If the review says one problem caused another, the cause is primary.
5. **Secondary code:** add a second D code only if another design problem is clearly there.
6. **Severity and evidence:** set the severity and copy the evidence words.

## Severity

| Value | When |
|---|---|
| blocks | They couldn't finish (can't log in, money stuck, app won't open) |
| degrades | They finished, but with delay, retries or a workaround |
| annoyance | It didn't stop or slow them |
| request | They ask for a missing feature and report no failure |

## Common mix-ups

- **Existing vs new account:** login, OTP, PIN or being logged out → **D2**; opening a new account, NID or KYC → **D5**.
- **Where the money went wrong:** stuck or missing inside the app → **D1**; bank, NPSB or another service → **D12**.
- **Slow or broken:** slow, crashing, a feature not working, or the phone not supported → **D7**. Use **D8** only if the reviewer blames an update.
- **Hard to find vs hard to see:** hard to find, or "not user-friendly" → **D11**; hard to see or read (small text, small icons) → **D10**.
- **Vague error messages:** "Something went wrong" → **D3**, usually as the secondary code.
- **OTP problems:** an OTP that's late or missing is **D2**, even if the reviewer names their mobile operator.
- **Feature requests:** code the area the feature belongs to, with severity **request**.
- **Mixed reviews:** praise plus a complaint → code the complaint.
- **Other apps:** a comparison with another app on its own is **N5**.

## When you're unsure

Pick your best code, put `x` in `unsure`, and write a short note. **Don't ask the other coder.** Unsure cases are discussed in the agreement meeting.

## When you finish

1. Check that:
   - every row has a primary code and an evidence span;
   - every D primary has a severity.
2. Save the file as `gold_<your initials>_final.xlsx` and send it to the lead.
3. Don't change it after sending.

## What happens next

1. The lead computes agreement between the two files.
2. In a meeting, both coders go through each disagreement, show their evidence, and agree on one label. If you still disagree, the tie-breaker decides.
3. The agreed labels become the gold standard used to check the LLM-assisted coding.
