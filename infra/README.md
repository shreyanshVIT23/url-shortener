# Infrastructure

Plain HCL Terraform for the URL shortener. Run commands from the repo root with
`terraform -chdir=infra ...`. The full build and deploy steps are in the [root README](../README.md).

## Requirements

| Name | Version |
|---|---|
| Terraform | `>= 1.15` |
| `hashicorp/aws` | `~> 6.72` |
| `hashicorp/archive` | `~> 2.8` |

Before you run `plan`, build the Lambda layer into `build/layer/python` (step 2 in the root README).
The `deps_layer` archive zips that directory.

## Files

| File | Resources |
|---|---|
| `versions.tf` | `terraform` block: required Terraform and provider versions |
| `providers.tf` | AWS provider with `default_tags` (`Project`, `ManagedBy`) |
| `variables.tf` | `aws_region`, `project_name`, `log_retention_days` |
| `dynamodb.tf` | `<project>-urls` table, hash key `code` (S), `PAY_PER_REQUEST` |
| `lambda.tf` | Code zip and layer zip (`archive_file`), IAM role (basic logs + `GetItem`/`PutItem` on the table), log groups, deps layer, and the `shorten` and `redirect` functions (python3.14, arm64, 128 MB, 5 s, JSON logging) |
| `apigw.tf` | HTTP API with CORS for the S3 site origin, a proxy integration (payload v2.0) and a route for each function, the `$default` stage (auto-deploy, 20 rps / burst 50), and invoke permissions |
| `s3.tf` | Site bucket (`<project>-site-*`), website config, `BucketOwnerEnforced` ownership, public access block (policies allowed, ACLs blocked), public-read policy, `index.html` and a generated `config.js` |
| `outputs.tf` | `api_url`, `website_url`, `dynamodb_table` |
| `terraform.tfvars.example` | Copy to `terraform.tfvars` to override the defaults |

## Generated, git-ignored files

- `build/lambda.zip`, `build/layer.zip`, `build/layer/`, `build/requirements.txt`
- `terraform.tfstate*` (local state, no remote backend)
- `tfplan`

## Commands

```bash
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra init -upgrade
terraform -chdir=infra validate
terraform -chdir=infra plan -out=tfplan
terraform -chdir=infra apply tfplan
terraform -chdir=infra output
terraform -chdir=infra destroy
```
