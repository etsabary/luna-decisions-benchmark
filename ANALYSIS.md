# Detailed analysis: Luna Decisions vs the recorded Jev baseline

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

| Family | n | Jev correct | Luna correct | Luna unanswered |
|---|---:|---:|---:|---:|
| Boolean scope and exclusivity | 44 | 43 (97.7%) | 29 (65.9%) | 0 |
| Deterministic causal intervention | 41 | 33 (80.5%) | 19 (46.3%) | 0 |
| Deterministic fault diagnosis | 41 | 40 (97.6%) | 30 (73.2%) | 1 |
| Deterministic preference ordering | 41 | 40 (97.6%) | 40 (97.6%) | 0 |
| Directed reachability | 35 | 35 (100.0%) | 35 (100.0%) | 0 |
| Exact truth counting | 45 | 15 (33.3%) | 10 (22.2%) | 0 |
| Exceptions and priority rules | 49 | 45 (91.8%) | 42 (85.7%) | 0 |
| Forward conditional reasoning | 36 | 36 (100.0%) | 24 (66.7%) | 4 |
| Necessary conditions and contraposition | 42 | 41 (97.6%) | 13 (31.0%) | 0 |
| Nested role and reference binding | 41 | 31 (75.6%) | 17 (41.5%) | 0 |
| Object tracking through swaps | 44 | 27 (61.4%) | 14 (31.8%) | 1 |
| One-to-one assignments | 44 | 37 (84.1%) | 25 (56.8%) | 6 |
| Perspective and belief tracking | 41 | 36 (87.8%) | 31 (75.6%) | 1 |
| Planning with preconditions | 34 | 32 (94.1%) | 25 (73.5%) | 0 |
| Quantifiers and set relations | 41 | 40 (97.6%) | 36 (87.8%) | 0 |
| Record lookup and filtering | 33 | 33 (100.0%) | 33 (100.0%) | 0 |
| Rule verification and counterexamples | 43 | 42 (97.7%) | 34 (79.1%) | 0 |
| Scheduling constraints | 52 | 35 (67.3%) | 18 (34.6%) | 2 |
| Sequential procedure execution | 38 | 5 (13.2%) | 8 (21.1%) | 0 |
| Source authority and stale records | 34 | 34 (100.0%) | 30 (88.2%) | 0 |
| Sufficiency and inconsistency | 34 | 27 (79.4%) | 18 (52.9%) | 0 |
| Temporal interval relations | 33 | 32 (97.0%) | 16 (48.5%) | 0 |
| Transitive comparisons | 32 | 32 (100.0%) | 31 (96.9%) | 0 |
| Truth-teller consistency | 42 | 25 (59.5%) | 16 (38.1%) | 0 |
| Verbal spatial tracking | 40 | 21 (52.5%) | 18 (45.0%) | 2 |

**Luna strengths.** Lookup and directed reachability were perfect in the observed sample. Preference ordering and transitive comparisons were also strong. Priority/exception rules, source authority and set relations were comparatively effective. These results suggest promise for bounded retrieval and simpler rule decisions, subject to checking on the user's actual distribution.

**Luna weaknesses.** Sequential execution, truth counting, contraposition, swap tracking, scheduling and reference binding were harder. Failures on these generated templates are consistent with difficulty preserving state over steps, applying implication direction correctly and satisfying several exact constraints. The API returns decisions rather than explanations, so those mechanisms are interpretations of the question families and scores, not verified internal reasoning traces.

**Comparison with Jev.** Jev had more correct answers in 21 families, tied in three and fewer in one. Luna's sole family-level lead was sequential procedure execution (8/38 vs 5/38), but both were weak there. Their three ties were reachability, record lookup and preference ordering. Jev's strongest relative advantages included contraposition (41 vs 13), Boolean scope (43 vs 29), interval relations (32 vs 16), scheduling (35 vs 18) and reference binding (31 vs 17). The complete counts matter more than a single overall average.

## Role, difficulty and split

| Role | n | Jev correct | Luna correct | Luna unanswered |
|---|---:|---:|---:|---:|
| contrast | 34 | 28 (82.4%) | 20 (58.8%) | 0 |
| core | 616 | 512 (83.1%) | 389 (63.1%) | 11 |
| probe | 24 | 11 (45.8%) | 9 (37.5%) | 0 |
| robustness | 326 | 266 (81.6%) | 194 (59.5%) | 6 |

The 616 core items are useful for checking that the result is not solely driven by robustness variants: Jev scored 83.1%, Luna 63.1% with all core items in the denominator. Probe questions are different questions about candidate violations, rather than ordinary repeats; their 24-item sample is particularly small.

| Level | n | Jev correct | Luna correct | Luna unanswered |
|---|---:|---:|---:|---:|
| 1 | 255 | 241 (94.5%) | 198 (77.6%) | 4 |
| 2 | 253 | 215 (85.0%) | 163 (64.4%) | 3 |
| 3 | 237 | 182 (76.8%) | 120 (50.6%) | 3 |
| 4 | 255 | 179 (70.2%) | 131 (51.4%) | 7 |

Luna fell from 77.6% at level 1 to 51.4% at level 4; Jev fell from 94.5% to 70.2%. Level is the bank's template complexity label, not a psychometrically validated difficulty scale.

| Split | n | Jev correct | Luna correct | Luna unanswered |
|---|---:|---:|---:|---:|
| development | 100 | 88 (88.0%) | 62 (62.0%) | 4 |
| evaluation | 900 | 729 (81.0%) | 550 (61.1%) | 13 |

The evaluation-only comparison (900 items) is similar to the whole run. The 100 development items were part of the historical run and were preserved for exact matching. We did not use their results to tune the Luna requests before evaluating the remainder.

## Confidence, coverage and probability calibration

| Confidence cutoff | Jev retained | Jev accuracy | Luna retained | Luna accuracy |
|---|---:|---:|---:|---:|
| ≥0 | 1000/1,000 | 81.7% | 983/1,000 | 62.3% |
| ≥0.5 | 786/1,000 | 93.4% | 400/1,000 | 93.2% |
| ≥0.6 | 734/1,000 | 95.5% | 327/1,000 | 96.6% |
| ≥0.7 | 680/1,000 | 96.9% | 258/1,000 | 98.8% |
| ≥0.8 | 632/1,000 | 97.9% | 201/1,000 | 99.0% |
| ≥0.9 | 557/1,000 | 99.3% | 128/1,000 | 100.0% |
| ≥0.95 | 493/1,000 | 99.8% | 83/1,000 | 100.0% |
| ≥0.99 | 365/1,000 | 100.0% | 32/1,000 | 100.0% |
| ≥1 | 276/1,000 | 100.0% | 5/1,000 | 100.0% |

Luna's high-confidence subset was reliable but small. Confidence ≥0.8 retains 20.1% of all attempted questions and yields 99.0% accuracy; ≥0.9 retains 12.8% with no observed errors. Jev retains 63.2% and 55.7% at those respective cutoffs, with 97.9% and 99.3% accuracy. Comparing equal cutoff numbers does not compare equal coverage or equivalent confidence semantics. The plot shows the practical accuracy/coverage tradeoff, not a transferable operating threshold.

Option probabilities are assessed separately on the same 983 paired valid items:

| Score (lower is better) | Jev | Luna |
|---|---:|---:|
| Five-class Brier score, sum over classes | 0.2319 | 0.4769 |
| Natural-log loss, gold probability clipped at 1e-15 | 0.4590 | 0.9687 |
| Selected-option probability ECE, 10 fixed bins | 0.0288 | 0.0764 |

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


## Additional refusal diagnosis

A slow matched-control test retained the same seven refusals while all seven controls worked. This argues against ordinary request-rate throttling; it does not establish the underlying cause. The input clusters, simple cases, low-confidence counterexamples and complete evidence are in [REFUSALS.md](REFUSALS.md). The primary scores are unchanged.
