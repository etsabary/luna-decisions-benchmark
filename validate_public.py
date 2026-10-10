#!/usr/bin/env python3
"""Validate public input identity, responses, retries, summaries and checksums.

This does not independently certify the private gold answers. Re-scoring needs
the external key and analyze_comparison.py; see METHODS.md.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from run_benchmark import MODEL, prepare_tasks, read_csv, parse_answer

ROOT = Path(__file__).resolve().parent

def validate():
    tasks = prepare_tasks(ROOT / "data/questions_1000.csv", ROOT / "data/results_jev_1000.csv", MODEL)
    assert len(tasks) == 1000
    by_id = {t["item_id"]: t for t in tasks}
    summary = json.loads((ROOT / "analysis/summary.json").read_text())
    primary = read_csv(ROOT / "data/results_luna_1000.csv")
    assert len(primary) == 1000 and len({r["item_id"] for r in primary}) == 1000
    assert set(by_id) == {r["item_id"] for r in primary}
    failures = {r["item_id"] for r in primary if r["status"] != "ok"}
    followup = read_csv(ROOT / "data/results_luna_refusal_followup.csv")
    assert {r["item_id"] for r in followup} == failures and len(followup) == len(failures)
    for stem, rows, maximum in [("1000", primary, 2), ("refusal_followup", followup, 3)]:
        attempts = [json.loads(s) for s in (ROOT / f"data/attempts_luna_{stem}.jsonl").read_text().splitlines()]
        counts = Counter(a["item_id"] for a in attempts)
        for r in rows:
            assert r["request_payload_sha256"] == by_id[r["item_id"]]["request_payload_sha256"]
            assert r["prompt_sha256"] == by_id[r["item_id"]]["prompt_sha256"]
            assert 1 <= counts[r["item_id"]] == int(r["attempt_count"]) <= maximum
            if r["status"] == "ok":
                raw = json.loads(r["raw_response_json"])
                choice, probs, confidence = parse_answer(raw)
                assert choice == r["selected_option"] and r["model_returned"] == raw["model"]
                assert all(float(r[f"probability_{i}"]) == probs[str(i)] for i in range(1, 6))
                assert float(r["reported_confidence"]) == confidence
            else:
                assert not r["selected_option"] and not r["reported_confidence"]
                assert int(r["http_status"]) == 502 and "refused to answer" in r["error_message"]
                assert all(not r[f"probability_{i}"] for i in range(1, 6))
        if stem == "1000":
            assert summary["cost"]["luna_http_attempts"] == len(attempts)
            assert abs(summary["cost"]["luna_sum_reported_usd"] - sum(a["provider_cost_usd"] or 0 for a in attempts)) < 1e-12
        else:
            assert summary["refusal_followup"]["http_attempts"] == len(attempts)
    for model, path in [("jev", "data/results_jev_1000.csv"), ("luna", "data/results_luna_1000.csv")]:
        rows = read_csv(ROOT / path)
        m = summary["primary"][model]
        assert m["attempted"] == len(rows) == m["valid"] + m["unanswered"]
        assert m["valid"] == sum(r["status"] == "ok" for r in rows) == m["correct"] + m["wrong_valid"]
        for field in ["family", "role", "level", "split"]:
            assert all(sum(x[model][key] for x in summary["by_" + field]) == m[key] for key in ["attempted", "valid", "correct", "unanswered", "wrong_valid"])
    p = summary["paired_valid"]
    assert p["n"] == sum(p[k] for k in ["both_correct", "jev_only_correct", "luna_only_correct", "both_wrong"])
    for manifest_path in ["data/luna_run_manifest.json", "data/luna_refusal_followup_manifest.json"]:
        m = json.loads((ROOT / manifest_path).read_text())
        assert m["questions_sha256"] == hashlib.sha256((ROOT / "data/questions_1000.csv").read_bytes()).hexdigest()
        assert m["baseline_sha256"] == hashlib.sha256((ROOT / "data/results_jev_1000.csv").read_bytes()).hexdigest()
    checksums = json.loads((ROOT / "data/checksums.json").read_text())
    for name, expected in checksums.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    forbidden = {"gold_option", "gold_canonical", "gold_text", "explanation"}
    for path in (ROOT / "data").glob("*.csv"):
        with path.open(encoding="utf-8-sig") as f:
            assert not forbidden.intersection(next(csv.reader(f))), path
    print("PASS: 1,000 exact inputs, frozen responses, 1,068 HTTP attempts, aggregate consistency, no public gold fields, all checksums")

if __name__ == "__main__":
    validate()
