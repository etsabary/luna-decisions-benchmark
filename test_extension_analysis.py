"""Check semantic alignment and choice/probability separation using tiny fixtures."""
import json
import unittest

from analyze_extension import normalize, aggregate_panels, panel_results


class ExtensionAnalysisTests(unittest.TestCase):
    def test_rounded_distribution_keeps_choice_without_changing_raw_response(self):
        raw = {"model":"fixture", "answers":{"decision":{"choice":"1", "confidence":.8,
            "probabilities":{"1":.79,"2":.05,"3":.05,"4":.05,"5":.05}}}}
        row = {"http_status":"200", "status":"invalid_response", "raw_response_json":json.dumps(raw)}
        normalized = normalize(row, "fixture")
        self.assertEqual(normalized["normalized_choice"], "1")
        self.assertEqual(normalized["normalized_status"], "ok")
        self.assertIn("sum to one", normalized["probability_warning"])
        self.assertEqual(normalized["raw_response_json"], row["raw_response_json"])

    def test_rotation_numbers_can_change_while_meaning_stays_the_same(self):
        rows, keys = [], {}
        for i in range(1,6):
            item = str(i)
            rows.append({"item_id":item,"normalized_status":"ok","normalized_choice":item})
            keys[item] = {"gold_option":item,f"option_{i}_canonical":"same_answer"}
        selection={"panels":{"rotations":[{"item_ids":list(keys)}],"contrasts":[],"candidate_checks":[]}}
        summary=aggregate_panels(panel_results(rows, keys, selection))["rotation"]
        self.assertEqual(summary["same_semantic_choice"],1)
        self.assertEqual(summary["all_five_correct"],1)
        keys["5"]["option_5_canonical"]="different_answer"
        summary=aggregate_panels(panel_results(rows, keys, selection))["rotation"]
        self.assertEqual(summary["changed_semantic_choice"],1)


if __name__ == "__main__":
    unittest.main()
