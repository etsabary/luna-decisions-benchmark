#!/usr/bin/env python3
"""Prepare, run and score the separately reported 136-item diagnostic extension.

Selection uses only public item structure and historical coverage, never answers.
The inference runner never opens the private answer key. Dry-run is the default.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import threading
import time

import run_benchmark as bench

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "extension_136"
MODELS = {
    "jev": ("typesafe/jev-1.13", "typesafe/jev-1.13-20260917"),
    "luna": ("openai/gpt-6-luna-decisions", "openai/gpt-6-luna-decisions-20261006"),
}


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def write_csv(path, rows):
    import csv
    with path.open("w", encoding="utf-8", newline="") as f:
        fields = list(dict.fromkeys(k for row in rows for k in row))
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def prepare(bank):
    meta = bench.read_csv(bank / "metadata_PRIVATE.csv")
    questions = {r["item_id"]: r for r in bench.read_csv(bank / "questions.csv")}
    observed = {r["item_id"] for r in bench.read_csv(ROOT / "data/results_jev_1000.csv")}
    assert observed == {r["item_id"] for r in bench.read_csv(ROOT / "data/results_luna_1000.csv")}
    by_id = {r["item_id"]: r for r in meta}
    selected, reasons = set(), {}
    stages, panels = [], {"candidate_checks": [], "rotations": [], "contrasts": []}

    def add(ids, reason):
        for item in sorted(set(ids) - observed - selected):
            selected.add(item)
            reasons[item] = reason

    probes = defaultdict(list)
    rotations = defaultdict(set)
    contrasts = defaultdict(list)
    for row in meta:
        if row["role"] == "probe":
            probes[row["base_id"]].append(row["item_id"])
        if row["variant"].startswith("option_rotation_"):
            rotations[row["base_id"]].update([row["base_id"], row["item_id"]])
        if row["role"] == "contrast":
            contrasts[row["family_id"]].append(row)
    for base, checks in sorted(probes.items()):
        add([base, *checks], "complete_candidate_checks")
        panels["candidate_checks"].append({"base_id": base, "check_ids": sorted(checks)})
    stages.append({"purpose": "complete_candidate_checks", "additional_questions": len(selected)})
    before = len(selected)
    for family in sorted(contrasts):
        candidates = [b for b in rotations if by_id[b]["family_id"] == family]
        base = min(candidates, key=lambda b: (len(rotations[b] - observed - selected), b))
        add(rotations[base], "complete_rotation_panel")
        panels["rotations"].append({"family_id": family, "base_id": base,
                                    "item_ids": sorted(rotations[base])})
    stages.append({"purpose": "complete_rotation_panel", "additional_questions": len(selected) - before})
    before = len(selected)
    for family, candidates in sorted(contrasts.items()):
        row = min(candidates, key=lambda r: (
            len({r["base_id"], r["item_id"]} - observed - selected),
            sorted([r["base_id"], r["item_id"]])))
        add([row["base_id"], row["item_id"]], "complete_changed_evidence_pair")
        panels["contrasts"].append({"family_id": family, "base_id": row["base_id"],
                                    "contrast_id": row["item_id"]})
    stages.append({"purpose": "complete_changed_evidence_pair", "additional_questions": len(selected) - before})
    assert len(selected) == 136 and [s["additional_questions"] for s in stages] == [68, 57, 11]
    assert not selected & observed
    ids = sorted(selected)
    random.Random(20261014).shuffle(ids)
    manifest = {
        "protocol": "JEV-DD-1.0 diagnostic extension; frozen before new provider calls",
        "selection_date": "2026-10-14", "seed": 20261014,
        "rule": "Complete all 16 candidate-check sets, then one cheapest rotation panel per family, then one cheapest contrast pair per family; ties use ascending IDs. Selection uses coverage and metadata only, never model answers or gold.",
        "total_additional_questions": 136, "stages": stages, "panels": panels,
        "selected_items": [{"item_id": i, "reason": reasons[i]} for i in ids],
        "historical_jev_sha256": sha_file(ROOT / "data/results_jev_1000.csv"),
        "historical_luna_sha256": sha_file(ROOT / "data/results_luna_1000.csv"),
        "rotation_levels": dict(Counter(by_id[p["base_id"]]["level"] for p in panels["rotations"])),
    }
    OUT.mkdir(exist_ok=True)
    path = OUT / "selection_manifest.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError("Refusing to change the frozen extension selection")
    public_fields = ["item_id", "base_id", "family_id", "family", "role", "level", "variant", "split", "prompt_sha256"]
    write_csv(OUT / "questions_136.csv", [questions[i] for i in ids])
    write_csv(OUT / "item_metadata.csv", [{k: by_id[i][k] for k in public_fields} for i in ids])
    write_json(path, manifest)
    print(json.dumps({"selected": len(ids), "stages": stages, "panels": {k: len(v) for k, v in panels.items()}}))


def tasks_for(model):
    tasks = []
    for q in bench.read_csv(OUT / "questions_136.csv"):
        content = {k: q[k] for k in ["instructions", "context", "question"]}
        content["options"] = [q[f"option_{i}"] for i in range(1, 6)]
        if bench.digest(content) != q["prompt_sha256"]:
            raise ValueError("Question hash mismatch: " + q["item_id"])
        payload = {"model": model, **bench.packet(q)}
        tasks.append({"item_id": q["item_id"], "prompt_sha256": q["prompt_sha256"],
                      "request_payload_sha256": bench.digest(payload), "payload": payload})
    assert len(tasks) == 136 and len({t["item_id"] for t in tasks}) == 136
    return tasks


def run(args):
    model, expected = MODELS[args.model]
    tasks = tasks_for(model)
    manifest = {"model_requested": model, "required_returned_model": expected,
        "endpoint": bench.ENDPOINT, "run_id": f"extension_136_{args.model}_20261014",
        "questions_sha256": sha_file(OUT / "questions_136.csv"),
        "selection_sha256": sha_file(OUT / "selection_manifest.json"),
        "max_attempts_per_item": 2, "timeout_seconds": 20, "workers": 4,
        "max_http_attempts": 272, "reported_cost_cap_usd": 0.10,
        "policy": "First valid answer retained; completed errors final on resume; no answer feedback; exact returned-version guard; no cross-model failover"}
    mp = OUT / f"manifest_{args.model}.json"
    if mp.exists() and json.loads(mp.read_text()) != manifest:
        raise ValueError("Manifest mismatch")
    write_json(mp, manifest)
    if not args.execute:
        print(f"DRY RUN: {len(tasks)} questions; {model}; require {expected}")
        return
    key = bench.api_key(args.env_file)
    if not key:
        raise ValueError("Set OPENROUTER_API_KEY locally")
    result_path = OUT / f"results_{args.model}.jsonl"
    attempt_path = OUT / f"attempts_{args.model}.jsonl"
    previous = bench.read_jsonl(result_path)
    previous_attempts = bench.read_jsonl(attempt_path)
    by_id = {t["item_id"]: t for t in tasks}
    assert len({r["item_id"] for r in previous}) == len(previous)
    for r in previous:
        assert r["request_payload_sha256"] == by_id[r["item_id"]]["request_payload_sha256"]
        assert r["model_requested"] == model
        if r["status"] == "ok":
            assert r["model_returned"] == expected
    done = {r["item_id"] for r in previous}
    pending = [t for t in tasks if t["item_id"] not in done][:args.batch_size]
    state = {"attempts": len(previous_attempts), "cost": sum(a.get("provider_cost_usd") or 0 for a in previous_attempts)}
    lock, stop = threading.Lock(), threading.Event()
    results = list(previous)

    def worker(task):
        start = time.perf_counter()
        calls = []
        for number in (1, 2):
            with lock:
                if stop.is_set() or state["attempts"] >= 272 or state["cost"] >= .10:
                    stop.set()
                    return
                state["attempts"] += 1
            response = bench.send(task["payload"], key, 20)
            raw = response["raw_response"]
            cost = raw.get("usage", {}).get("cost")
            attempt = {"item_id": task["item_id"], "attempt": number,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "request_payload_sha256": task["request_payload_sha256"],
                "provider_cost_usd": cost, **response}
            with lock:
                bench.append_json(attempt_path, attempt)
                state["cost"] += cost or 0
            calls.append(attempt)
            status = response["http_status"]
            if status in (400, 401, 402, 403, 404):
                stop.set()
            if status == 200 or status not in (0, 429, 500, 502, 503, 504, 524, 529) or number == 2 or stop.is_set():
                break
            time.sleep(1)
        raw = response["raw_response"]
        status, choice, probs, confidence = "error", "", {}, None
        error = response["error_message"]
        if response["http_status"] == 200 and not error:
            try:
                if raw.get("model") != expected:
                    stop.set()
                    raise ValueError(f"VERSION GUARD: expected {expected}; returned {raw.get('model')}")
                choice, probs, confidence = bench.parse_answer(raw)
                status = "ok"
            except ValueError as exc:
                status, error = "invalid_response", str(exc)
        row = {"run_id": manifest["run_id"], "item_id": task["item_id"], "repeat_index": "1",
            "status": status, "selected_option": choice, "reported_confidence": confidence,
            **{f"probability_{i}": probs.get(str(i)) for i in range(1, 6)},
            "provider": "openrouter", "upstream_provider": raw.get("provider"),
            "model_requested": model, "model_returned": raw.get("model", ""),
            "prompt_mode": "native_choice", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "latency_ms": response["latency_ms"], "headers_latency_ms": response["headers_latency_ms"],
            "end_to_end_latency_ms": (time.perf_counter() - start) * 1000,
            "attempt_count": len(calls), "input_tokens": raw.get("usage", {}).get("input_tokens"),
            "output_tokens": raw.get("usage", {}).get("output_tokens"),
            "provider_cost_usd": sum(c["provider_cost_usd"] for c in calls) if all(c["provider_cost_usd"] is not None for c in calls) else None,
            "http_status": response["http_status"], "api_request_id": raw.get("id", ""),
            "prompt_sha256": task["prompt_sha256"], "request_payload_sha256": task["request_payload_sha256"],
            "error_message": bench.clean(error, key), "raw_response_json": json.dumps(raw, ensure_ascii=False)}
        with lock:
            bench.append_json(result_path, row)
            results.append(row)
            if len(results) % 25 == 0 or status != "ok" or len(pending) <= 5:
                print(f"{args.model}: {len(results)}/136 saved; {status}; model={row['model_returned']}; reported cost=${state['cost']:.6f}", flush=True)

    # A retained one-item pilot is run before bulk execution by the operator.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(worker, t) for t in pending]):
            future.result()
    if results:
        write_csv(OUT / f"results_{args.model}.csv", sorted(results, key=lambda r: r["item_id"]))
    print(json.dumps({"model": args.model, "saved": len(results), "valid": sum(r["status"] == "ok" for r in results), **state, "stopped": stop.is_set()}), flush=True)
    if stop.is_set():
        raise RuntimeError("Run stopped by version, authentication, or budget guard; inspect retained attempts")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--bank", type=Path, required=True)
    live = sub.add_parser("run")
    live.add_argument("--model", choices=MODELS, required=True)
    live.add_argument("--env-file", type=Path)
    live.add_argument("--batch-size", type=int, default=136)
    live.add_argument("--execute", action="store_true")
    args = p.parse_args()
    if args.command == "prepare":
        prepare(args.bank)
    else:
        if args.batch_size < 1:
            p.error("batch size must be positive")
        run(args)


if __name__ == "__main__":
    main()
