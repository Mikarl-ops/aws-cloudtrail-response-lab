import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "lambda" / "handler.py"
SPEC = importlib.util.spec_from_file_location("response_handler", MODULE_PATH)
handler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handler)


class ConsoleLoginHandlerTests(unittest.TestCase):
    def test_parses_failed_signin_fixture(self):
        event = json.loads((ROOT / "samples" / "failed_console_login.json").read_text(encoding="utf-8"))
        alert = handler.parse_failed_console_login(event)
        self.assertEqual(alert["principal"], "demo-user")
        self.assertEqual(alert["source_ip"], "203.0.113.70")
        self.assertEqual(alert["account_id"], "123456789012")
        self.assertEqual(len(alert["triage_steps"]), 3)

    def test_ignores_successes_and_other_events(self):
        event = json.loads((ROOT / "samples" / "failed_console_login.json").read_text(encoding="utf-8"))
        event["detail"]["responseElements"]["ConsoleLogin"] = "Success"
        self.assertIsNone(handler.parse_failed_console_login(event))
        event["detail"]["eventName"] = "CreateAccessKey"
        self.assertIsNone(handler.parse_failed_console_login(event))

    def test_dry_run_does_not_publish(self):
        event = json.loads((ROOT / "samples" / "failed_console_login.json").read_text(encoding="utf-8"))
        with patch.dict(os.environ, {"DRY_RUN": "true"}):
            result = handler.lambda_handler(event, None)
        self.assertTrue(result["dry_run"])


if __name__ == "__main__":
    unittest.main()
