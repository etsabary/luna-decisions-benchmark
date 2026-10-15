#!/usr/bin/env python3
"""Validate the public 1,136-item reference without an answer key or network."""
from collections import Counter
import json
from pathlib import Path

import run_benchmark as bench
import run_extension as ext
from analyze_extension import normalize


def validate():
    out = ext.OUT
    selection = json.loads((out / "selection_manifest.json").read_text())
    selected = {r["item_id"] for r in selection["selected_items"]}
    original = {r["item_id"] for r in bench.read_csv(ext.ROOT / "data/questions_1000.csv")}
    assert len(selected) == 136 and not selected & original
    assert [r["additional_questions"] for r in selection["stages"]] == [68, 57, 11]
    assert len(selection["panels"]["candidate_checks"]) == 16
    assert len(selection["panels"]["rotations"]) == len(selection["panels"]["contrasts"]) == 25
    questions = {q["item_id"]: q for q in bench.read_csv(out / "questions_1136.csv")}
    assert set(questions) == selected | original and len(questions) == 1136
    for q in questions.values():
        content = {k: q[k] for k in ["instructions", "context", "question"]}
        content["options"] = [q[f"option_{i}"] for i in range(1, 6)]
        assert bench.digest(content) == q["prompt_sha256"]
    s = json.loads((out / "summary.json").read_text())
    for model, (requested, expected) in ext.MODELS.items():
        historical = bench.read_csv(ext.ROOT / f"data/results_{model}_1000.csv")
        raw = bench.read_csv(out / f"results_{model}.csv")
        attempts = bench.read_jsonl(out / f"attempts_{model}.jsonl")
        indexed = {r["item_id"]: r for r in raw}
        assert set(indexed) == selected and len(raw) == 136
        counts = Counter(a["item_id"] for a in attempts)
        normalized = bench.read_csv(out / f"decisions_{model}_1136.csv")
        assert len(normalized) == len({r["item_id"] for r in normalized}) == 1136
        derived = {r["item_id"]: r for r in normalized}
        for r in raw:
            q = questions[r["item_id"]]
            assert r["prompt_sha256"] == q["prompt_sha256"]
            assert r["model_requested"] == requested
            assert r["request_payload_sha256"] == bench.digest({"model": requested, **bench.packet(q)})
            assert 1 <= counts[r["item_id"]] == int(r["attempt_count"]) <= 2
            body = json.loads(r["raw_response_json"])
            if r["http_status"] == "200":
                assert body["model"] == expected
            else:
                assert model == "luna" and r["http_status"] == "502"
                assert "refused to answer" in r["error_message"]
        for cohort, rows in [("historical_1000", historical), ("extension_136", raw)]:
            for row in rows:
                expected_row = normalize(row, cohort)
                actual = derived[row["item_id"]]
                for field in [*row, "source_cohort", "normalized_status", "normalized_choice", "probability_warning"]:
                    assert actual[field] == ("" if expected_row[field] is None else str(expected_row[field])), (model,row["item_id"],field)
        m = s["extension"][model]
        assert m["attempted"] == 136 == m["answered"] + m["unanswered"]
        assert m["answered"] == sum(r["normalized_status"] == "ok" for r in normalized if r["source_cohort"] == "extension_136")
        assert m["answered"] == m["correct"] + m["wrong"]
        for group in ["family", "level", "role"]:
            for field in ["attempted", "answered", "correct", "wrong", "unanswered"]:
                assert sum(r[model][field] for r in s["by_" + group]) == s["reference_1136"][model][field]
        u = s["usage_extension"][model]
        assert len(attempts) == u["http_attempts"]
        assert abs(sum(a["provider_cost_usd"] or 0 for a in attempts) - u["reported_cost_usd"]) < 1e-12
        for p in selection["panels"]["rotations"]:
            assert len(p["item_ids"]) == 5 and set(p["item_ids"]) <= set(derived)
        for p in selection["panels"]["candidate_checks"]:
            assert len(p["check_ids"]) == 5 and set([p["base_id"],*p["check_ids"]]) <= set(derived)
    reference = json.loads((out / "reference_manifest.json").read_text())
    for field, name in [("questions_sha256","questions_1136.csv"),("jev_decisions_sha256","decisions_jev_1136.csv"),("luna_decisions_sha256","decisions_luna_1136.csv")]:
        assert ext.sha_file(out / name) == reference[field]
    assert reference["key_sha256"] == s["answer_key_sha256"]
    assert s["answer_key_sha256"] == json.loads((ext.ROOT / "analysis/summary.json").read_text())["answer_key_sha256"]
    recheck = bench.read_csv(out / "recheck_256/results_completed.csv")
    assert len(recheck) == 256 and all(r["model_returned"] == ext.MODELS["jev"][1] for r in recheck)
    assert {r["item_id"] for r in recheck} == {r["item_id"] for r in bench.read_csv(ext.ROOT / "data/results_jev_1000.csv") if r["model_returned"] == "jev-latest"}
    forbidden = {"gold_option", "gold_canonical", "gold_text", "explanation"}
    for path in out.rglob("*.csv"):
        if path.name != "checksums.json":
            assert not forbidden.intersection(bench.read_csv(path)[0]), path
    for name, digest in json.loads((out / "checksums.json").read_text()).items():
        assert ext.sha_file(out / name) == digest, name
    print("PASS: 136 unique additions; 1,136 frozen questions and first responses per model; exact model versions; source preservation; retry and cost ledgers; separate 256-item recheck; aggregates and checksums; no public gold fields")


if __name__ == "__main__":
    validate()
