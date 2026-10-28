import importlib.util
import json
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "ai_soc_demo.py"
spec = importlib.util.spec_from_file_location("ai_soc_demo", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PolicyTests(unittest.TestCase):
    def base(self):
        return {
            "action": "isolate_pod",
            "confidence": 0.98,
            "namespace": "aisoc-demo",
            "environment": "development",
        }

    def test_safe_dev_action_allowed(self):
        self.assertTrue(module.local_policy_decision(self.base()))

    def test_production_namespace_denied(self):
        data = self.base()
        data["namespace"] = "prod-core"
        data["environment"] = "production"
        self.assertFalse(module.local_policy_decision(data))

    def test_unknown_action_denied(self):
        data = self.base()
        data["action"] = "delete_database"
        self.assertFalse(module.local_policy_decision(data))

    def test_low_confidence_denied(self):
        data = self.base()
        data["confidence"] = 0.70
        self.assertFalse(module.local_policy_decision(data))


if __name__ == "__main__":
    unittest.main()
