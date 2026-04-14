from django.test import SimpleTestCase

from .algorithms import get_default_weight_config, resolve_weight_config


class WeightConfigTests(SimpleTestCase):
    def test_defaults_are_returned_when_no_payload_is_provided(self):
        defaults = get_default_weight_config()
        resolved = resolve_weight_config()
        self.assertEqual(resolved, defaults)
        self.assertIsNot(resolved, defaults)

    def test_missing_values_fall_back_to_defaults_and_group_is_normalized(self):
        resolved = resolve_weight_config(
            {
                "server_utility": {
                    "cpu": "7",
                    "bytes": "",
                }
            }
        )

        expected_cpu = 7 / 7.3
        expected_bytes = 0.3 / 7.3
        self.assertAlmostEqual(resolved["server_utility"]["cpu"], expected_cpu)
        self.assertAlmostEqual(resolved["server_utility"]["bytes"], expected_bytes)

    def test_zero_sum_group_falls_back_to_defaults(self):
        defaults = get_default_weight_config()
        resolved = resolve_weight_config(
            {
                "migration_score": {
                    "risk": 0,
                    "feasibility": 0,
                    "complexity": 0,
                }
            }
        )
        self.assertEqual(resolved["migration_score"], defaults["migration_score"])

    def test_non_numeric_weights_raise_error(self):
        with self.assertRaisesMessage(ValueError, "must be numeric"):
            resolve_weight_config({"server_utility": {"cpu": "abc"}})

    def test_negative_weights_raise_error(self):
        with self.assertRaisesMessage(ValueError, "cannot be negative"):
            resolve_weight_config({"device_utility": {"ram": -1}})
