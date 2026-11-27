variable "region" {
  description = "AWS region. The Free plan project is fixed to ap-southeast-2 (Sydney)."
  type        = string
  default     = "ap-southeast-2"
}

variable "env" {
  type    = string
  default = "prod"
}

variable "image_tag" {
  description = "Tag of the image in ECR to run (the git commit SHA when deployed from CI)"
  type        = string
  default     = "latest"
}

variable "llm_provider" {
  description = "mock (no key needed) or groq (free key in SSM). Switch to bedrock if AWS unlocks it."
  type        = string
  default     = "groq"
}

variable "search_provider" {
  description = "offline (labelled demo data) or tavily (live web search, free key in SSM)"
  type        = string
  default     = "offline"
}

variable "price_provider" {
  description = "Prices for the Claim Ledger: none, or alphavantage (free key in SSM, 25 requests a day)"
  type        = string
  default     = "alphavantage" # without a key in SSM this falls back to none
}

variable "github_oidc_subject" {
  description = <<-EOT
    The repository part of GitHub's OIDC "sub" claim. This repository uses GitHub's immutable
    subject format (owner and repo with their numeric ids), so a renamed or re-created
    repository with the same name can never deploy. See it with:
    gh api repos/OWNER/REPO/actions/oidc/customization/sub
  EOT
  type        = string
  default     = "repo:Anushkajoshii@89680319/PaperTrail@1473509764"
}

variable "budget_email" {
  description = "Email for budget alerts. Empty: no budget is created. Set it in terraform.tfvars (git-ignored)."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  type    = number
  default = 5
}

variable "worker_max_concurrency" {
  description = "Checks running at once. Low on purpose: protects the free Groq rate limit and cost."
  type        = number
  default     = 2
}

variable "log_retention_days" {
  type    = number
  default = 14
}
