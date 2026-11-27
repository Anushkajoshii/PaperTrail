# Compute: one container image in ECR, two Lambda functions, and an HTTP API in front.

resource "aws_ecr_repository" "app" {
  name                 = "papertrail"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 5 images (storage cost stays near zero)"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}

locals {
  image_uri = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  common_env = {
    PAPERTRAIL_ENV              = var.env
    PAPERTRAIL_AWS_REGION       = var.region
    PAPERTRAIL_LLM_PROVIDER     = var.llm_provider
    PAPERTRAIL_SEARCH_PROVIDER  = var.search_provider
    PAPERTRAIL_STORE_BACKEND    = "dynamodb"
    PAPERTRAIL_DYNAMODB_TABLE   = aws_dynamodb_table.checks.name
    PAPERTRAIL_LEDGER_TABLE     = aws_dynamodb_table.ledger.name
    PAPERTRAIL_PRICE_PROVIDER   = var.price_provider
    PAPERTRAIL_QUEUE_MODE       = "sqs"
    PAPERTRAIL_SQS_QUEUE_URL    = aws_sqs_queue.jobs.url
    PAPERTRAIL_UPLOAD_BACKEND   = "s3"
    PAPERTRAIL_MEDIA_BUCKET     = aws_s3_bucket.media.bucket
    PAPERTRAIL_SSM_SECRETS_PATH = local.ssm_path
    PAPERTRAIL_MAX_UPLOAD_BYTES = "4000000" # Lambda request limit is 6 MB (base64 adds a third)
    PAPERTRAIL_CORS_ORIGINS     = "[]"      # the web app is served from the same URL
    PAPERTRAIL_LOG_LEVEL        = "INFO"
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name}-api"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/lambda/${local.name}-worker"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "api" {
  function_name = "${local.name}-api"
  role          = aws_iam_role.api.arn
  package_type  = "Image"
  image_uri     = local.image_uri
  architectures = ["arm64"]
  memory_size   = 1024
  timeout       = 29 # API Gateway waits at most 30 s; long work goes to the worker
  environment { variables = local.common_env }
  depends_on = [aws_cloudwatch_log_group.api]
  # After the first deploy, GitHub Actions ships new images; Terraform must not roll them back.
  lifecycle { ignore_changes = [image_uri] }
}

resource "aws_lambda_function" "worker" {
  function_name = "${local.name}-worker"
  role          = aws_iam_role.worker.arn
  package_type  = "Image"
  image_uri     = local.image_uri
  architectures = ["arm64"]
  memory_size   = 1024
  timeout       = 900 # the Lambda maximum: free-tier rate limits can make a check slow
  image_config { command = ["papertrail.aws.worker_lambda.handler"] }
  environment { variables = local.common_env }
  depends_on = [aws_cloudwatch_log_group.worker]
  # After the first deploy, GitHub Actions ships new images; Terraform must not roll them back.
  lifecycle { ignore_changes = [image_uri] }
}

resource "aws_lambda_event_source_mapping" "jobs" {
  event_source_arn        = aws_sqs_queue.jobs.arn
  function_name           = aws_lambda_function.worker.arn
  batch_size              = 1
  function_response_types = ["ReportBatchItemFailures"]
  scaling_config { maximum_concurrency = var.worker_max_concurrency }
}

resource "aws_apigatewayv2_api" "http" {
  name          = local.name
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "all" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
  # Throttling caps traffic (and so cost) even if the URL is shared widely.
  default_route_settings {
    throttling_burst_limit = 20
    throttling_rate_limit  = 10
  }
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowHttpApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
