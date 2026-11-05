locals {
  functions = {
    shorten  = "shorten.handler"
    redirect = "redirect.handler"
  }

  lambda_runtime      = "python3.14"
  lambda_architecture = "arm64"
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../src/lambda"
  output_path = "${path.module}/build/lambda.zip"
  excludes    = ["__pycache__", "__pycache__/**"]
}

# Runtime dependencies (boto3) installed by `uv pip install --target build/layer/python`.
data "archive_file" "deps_layer" {
  type        = "zip"
  source_dir  = "${path.module}/build/layer"
  output_path = "${path.module}/build/layer.zip"
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "dynamodb" {
  statement {
    actions   = ["dynamodb:PutItem", "dynamodb:GetItem"]
    resources = [aws_dynamodb_table.urls.arn]
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.project_name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "dynamodb" {
  name   = "${var.project_name}-dynamodb"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.dynamodb.json
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each = local.functions

  name              = "/aws/lambda/${var.project_name}-${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_layer_version" "deps" {
  layer_name               = "${var.project_name}-deps"
  filename                 = data.archive_file.deps_layer.output_path
  source_code_hash         = data.archive_file.deps_layer.output_base64sha256
  compatible_runtimes      = [local.lambda_runtime]
  compatible_architectures = [local.lambda_architecture]
}

resource "aws_lambda_function" "this" {
  for_each = local.functions

  function_name = "${var.project_name}-${each.key}"
  role          = aws_iam_role.lambda.arn
  runtime       = local.lambda_runtime
  architectures = [local.lambda_architecture]
  handler       = each.value
  filename      = data.archive_file.lambda.output_path
  code_sha256   = data.archive_file.lambda.output_base64sha256
  layers        = [aws_lambda_layer_version.deps.arn]
  timeout       = 5
  memory_size   = 128

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.urls.name
    }
  }

  logging_config {
    log_format            = "JSON"
    application_log_level = "INFO"
    system_log_level      = "WARN"
    log_group             = aws_cloudwatch_log_group.lambda[each.key].name
  }

  depends_on = [aws_iam_role_policy_attachment.lambda_logs]
}
