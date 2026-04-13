import pytest
from pydantic import ValidationError
from ssid_autorunner.models import AutoRunnerPayload, StatusCode


def test_valid_payload_accepted():
    payload = AutoRunnerPayload(
        run_id="550e8400-e29b-41d4-a716-446655440000",
        autorunner_id="AR-07",
        trigger="push",
        repo="SSID",
        branch="main",
        commit_sha="a" * 40,
    )
    assert payload.autorunner_id == "AR-07"


def test_invalid_commit_sha_rejected():
    with pytest.raises(ValidationError):
        AutoRunnerPayload(
            run_id="550e8400-e29b-41d4-a716-446655440000",
            autorunner_id="AR-07",
            trigger="push",
            repo="SSID",
            commit_sha="not-a-sha",
        )


def test_invalid_autorunner_id_rejected():
    with pytest.raises(ValidationError):
        AutoRunnerPayload(
            run_id="550e8400-e29b-41d4-a716-446655440000",
            autorunner_id="AR-99",
            trigger="push",
            repo="SSID",
            commit_sha="a" * 40,
        )


def test_status_codes_complete():
    expected = {
        "PASS",
        "FAIL_POLICY",
        "FAIL_SOT",
        "FAIL_QA",
        "FAIL_DUPLICATE",
        "FAIL_SCOPE",
        "FAIL_FORBIDDEN",
        "FAIL_FRESHNESS",
        "FAIL_DORA",
        "FAIL_SHARD",
        "ERROR",
    }
    assert set(s.value for s in StatusCode) == expected
