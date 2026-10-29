import unittest

from model.load import (
    MODEL_ID,
    load_high_reasoning_model,
    load_low_reasoning_model,
    load_model,
)


class ModelLoadTests(unittest.TestCase):
    def test_existing_model_loader_keeps_the_default_configuration(self):
        model = load_model()

        self.assertEqual(model.config["model_id"], MODEL_ID)
        self.assertNotIn("additional_request_fields", model.config)

    def test_low_reasoning_model_uses_low_adaptive_effort(self):
        model = load_low_reasoning_model()

        self.assertEqual(model.config["model_id"], MODEL_ID)
        self.assertEqual(
            model.config["additional_request_fields"],
            {
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": "low"},
            },
        )

    def test_high_reasoning_model_uses_high_adaptive_effort(self):
        model = load_high_reasoning_model()

        self.assertEqual(model.config["model_id"], MODEL_ID)
        self.assertEqual(
            model.config["additional_request_fields"],
            {
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": "high"},
            },
        )


if __name__ == "__main__":
    unittest.main()
