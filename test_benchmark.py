"""Offline integrity, transport timing, and checkpoint tests; no API credentials needed."""
import argparse
import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import run_benchmark as bench


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.questions = bench.read_csv(bench.ROOT / "data/questions_1000.csv")[:2]
        ids = {q["item_id"] for q in self.questions}
        self.baseline = [r for r in bench.read_csv(bench.ROOT / "data/results_jev_1000.csv") if r["item_id"] in ids]

    def write_fixture(self):
        paths = []
        for name, rows in [("questions.csv", self.questions), ("baseline.csv", self.baseline)]:
            path = self.root / name
            with path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            paths.append(path)
        return paths

    def test_exact_thousand_payloads(self):
        tasks = bench.prepare_tasks(bench.ROOT / "data/questions_1000.csv",
            bench.ROOT / "data/results_jev_1000.csv", bench.MODEL)
        self.assertEqual(len(tasks), 1000)
        self.assertEqual(len({t["item_id"] for t in tasks}), 1000)
        for t in tasks:
            self.assertEqual(set(t["payload"]), {"model", "state", "questions"})
            self.assertEqual(set(t["payload"]["questions"]), {"decision"})
            self.assertEqual(list(t["payload"]["questions"]["decision"]["criteria"]), ["1", "2", "3", "4", "5"])

    def test_changed_question_rejected(self):
        self.questions[0]["context"] += " Extra evidence."
        with self.assertRaisesRegex(ValueError, "Question text hash mismatch"):
            bench.prepare_tasks(*self.write_fixture(), bench.MODEL)

    def test_historical_request_mismatch_rejected(self):
        self.baseline[0]["request_payload_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Historical native payload mismatch"):
            bench.prepare_tasks(*self.write_fixture(), bench.MODEL)

    def test_duplicate_ids_rejected(self):
        self.questions.append(self.questions[0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            bench.prepare_tasks(*self.write_fixture(), bench.MODEL)

    def test_invalid_probability_distribution_rejected(self):
        response = {"model": bench.MODEL, "answers": {"decision": {"choice": "1",
            "probabilities": {str(i): 0.3 for i in range(1, 6)}, "confidence": 1}}}
        with self.assertRaisesRegex(ValueError, "sum to one"):
            bench.parse_answer(response)

    def test_transport_timer_includes_body_read(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self):
                time.sleep(.02)
                return b'{"model":"mock"}'
        with patch.object(bench.urllib.request, "urlopen", return_value=Response()), patch.object(bench, "ssl_context", return_value=None):
            result = bench.send({"model": "mock"}, "secret-not-published", 5)
        self.assertGreater(result["latency_ms"] - result["headers_latency_ms"], 15)

    def args(self):
        questions, baseline = self.write_fixture()
        return argparse.Namespace(questions=questions, baseline=baseline, model=bench.MODEL,
            out=self.root / "output", run_id="test", workers=1, timeout=5,
            max_attempts=2, max_http_attempts=10, cost_cap=.25,
            env_file=None, batch_size=1, execute=True)

    def test_resume_keeps_first_responses_and_records_cost(self):
        args = self.args()
        response = {"model": bench.MODEL, "provider": "OpenAI", "answers": {"decision": {
            "choice": "3", "confidence": .9, "probabilities": {"1": .05, "2": .05, "3": .8, "4": .05, "5": .05}}},
            "usage": {"input_tokens": 100, "output_tokens": 0, "cost": .00001}}
        sent = {"http_status": 200, "raw_response": response, "error_message": "",
                "headers_latency_ms": 1, "latency_ms": 2}
        with patch.object(bench, "api_key", return_value="secret-not-published"), patch.object(bench, "send", return_value=sent) as send, contextlib.redirect_stdout(io.StringIO()):
            bench.run(args)
            args.batch_size = 100
            bench.run(args)
            bench.run(args)
            self.assertEqual(send.call_count, 2)
        rows = bench.read_jsonl(args.out / "results.jsonl")
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(sum(r["provider_cost_usd"] for r in rows), .00002)
        self.assertNotIn("secret-not-published", (args.out / "results.jsonl").read_text())

    def test_different_model_cannot_resume_same_run(self):
        args = self.args()
        args.execute = False
        with contextlib.redirect_stdout(io.StringIO()):
            bench.run(args)
        args.model = "another/model"
        with self.assertRaisesRegex(ValueError, "different configuration"):
            bench.run(args)

    def test_refusals_are_retained_on_resume(self):
        args = self.args()
        sent = {"http_status": 502, "raw_response": {}, "error_message": "OpenAI refused to answer",
                "headers_latency_ms": None, "latency_ms": 2}
        with patch.object(bench, "api_key", return_value="test-key"), patch.object(bench, "send", return_value=sent) as send, patch.object(bench.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            bench.run(args)
            bench.run(args)
            bench.run(args)
            self.assertEqual(send.call_count, 4)
        rows = bench.read_jsonl(args.out / "results.jsonl")
        self.assertEqual([r["status"] for r in rows], ["error", "error"])
        self.assertTrue(all(r["attempt_count"] == 2 and r["reported_confidence"] is None for r in rows))

    def test_followup_selection_is_bound_to_its_manifest(self):
        args = self.args()
        args.execute = False
        args.only_items = self.root / "subset.csv"
        args.only_items.write_text("item_id\n" + self.questions[0]["item_id"] + "\n")
        with contextlib.redirect_stdout(io.StringIO()):
            bench.run(args)
        manifest = json.loads((args.out / "run_manifest.json").read_text())
        self.assertEqual(manifest["total_questions"], 1)
        args.only_items.write_text("item_id\n" + self.questions[1]["item_id"] + "\n")
        with self.assertRaisesRegex(ValueError, "different configuration"):
            bench.run(args)


if __name__ == "__main__":
    unittest.main()
