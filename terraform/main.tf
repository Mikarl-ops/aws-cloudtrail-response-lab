data "archive_file" "lambda_package" {
  type        = "zip"
  source_file = format("%s/../lambda/handler.py", path.module)
  output_path = format("%s/lambda.zip", path.module)
}

resource "aws_sns_topic" "security_alerts" {
  name = "aws-console-signin-security-alerts"
}

resource "aws_iam_role" "lambda_execution" {
  name = "aws-console-signin-lab-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/aws-console-signin-lab"
  retention_in_days = 14
}

resource "aws_iam_role_policy" "lambda_permissions" {
  name = "publish-alert-and-write-own-logs"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "PublishToLabTopic"
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.security_alerts.arn
      },
      {
        Sid      = "WriteFunctionLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = format("%s:*", aws_cloudwatch_log_group.lambda.arn)
      }
    ]
  })
}

resource "aws_lambda_function" "console_signin_alert" {
  function_name    = "aws-console-signin-lab"
  role             = aws_iam_role.lambda_execution.arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.lambda_package.output_path
  source_code_hash = data.archive_file.lambda_package.output_base64sha256
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      ALERT_TOPIC_ARN = aws_sns_topic.security_alerts.arn
      DRY_RUN         = var.dry_run ? "true" : "false"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy.lambda_permissions,
  ]
}

resource "aws_cloudwatch_event_rule" "failed_console_login" {
  name        = "detect-failed-console-signin"
  description = "Matches failed AWS ConsoleLogin events delivered through CloudTrail."

  event_pattern = jsonencode({
    source        = ["aws.signin"]
    "detail-type" = ["AWS API Call via CloudTrail"]
    detail = {
      eventSource = ["signin.amazonaws.com"]
      eventName   = ["ConsoleLogin"]
      responseElements = {
        ConsoleLogin = ["Failure"]
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.failed_console_login.name
  target_id = "console-signin-lambda"
  arn       = aws_lambda_function.console_signin_alert.arn

  depends_on = [aws_lambda_permission.allow_eventbridge]
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.console_signin_alert.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.failed_console_login.arn
}

output "alert_topic_arn" {
  value       = aws_sns_topic.security_alerts.arn
  description = "Subscribe an authorized recipient after reviewing the lab plan."
}

output "event_rule_arn" {
  value       = aws_cloudwatch_event_rule.failed_console_login.arn
  description = "EventBridge rule for failed ConsoleLogin events."
}
