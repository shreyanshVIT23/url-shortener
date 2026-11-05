# URL Shortener

A serverless URL shortener on AWS. API Gateway (HTTP API) sends requests to two Python 3.14 Lambda
functions, short codes are stored in DynamoDB, and a static HTML page served from S3 website hosting
provides the frontend. All infrastructure is plain HCL Terraform in [`infra/`](infra/), and the
Python side is managed with [uv](https://docs.astral.sh/uv/).

## Architecture

```
 Browser ──HTTP──▶ S3 static website (index.html + config.js)
    │
    │  POST /shorten  (CORS: only the S3 website origin)
    ▼
 API Gateway HTTP API ($default stage, throttled 20 rps / burst 50)
    │                         │
    │ POST /shorten           │ GET /{code}
    ▼                         ▼
 Lambda "shorten"          Lambda "redirect"      python3.14 · arm64 · JSON logs
    │  PutItem (conditional)  │  GetItem
    └──────────┬──────────────┘
               ▼
     DynamoDB table "<project>-urls"  (PK: code, on-demand)
```

- **Short codes**: 7 characters of base62 from `secrets` (about 3.5 × 10¹² combinations). Each write
  is a conditional `PutItem`, and a collision is retried up to 5 times.
- **Redirects**: `GET /{code}` returns `301` with a `Location` header, or `404` if the code is unknown.
- **Short URL host**: taken from the request's `requestContext.domainName`, so the Lambda doesn't need
  an env var for its own URL.
- **Dependencies**: boto3 is a runtime dependency and ships in a separate Lambda **layer**, built
  with uv. The function zip holds only `src/lambda/`.
- **Frontend**: Terraform uploads `index.html` and generates `config.js` (`window.API_URL = ...`).
  The site is HTTP only, because S3 website endpoints can't serve HTTPS. The API and the short links
  use HTTPS.

## Project layout

```
.
├── pyproject.toml          # uv project: boto3 runtime dep, dev group (pytest, moto, ruff), tool config
├── uv.lock
├── .python-version         # 3.14, matches the Lambda runtime
├── src/
│   ├── lambda/
│   │   ├── common.py       # DynamoDB table handle, code generator, JSON response helper, logging
│   │   ├── shorten.py      # POST /shorten
│   │   └── redirect.py     # GET /{code}
│   └── s3/
│       └── index.html      # static frontend
├── tests/
│   └── test_handlers.py    # pytest + moto (mocked DynamoDB)
├── infra/                  # Terraform, see infra/README.md
└── .claude/                # goals, decisions, tasks, setup notes, official-docs references
```

## API

### `POST /shorten`

```bash
curl -s -X POST "$API/shorten" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/some/long/path"}'
```

| Status | Body |
|---|---|
| `201` | `{"code": "aB3xK9q", "short_url": "https://<api-domain>/aB3xK9q"}` |
| `400` | `{"error": "Request body must be JSON like {\"url\": \"...\"}"}` or `{"error": "A valid http(s) URL is required"}` |
| `500` | `{"error": "Could not allocate a unique code, try again"}` (all 5 attempts collided) |

A valid URL has an `http` or `https` scheme, a host, and is at most 2048 characters long. Each call
creates a new code, so shortening the same URL twice gives two different codes.

### `GET /{code}`

| Status | Result |
|---|---|
| `301` | `Location: <original URL>` |
| `404` | `{"error": "Not found"}` |

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (it installs Python 3.14 for you)
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.15
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) with
  credentials configured (`aws configure` or SSO)

## Getting started

Run every command from the repo root.

### 1. Install, lint and test

```bash
uv sync                       # creates .venv with runtime + dev dependencies
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Tests use [moto](https://docs.getmoto.org/) to mock DynamoDB, so they need no AWS account.

### 2. Build the Lambda dependency layer

The layer must be built for Linux arm64 and Python 3.14 to match the Lambda runtime:

```bash
rm -rf infra/build/layer infra/build/requirements.txt
uv export --frozen --no-dev --no-editable --no-emit-project -o infra/build/requirements.txt
uv pip install --no-installer-metadata --no-compile-bytecode \
  --python-platform aarch64-manylinux2014 --python 3.14 \
  --target infra/build/layer/python -r infra/build/requirements.txt
```

Rebuild the layer whenever runtime dependencies in `pyproject.toml` change.

### 3. Deploy

```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars   # optional: change region or names
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra init -upgrade
terraform -chdir=infra validate
terraform -chdir=infra plan -out=tfplan
terraform -chdir=infra apply tfplan
```

### 4. Try it

```bash
API=$(terraform -chdir=infra output -raw api_url)
curl -s -X POST "$API/shorten" -H 'Content-Type: application/json' -d '{"url":"https://example.com"}'
curl -i "$API/<code>"                              # expect 301 + Location header
terraform -chdir=infra output -raw website_url     # open in a browser (HTTP)

# Lambda logs are JSON. Pass --region explicitly, because your CLI default may differ from aws_region.
aws logs tail /aws/lambda/url-shortener-shorten --since 10m --region us-east-1
```

### 5. Tear down

```bash
terraform -chdir=infra destroy
```

The S3 bucket has `force_destroy = true`, so `destroy` also removes the site files.

## Configuration

Terraform variables (see [`infra/variables.tf`](infra/variables.tf)):

| Variable | Default | Description |
|---|---|---|
| `aws_region` | `us-east-1` | AWS region to deploy into |
| `project_name` | `url-shortener` | Prefix for all resource names |
| `log_retention_days` | `14` | CloudWatch log retention for the Lambdas |

Outputs: `api_url`, `website_url`, `dynamodb_table`.

The Lambdas read a single environment variable, `TABLE_NAME`, which Terraform sets.

## Development notes

- Python 3.14 is pinned in three places that must agree: `.python-version`, `requires-python` in
  `pyproject.toml`, and `lambda_runtime` in `infra/lambda.tf`.
- `lambda` is a Python keyword, so the handlers are imported as top-level modules
  (`pythonpath = ["src/lambda"]` in the pytest config) instead of as a package.
- Ruff targets the version from `requires-python` and skips the vendored layer in `infra/build/`.
- Terraform state is **local** (`infra/terraform.tfstate`) and git-ignored, along with `*tfplan*`
  and `build/`. Keep the state file safe, or move it to a remote backend before sharing the project.
- Design decisions and the official-docs notes behind them are in [`.claude/decisions.md`](.claude/decisions.md)
  and [`.claude/references/`](.claude/references/).

## Ideas

- Click analytics (atomic counter on redirect)
- Custom aliases and link expiry (DynamoDB TTL)
- Deduplicate identical URLs (idempotent shorten)
- CloudWatch alarms on Lambda errors and API 5xx responses
