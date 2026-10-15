#!/usr/bin/env python3
"""Score the frozen diagnostic extension with an external key; emit aggregates only.

Preserves original response files. A separate normalized decisions file retains
valid choices when a provider's probability distribution fails normalization.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics

import run_benchmark as bench
import run_extension as ext

ROOT, OUT = ext.ROOT, ext.OUT


def normalize(row, cohort):
    raw = json.loads(row["raw_response_json"])
    answer = raw.get("answers", {}).get("decision", {})
    choice = str(answer.get("choice", ""))
    valid = str(row["http_status"]) == "200" and choice in {"1", "2", "3", "4", "5"}
    warning = ""
    if valid:
        try:
            bench.parse_answer(raw)
        except ValueError as exc:
            warning = str(exc)
    return {**row, "source_cohort": cohort, "normalized_status": "ok" if valid else row["status"],
            "normalized_choice": choice if valid else "", "probability_warning": warning,
            "normalized_confidence": answer.get("confidence") if valid else None}


def valid(row):
    return row["normalized_status"] == "ok"


def correct(row, keys):
    return valid(row) and row["normalized_choice"] == keys[row["item_id"]]["gold_option"]


def semantic(row, keys):
    return keys[row["item_id"]][f"option_{row['normalized_choice']}_canonical"]


def metrics(rows, keys):
    n = len(rows)
    answered = sum(map(valid, rows))
    good = sum(correct(r, keys) for r in rows)
    return {"attempted": n, "answered": answered, "correct": good,
        "wrong": answered - good, "unanswered": n - answered,
        "accuracy_attempted": good / n if n else None,
        "accuracy_answered": good / answered if answered else None,
        "probability_warnings": sum(bool(r["probability_warning"]) for r in rows)}


def distribution(values):
    values = sorted(float(v) for v in values if v not in (None, ""))
    def quantile(p):
        at = (len(values) - 1) * p
        lo = int(at)
        return values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (at - lo)
    return {"n": len(values), "median_ms": quantile(.5), "p95_ms": quantile(.95)} if values else None


def panel_results(rows, keys, selection):
    indexed = {r["item_id"]: r for r in rows}
    rotations, contrasts, candidates = [], [], []
    for p in selection["panels"]["rotations"]:
        group = [indexed[i] for i in p["item_ids"]]
        complete = all(map(valid, group))
        rotations.append({"complete": complete, "all_correct": all(correct(r, keys) for r in group),
            "consistent": complete and len({semantic(r, keys) for r in group}) == 1,
            "correct_choices": sum(correct(r, keys) for r in group)})
    for p in selection["panels"]["contrasts"]:
        a, b = indexed[p["base_id"]], indexed[p["contrast_id"]]
        complete = valid(a) and valid(b)
        contrasts.append({"complete": complete,
            "both_correct": correct(a, keys) and correct(b, keys),
            "changed": complete and semantic(a, keys) != semantic(b, keys),
            "base_correct": correct(a, keys), "contrast_correct": correct(b, keys)})
    for p in selection["panels"]["candidate_checks"]:
        a, checks = indexed[p["base_id"]], [indexed[i] for i in p["check_ids"]]
        candidates.append({"family_id": keys[a["item_id"]]["family_id"],
            "family": keys[a["item_id"]]["family"], "complete": valid(a) and all(map(valid, checks)),
            "parent_correct": correct(a, keys), "all_checks_correct": all(correct(c, keys) for c in checks),
            "checks_correct": sum(correct(c, keys) for c in checks),
            "checks_answered": sum(map(valid, checks))})
    return rotations, contrasts, candidates


def aggregate_panels(panels):
    rotations, contrasts, candidates = panels
    eligible = [p for p in contrasts if p["complete"] and p["base_correct"]]
    return {
        "rotation": {"planned": len(rotations), "complete_answered": sum(p["complete"] for p in rotations),
            "all_five_correct": sum(p["all_correct"] for p in rotations),
            "same_semantic_choice": sum(p["consistent"] for p in rotations),
            "changed_semantic_choice": sum(p["complete"] and not p["consistent"] for p in rotations),
            "correct_of_125": sum(p["correct_choices"] for p in rotations)},
        "contrast": {"planned": len(contrasts), "complete_answered": sum(p["complete"] for p in contrasts),
            "both_correct": sum(p["both_correct"] for p in contrasts),
            "answer_changed": sum(p["changed"] for p in contrasts),
            "base_correct_complete_pairs": len(eligible),
            "contrast_correct_given_base_correct": sum(p["contrast_correct"] for p in eligible)},
        "candidate_checks": {"planned_parents": len(candidates), "planned_checks": 5 * len(candidates),
            "complete_answered": sum(p["complete"] for p in candidates),
            "parent_correct": sum(p["parent_correct"] for p in candidates),
            "checks_correct": sum(p["checks_correct"] for p in candidates),
            "checks_answered": sum(p["checks_answered"] for p in candidates),
            "all_five_checks_correct": sum(p["all_checks_correct"] for p in candidates),
            "parent_and_all_checks_correct": sum(p["parent_correct"] and p["all_checks_correct"] for p in candidates),
            "wrong_parent_all_checks_correct": sum(p["complete"] and not p["parent_correct"] and p["all_checks_correct"] for p in candidates)}}


def analyze(key_path, recheck_dir=None):
    keys = {r["item_id"]: r for r in bench.read_csv(key_path)}
    selection = json.loads((OUT / "selection_manifest.json").read_text())
    questions = bench.read_csv(ROOT / "data/questions_1000.csv") + bench.read_csv(OUT / "questions_136.csv")
    assert len(questions) == len({q["item_id"] for q in questions}) == 1136
    all_rows, new_rows, panels = {}, {}, {}
    summary = {"answer_key_sha256": ext.sha_file(key_path), "date": "2026-10-14",
        "reference_policy": "Original 1,000 first responses plus exactly 136 new questions; no replacements from the repeatability recheck",
        "scoring_policy": "Score a valid typed choice even when probabilities do not sum to one; preserve and flag original strict-parser failures; no probability renormalization",
        "selection": {"additional": 136, "stage_counts": [68, 57, 11], "rotation_levels": selection["rotation_levels"]},
        "extension": {}, "reference_1136": {}, "diagnostics": {}, "timing_extension": {}, "usage_extension": {}}
    for model in ext.MODELS:
        historical = [normalize(r, "historical_1000") for r in bench.read_csv(ROOT / f"data/results_{model}_1000.csv")]
        new = [normalize(r, "extension_136") for r in bench.read_csv(OUT / f"results_{model}.csv")]
        assert len(new) == 136 and all(r["model_returned"] == ext.MODELS[model][1] for r in new if valid(r))
        rows = historical + new
        assert len(rows) == len({r["item_id"] for r in rows}) == 1136
        assert {q["item_id"] for q in questions} == {r["item_id"] for r in rows} <= set(keys)
        all_rows[model], new_rows[model] = rows, new
        summary["extension"][model] = metrics(new, keys)
        summary["reference_1136"][model] = metrics(rows, keys)
        panels[model] = panel_results(rows, keys, selection)
        summary["diagnostics"][model] = aggregate_panels(panels[model])
        summary["timing_extension"][model] = distribution(r["latency_ms"] for r in new if valid(r))
        attempts = bench.read_jsonl(OUT / f"attempts_{model}.jsonl")
        summary["usage_extension"][model] = {"http_attempts": len(attempts),
            "attempts_with_cost": sum(a["provider_cost_usd"] is not None for a in attempts),
            "reported_cost_usd": sum(a["provider_cost_usd"] or 0 for a in attempts),
            "input_tokens": sum(int(r["input_tokens"] or 0) for r in new),
            "output_tokens": sum(int(r["output_tokens"] or 0) for r in new),
            "returned_models": dict(Counter(r["model_returned"] or "unreported (error)" for r in new))}
        ext.write_csv(OUT / f"decisions_{model}_1136.csv", rows)
    q_path = OUT / "questions_1136.csv"
    ext.write_csv(q_path, questions)
    bound = {"question_count": 1136, "questions_sha256": ext.sha_file(q_path),
        "jev_decisions_sha256": ext.sha_file(OUT / "decisions_jev_1136.csv"),
        "luna_decisions_sha256": ext.sha_file(OUT / "decisions_luna_1136.csv"),
        "key_sha256": ext.sha_file(key_path),
        "purpose": "Frozen reference point for later model releases; exact original prompts, five options and their order"}
    ext.write_json(OUT / "reference_manifest.json", bound)
    shared = {}
    for panel_type, pos in [("rotation", 0), ("contrast", 1), ("candidate_checks", 2)]:
        indices = [i for i, (j, l) in enumerate(zip(panels["jev"][pos], panels["luna"][pos])) if j["complete"] and l["complete"]]
        shared[panel_type] = {"n": len(indices)}
        for model in ext.MODELS:
            subset = [[panels[model][k][i] for i in indices] if k == pos else [] for k in range(3)]
            shared[panel_type][model] = aggregate_panels(subset)[panel_type]
    summary["common_answered_panels"] = shared
    ids = sorted({r["item_id"] for r in new_rows["jev"] if valid(r)} & {r["item_id"] for r in new_rows["luna"] if valid(r)})
    indexed = {m: {r["item_id"]: r for r in rs} for m, rs in new_rows.items()}
    paired = Counter((correct(indexed["jev"][i], keys), correct(indexed["luna"][i], keys)) for i in ids)
    summary["extension_paired"] = {"n": len(ids), "both_correct": paired[True, True], "jev_only_correct": paired[True, False], "luna_only_correct": paired[False, True], "both_wrong": paired[False, False]}
    for field in ["family", "level", "role"]:
        summary["by_" + field] = [{field: value, **{
            model: metrics([r for r in rows if keys[r["item_id"]][field] == value], keys)
            for model, rows in all_rows.items()}}
            for value in sorted({keys[r["item_id"]][field] for r in all_rows["jev"]})]
    summary["confidence_1136"] = {model: [{"threshold": threshold,
        **metrics([r for r in rows if valid(r) and r["normalized_confidence"] is not None and float(r["normalized_confidence"]) >= threshold], keys)}
        for threshold in [.8, .9, .95]] for model, rows in all_rows.items()}
    families = []
    for family in sorted({p["family_id"] for p in panels["jev"][2]}):
        row = {"family_id": family}
        for model in ext.MODELS:
            group = [p for p in panels[model][2] if p["family_id"] == family]
            row["family"] = group[0]["family"]
            row[model] = aggregate_panels([[], [], group])["candidate_checks"]
        families.append(row)
    summary["candidate_by_family"] = families
    if recheck_dir:
        original = {r["item_id"]: r for r in all_rows["jev"]}
        repeated = [normalize(r, "repeatability_recheck") for r in bench.read_csv(recheck_dir / "results_completed.csv")]
        transitions = Counter((correct(original[r["item_id"]], keys), correct(r, keys)) for r in repeated)
        summary["recheck_256"] = {"n": len(repeated),
            "old_correct": sum(correct(original[r["item_id"]], keys) for r in repeated),
            "new_correct": sum(correct(r, keys) for r in repeated),
            "same_choice": sum(r["normalized_choice"] == original[r["item_id"]]["normalized_choice"] for r in repeated),
            "wrong_to_correct": transitions[False, True], "correct_to_wrong": transitions[True, False],
            "both_wrong": transitions[False, False], "both_correct": transitions[True, True],
            "returned_models": dict(Counter(r["model_returned"] for r in repeated)),
            "reported_cost_usd": sum(a["provider_cost_usd"] or 0 for a in bench.read_jsonl(recheck_dir / "attempts.jsonl"))}
    ext.write_json(OUT / "summary.json", summary)
    build_report(summary)
    print(json.dumps(summary, indent=2))


def build_report(s):
    j, l = s["extension"]["jev"], s["extension"]["luna"]
    dj, dl = s["diagnostics"]["jev"], s["diagnostics"]["luna"]
    pct = lambda n, d: f"{100*n/d:.1f}%" if d else "n/a"
    text = f"""# Jev 1.13 vs Luna Decisions: 136-question diagnostic extension

14 October 2026. This extends the original 1,000-question comparison to a frozen **1,136-question reference**. It adds complete matched tests rather than another random sample. The original 1,000 responses and their published scores remain unchanged. No Jev 1.14 results enter this reference.

## New results

| Additional questions | Jev 1.13 | Luna Decisions |
|---|---:|---:|
| Attempted | 136 | 136 |
| Valid choices | {j['answered']} | {l['answered']} |
| Correct against the existing key | {j['correct']}/136 ({pct(j['correct'],136)}) | {l['correct']}/136 ({pct(l['correct'],136)}) |
| Wrong valid choices | {j['wrong']} | {l['wrong']} |
| Unanswered | {j['unanswered']} | {l['unanswered']} |
| Probability-format warnings | {j['probability_warnings']} | {l['probability_warnings']} |

The extension is deliberately diagnostic, includes dependent questions and different task proportions, and must not be interpreted as an independent representative sample. In particular, its lower accuracy is not evidence of regression from the original scores.

## What changes in the interpretation

The added questions reinforce the original distinction: Jev 1.13 is strong at applying stated rules to a supplied situation, while repeated state changes and exact counting remain weak. In the full reference, Jev answers all 37 lookup and all 37 directed-reachability questions correctly, but only 5/42 sequential-procedure questions. Luna also answers all lookup and reachability questions correctly, while scoring 9/42 on sequential procedures. These are observations on these generated questions, not guarantees for new tasks.

The supplied-candidate checks make the weakness more specific. Jev gets 36/80 and Luna 32/80, even though the proposed arrangement or hypothetical location is supplied. Searching for a solution therefore cannot be the only difficulty: errors remain in checking constraints or counting their consequences. The small panel does not establish an internal mechanism.

The rotation panels also qualify an earlier claim. Balanced overall option counts do not establish zero position sensitivity. Jev changes semantic choice in 3/25 fully answered panels; Luna changes in 6/21. Jev is more consistent here, but neither is invariant across all observed panels. On the 21 panels both fully answer, Jev gets every rotation correct in 18, compared with Luna's 14.

Jev handles changed evidence more reliably in this selection: both answers are correct in 20/25 planned pairs, compared with Luna's 13/25. On the 22 pairs both answer, the comparison is 18/22 versus 13/22. This tests appropriate response to one edited fact, not general real-world adaptability.

High confidence still selects a much stronger subset. Jev's confidence ≥0.95 group contains 543 correct decisions out of 544, covering 47.9% of the full reference. Luna's corresponding group contains 96/96, covering 8.5%. Luna's smaller error-free sample does not demonstrate a zero error rate; Jev's larger coverage does not eliminate its observed error. These thresholds were inspected on the evaluation results and need separate validation before operational use.

![Reasoning-family results and matched diagnostic panels](abilities_baseline.png)

## What the complete matched tests reveal

These panels combine retained historical responses with the new responses. They are diagnostic first-response comparisons across dates and, for historical Jev, across provider routes. They are not fresh same-session repeats.

| Planned panel / outcome | Jev 1.13 | Luna Decisions |
|---|---:|---:|
| Five-position panels: all five answered / 25 | {dj['rotation']['complete_answered']} | {dl['rotation']['complete_answered']} |
| Five-position panels: all five correct / 25 | {dj['rotation']['all_five_correct']} | {dl['rotation']['all_five_correct']} |
| Same semantic choice across all five / complete panels | {dj['rotation']['same_semantic_choice']}/{dj['rotation']['complete_answered']} | {dl['rotation']['same_semantic_choice']}/{dl['rotation']['complete_answered']} |
| Changed-evidence pairs: both answered / 25 | {dj['contrast']['complete_answered']} | {dl['contrast']['complete_answered']} |
| Changed-evidence pairs: both correct / 25 | {dj['contrast']['both_correct']} | {dl['contrast']['both_correct']} |
| Candidate checks correct / 80 | {dj['candidate_checks']['checks_correct']} | {dl['candidate_checks']['checks_correct']} |
| Original parent puzzles correct / 16 | {dj['candidate_checks']['parent_correct']} | {dl['candidate_checks']['parent_correct']} |
| Parent plus all five candidate checks correct / 16 | {dj['candidate_checks']['parent_and_all_checks_correct']} | {dl['candidate_checks']['parent_and_all_checks_correct']} |

Semantic consistency aligns option meanings, not their displayed numbers. Consistent wrong answers are not successful solutions. Changing a choice after an evidence edit is also insufficient: getting both members correct is the stronger criterion. Refusals count as unanswered, not as demonstrated logical errors. The machine-readable summary also reports results restricted to panels fully answered by both models.

### Supplied-candidate verification by task family

Each family has four parent puzzles and 20 candidate checks. Supplying a proposed arrangement reduces search, but checking or counting its constraints can still be difficult.

| Family | Jev parent / 4 | Jev checks / 20 | Luna parent / 4 | Luna checks / 20 |
|---|---:|---:|---:|---:|
"""
    for f in s["candidate_by_family"]:
        a, b = f["jev"], f["luna"]
        text += f"| {f['family']} | {a['parent_correct']} | {a['checks_correct']} | {b['parent_correct']} | {b['checks_correct']} |\n"
    text += "\n## Frozen reference for future releases\n\n"
    text += "| Existing-key score, descriptive only | Jev 1.13 | Luna Decisions |\n|---|---:|---:|\n"
    text += "| Original 1,000 questions | 817/1,000 (81.7%) | 612/1,000 (61.2%) |\n"
    a,b=s["reference_1136"]["jev"],s["reference_1136"]["luna"]
    text += f"| All 1,136 questions | {a['correct']}/1,136 ({pct(a['correct'],1136)}) | {b['correct']}/1,136 ({pct(b['correct'],1136)}) |\n"
    text += f"| Unanswered across 1,136 | {a['unanswered']} | {b['unanswered']} |\n\n"
    text += "The combined number mixes core questions and dependent diagnostic variants; it is a reproducible reference statistic, not a stronger estimate of general ability. Use matched per-family and per-panel outcomes to assess subsequent releases. The full original question text, instructions and option order are frozen in `questions_1136.csv`; `reference_manifest.json` binds the input and response hashes.\n\n"
    text += "### All 1,136 questions by reasoning family\n\nThese per-family totals also contain dependent variants. The JSON summary additionally separates roles and difficulty levels.\n\n| Family | n | Jev correct | Luna correct | Luna unanswered |\n|---|---:|---:|---:|---:|\n"
    for f in s["by_family"]:
        a,b=f["jev"],f["luna"]
        text += f"| {f['family']} | {a['attempted']} | {a['correct']} ({pct(a['correct'],a['attempted'])}) | {b['correct']} ({pct(b['correct'],b['attempted'])}) | {b['unanswered']} |\n"
    text += "\n### Confidence-filtered reference outcomes\n\nExploratory cutoffs, not held-out production thresholds. Retained populations differ by model.\n\n| Confidence | Jev retained | Jev correct | Luna retained | Luna correct |\n|---|---:|---:|---:|---:|\n"
    for a,b in zip(s["confidence_1136"]["jev"],s["confidence_1136"]["luna"]):
        text += f"| ≥{a['threshold']:g} | {a['attempted']} | {a['correct']} ({pct(a['correct'],a['attempted'])}) | {b['attempted']} | {b['correct']} ({pct(b['correct'],b['attempted'])}) |\n"
    text += "\n"
    text += "## Selection and execution\n\nExactly 68 additions complete all 16 parent-plus-five-check sets; 57 more complete one five-position rotation panel per family; 11 more complete at least one changed-evidence pair per family. The deterministic selection used item metadata and historical coverage, never gold answers or model successes. Ties used ascending IDs. Rotation anchors cover levels 1/2/3/4 in counts 11/5/4/5; this cost-minimizing extension is not level-balanced. All semantic inputs are the unchanged bank texts, with no demonstrations, tools, answer feedback or model-specific tuning.\n\n"
    for model in ["jev","luna"]:
        u,t=s["usage_extension"][model],s["timing_extension"][model]
        text += f"- **{model.title()}**: requested `{ext.MODELS[model][0]}`; all successful responses returned `{ext.MODELS[model][1]}`. {u['http_attempts']} HTTP attempts; {u['input_tokens']:,} input / {u['output_tokens']:,} output tokens; ${u['reported_cost_usd']:.8f} reported cost. Valid-choice response-body median {t['median_ms']:.0f} ms; p95 {t['p95_ms']:.0f} ms.\n"
    text += "\nThe runner retains one first response per item; retries only bounded transport/HTTP failures, at most twice. Luna's six new unanswered items each returned HTTP 502 refusals on both attempts. Those 12 attempts report no usage/cost, so their billed cost is unknown. All Jev requests explicitly used `typesafe/jev-1.13`, never `jev-latest`. Both model IDs are guarded against returned-version drift. Historical `jev-latest` responses are retained as the owner's September 22 Jev 1.13 run; 256 of their original response records contain only that alias.\n\n"
    text += "### Probability parsing disclosure\n\nThree new Jev responses supply a valid choice and confidence but probabilities summing to 0.99. The strict runner recorded them as `invalid_response` and left its parsed choice blank. Raw records remain unchanged. The separate `decisions_jev_1136.csv` extracts those first typed choices, flags the distribution warning, and scores the choices against the existing key. This follows the original protocol's separation of choice accuracy from probability quality. No probabilities are renormalized, and none of these items was resampled. The same check flags ten pre-existing historical Jev distributions; their originally recorded choices and scores are unchanged.\n\n"
    if "recheck_256" in s:
        r=s["recheck_256"]
        text += f"## Separate 256-question Jev 1.13 repeatability recheck\n\nA supplementary recheck replayed the historical gateway's 256 alias-only items through the pinned OpenRouter Jev 1.13 route. All 256 returned `typesafe/jev-1.13-20260917`. Choices agreed on {r['same_choice']}/256 (96.9%); eight changed. Accuracy changed from {r['old_correct']}/256 (83.2%) to {r['new_correct']}/256 (82.4%): two wrong-to-correct, four correct-to-wrong, and two wrong-to-different-wrong changes. This crosses dates and routes; it cannot identify whether the differences arose from provider processing, inference variation, caching or other serving changes. It is not evidence of Jev 1.14. Its ${r['reported_cost_usd']:.8f} reported cost is separate from the extension. One recheck probability distribution also summed to 0.99; the same choice-only scoring policy applies. The recheck does **not** replace any reference answer.\n\n"
    text += "## Validation and limitations\n\nQuestion hashes, native packet identities, returned snapshots, first-response retention, attempt ledgers and aggregate arithmetic are checked. All scores use the original external answer key; its fingerprint matches the original comparison. The key has deterministic solver validation but has not received a fully independent audit of every printed English question. These results do not certify that key. There is no Jev 1.14 or multimodal evidence in this report. Confidence filtering is exploratory, not a verified deployment guarantee.\n\n"
    text += "## Artifacts and reproduction\n\n- [Selection and panel manifest](selection_manifest.json), [136 new questions](questions_136.csv), [all 1,136 questions](questions_1136.csv), [reference hashes](reference_manifest.json).\n- [Jev raw results](results_jev.csv), [Luna raw results](results_luna.csv), and attempt ledgers (`attempts_jev.jsonl`, `attempts_luna.jsonl`).\n- [Normalized Jev reference](decisions_jev_1136.csv), [normalized Luna reference](decisions_luna_1136.csv), [aggregate summary](summary.json), [checksums](checksums.json).\n- [Separate 256-question recheck](recheck_256/results_completed.csv), [recheck attempts](recheck_256/attempts.jsonl), [recheck manifest](recheck_256/run_manifest.json).\n\nThe canonical reproduction scripts live in [luna-decisions-benchmark](https://github.com/etsabary/luna-decisions-benchmark). `python3 validate_extension.py` checks the public evidence without a key or network. `python3 analyze_extension.py --answer-key /path/to/answer_key_PRIVATE.csv --recheck-dir extension_136/recheck_256` reproduces gold-dependent aggregates. `python3 run_extension.py run --model jev` (or `luna`) is a dry-run; add `--execute --env-file /external/path/.env` only for a separately recorded paid replay. Published output files are retained on resume; a new paid replay requires a separate output destination, not deleting frozen responses.\n"
    (OUT / "README.md").write_text(text)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--answer-key", type=Path, required=True)
    p.add_argument("--recheck-dir", type=Path)
    args = p.parse_args()
    analyze(args.answer_key, args.recheck_dir)
