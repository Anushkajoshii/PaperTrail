"""AWS adapters and Lambda entry points, tested against moto (a local fake of AWS: no account,
no network, no cost)."""

import json
import os

import boto3
import pytest
from moto import mock_aws

from papertrail.aws import worker_lambda
from papertrail.aws.secrets import load_secrets_from_env, load_ssm_secrets
from papertrail.config import Settings
from papertrail.ledger.store import DynamoDbLedgerStore
from papertrail.models import Check, CheckInput, CheckStatus, InputKind
from papertrail.store import (
    DynamoDbCheckStore,
    S3UploadStorage,
    SqsJobQueue,
    UploadError,
    get_check_store,
    get_job_queue,
    get_upload_storage,
)

REGION = "ap-southeast-2"


@pytest.fixture(autouse=True)
def fake_aws(monkeypatch):
    for k, v in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": REGION,
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        yield


def make_table():
    ddb = boto3.resource("dynamodb", region_name=REGION)
    return ddb.create_table(
        TableName="checks",
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "creator", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by_creator",
                "KeySchema": [
                    {"AttributeName": "creator", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )


def make_ledger_table():
    ddb = boto3.resource("dynamodb", region_name=REGION)
    return ddb.create_table(
        TableName="ledger",
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "creator", "AttributeType": "S"},
            {"AttributeName": "made_on", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by_creator",
                "KeySchema": [
                    {"AttributeName": "creator", "KeyType": "HASH"},
                    {"AttributeName": "made_on", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )


def new_check(handle=None, text="Nifty hit 26,000."):
    return Check(input=CheckInput(kind=InputKind.TEXT, text=text, creator_handle=handle))


def test_dynamodb_store_roundtrip_status_and_creator_index():
    store = DynamoDbCheckStore(make_table())
    a, b, other = new_check("@Demo"), new_check("demo"), new_check("@else")
    for c in (a, b, other):
        store.save(c)
    assert store.get(a.id) == a and store.get("chk_missing") is None
    store.set_status(a.id, CheckStatus.RESEARCHING, "round 1")
    assert store.get(a.id).status_detail == "round 1"
    assert {c.id for c in store.list_by_creator("@DEMO")} == {a.id, b.id}


def test_dynamodb_store_never_overwrites_a_finished_check():
    store = DynamoDbCheckStore(make_table())
    c = new_check()
    store.save(c.model_copy(update={"status": CheckStatus.FAILED, "error": "boom"}))
    store.set_status(c.id, CheckStatus.RESEARCHING)
    assert store.get(c.id).status is CheckStatus.FAILED


def test_dynamodb_store_compresses_large_checks_and_sets_ttl():
    table = make_table()
    store = DynamoDbCheckStore(table, retention_days=30)
    c = new_check(text="Nifty will double. " * 2500)  # ~47 KB of text
    store.save(c)
    item = table.get_item(Key={"id": c.id})["Item"]
    assert len(item["body"].value) < 5_000
    assert int(item["expires_at"]) > int(c.created_at.timestamp())
    assert "creator" not in item  # sparse index: no handle, no index entry
    assert store.get(c.id) == c


def test_sqs_queue_roundtrip_and_malformed_jobs():
    sqs = boto3.client("sqs", region_name=REGION)
    url = sqs.create_queue(QueueName="jobs")["QueueUrl"]
    q = SqsJobQueue(sqs, url)
    q.enqueue("chk_abc")
    assert q.claim() == "chk_abc"
    q.complete("chk_abc")
    assert q.claim() is None
    q.fail("chk_unknown")  # no-op


def test_s3_uploads_validate_and_roundtrip():
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket="media", CreateBucketConfiguration={"LocationConstraint": REGION})
    store = S3UploadStorage(s3, "media", max_bytes=1000)
    key = store.save("talk.srt", b"1\n00:00:01,000 --> 00:00:02,000\nhello\n")
    assert key.startswith("uploads/") and key.endswith(".srt")
    assert "hello" in store.read_text(key)
    with pytest.raises(UploadError, match="Unknown upload"):
        store.read_text("../../etc/passwd")
    with pytest.raises(UploadError, match="limit"):
        store.save("clip.mp4", b"x" * 1001)


def test_factories_pick_aws_backends_from_settings():
    make_table()
    sqs_url = boto3.client("sqs", region_name=REGION).create_queue(QueueName="q")["QueueUrl"]
    s = Settings(
        _env_file=None,
        aws_region=REGION,
        store_backend="dynamodb",
        dynamodb_table="checks",
        queue_mode="sqs",
        sqs_queue_url=sqs_url,
        upload_backend="s3",
        media_bucket="media",
    )
    assert isinstance(get_check_store(s), DynamoDbCheckStore)
    assert isinstance(get_job_queue(s), SqsJobQueue)
    assert isinstance(get_upload_storage(s), S3UploadStorage)
    for bad in (
        {"store_backend": "dynamodb"},
        {"queue_mode": "sqs"},
        {"upload_backend": "s3"},
        {"queue_mode": "carrier-pigeon"},
    ):
        with pytest.raises(ValueError):
            fn = (
                get_check_store
                if "store_backend" in bad
                else get_upload_storage
                if "upload_backend" in bad
                else get_job_queue
            )
            fn(Settings(_env_file=None, **bad))


def test_ssm_secrets_are_loaded_only_for_papertrail_names(monkeypatch):
    ssm = boto3.client("ssm", region_name=REGION)
    for name, value in {
        "/papertrail/prod/PAPERTRAIL_GROQ_API_KEY": "gsk_fake",
        "/papertrail/prod/PATH": "/evil",
        "/papertrail/prod/PAPERTRAIL_TAVILY_API_KEY": "unset",
    }.items():
        ssm.put_parameter(Name=name, Value=value, Type="SecureString")
    # Register the variable with monkeypatch first so it is removed again after the test.
    monkeypatch.setenv("PAPERTRAIL_GROQ_API_KEY", "placeholder")
    monkeypatch.delenv("PAPERTRAIL_GROQ_API_KEY")
    path_before = os.environ["PATH"]
    assert load_ssm_secrets("/papertrail/prod", ssm) == ["PAPERTRAIL_GROQ_API_KEY"]
    assert os.environ["PAPERTRAIL_GROQ_API_KEY"] == "gsk_fake"
    assert os.environ["PATH"] == path_before
    monkeypatch.delenv("PAPERTRAIL_GROQ_API_KEY")
    monkeypatch.setenv("PAPERTRAIL_SSM_SECRETS_PATH", "/papertrail/prod")
    assert load_secrets_from_env() == ["PAPERTRAIL_GROQ_API_KEY"]
    monkeypatch.delenv("PAPERTRAIL_SSM_SECRETS_PATH")
    assert load_secrets_from_env() == []


def test_worker_lambda_runs_checks_and_reports_failures(monkeypatch):
    store = DynamoDbCheckStore(make_table())
    good = new_check("@demo", "Nifty 50 gave 300% returns in 2023. Guaranteed profit daily!")
    store.save(good)
    calls = []

    def fake_process(check_id, store_, make_deps, ledger):
        calls.append(check_id)
        if check_id == "chk_boom":
            raise RuntimeError("model down")

    monkeypatch.setattr(worker_lambda, "_runtime", lambda: (store, None, None))
    monkeypatch.setattr(worker_lambda, "process_check", fake_process)
    event = {
        "Records": [
            {"messageId": "1", "body": json.dumps({"check_id": good.id})},
            {"messageId": "2", "body": json.dumps({"check_id": "chk_boom"})},
            {"messageId": "3", "body": "not json"},
            {"messageId": "4", "body": json.dumps({"check_id": "rm -rf"})},
        ]
    }
    assert worker_lambda.handler(event) == {"batchItemFailures": [{"itemIdentifier": "2"}]}
    assert calls == [good.id, "chk_boom"]


def test_worker_lambda_end_to_end_with_mock_llm(monkeypatch):
    monkeypatch.setenv("PAPERTRAIL_STORE_BACKEND", "dynamodb")
    monkeypatch.setenv("PAPERTRAIL_DYNAMODB_TABLE", "checks")
    monkeypatch.setenv("PAPERTRAIL_LEDGER_TABLE", "ledger")
    monkeypatch.setenv("PAPERTRAIL_AWS_REGION", REGION)
    from papertrail.config import get_settings

    get_settings.cache_clear()
    worker_lambda._runtime.cache_clear()
    try:
        store = DynamoDbCheckStore(make_table())
        ledger = DynamoDbLedgerStore(make_ledger_table())
        c = new_check(
            "@demo", "Nifty 50 gave 300% returns in 2023. KESTREL ka target ₹1500 hai, March tak."
        )
        store.save(c)
        out = worker_lambda.handler(
            {"Records": [{"messageId": "1", "body": json.dumps({"check_id": c.id})}]}
        )
        assert out == {"batchItemFailures": []}
        done = store.get(c.id)
        assert done.status is CheckStatus.COMPLETED and done.claims
        (tracked,) = ledger.list_by_creator("demo")  # the stock call is now in the ledger
        assert tracked.ticker == "KESTREL" and tracked.target_price == 1500
    finally:
        get_settings.cache_clear()
        worker_lambda._runtime.cache_clear()


def test_push_secrets_sends_only_known_names_and_never_prints_values(tmp_path, capsys):
    from scripts.push_secrets import main

    env = tmp_path / ".env"
    env.write_text(
        "PAPERTRAIL_LLM_PROVIDER=groq\nPAPERTRAIL_GROQ_API_KEY='gsk_secret_value'\n"
        "# comment\nPAPERTRAIL_TAVILY_API_KEY=\nOTHER_SECRET=nope\n"
    )
    ssm = boto3.client("ssm", region_name=REGION)
    assert main(["--env-file", str(env)], ssm=ssm) == 0
    got = ssm.get_parameter(Name="/papertrail/prod/PAPERTRAIL_GROQ_API_KEY", WithDecryption=True)
    assert got["Parameter"]["Value"] == "gsk_secret_value"
    out = capsys.readouterr().out
    assert "gsk_secret_value" not in out and "16 characters" in out
    names = [p["Name"] for p in ssm.describe_parameters()["Parameters"]]
    assert names == ["/papertrail/prod/PAPERTRAIL_GROQ_API_KEY"]
    env.write_text("NOTHING=here\n")
    assert main(["--env-file", str(env)], ssm=ssm) == 1


def test_dynamodb_list_recent_reads_all_pages_newest_first():
    store = DynamoDbCheckStore(make_table())
    checks = [new_check(f"@c{i}") for i in range(5)]
    for c in checks:
        store.save(c)
    assert [c.id for c in store.list_recent(3)] == [c.id for c in reversed(checks)][:3]


def test_dynamodb_ledger_store_and_daily_lambda(monkeypatch):
    from datetime import date

    from papertrail.aws import ledger_lambda
    from papertrail.config import get_settings
    from papertrail.ledger.models import LedgerEntry, LedgerStatus

    ledger = DynamoDbLedgerStore(make_ledger_table())
    base = dict(
        check_id="chk_1",
        claim_id="clm_1",
        ticker="KESTREL",
        claim_text="t",
        quote="q",
        target_price=1500.0,
        made_on=date(2026, 7, 1),
        due_on=date(2027, 3, 31),
        deadline_stated=True,
    )
    ledger.save(LedgerEntry(id="led_a", creator="demo", **base))
    ledger.save(LedgerEntry(id="led_b", status=LedgerStatus.MISSED, **base))
    assert ledger.get("led_a").creator == "demo" and ledger.get("led_zz") is None
    assert [e.id for e in ledger.list_by_creator("demo")] == ["led_a"]
    assert [e.id for e in ledger.list_active()] == ["led_a"]
    assert {e.id for e in ledger.list_recent()} == {"led_a", "led_b"}

    for k, v in {
        "PAPERTRAIL_STORE_BACKEND": "dynamodb",
        "PAPERTRAIL_DYNAMODB_TABLE": "checks",
        "PAPERTRAIL_LEDGER_TABLE": "ledger",
        "PAPERTRAIL_PRICE_PROVIDER": "offline",
    }.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    try:
        summary = ledger_lambda.handler({}, None)
    finally:
        get_settings.cache_clear()
    assert summary["tickers"] == 1
    assert ledger.get("led_a").status in (LedgerStatus.OPEN, LedgerStatus.HIT)
