# AWS CloudTrail Detection and Response Lab

An event-driven lab that detects failed AWS console sign-ins, enriches them into a compact triage alert, and publishes the alert to SNS. The response is analyst-guided: the Lambda does not disable users, rotate keys, or make other account changes.

## Event flow

CloudTrail sign-in event → EventBridge rule → Lambda parser and triage summary → SNS topic. The Terraform configuration scopes the Lambda role to publishing to the one alert topic and writing to its own log group. The default DRY_RUN setting is true; Lambda writes a preview to its logs and does not publish to SNS until you deliberately set dry_run to false.

## Local checks

Use Python 3.11 or newer:

    python -m unittest discover -s tests -v
    python -m unittest tests.test_handler

The sample event is in samples/failed_console_login.json. Tests exercise event matching and triage parsing without AWS credentials or boto3 installed.

## Deploy in an isolated account

Use Terraform 1.5 or newer and an AWS profile with permission to create the listed IAM, Lambda, EventBridge, CloudWatch Logs, and SNS resources. From the terraform directory, run terraform init, terraform validate, and terraform plan. Review the plan before apply. The default Lambda mode is dry-run. To publish alerts, set dry_run=false and apply; then subscribe an authorized address or endpoint to the SNS topic.

S3 data events, external CloudTrail trails, and automatic containment are out of scope. The rule matches failed ConsoleLogin events documented by AWS. Event delivery is best effort; use appropriate production controls and monitoring.

## Analyst response checklist

1. Verify the user, source IP, region, MFA context, and time against expected access patterns.
2. Review nearby CloudTrail activity and identity-provider records.
3. Preserve relevant event details and open an incident record.
4. Follow the organization's approved account-recovery process if the attempt is suspicious.

## References

- AWS Sign-In event patterns: https://docs.aws.amazon.com/eventbridge/latest/ref/events-ref-signin.html
- AWS CloudTrail console sign-in events: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-aws-console-sign-in-events.html
- EventBridge event matching: https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns.html

No deployment or performance claims are made by this repository.
