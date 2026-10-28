# AWS CloudTrail Detection and Response Lab

An event-driven AWS security lab that identifies failed AWS console sign-ins, creates a normalized triage alert, and can publish it to an SNS topic. The response is **analyst-guided**: the Lambda does not disable users, rotate keys, revoke sessions, or make other account changes.

> **Safe by default:** Terraform sets `dry_run = true`. In dry-run mode the function logs a structured alert preview and does not call SNS. This repository contains synthetic test events. No AWS resources are deployed by the automated tests.

## Architecture

```text
CloudTrail ConsoleLogin failure
            |
            v
     Amazon EventBridge
            |
            v
      AWS Lambda parser
      /             \
 DRY_RUN=true     DRY_RUN=false
 structured log   SNS alert publish
      |               |
      v               v
 Analyst review    Authorized subscriber
```

The EventBridge pattern filters failed `ConsoleLogin` events. Lambda extracts account, principal, event time, source IP, region, and event ID, then includes a short analyst triage checklist. The execution role is scoped to the lab SNS topic and the function's CloudWatch log group.

## Local validation (no AWS credentials required)

Use Python 3.11 or newer:

```bash
python -m unittest discover -s tests -v
python -m unittest tests.test_handler
```

The tests use the standard library and synthetic event fixture. They cover:

- Correct parsing and identity/account/region fields.
- Successful sign-ins, unrelated API events, and wrong event sources not matching.
- Malformed event shapes and incomplete identity fields.
- Dry-run behavior, including proving that the AWS SDK is not needed for preview.
- Unmatched events not publishing even when live mode is configured.
- Live-mode SNS publishing through a mocked client (no real SNS call).
- Refusal to enter live mode without an alert topic ARN.

GitHub Actions runs the Python tests and Terraform formatting/validation. These checks validate code and configuration; they do not deploy resources or demonstrate a live AWS integration.

## Event flow and alert fields

The sample is `samples/failed_console_login.json`. The parser accepts only events matching all of these conditions:

- `source = aws.signin`
- `detail-type = AWS API Call via CloudTrail`
- `detail.eventSource = signin.amazonaws.com`
- `detail.eventName = ConsoleLogin`
- `detail.responseElements.ConsoleLogin = Failure`

The returned alert includes `account_id`, `event_time`, `principal`, `source_ip`, `region`, `event_id`, and `triage_steps`. Missing optional context is represented with a fallback rather than preventing the alert.

## Deploy only after review

**Do not apply this Terraform in a personal or production AWS account without reviewing the plan, permissions, and expected cost.** To inspect configuration only, with Terraform 1.5 or newer:

```bash
cd terraform
terraform init -backend=false
terraform validate
terraform plan
```

The plan can create IAM, Lambda, EventBridge, CloudWatch Logs, and SNS resources, which may incur charges. Review the plan carefully before any apply. The default is dry-run. Only set `dry_run = false` when you intentionally want SNS publishing and have configured an authorized subscription. The function itself performs no automatic containment.

S3 data events, external CloudTrail trails, and automated containment are out of scope. EventBridge delivery is best effort; production systems need appropriate monitoring, retry/DLQ configuration, and operational controls.

## Analyst response checklist

1. Verify the principal, source IP, region, MFA context, and time against expected access patterns.
2. Review nearby CloudTrail and identity-provider events.
3. Preserve relevant event details and open an incident record.
4. Follow the organization's approved account-recovery and incident-response procedures if suspicious.

## References

- [AWS Sign-In event patterns](https://docs.aws.amazon.com/eventbridge/latest/ref/events-ref-signin.html)
- [AWS CloudTrail console sign-in events](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-aws-console-sign-in-events.html)
- [EventBridge event matching](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns.html)

No live deployment, end-to-end AWS integration, or performance claims are made by this repository.
