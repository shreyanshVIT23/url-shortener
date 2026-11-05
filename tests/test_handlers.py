import json

import boto3
import pytest
from moto import mock_aws

TABLE_NAME = "test-urls"


@pytest.fixture
def table(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", TABLE_NAME)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")

    import common

    with mock_aws():
        common.get_table.cache_clear()
        tbl = boto3.resource("dynamodb").create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "code", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "code", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield tbl
        common.get_table.cache_clear()


def _shorten_event(body):
    return {"body": json.dumps(body), "requestContext": {"domainName": "abc.example.com"}}


def test_shorten_valid_url(table):
    import shorten

    resp = shorten.handler(_shorten_event({"url": "https://example.com/path"}), None)

    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert len(body["code"]) == 7
    assert body["short_url"] == f"https://abc.example.com/{body['code']}"
    item = table.get_item(Key={"code": body["code"]})["Item"]
    assert item["url"] == "https://example.com/path"


@pytest.mark.parametrize("url", ["not-a-url", "ftp://example.com", "", None, 42])
def test_shorten_invalid_url(table, url):
    import shorten

    resp = shorten.handler(_shorten_event({"url": url}), None)

    assert resp["statusCode"] == 400


def test_shorten_invalid_json(table):
    import shorten

    resp = shorten.handler({"body": "{not json"}, None)

    assert resp["statusCode"] == 400


def test_create_short_link_gives_up_after_collisions(table, monkeypatch):
    import shorten

    table.put_item(Item={"code": "taken00", "url": "https://example.com"})
    monkeypatch.setattr(shorten, "generate_code", lambda: "taken00")

    assert shorten.create_short_link("https://example.org") is None


def test_redirect_hit(table):
    import redirect

    table.put_item(Item={"code": "abc1234", "url": "https://example.com"})

    resp = redirect.handler({"pathParameters": {"code": "abc1234"}}, None)

    assert resp["statusCode"] == 301
    assert resp["headers"]["Location"] == "https://example.com"


def test_redirect_miss(table):
    import redirect

    resp = redirect.handler({"pathParameters": {"code": "missing"}}, None)

    assert resp["statusCode"] == 404
