"""Offline scoring-boundary and semantic robustness regression tests."""
import math
import unittest
from analyze_comparison import metrics, probability_quality, robustness, quantile

class AnalysisTests(unittest.TestCase):
    def test_unanswered_is_not_a_wrong_valid_answer(self):
        rows = [{"item_id": "a", "status": "ok", "selected_option": "1"},
                {"item_id": "b", "status": "ok", "selected_option": "2"},
                {"item_id": "c", "status": "error", "selected_option": "1"}]
        result = metrics(rows, {i:{"gold_option":"1"} for i in "abc"})
        self.assertEqual((result["correct"], result["wrong_valid"], result["unanswered"]), (1, 1, 1))
        self.assertEqual(result["accuracy_attempted"], 1/3)
        self.assertEqual(result["accuracy_valid"], .5)

    def test_zero_gold_probability_has_finite_documented_loss(self):
        row = {"item_id":"a", "status":"ok", "selected_option":"2", **{f"probability_{i}": int(i == 2) for i in range(1,6)}}
        result = probability_quality([row], {"a":{"gold_option":"1"}})
        self.assertEqual(result["multiclass_brier_sum"], 2)
        self.assertAlmostEqual(result["log_loss_clipped_1e_15"], -math.log(1e-15))

    def test_option_rotation_can_be_consistent_and_wrong(self):
        rows = [{"item_id":"base", "status":"ok", "selected_option":"2"},
                {"item_id":"variant", "status":"ok", "selected_option":"3"}]
        keys = {"base":{"gold_option":"1", "gold_canonical":"right", "option_2_canonical":"wrong"},
                "variant":{"gold_option":"2", "gold_canonical":"right", "option_3_canonical":"wrong"}}
        metadata = {"variant":{"item_id":"variant", "base_id":"base", "role":"robustness", "variant":"option_rotation_1"}}
        result = robustness(rows, keys, metadata)[0]
        self.assertEqual(result["same_canonical_choice"], 1)
        self.assertEqual(result["both_correct"], 0)

    def test_quantiles_interpolate(self):
        self.assertEqual(quantile([4,1,3,2], .5), 2.5)
        self.assertIsNone(quantile([], .95))

if __name__ == "__main__":
    unittest.main()
