output "api_url" {
  description = "Base URL of the HTTP API (short links live here)"
  value       = trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")
}

output "website_url" {
  description = "Static frontend hosted on the S3 website endpoint (HTTP only)"
  value       = "http://${aws_s3_bucket_website_configuration.site.website_endpoint}"
}

output "dynamodb_table" {
  description = "Name of the DynamoDB table holding short codes"
  value       = aws_dynamodb_table.urls.name
}
