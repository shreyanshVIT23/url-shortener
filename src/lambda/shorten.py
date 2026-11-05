"""POST /shorten -- store a long URL and return its short code."""

import base64
import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from botocore.exceptions import ClientError

from common import generate_code, get_table, json_response, logger

MAX_ATTEMPTS = 5
MAX_URL_LENGTH = 2048


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()
    return json.loads(body)


def is_valid_url(url: object) -> bool:
    if not isinstance(url, str) or len(url) > MAX_URL_LENGTH:
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def create_short_link(url: str) -> str | None:
    """Store url under a new unique code and return the code, or None if every attempt collided."""
    table = get_table()
    for _ in range(MAX_ATTEMPTS):
        code = generate_code()
        try:
            table.put_item(
                Item={
                    "code": code,
                    "url": url,
                    "created_at": datetime.now(UTC).isoformat(),
                },
                ConditionExpression="attribute_not_exists(code)",
            )
        except ClientError as err:
            if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning("Short code collision, retrying", extra={"code": code})
                continue
            raise
        return code
    return None


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        url = _parse_body(event).get("url")
    except ValueError, AttributeError:
        return json_response(400, {"error": 'Request body must be JSON like {"url": "..."}'})

    if not is_valid_url(url):
        return json_response(400, {"error": "A valid http(s) URL is required"})

    code = create_short_link(url)
    if code is None:
        logger.error("Could not allocate a unique short code", extra={"attempts": MAX_ATTEMPTS})
        return json_response(500, {"error": "Could not allocate a unique code, try again"})

    logger.info("Created short link", extra={"code": code})
    domain = event.get("requestContext", {}).get("domainName", "")
    return json_response(201, {"code": code, "short_url": f"https://{domain}/{code}"})
