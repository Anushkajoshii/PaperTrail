# Claim Ledger: a small table of tracked stock calls, and a daily job that re-checks them
# against prices after the market closes. Costs ~$0 (one short Lambda run a day).

resource "aws_dynamodb_table" "ledger" {
  name         = "${local.name}-ledger"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "creator"
    type = "S"
  }
  attribute {
    name = "made_on"
    type = "S"
  }

  global_secondary_index {
    name            = "by_creator"
    projection_type = "ALL"
    key_schema {
      attribute_name = "creator"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "made_on"
      key_type       = "RANGE"
    }
  }

  server_side_encryption { enabled = true }
}

resource "aws_cloudwatch_log_group" "ledger" {
  name              = "/aws/lambda/${local.name}-ledger"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "ledger" {
  name               = "${local.name}-ledger"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "ledger_logs" {
  role       = aws_iam_role.ledger.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "ledger" {
  statement {
    sid       = "ReadSecrets"
    actions   = ["ssm:GetParametersByPath"]
    resources = [local.ssm_arn, "${local.ssm_arn}/*"]
  }
  statement {
    sid       = "LedgerTable"
    actions   = ["dynamodb:Scan", "dynamodb:PutItem", "dynamodb:GetItem"]
    resources = [aws_dynamodb_table.ledger.arn]
  }
}

resource "aws_iam_role_policy" "ledger" {
  role   = aws_iam_role.ledger.id
  policy = data.aws_iam_policy_document.ledger.json
}

resource "aws_lambda_function" "ledger" {
  function_name = "${local.name}-ledger"
  role          = aws_iam_role.ledger.arn
  package_type  = "Image"
  image_uri     = local.image_uri
  architectures = ["arm64"]
  memory_size   = 512
  timeout       = 300
  image_config { command = ["papertrail.aws.ledger_lambda.handler"] }
  environment { variables = local.common_env }
  depends_on = [aws_cloudwatch_log_group.ledger]
  lifecycle { ignore_changes = [image_uri] }
}

# 11:30 UTC = 17:00 IST, after Indian markets close (15:30 IST), Monday to Friday.
resource "aws_cloudwatch_event_rule" "ledger_daily" {
  name                = "${local.name}-ledger-daily"
  description         = "Re-check open stock calls in the Claim Ledger"
  schedule_expression = "cron(30 11 ? * MON-FRI *)"
}

resource "aws_cloudwatch_event_target" "ledger_daily" {
  rule = aws_cloudwatch_event_rule.ledger_daily.name
  arn  = aws_lambda_function.ledger.arn
}

resource "aws_lambda_permission" "ledger_daily" {
  statement_id  = "AllowDailySchedule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ledger.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ledger_daily.arn
}
