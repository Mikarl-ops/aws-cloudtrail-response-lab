"""Parse failed console sign-ins into a dry-run-first analyst alert."""

import json
import os


def parse_failed_console_login(event):
    """Return a normalized incident summary for a failed ConsoleLogin event."""
    if not isinstance(event, dict):
        return None
    if event.get("source") != "aws.signin":
        return None
    if event.get("detail-type") != "AWS API Call via CloudTrail":
        return None

    detail = event.get("detail")
    if not isinstance(detail, dict):
        return None
    if detail.get("eventSource") != "signin.amazonaws.com":
        return None
    if detail.get("eventName") != "ConsoleLogin":
        return None

    response = detail.get("responseElements")
    if not isinstance(response, dict) or response.get("ConsoleLogin") != "Failure":
        return None
    identity = detail.get("userIdentity")
    identity = identity if isinstance(identity, dict) else {}

    return {
        "type": "failed_console_login",
        "account_id": event.get("account") or detail.get("recipientAccountId", "unknown"),
        "event_time": detail.get("eventTime", event.get("time", "unknown")),
        "principal": identity.get("userName") or identity.get("arn") or identity.get("type", "unknown"),
        "source_ip": detail.get("sourceIPAddress", "unknown"),
        "region": detail.get("awsRegion", event.get("region", "unknown")),
        "event_id": detail.get("eventID", "unknown"),
        "triage_steps": [
            "Check whether the sign-in was expected for this principal and source.",
            "Review nearby CloudTrail and identity-provider events.",
            "Preserve the event and follow the approved account-recovery runbook if suspicious.",
        ],
    }


def lambda_handler(event, context):
    alert = parse_failed_console_login(event)
    if alert is None:
        return {"matched": False}

    if os.environ.get("DRY_RUN", "true").lower() == "true":
        print(json.dumps({"dry_run": True, "alert": alert}, sort_keys=True))
        return {"matched": True, "dry_run": True, "alert": alert}

    topic_arn = os.environ.get("ALERT_TOPIC_ARN")
    if not topic_arn:
        raise RuntimeError("ALERT_TOPIC_ARN is required when DRY_RUN is false")

    import boto3

    response = boto3.client("sns").publish(
        TopicArn=topic_arn,
        Subject="Failed AWS console sign-in",
        Message=json.dumps(alert, indent=2, sort_keys=True),
    )
    return {"matched": True, "dry_run": False, "message_id": response["MessageId"]}


if __name__ == "__main__":
    with open("samples/failed_console_login.json", encoding="utf-8") as sample_file:
        sample = json.load(sample_file)
    print(json.dumps(parse_failed_console_login(sample), indent=2, sort_keys=True))
