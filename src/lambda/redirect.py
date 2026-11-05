"""GET /{code} -- redirect a short code to its original URL."""

from typing import Any

from common import get_table, json_response


def resolve_code(code: str) -> str | None:
    """Return the long URL stored for code, or None if it doesn't exist."""
    item = get_table().get_item(Key={"code": code}).get("Item")
    return item["url"] if item else None


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    code = (event.get("pathParameters") or {}).get("code")
    url = resolve_code(code) if code else None
    if url is None:
        return json_response(404, {"error": "Not found"})

    return {"statusCode": 301, "headers": {"Location": url}, "body": ""}
