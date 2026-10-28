import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "lambda" / "handler.py"
SPEC = importlib.util.spec_from_file_location("response_handler", MODULE_PATH)
handler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handler)


def sample_event():
    return json.loads(
        (ROOT / "samples" / "failed_console_login.json").read_text(encoding="utf-8")
    )


class ConsoleLoginHandlerTests(unittest.TestCase):
    def test_parses_failed_signin_fixture_and_normalizes_identity(self):
        alert = handler.parse_failed_console_login(sample_event())
        self.assertEqual(alert["type"], "failed_console_login")
        self.assertEqual(alert["principal"], "demo-user")
        self.assertEqual(alert["source_ip"], "203.0.113.70")
        self.assertEqual(alert["account_id"], "123456789012")
        self.assertEqual(alert["region"], "ap-southeast-1")
        self.assertEqual(alert["event_id"], "synthetic-event-001")
        self.assertEqual(len(alert["triage_steps"]), 3)

    def test_ignores_successes_and_other_events(self):
        event = sample_event()
        event["detail"]["responseElements"]["ConsoleLogin"] = "Success"
        self.assertIsNone(handler.parse_failed_console_login(event))

        event = sample_event()
        event["detail"]["eventName"] = "CreateAccessKey"
        self.assertIsNone(handler.parse_failed_console_login(event))

        event = sample_event()
        event["source"] = "aws.ec2"
        self.assertIsNone(handler.parse_failed_console_login(event))

    def test_rejects_malformed_event_shapes(self):
        for event in (None, [], "not-an-event", {}, {"detail": []}):
            with self.subTest(event=event):
                self.assertIsNone(handler.parse_failed_console_login(event))

        event = sample_event()
        event["detail"]["responseElements"] = "Failure"
        self.assertIsNone(handler.parse_failed_console_login(event))

    def test_uses_fallback_fields_when_identity_is_partial(self):
        event = sample_event()
        event["detail"]["userIdentity"] = {"type": "AssumedRole"}
        event["detail"].pop("eventTime")
        alert = handler.parse_failed_console_login(event)
        self.assertEqual(alert["principal"], "AssumedRole")
        self.assertEqual(alert["event_time"], event["time"])

    def test_dry_run_returns_alert_and_does_not_publish(self):
        event = sample_event()
        with patch.dict(os.environ, {"DRY_RUN": "true"}, clear=False):
            with patch.dict(sys.modules, {"boto3": None}):
                result = handler.lambda_handler(event, None)
        self.assertTrue(result["matched"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["alert"]["type"], "failed_console_login")
        self.assertNotIn("message_id", result)

    def test_unmatched_event_does_not_publish_even_when_dry_run_disabled(self):
        event = sample_event()
        event["detail"]["responseElements"]["ConsoleLogin"] = "Success"
        with patch.dict(os.environ, {"DRY_RUN": "false", "ALERT_TOPIC_ARN": "arn:aws:sns:region:account:topic"}):
            with patch.dict(sys.modules, {"boto3": None}):
                result = handler.lambda_handler(event, None)
        self.assertEqual(result, {"matched": False})

    def test_live_mode_publishes_to_configured_topic(self):
        event = sample_event()
        sns = SimpleNamespace(publish=unittest.mock.Mock(return_value={"MessageId": "mock-message-123"}))
        boto3 = SimpleNamespace(client=unittest.mock.Mock(return_value=sns))
        with patch.dict(os.environ, {"DRY_RUN": "false", "ALERT_TOPIC_ARN": "arn:aws:sns:ap-southeast-1:123456789012:lab-alerts"}):
            with patch.dict(sys.modules, {"boto3": boto3}):
                result = handler.lambda_handler(event, None)

        self.assertFalse(result["dry_run"])
        self.assertEqual(result["message_id"], "mock-message-123")
        boto3.client.assert_called_once_with("sns")
        sns.publish.assert_called_once()
        self.assertEqual(
            sns.publish.call_args.kwargs["TopicArn"],
            "arn:aws:sns:ap-southeast-1:123456789012:lab-alerts",
        )

    def test_live_mode_requires_topic_arn(self):
        with patch.dict(os.environ, {"DRY_RUN": "false"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ALERT_TOPIC_ARN is required"):
                handler.lambda_handler(sample_event(), None)


if __name__ == "__main__":
    unittest.main()
