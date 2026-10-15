# Protocol and reproduction

## October 14 diagnostic extension

The separately reported [136-question extension](extension_136/README.md) freezes the reference at 1,136 exact prompts. `run_extension.py` selects additions using metadata and historical coverage only, then uses explicit model IDs and exact returned-snapshot guards. Original questions, responses and analysis artifacts remain unchanged. `analyze_extension.py` preserves strict-parser output and separately extracts valid choices from three Jev responses whose probabilities sum to 0.99. These choices are scored; their distributions remain flagged. `validate_extension.py` checks the public evidence without exposing the external gold key. A separately retained 256-item Jev 1.13 recheck measures repeatability and never replaces reference responses.

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
      "instructions": "<original instructions>\n\n<original question>",
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
python3 run_benchmark.py --execute --only-items data/refusal_followup_items.csv \
  --out runs/new_followup --run-id new_followup --max-attempts 3
```

The model alias can change; capture the returned version on every future run. Published CSVs and manifests are frozen evidence, not output destinations for new runs. `runs/`, credentials, virtual environments and logs are excluded from Git. The published HTTP attempt files contain sanitized benchmark responses and errors only, with no authorization headers.

## Limits of inference

The old baseline spans three providers and does not reveal the underlying Jev snapshot for all alias responses. The runs occurred on different dates and do not control load or routing. The benchmark includes dependent variants, small per-family samples, and a development subset. It measures one response per item, not generation variance. It uses synthetic, English, text-only problems and public prompts; external validity and possible training exposure remain unmeasured. These limits should accompany any reuse of the headline scores.


## Separate slow-rate diagnosis

`diagnose_refusals.py` performs the seven-family, matched-control test documented in [REFUSALS.md](REFUSALS.md). It is dry-run by default; `--execute` uses one worker and at least three seconds between starts, one call per selected item, and no retries. The manifest records the deterministic selection rule and paired IDs. `analyze_diagnostics.py` reproduces the key-independent content-group counts and timing/status summary. This post-run experiment is reported separately and cannot modify the original score.
