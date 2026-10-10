#!/usr/bin/env python3
"""Separate slow-rate diagnostic, never a replacement for primary outcomes.

One refused item per affected family, each paired with a previously answered
control of the same family and level. One worker, no retries, 3 seconds minimum
between request starts. No answer key or gold feedback is used for selection.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from run_benchmark import ROOT, MODEL, ENDPOINT, read_csv, prepare_tasks, send, api_key, parse_answer, append_json

def select_pairs():
    qs = {r["item_id"]: r for r in read_csv(ROOT / "data/questions_1000.csv")}
    ms = {r["item_id"]: r for r in read_csv(ROOT / "data/item_metadata.csv")}
    rows = {r["item_id"]: r for r in read_csv(ROOT / "data/results_luna_1000.csv")}
    failed = sorted(i for i, r in rows.items() if r["status"] != "ok")
    families = sorted({ms[i]["family"] for i in failed})
    pairs = []
    for family in families:
        target = next(i for i in failed if ms[i]["family"] == family)
        candidates = [i for i, r in rows.items() if r["status"] == "ok" and ms[i]["family"] == family and ms[i]["level"] == ms[target]["level"]]
        if not candidates:
            raise ValueError("No matched answered control")
        control = min(candidates, key=lambda i: (ms[i]["role"] != ms[target]["role"], ms[i]["variant"] != ms[target]["variant"], abs(len(qs[i]["context"].split()) - len(qs[target]["context"].split())), i))
        pairs.append({"family": family, "level": ms[target]["level"], "refused_item_id": target, "answered_control_item_id": control})
    return pairs

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "runs/slow_rate_diagnostic")
    args = parser.parse_args()
    pairs = select_pairs()
    tasks = {t["item_id"]: t for t in prepare_tasks(ROOT / "data/questions_1000.csv", ROOT / "data/results_jev_1000.csv", MODEL)}
    if not args.execute:
        print(json.dumps({"dry_run": True, "pairs": pairs}, indent=2)); return
    key = api_key(args.env_file)
    if not key:
        raise ValueError("OPENROUTER_API_KEY is not configured")
    args.out.mkdir(parents=True, exist_ok=True)
    if (args.out / "attempts.jsonl").exists():
        raise ValueError("Diagnostic evidence already exists; use a fresh output directory")
    manifest = {"model_requested": MODEL, "endpoint": ENDPOINT, "workers": 1,
        "max_attempts_per_item": 1, "minimum_request_start_interval_seconds": 3,
        "selection": "Lexicographically first refused ID per family; answered control matched by family and level, preferring role/variant then nearest context word count and ID",
        "pairs": pairs}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    last_start = None
    for pair in pairs:
        for group, item_id in [("originally_refused", pair["refused_item_id"]), ("answered_control", pair["answered_control_item_id"])]:
            if last_start is not None:
                time.sleep(max(0, 3 - (time.monotonic() - last_start)))
            last_start = time.monotonic()
            timestamp = datetime.now(timezone.utc).isoformat()
            task = tasks[item_id]
            response = send(task["payload"], key, 20)
            status = "error"
            choice = ""
            if response["http_status"] == 200 and not response["error_message"]:
                try:
                    choice, _, _ = parse_answer(response["raw_response"])
                    status = "ok"
                except ValueError:
                    status = "invalid_response"
            row = {"item_id": item_id, "group": group, "family": pair["family"],
                   "level": pair["level"], "timestamp_utc": timestamp,
                   "model_requested": MODEL, "request_payload_sha256": task["request_payload_sha256"],
                   "status": status, "selected_option": choice,
                   "provider_cost_usd": response["raw_response"].get("usage", {}).get("cost"), **response}
            append_json(args.out / "attempts.jsonl", row)
            print(f"{group}: {item_id} HTTP {response['http_status']} {status}", flush=True)
            if response["http_status"] in (400,401,402,403,404,429):
                raise ValueError("Diagnostic stopped on configuration, quota or rate-limit error")

if __name__ == "__main__":
    main()
