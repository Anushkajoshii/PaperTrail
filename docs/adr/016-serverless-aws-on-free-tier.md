# ADR-016: Serverless AWS deployment that costs ~$0, with a free AI provider

- **Status:** Accepted
- **Date:** 2026-11-27

## Context

PaperTrail needs a public deployment for a portfolio. The AWS account is a new Free plan
"project". It is fixed to `ap-southeast-2`, has no IAM Identity Center or Organizations, and its
Bedrock access to Anthropic models is currently withheld ("reduced quotas"). The budget for
paid APIs is zero. Secrets must never reach GitHub.

## Decision

- **Compute:** one container image (ECR, arm64) running two Lambda functions. The API function
  serves FastAPI under `/api` and the built React app at `/`, behind an API Gateway HTTP API.
  The worker function is triggered by SQS, one check per message, with partial batch failures
  and a dead-letter queue after 3 tries.
- **Data:** DynamoDB on-demand, holding compressed check JSON with a sparse `by_creator` index
  and a 180-day TTL. Uploads go to a private, encrypted S3 bucket and expire after 7 days.
- **AI:** the existing pluggable provider gains a `groq` preset. It uses the free tier, with
  `gpt-oss-20b` to extract and `gpt-oss-120b` to judge. If a model can't follow a JSON schema it
  falls back to JSON mode, and it waits and retries on rate limits. Bedrock stays one setting
  away.
- **Secrets:** Terraform creates SSM SecureString placeholders and ignores their values. Real
  values are pushed from the local `.env` by a script that never prints them. Lambdas load only
  `PAPERTRAIL_*` names at cold start.
- **Deploys:** GitHub Actions authenticates through OIDC to a role limited to pushing the image
  and updating the two functions, and only from `main`. Terraform runs locally with remote
  state in S3 (`use_lockfile`), so infrastructure changes always need a human `yes`.
- **Cost guards:** no always-on resources. API Gateway is throttled and worker concurrency is
  set to 2. Logs are kept for 14 days, ECR keeps the last 5 images, and an optional $5 budget
  sends email alerts.

## Consequences

- Serving the web app from Lambda avoids CloudFront, CORS and a second hosting service. The
  trade-off is cold starts on first load and a 4 MB upload limit (Lambda's 6 MB request cap).
- Open models on Groq are weaker than Claude, so the code-enforced rules (grounding, citations,
  confidence caps) matter even more. The eval harness can compare providers.
- The free tier's rate limits make bursts slower: requests wait and retry rather than fail.
- CI deploys code but never changes infrastructure, which keeps the deploy role's permissions
  small.

## In plain English

The app lives on AWS without any server running all the time, so it costs almost nothing when
nobody is using it. The AI comes from a free service. Passwords and keys are kept in AWS's
locked storage, never in the code, and new versions go live automatically when code is merged.
