#!/usr/bin/env python3
"""Summarize refusal patterns and the slow matched-control test without a key."""
from collections import Counter
from datetime import datetime
import json
from run_benchmark import ROOT, read_csv

metadata = {r["item_id"]: r for r in read_csv(ROOT / "data/item_metadata.csv")}
primary = read_csv(ROOT / "data/results_luna_1000.csv")
failed = [r for r in primary if r["status"] != "ok"]
attempts = [json.loads(s) for s in (ROOT / "data/slow_rate_diagnostic_attempts.jsonl").read_text().splitlines()]
starts = [datetime.fromisoformat(r["timestamp_utc"]) for r in attempts]
summary = {"primary_refusals": len(failed),
    "refused_by_family": dict(sorted(Counter(metadata[r["item_id"]]["family"] for r in failed).items())),
    "refused_by_level": dict(sorted(Counter(metadata[r["item_id"]]["level"] for r in failed).items())),
    "refused_by_role": dict(sorted(Counter(metadata[r["item_id"]]["role"] for r in failed).items())),
    "slow_diagnostic": {"http_attempts": len(attempts), "minimum_observed_start_interval_seconds": min((b-a).total_seconds() for a,b in zip(starts, starts[1:])),
        "groups": {g: {"n": len(rs), "http_status_counts": dict(Counter(r["http_status"] for r in rs)), "valid": sum(r["status"] == "ok" for r in rs)} for g in ["originally_refused", "answered_control"] for rs in [[r for r in attempts if r["group"] == g]]},
        "sum_reported_cost_usd": sum(r["provider_cost_usd"] or 0 for r in attempts),
        "attempts_with_reported_cost": sum(r["provider_cost_usd"] is not None for r in attempts),
        "scope": "Separate post-run diagnostic; seven refused questions and seven matched controls; no change to primary scores"}}
(ROOT / "analysis/refusal_diagnostics.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
