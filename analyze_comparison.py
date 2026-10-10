#!/usr/bin/env python3
"""Score the frozen runs with an external answer key; publish aggregates only.

No answer key, gold option, or individual correctness label is written to the
public outputs. Use validate_public.py to audit artifacts without the key.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent

def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def index(rows):
    result = {r["item_id"]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate item IDs")
    return result

def number(value):
    return None if value in (None, "", "None") else float(value)

def correct(row, key):
    return row["status"] == "ok" and str(row["selected_option"]) == str(key["gold_option"])

def quantile(values, p):
    values = sorted(values)
    if not values:
        return None
    x = (len(values) - 1) * p
    lo, hi = math.floor(x), math.ceil(x)
    return values[lo] + (values[hi] - values[lo]) * (x - lo)

def distribution(values):
    values = [number(v) for v in values if number(v) is not None]
    return {"n": len(values), "mean": statistics.mean(values) if values else None,
            "p50": quantile(values, .5), "p95": quantile(values, .95)}

def metrics(rows, keys):
    valid = [r for r in rows if r["status"] == "ok"]
    n_correct = sum(correct(r, keys[r["item_id"]]) for r in valid)
    return {"attempted": len(rows), "valid": len(valid), "unanswered": len(rows) - len(valid),
            "correct": n_correct, "wrong_valid": len(valid) - n_correct,
            "accuracy_attempted": n_correct / len(rows) if rows else None,
            "accuracy_valid": n_correct / len(valid) if valid else None}

def probability_quality(rows, keys):
    valid = [r for r in rows if r["status"] == "ok"]
    brier, losses = [], []
    bins = defaultdict(list)
    for r in valid:
        gold = keys[r["item_id"]]["gold_option"]
        probs = [float(r[f"probability_{i}"]) for i in range(1, 6)]
        brier.append(sum((p - int(str(i) == gold)) ** 2 for i, p in enumerate(probs, 1)))
        losses.append(-math.log(max(probs[int(gold) - 1], 1e-15)))
        selected_p = probs[int(r["selected_option"]) - 1]
        bins[min(int(selected_p * 10), 9)].append((selected_p, correct(r, keys[r["item_id"]])))
    calibration = [{"bin_lower": i / 10, "bin_upper": (i + 1) / 10, "n": len(v),
                    "mean_selected_probability": statistics.mean(x[0] for x in v),
                    "accuracy": statistics.mean(x[1] for x in v)} for i, v in sorted(bins.items())]
    return {"n": len(valid), "multiclass_brier_sum": statistics.mean(brier) if brier else None,
            "log_loss_clipped_1e_15": statistics.mean(losses) if losses else None,
            "selected_probability_ece_10_bins": sum(b["n"] * abs(b["mean_selected_probability"] - b["accuracy"]) for b in calibration) / len(valid) if valid else None,
            "calibration_bins": calibration}

def confidence_curve(rows, keys):
    curve = []
    for threshold in [0, .5, .6, .7, .8, .9, .95, .99, 1]:
        kept = [r for r in rows if r["status"] == "ok" and number(r["reported_confidence"]) is not None and number(r["reported_confidence"]) >= threshold]
        m = metrics(kept, keys)
        curve.append({"threshold": threshold, "retained": len(kept),
                      "coverage_attempted": len(kept) / len(rows),
                      "correct": m["correct"], "wrong": m["wrong_valid"],
                      "accuracy": m["accuracy_valid"]})
    return curve

def robustness(rows, keys, metadata):
    by_id = index(rows)
    groups = defaultdict(list)
    for m in metadata.values():
        if m["role"] != "robustness":
            continue
        base, variant = by_id.get(m["base_id"]), by_id.get(m["item_id"])
        if not base or not variant or base["status"] != "ok" or variant["status"] != "ok":
            continue
        kb, kv = keys[base["item_id"]], keys[variant["item_id"]]
        if kb["gold_canonical"] != kv["gold_canonical"]:
            raise ValueError("Robustness pair changed the canonical gold outcome")
        cb = kb[f"option_{base['selected_option']}_canonical"]
        cv = kv[f"option_{variant['selected_option']}_canonical"]
        groups[m["variant"]].append((cb == cv, correct(base, kb) and correct(variant, kv)))
    return [{"variant": v, "complete_pairs": len(p), "same_canonical_choice": sum(x[0] for x in p),
             "both_correct": sum(x[1] for x in p), "consistency": statistics.mean(x[0] for x in p)} for v, p in sorted(groups.items())]

def grouped(rows_by_model, keys, metadata, field):
    values = sorted({m[field] for m in metadata.values()})
    output = []
    for value in values:
        line = {field: value}
        for model, rows in rows_by_model.items():
            line[model] = metrics([r for r in rows if metadata[r["item_id"]][field] == value], keys)
        output.append(line)
    return output

def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

def analyze(answer_key, out):
    metadata = index(read_csv(ROOT / "data/item_metadata.csv"))
    keys = index(read_csv(answer_key))
    rows_by_model = {"jev": read_csv(ROOT / "data/results_jev_1000.csv"),
                     "luna": read_csv(ROOT / "data/results_luna_1000.csv")}
    if any(set(index(rows)) != set(metadata) for rows in rows_by_model.values()) or not set(metadata) <= set(keys):
        raise ValueError("All scored IDs must match the frozen 1,000-item selection")
    for item_id, m in metadata.items():
        if any(m[field] != keys[item_id][field] for field in m if field != "prompt_sha256"):
            raise ValueError("Key metadata mismatch")
        if keys[item_id]["gold_option"] not in {"1", "2", "3", "4", "5"}:
            raise ValueError("Invalid answer key")
    summary = {"protocol": "Exact historical payloads except requested model; no answer feedback",
               "answer_key_sha256": hashlib.sha256(Path(answer_key).read_bytes()).hexdigest(),
               "primary": {name: metrics(rows, keys) for name, rows in rows_by_model.items()}}
    j, l = (index(rows_by_model[name]) for name in ("jev", "luna"))
    common = [i for i in metadata if j[i]["status"] == l[i]["status"] == "ok"]
    paired = Counter((correct(j[i], keys[i]), correct(l[i], keys[i])) for i in common)
    summary["paired_valid"] = {"n": len(common), "both_correct": paired[True, True],
        "jev_only_correct": paired[True, False], "luna_only_correct": paired[False, True],
        "both_wrong": paired[False, False], "jev_correct": sum(correct(j[i], keys[i]) for i in common),
        "luna_correct": sum(correct(l[i], keys[i]) for i in common)}
    for field in ["family", "role", "level", "split"]:
        summary["by_" + field] = grouped(rows_by_model, keys, metadata, field)
    summary["confidence"] = {n: confidence_curve(r, keys) for n, r in rows_by_model.items()}
    summary["probability_quality_paired_valid"] = {n: probability_quality([index(r)[i] for i in common], keys) for n, r in rows_by_model.items()}
    summary["robustness"] = {n: robustness(r, keys, metadata) for n, r in rows_by_model.items()}
    summary["robustness_paired_valid"] = {n: robustness([index(r)[i] for i in common], keys, metadata) for n, r in rows_by_model.items()}
    summary["versions"] = {n: dict(Counter(r["model_returned"] or "unreported (error)" for r in rows)) for n, rows in rows_by_model.items()}
    summary["providers"] = {n: dict(Counter(r["provider"] for r in rows)) for n, rows in rows_by_model.items()}
    summary["timing"] = {
        "jev_headers_final_attempt_ms": distribution(r["latency_ms"] for r in rows_by_model["jev"]),
        "luna_headers_final_attempt_valid_ms": distribution(r["headers_latency_ms"] for r in rows_by_model["luna"] if r["status"] == "ok"),
        "luna_body_final_attempt_valid_ms": distribution(r["latency_ms"] for r in rows_by_model["luna"] if r["status"] == "ok"),
        "luna_end_to_end_all_ms": distribution(r["end_to_end_latency_ms"] for r in rows_by_model["luna"]),
        "jev_openrouter_headers_ms": distribution(r["latency_ms"] for r in rows_by_model["jev"] if r["provider"] == "openrouter")}
    attempts = [json.loads(line) for line in (ROOT / "data/attempts_luna_1000.jsonl").read_text().splitlines()]
    jev_costs = [number(json.loads(r["raw_response_json"]).get("usage", {}).get("cost")) for r in rows_by_model["jev"]]
    summary["cost"] = {"luna_http_attempts": len(attempts), "luna_attempts_with_reported_cost": sum(a["provider_cost_usd"] is not None for a in attempts),
        "luna_sum_reported_usd": sum(number(a["provider_cost_usd"]) or 0 for a in attempts),
        "luna_input_tokens_valid": sum(int(r["input_tokens"]) for r in rows_by_model["luna"] if r["status"] == "ok"),
        "jev_responses_with_reported_cost": sum(v is not None for v in jev_costs),
        "jev_sum_reported_usd_incomplete": sum(v or 0 for v in jev_costs)}
    followup = read_csv(ROOT / "data/results_luna_refusal_followup.csv")
    if set(index(followup)) != {i for i, r in l.items() if r["status"] != "ok"}:
        raise ValueError("Follow-up must contain exactly the original unanswered items")
    followup_attempts = [json.loads(line) for line in (ROOT / "data/attempts_luna_refusal_followup.jsonl").read_text().splitlines()]
    summary["refusal_followup"] = {**metrics(followup, keys), "http_attempts": len(followup_attempts),
        "sum_reported_cost_usd": sum(number(a["provider_cost_usd"]) or 0 for a in followup_attempts),
        "attempts_with_reported_cost": sum(a["provider_cost_usd"] is not None for a in followup_attempts),
        "primary_plus_followup_correct": summary["primary"]["luna"]["correct"] + sum(correct(r, keys[r["item_id"]]) for r in followup),
        "primary_plus_followup_valid": summary["primary"]["luna"]["valid"] + sum(r["status"] == "ok" for r in followup)}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    flat = []
    for f in summary["by_family"]:
        row = {"family": f["family"]}
        for model in rows_by_model:
            row.update({f"{model}_{k}": v for k, v in f[model].items()})
        flat.append(row)
    write_csv(out / "family_comparison.csv", flat)
    write_csv(out / "confidence_comparison.csv", [{"model": n, **p} for n, curve in summary["confidence"].items() for p in curve])
    print(json.dumps({"primary": summary["primary"], "followup": summary["refusal_followup"]}, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answer-key", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "analysis")
    args = parser.parse_args()
    analyze(args.answer_key, args.out)
