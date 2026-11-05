"""Shared helpers for the URL shortener Lambda handlers."""

import json
import logging
import os
import secrets
import string
from functools import cache
from typing import Any

import boto3

CODE_ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7

# Lambda's JSON log format (logging_config in infra/lambda.tf) formats stdlib log records,
# and application_log_level sets the level.
logger = logging.getLogger()
# botocore logs INFO noise (e.g. "Found credentials...") on cold start; keep only its warnings.
logging.getLogger("botocore").setLevel(logging.WARNING)


@cache
def get_table():
    """Return the DynamoDB table, created once and reused across warm invocations."""
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def generate_code(length: int = CODE_LENGTH) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def json_response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
