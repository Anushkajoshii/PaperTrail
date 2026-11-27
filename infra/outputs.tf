output "app_url" {
  description = "The live app (web at /, API at /api, API docs at /api/docs)"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "api_function" {
  value = aws_lambda_function.api.function_name
}

output "worker_function" {
  value = aws_lambda_function.worker.function_name
}

output "github_deploy_role_arn" {
  description = "Set as the AWS_DEPLOY_ROLE_ARN variable in the GitHub repository"
  value       = aws_iam_role.github_deploy.arn
}

output "ssm_secrets_path" {
  value = local.ssm_path
}

output "jobs_dlq_url" {
  description = "Failed checks land here after 3 tries"
  value       = aws_sqs_queue.jobs_dlq.url
}

output "ledger_function" {
  value = aws_lambda_function.ledger.function_name
}
