"""Version pinning and first-response retention checks; no network calls."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_extension as ext


class ExtensionTests(unittest.TestCase):
    def exercise(self, returned, repeat=False):
        with tempfile.TemporaryDirectory() as work:
            out = Path(work)
            (out / "questions_136.csv").write_text("fixture")
            (out / "selection_manifest.json").write_text("{}")
            response = {"http_status": 200, "headers_latency_ms": 1, "latency_ms": 2,
                "error_message": "", "raw_response": {"model": returned, "answers": {
                    "decision": {"choice": "1", "confidence": .9,
                        "probabilities": {"1": .8, "2": .05, "3": .05, "4": .05, "5": .05}}},
                    "usage": {"cost": .00001}}}
            task = {"item_id": "fixture", "prompt_sha256": "prompt", "request_payload_sha256": "request", "payload": {}}
            args = argparse.Namespace(model="jev", env_file=None, execute=True, batch_size=1)
            with patch.object(ext, "OUT", out), patch.object(ext, "tasks_for", return_value=[task]), \
                 patch.object(ext.bench, "api_key", return_value="DO_NOT_PUBLISH"), \
                 patch.object(ext.bench, "send", return_value=response) as send, \
                 contextlib.redirect_stdout(io.StringIO()):
                if returned != ext.MODELS["jev"][1]:
                    with self.assertRaisesRegex(RuntimeError, "version"):
                        ext.run(args)
                else:
                    ext.run(args)
                    if repeat:
                        ext.run(args)
                self.assertEqual(send.call_count, 1)
            text = (out / "results_jev.jsonl").read_text()
            self.assertNotIn("DO_NOT_PUBLISH", text)
            return json.loads(text)

    def test_jev_114_cannot_enter_113_results(self):
        row = self.exercise("typesafe/jev-1.14-20261014")
        self.assertEqual(row["status"], "invalid_response")
        self.assertEqual(row["selected_option"], "")
        self.assertIn("VERSION GUARD", row["error_message"])

    def test_pinned_snapshot_is_retained_without_respending_on_resume(self):
        row = self.exercise(ext.MODELS["jev"][1], repeat=True)
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["model_requested"], "typesafe/jev-1.13")


if __name__ == "__main__":
    unittest.main()
