#!/usr/bin/env python3
"""Rebuild the public Markdown reports from the frozen aggregate analysis."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
S = json.loads((ROOT / "analysis/summary.json").read_text())
pct = lambda x: f"{100*x:.1f}%"
J, L = S["primary"]["jev"], S["primary"]["luna"]
paired = S["paired_valid"]

def metric_table(group, field):
    lines = [f"| {field.title()} | n | Jev correct | Luna correct | Luna unanswered |", "|---|---:|---:|---:|---:|"]
    for x in group:
        j, l = x["jev"], x["luna"]
        lines.append(f"| {x[field]} | {l['attempted']} | {j['correct']} ({pct(j['accuracy_attempted'])}) | {l['correct']} ({pct(l['accuracy_attempted'])}) | {l['unanswered']} |")
    return "\n".join(lines)

confidence_lines = ["| Confidence cutoff | Jev retained | Jev accuracy | Luna retained | Luna accuracy |", "|---|---:|---:|---:|---:|"]
for j, l in zip(S["confidence"]["jev"], S["confidence"]["luna"]):
    confidence_lines.append(f"| ≥{l['threshold']:g} | {j['retained']}/1,000 | {pct(j['accuracy'])} | {l['retained']}/1,000 | {pct(l['accuracy'])} |")
confidence_table = "\n".join(confidence_lines)

README = f"""# Luna Decisions vs Jev: the same 1,000 questions

An independent comparison of OpenAI's **GPT-6 Luna Decisions** and the recorded **Jev September 22, 2026 provider mix**, using the exact same five-option deterministic logic questions, instructions, facts and option order.

**On this benchmark, Jev scored {J['correct']}/1,000 ({pct(J['accuracy_attempted'])}); Luna scored {L['correct']}/1,000 ({pct(L['accuracy_attempted'])}).** Luna answered {L['valid']} questions and left {L['unanswered']} unanswered with API refusal errors. Among answered questions, Luna's accuracy was {pct(L['accuracy_valid'])}. Its high-confidence decisions were much stronger: **199/201 correct at confidence ≥0.8**, covering 20.1% of the original set.

This evaluates a particular text decision API snapshot on a particular generated logic benchmark. It does not establish a general ranking of either product.

![Overall results](figures/overall_results.png)

## Exact versions and dates

| Run | Requested model | Model reported by successful responses | Date |
|---|---|---|---|
| Luna, through OpenRouter Decisions | `openai/gpt-6-luna-decisions` | `openai/gpt-6-luna-decisions-20261006` on all 983 successful responses | October 10, 2026 |
| Jev, TypeSafe | `jev-latest` | `jev-1.13.0` on 412 responses | September 22, 2026 |
| Jev, OpenRouter | `jev-latest` | `typesafe/jev-1.13-20260917` on 332 responses | September 22, 2026 |
| Jev, Experiential | `jev-latest` | `jev-latest` on 256 responses; exact underlying snapshot unverified | September 22, 2026 |

The historical baseline is a provider mix, with incomplete snapshot identification for 256 responses. The Luna error responses did not return a model identity. The model alias was captured when the run occurred; future uses of that alias may resolve differently.

## What the comparison shows

| Measure | Jev | Luna Decisions |
|---|---:|---:|
| Attempted questions | 1,000 | 1,000 |
| Valid decisions saved | 1,000 | 983 |
| Correct | 817 | 612 |
| Wrong valid decisions | 183 | 371 |
| Unanswered after primary retry policy | 0 | 17 |
| Correct / all attempted | 81.7% | 61.2% |
| Correct / valid decisions | 81.7% | 62.3% |
| Core-question accuracy | 512/616 (83.1%) | 389/616 (63.1%) |
| Evaluation-split accuracy | 729/900 (81.0%) | 550/900 (61.1%) |

On the **983 mutually answered questions**, both were correct on {paired['both_correct']}, Jev alone on {paired['jev_only_correct']}, Luna alone on {paired['luna_only_correct']}, and both were wrong on {paired['both_wrong']}. Jev's accuracy on that same subset was {pct(paired['jev_correct']/paired['n'])}; Luna's was {pct(paired['luna_correct']/paired['n'])}. Jev's lead therefore remains when refusals are excluded.

Luna was strongest on directed reachability (35/35), record lookup (33/33), preference ordering (40/41) and transitive comparisons (31/32). Its hardest families included sequential procedures (8/38), exact truth counting (10/45), contraposition (13/42) and object tracking through swaps (14/44). Jev also struggled with sequential procedures and exact truth counting.

![Accuracy across 25 families](figures/family_comparison.png)

## Confidence is useful, but coverage matters

Luna's confidence ≥0.8 subset scored 199/201 (99.0%). At ≥0.9 it scored 128/128. Jev's ≥0.8 subset scored 619/632 (97.9%); its ≥0.9 subset scored 553/557 (99.3%). These are different retained populations. Zero observed errors in a small subset does not guarantee zero future errors.

![Confidence and option-probability calibration](figures/confidence_and_calibration.png)

Confidence is a separate API field from the selected option's probability. Cutoffs here are exploratory descriptions of this sample, not production thresholds validated on a new sample. See the [full analysis](ANALYSIS.md) for all cutoffs, probability scores, difficulty levels and robustness pairs.

## The persistent refusals

OpenRouter returned **HTTP 502** with `OpenAI refused to answer question \\"decision\\"` for 17 items, without a decision, probability distribution or confidence. Each failed twice in the primary run. A separately retained follow-up made up to three more attempts per refused question: **all 51 additional calls refused**. Each affected question thus refused on five attempts, with no recovery.

The questions are ordinary logic puzzles. The error message does not reveal whether the underlying cause was a safety policy, inability to produce a decision, or an upstream/API issue. Repetition shows persistence in this session, not its cause. All errors and timestamps are retained; see [REFUSALS.md](REFUSALS.md).

## Observed latency and cost

Luna's median successful response time, including the body, was **221 ms** (p95 319 ms). Its comparable response-header median was 221 ms; the historical Jev header median was 338 ms across providers and 262 ms for the 332 OpenRouter responses. Different dates, provider routing, concurrency and network conditions prevent a controlled speed claim. Historical Jev timing also omits the response body and earlier retries/failover; the new run records both boundaries and total item time.

The 983 successful Luna responses reported **$0.0351747** total cost and 351,747 input tokens. The 85 refusal attempts across both runs reported no usage/cost. Their charge is unknown from these responses. Jev's billing fields are incomplete, so this report makes no total-cost winner claim.

## Data and reproduction

- [Questions: all 1,000 exact prompts and options](data/questions_1000.csv)
- [Jev historical results](data/results_jev_1000.csv) and [Luna primary results](data/results_luna_1000.csv)
- [Primary HTTP attempt ledger](data/attempts_luna_1000.jsonl), [refusal follow-up results](data/results_luna_refusal_followup.csv) and [follow-up attempt ledger](data/attempts_luna_refusal_followup.jsonl)
- [Public item metadata](data/item_metadata.csv), [aggregate summary](analysis/summary.json), [family CSV](analysis/family_comparison.csv) and [confidence CSV](analysis/confidence_comparison.csv)
- [Protocol and reproducibility limits](METHODS.md), [refusal details](REFUSALS.md), [checksums](data/checksums.json)

The answer key remains outside this repository, preserving the original benchmark's key separation. Public code and inputs let anyone inspect/replay the requests and verify data integrity. Independently reproducing gold accuracy requires the external key; aggregate scores alone cannot certify that key.

```bash
# Python 3.10+; standard library; no API calls
python3 validate_public.py
python3 -m unittest -v test_benchmark.py test_analysis.py
python3 run_benchmark.py

# Optional figure reproduction
python3 -m pip install -r requirements-plots.txt
python3 plot_results.py
python3 build_report.py

# New paid run: set OPENROUTER_API_KEY in your environment first.
# A fresh output folder keeps the published evidence intact.
python3 run_benchmark.py --execute --run-id my_new_run --out runs/my_new_run
```

The runner uses bounded retries, checkpoints, one retained first valid response per item and no correctness feedback. It never retries a wrong valid answer. It does not automatically re-ask completed refusal rows on resume. See [METHODS.md](METHODS.md) to reproduce scoring with an external key.

## Provenance and API references

The original benchmark is [etsabary/jev-deterministic-benchmark](https://github.com/etsabary/jev-deterministic-benchmark/tree/4dd026a3a530eb9edd41dcdae07d62b7a2446e80). This repository copies its already public questions and response CSV byte for byte. The original bank was `JEV_Deterministic_Decision_Benchmark_v1`; these 1,000 items comprise the 100-question development smoke set and the first 900 items of its shuffled evaluation plan. There was no fresh sampling or Luna-specific prompt tuning.

OpenAI documents its [Decisions API](https://developers.openai.com/api/docs/guides/decisions). This run used [OpenRouter's Decisions endpoint](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request) and [GPT-6 Luna Decisions model](https://openrouter.ai/openai/gpt-6-luna-decisions), with the Jev-compatible native choice packet rather than the direct OpenAI endpoint.

Independent community benchmark; no affiliation with OpenAI, OpenRouter or Jev/TypeSafe. Repository code, documentation and benchmark artifacts are shared under the [MIT license](LICENSE).
"""

ANALYSIS = f"""# Detailed analysis: Luna Decisions vs the recorded Jev baseline

Run dates: Luna October 10, 2026; Jev September 22, 2026. Luna reported `openai/gpt-6-luna-decisions-20261006` on all 983 valid decisions. Jev's provenance is the provider mix documented in [README.md](README.md).

## Accuracy and paired outcomes

Luna scored 612/1,000 (61.2%) and Jev 817/1,000 (81.7%): a **20.5 percentage point** difference on all attempted questions. Treating refusals separately, Luna was 612/983 (62.3%), and Jev was 804/983 (81.8%) on the identical mutually answered subset: a **19.5 point** difference. The missing decisions therefore explain only a small part of the overall gap.

| Paired outcome, both valid | Questions |
|---|---:|
| Both correct | 573 |
| Jev correct, Luna wrong | 231 |
| Luna correct, Jev wrong | 39 |
| Both wrong | 140 |
| Total | 983 |

These are descriptive paired counts. The set includes related variants of the same base problems, and a single generation from each model does not measure run-to-run variance. We do not attach naive independent-item significance tests or universal capability claims.

## Strengths and weaknesses by family

Percentages use every attempted question in each family, including unanswered ones. Full group sizes are shown; small differences can reflect only one or two items.

{metric_table(S['by_family'], 'family')}

**Luna strengths.** Lookup and directed reachability were perfect in the observed sample. Preference ordering and transitive comparisons were also strong. Priority/exception rules, source authority and set relations were comparatively effective. These results suggest promise for bounded retrieval and simpler rule decisions, subject to checking on the user's actual distribution.

**Luna weaknesses.** Sequential execution, truth counting, contraposition, swap tracking, scheduling and reference binding were harder. Failures on these generated templates are consistent with difficulty preserving state over steps, applying implication direction correctly and satisfying several exact constraints. The API returns decisions rather than explanations, so those mechanisms are interpretations of the question families and scores, not verified internal reasoning traces.

**Comparison with Jev.** Jev had more correct answers in 21 families, tied in three and fewer in one. Luna's sole family-level lead was sequential procedure execution (8/38 vs 5/38), but both were weak there. Their three ties were reachability, record lookup and preference ordering. Jev's strongest relative advantages included contraposition (41 vs 13), Boolean scope (43 vs 29), interval relations (32 vs 16), scheduling (35 vs 18) and reference binding (31 vs 17). The complete counts matter more than a single overall average.

## Role, difficulty and split

{metric_table(S['by_role'], 'role')}

The 616 core items are useful for checking that the result is not solely driven by robustness variants: Jev scored 83.1%, Luna 63.1% with all core items in the denominator. Probe questions are different questions about candidate violations, rather than ordinary repeats; their 24-item sample is particularly small.

{metric_table(S['by_level'], 'level')}

Luna fell from 77.6% at level 1 to 51.4% at level 4; Jev fell from 94.5% to 70.2%. Level is the bank's template complexity label, not a psychometrically validated difficulty scale.

{metric_table(S['by_split'], 'split')}

The evaluation-only comparison (900 items) is similar to the whole run. The 100 development items were part of the historical run and were preserved for exact matching. We did not use their results to tune the Luna requests before evaluating the remainder.

## Confidence, coverage and probability calibration

{confidence_table}

Luna's high-confidence subset was reliable but small. Confidence ≥0.8 retains 20.1% of all attempted questions and yields 99.0% accuracy; ≥0.9 retains 12.8% with no observed errors. Jev retains 63.2% and 55.7% at those respective cutoffs, with 97.9% and 99.3% accuracy. Comparing equal cutoff numbers does not compare equal coverage or equivalent confidence semantics. The plot shows the practical accuracy/coverage tradeoff, not a transferable operating threshold.

Option probabilities are assessed separately on the same 983 paired valid items:

| Score (lower is better) | Jev | Luna |
|---|---:|---:|
| Five-class Brier score, sum over classes | {S['probability_quality_paired_valid']['jev']['multiclass_brier_sum']:.4f} | {S['probability_quality_paired_valid']['luna']['multiclass_brier_sum']:.4f} |
| Natural-log loss, gold probability clipped at 1e-15 | {S['probability_quality_paired_valid']['jev']['log_loss_clipped_1e_15']:.4f} | {S['probability_quality_paired_valid']['luna']['log_loss_clipped_1e_15']:.4f} |
| Selected-option probability ECE, 10 fixed bins | {S['probability_quality_paired_valid']['jev']['selected_probability_ece_10_bins']:.4f} | {S['probability_quality_paired_valid']['luna']['selected_probability_ece_10_bins']:.4f} |

ECE is descriptive and depends on the chosen bins; it is not a complete calibration measure. The bin counts and means are public in `analysis/summary.json`. Luna's mid/high option probabilities often understate observed accuracy in these bins, while its low-probability decisions remain unreliable. Confidence filtering cannot remove the need to validate the intended workload.

## Robustness against harmless changes

We compare semantic choices, using the external key's canonical option mapping, rather than raw option numbers. That prevents an option rotation from being counted as a contradiction solely because the correct numbered slot changed.

Only **78 base/variant pairs** have both members present and valid for both models. On those identical pairs, Jev selected the same canonical outcome on **71/78** and Luna on **63/78**. Both members were correct on **66/78** Jev pairs and **52/78** Luna pairs. Consistency can include consistently wrong answers, which is why both measures are reported.

The 326 robustness items are not 326 complete matched pairs: most base items were outside this 1,000-item selection. Per-variant counts are small (5–11 shared complete pairs); see `robustness_paired_valid` in the summary. These results suggest an area to examine in a larger dedicated robustness run, rather than a definitive stability ranking. No same-prompt repeated valid generations were collected to measure stochastic repeatability.

## Refusals and retries

17 primary items produced the explicit refusal message through HTTP 502 and no structured answer. Two primary attempts plus three separately recorded follow-up attempts per affected question yielded **85 refusals** with zero recoveries. The errors cluster in seven families, including six assignment and four forward-reasoning items. The logs do not establish the reason. See [REFUSALS.md](REFUSALS.md) for IDs and the exact error.

A deployment would need an explicit error/fallback policy for these cases. Treating them as low-confidence decisions would be incorrect because no confidence was returned. This benchmark does not silently replace them, and preserves the primary score after follow-up.

## Latency and billing

| Observed timing boundary | n | Median ms | p95 ms |
|---|---:|---:|---:|
| Jev final-attempt headers, all providers | 1,000 | 338 | 1,243 |
| Jev final-attempt headers, OpenRouter only | 332 | 262 | 462 |
| Luna final-attempt headers, valid decisions | 983 | 221 | 319 |
| Luna final-attempt complete body, valid decisions | 983 | 221 | 319 |
| Luna item time including retries/backoff, all primary items | 1,000 | 223 | 393 |

The observed Luna successful responses were quicker in this session. This is not a controlled latency contest: dates and workloads were sampled differently, provider routes differed, and the old measurements exclude body reading and earlier retries/provider failover. Four worker threads were used for Luna, with a three-item pilot followed by the remaining 997; the pilot responses were retained. These wall-clock measurements include the client's normal HTTPS handling.

Luna's valid responses reported $0.0351747 for 351,747 input tokens and zero output tokens. Primary execution made 1,017 HTTP calls (983 successes plus 34 refusals); follow-up made 51 more. Every successful response reported a cost, and no refusal response did. **Missing cost is unknown, not verified free.**

Only 588/1,000 Jev final responses have a cost field. Their $0.007966854 sum is incomplete, may contain zero-valued provider reporting, and excludes earlier attempts. It is unsuitable for estimating a full run price or declaring a cost winner. Token counts also differ across model/provider tokenizers despite matched source text.

## Practical interpretation and next experiments

This snapshot of Luna was effective on simpler bounded decisions and produced a useful confidence signal. It was less accurate than the recorded Jev baseline on this deterministic suite, especially several multi-constraint or state-tracking families. A fast first-stage decision with escalation on uncertainty/errors is a plausible use to investigate, but the observed thresholds need independent validation and the fallback must itself be measured.

Useful follow-ups are a concurrent, single-provider rerun of both version-pinned models; a fresh hidden item set built from new templates; repeated identical calls to measure variance; a larger matched robustness set; and confidence thresholds fixed on development data before evaluation. Routing Jev and Luna in a combined cascade could be benchmarked separately, including escalation cost, error recovery and end-to-end latency.

The benchmark covers synthetic text logic, not images, production classification, multilingual decisions, long-context retrieval or high-stakes real-world judgment. Public prompts and previous results also mean training exposure cannot be excluded. These limitations narrow the conclusion to the released artifacts and protocol.
"""

METHODS = """# Protocol and reproduction

## Frozen historical selection

The original question bank is `JEV_Deterministic_Decision_Benchmark_v1`. We replay exactly the 1,000 distinct IDs present in the published Jev results: 100 development smoke questions plus the first 900 questions from the original shuffled evaluation plan. The historical run consists of a 100-item smoke run and 300-, 200- and 400-item evaluation batches, all on September 22, 2026.

The public question CSV and Jev response CSV are byte-identical to the original repository at commit `4dd026a3a530eb9edd41dcdae07d62b7a2446e80`. Their SHA-256 hashes and all other frozen data hashes are in `data/checksums.json`. The metadata CSV is a projection of the original private metadata containing IDs, family, role, level, variant, split, base ID and prompt hash; it contains no gold answers or explanations.

## Exact request mapping

For each question, the runner reconstructs:

```json
{
  "model": "openai/gpt-6-luna-decisions",
  "state": "<original context>",
  "questions": {
    "decision": {
      "type": "choice",
      "instructions": "<original instructions>\\n\\n<original question>",
      "criteria": {
        "1": "<original option 1>", "2": "<original option 2>",
        "3": "<original option 3>", "4": "<original option 4>",
        "5": "<original option 5>"
      }
    }
  }
}
```

It verifies every original prompt-content hash and every historical native request hash before API calls. The new request changes only `model`. There are no demonstrations, gold answers, explanations, chain-of-thought requests, temperature overrides or model-specific prompt changes.

Canonical hashes use UTF-8 JSON with sorted keys, compact separators and unescaped Unicode. The prompt-content hash covers `{instructions, context, question, options:[...]}`; the request hash covers the complete native packet including the model. It is not a hash of the display-only `prompt_text` field.

Requests went to `POST https://openrouter.ai/api/alpha/decisions`, using the OpenRouter native decision schema. This is not the direct OpenAI `/v1/decisions` schema and is not a chat completion. All successful responses identified the upstream provider as OpenAI and the dated model as `openai/gpt-6-luna-decisions-20261006`.

## Primary execution and follow-up

The October 10 primary run used four workers, a 20-second request timeout, at most two HTTP attempts per item, a 1,200-call ceiling and a $0.25 ceiling on **reported** cost. A three-item pilot was retained, then the other 997 items ran with the same configuration. The ceiling does not guarantee billed spending when errors omit usage, and in-flight requests can slightly exceed a reported-cost threshold.

The runner retries transport failures, HTTP 429 and selected 5xx statuses with bounded backoff. In this run all retries were explicit HTTP 502 refusals. It retains the first valid response and never resamples a wrong valid answer. Completed error rows also remain final on resume. All response choices, probability fields and returned model identities were validated. The primary run completed 1,000 items in 1,017 HTTP attempts, producing 983 valid decisions and 17 final errors.

After observing the refusals, a separately recorded follow-up selected exactly those 17 IDs and allowed three additional attempts each, keeping identical input packets. All 51 calls refused; the original results and scores remain intact. Each affected question has five refusal attempts across the two records. This follow-up was requested after the primary run and is disclosed as an additional experiment.

Manifests bind the question and baseline hashes, requested model, endpoint, run ID and limits. Follow-up manifests also bind the selected ID list. Checkpoints are flushed to disk, and mismatched resumes are rejected. API credentials are loaded from the environment or an external environment file and never written into the published artifacts.

## Scoring

The external original answer key maps each item to one correct numbered option and to semantic canonical options. `analyze_comparison.py` requires an exact ID match, checks key metadata, and counts a correct response only when status is `ok` and the selected option equals the gold option. It does not infer correctness from confidence.

Primary accuracy is correct/all attempted, with unanswered items retained in the denominator. Accuracy among valid responses is reported separately. Paired comparisons use the intersection of valid responses from both models. Family, role, split and level summaries retain their own attempted denominators.

Confidence filtering uses the API's `reported_confidence` field, independently of option probability. Coverage is retained/all attempted. Multiclass Brier uses the sum of squared probability errors over five classes. Log loss uses natural logarithms with gold probability clipped to 1e-15. Calibration bins the selected option's probability into ten fixed intervals (the last includes 1.0) and weights absolute bin accuracy gaps by bin size. These probability scores use the same 983 valid paired items.

Robustness pairs require both base and variant to be in the observed set, compare semantic canonical choices and exclude unanswered members. The shared-pair comparison additionally requires both models to answer both members. A separate count records whether both are correct, since consistent wrong responses are possible. The key's canonical gold outcome must agree within a robustness pair.

Quantiles use linear interpolation between sorted observations at index `(n-1)*p`. Luna's `latency_ms` includes response-body reading; `headers_latency_ms` stops at response headers, matching the historical timer boundary. `end_to_end_latency_ms` includes retries and backoff. The old Jev CSV contains only its final-attempt header timing. Earlier historical failover costs and durations cannot be reconstructed from that CSV alone.

## Public validation and answer-key separation

`python3 validate_public.py` requires no key or credentials. It checks exact input/payload identities, result fields against raw responses, retry ledgers, manifests, hashes and aggregate arithmetic. It verifies artifact consistency, **not the truth of the private gold answers**.

To score independently with an authorized external answer key:

```bash
python3 analyze_comparison.py --answer-key /absolute/path/to/answer_key_PRIVATE.csv
python3 build_report.py
python3 -m pip install -r requirements-plots.txt
python3 plot_results.py
```

The key must supply `item_id`, family/role/level/split/variant/base metadata, `gold_option`, `gold_canonical`, and `option_1_canonical` through `option_5_canonical` as in the original bank. No individual correctness labels or gold options are emitted into the public aggregates. The key file's SHA-256 fingerprint is recorded so the scoring source can be checked privately. The repository cannot independently reproduce gold scores without that file.

Replaying the API is separate from re-scoring the recorded outputs:

```bash
# Dry-run: verifies all historical packet hashes; no paid calls.
python3 run_benchmark.py --out runs/new_run --run-id new_run

# Set OPENROUTER_API_KEY in your environment, then make a fresh paid run.
python3 run_benchmark.py --execute --out runs/new_run --run-id new_run

# Example separately recorded follow-up selection, never overwrite a primary run.
python3 run_benchmark.py --execute --only-items data/refusal_followup_items.csv \\
  --out runs/new_followup --run-id new_followup --max-attempts 3
```

The model alias can change; capture the returned version on every future run. Published CSVs and manifests are frozen evidence, not output destinations for new runs. `runs/`, credentials, virtual environments and logs are excluded from Git. The published HTTP attempt files contain sanitized benchmark responses and errors only, with no authorization headers.

## Limits of inference

The old baseline spans three providers and does not reveal the underlying Jev snapshot for all alias responses. The runs occurred on different dates and do not control load or routing. The benchmark includes dependent variants, small per-family samples, and a development subset. It measures one response per item, not generation variance. It uses synthetic, English, text-only problems and public prompts; external validity and possible training exposure remain unmeasured. These limits should accompany any reuse of the headline scores.
"""

rows = list(csv.DictReader((ROOT / "data/results_luna_1000.csv").open(encoding="utf-8-sig")))
metadata = {r["item_id"]: r for r in csv.DictReader((ROOT / "data/item_metadata.csv").open(encoding="utf-8-sig"))}
questions = {r["item_id"]: r for r in csv.DictReader((ROOT / "data/questions_1000.csv").open(encoding="utf-8-sig"))}
refusal_table = ["| Item ID | Family | Question | Primary calls | Follow-up calls | Recovered? |", "|---|---|---|---:|---:|---|"]
for r in sorted(rows, key=lambda r:r["item_id"]):
    if r["status"] != "ok":
        i = r["item_id"]
        refusal_table.append(f"| {i} | {metadata[i]['family']} | {questions[i]['question'].replace('|', '/')} | 2 | 3 | No |")
REFUSALS = """# Persistent refusal observations

17 of the 1,000 primary questions ended in HTTP 502. The exact body, preserved in the attempt error message, was:

```json
{"error":{"message":"OpenAI refused to answer question \\"decision\\"","code":502}}
```

These are API errors with no choice, confidence, probabilities or usage fields. They are distinct from low-confidence answers and wrong valid decisions. Error responses do not identify the dated underlying model; all valid responses in the same requested-model run identified the October 6 Luna Decisions snapshot.

Each affected item failed on both original attempts and all three separately recorded follow-up attempts: **85 refusals across 17 items**, five per item, with zero recovered answers. This persistence argues against a one-off transient recovery in this session, but does not establish the underlying cause. The message alone is insufficient to label the event a safety refusal or inability to solve a puzzle.

""" + "\n".join(refusal_table) + """

Full facts and choices are in `data/questions_1000.csv`, indexed by item ID. Original outcomes are in `data/results_luna_1000.csv`; follow-up outcomes are in `data/results_luna_refusal_followup.csv`. Every HTTP attempt and UTC timestamp is retained in the two `attempts_luna_*.jsonl` files. The primary run's 61.2% attempted accuracy and 62.3% answered accuracy are unchanged after the follow-up.

No refusal attempt returned billing information. Missing usage/cost must not be treated as confirmed zero charge. The original and follow-up manifests document retry bounds and input identity. Further tests could compare a direct OpenAI call and a newly recorded run after an API update; neither was performed in this experiment.
"""

for name, content in [("README.md", README), ("ANALYSIS.md", ANALYSIS), ("METHODS.md", METHODS), ("REFUSALS.md", REFUSALS)]:
    (ROOT / name).write_text(content)
print("Rebuilt README.md, ANALYSIS.md, METHODS.md and REFUSALS.md")
