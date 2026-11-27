# Storage: DynamoDB (checks), SQS (jobs), S3 (uploads). All pay-per-use: ~$0 when idle.

locals {
  name       = "papertrail-${var.env}"
  account_id = data.aws_caller_identity.me.account_id
  ssm_path   = "/papertrail/${var.env}"
}

resource "aws_dynamodb_table" "checks" {
  name         = "${local.name}-checks"
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
    name = "created_at"
    type = "S"
  }

  # Checks grouped by creator, newest first (only items with a creator handle are indexed)
  global_secondary_index {
    name            = "by_creator"
    projection_type = "ALL"
    key_schema {
      attribute_name = "creator"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "created_at"
      key_type       = "RANGE"
    }
  }

  # Old checks delete themselves (privacy and cost); the app sets expires_at.
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  server_side_encryption { enabled = true }
}

resource "aws_sqs_queue" "jobs_dlq" {
  name                      = "${local.name}-jobs-dlq"
  message_retention_seconds = 1209600 # 14 days to inspect failures
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "jobs" {
  name = "${local.name}-jobs"
  # Longer than the worker's 900 s limit, so a timed-out check is retried after 20 minutes
  # (work is idempotent: a finished check is never overwritten).
  visibility_timeout_seconds = 1200
  message_retention_seconds  = 86400
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_s3_bucket" "media" {
  bucket        = "${local.name}-media-${local.account_id}"
  force_destroy = true # uploads are temporary; lets `make destroy` remove everything
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket                  = aws_s3_bucket.media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "media" {
  bucket = aws_s3_bucket.media.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    id     = "delete-uploads-after-7-days"
    status = "Enabled"
    filter {}
    expiration { days = 7 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
}

resource "aws_s3_bucket_policy" "media_tls_only" {
  bucket = aws_s3_bucket.media.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.media.arn, "${aws_s3_bucket.media.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.media]
}

# Secrets: Terraform creates placeholders only. Real values are set by hand with the AWS CLI
# (see docs/DEPLOY.md), so they never appear in Terraform state or in GitHub.
resource "aws_ssm_parameter" "secret" {
  for_each = toset([
    "PAPERTRAIL_GROQ_API_KEY",
    "PAPERTRAIL_TAVILY_API_KEY",
    "PAPERTRAIL_LANGFUSE_PUBLIC_KEY",
    "PAPERTRAIL_LANGFUSE_SECRET_KEY",
    "PAPERTRAIL_ALPHAVANTAGE_API_KEY",
  ])
  name  = "${local.ssm_path}/${each.key}"
  type  = "SecureString"
  value = "unset"
  lifecycle { ignore_changes = [value] }
}
