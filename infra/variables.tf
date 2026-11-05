variable "aws_region" {
  type        = string
  description = "AWS region to deploy into"
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Prefix used for naming all resources"
  default     = "url-shortener"
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention for the Lambda functions"
  default     = 14
}
