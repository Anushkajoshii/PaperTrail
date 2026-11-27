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

variable "github_repo" {
  description = "owner/name allowed to deploy through GitHub OIDC (main branch only)"
  type        = string
  default     = "Anushkajoshii/PaperTrail"
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
