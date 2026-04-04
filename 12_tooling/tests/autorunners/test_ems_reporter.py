"""Tests for ems_reporter — fire-and-forget HTTP reporter."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import contextlib

from ssid_autorunner.ems_reporter import EMSReporterResult, post_result

SSID_ROOT = Path(__file__).parent.parent.parent.parent


def test_post_result_success():
    """Successful POST returns EMSReporterResult with sent=True."""
    mock_response = MagicMock()
    mock_response.status = 201
    mock_response.read.return_value = b'{"status":"created","run_id":"abc"}'
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = post_result(
            ems_url="http://localhost:8000",
            ar_id="AR-01",
            run_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            result={"status": "PASS", "total_findings": 0},
            commit_sha="a" * 40,
        )

    assert result.sent is True
    assert result.status_code == 201


def test_ems_unavailable_does_not_raise():
    """Connection error → sent=False, no exception raised."""
    from urllib.error import URLError

    with patch("urllib.request.urlopen", side_effect=URLError("Connection refused")):
        result = post_result(
            ems_url="http://localhost:8000",
            ar_id="AR-01",
            run_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            result={"status": "PASS"},
            commit_sha="a" * 40,
        )

    assert result.sent is False
    assert "Connection refused" in (result.error or "")


def test_timeout_does_not_raise():
    """Timeout → sent=False, no exception."""

    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        result = post_result(
            ems_url="http://localhost:8000",
            ar_id="AR-01",
            run_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            result={"status": "FAIL_POLICY"},
            commit_sha="a" * 40,
        )

    assert result.sent is False


def test_empty_ems_url_skips_silently():
    """When ems_url is empty, sent=False with no HTTP call."""
    with patch("urllib.request.urlopen") as mock_open:
        result = post_result(
            ems_url="",
            ar_id="AR-01",
            run_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            result={"status": "PASS"},
            commit_sha="a" * 40,
        )
    mock_open.assert_not_called()
    assert result.sent is False


def test_pii_scan_with_ems_url_calls_post_result(tmp_path):
    """When pii_regex_scan.py is invoked with --ems-url, ems_reporter.post_result is called."""
    clean = tmp_path / "clean.py"
    clean.write_text("x = 1\n")
    out = tmp_path / "result.json"

    # Ensure ems_reporter is in sys.modules before patching
    import ssid_autorunner.ems_reporter  # noqa: F401

    posted = []

    def fake_post(ems_url, ar_id, run_id, result, commit_sha, **kwargs):
        posted.append({"ems_url": ems_url, "ar_id": ar_id, "status": result.get("status")})
        return EMSReporterResult(sent=True, status_code=201)

    spec = importlib.util.spec_from_file_location(
        "pii_regex_scan_test",
        str(SSID_ROOT / "23_compliance" / "scripts" / "pii_regex_scan.py"),
    )
    mod = importlib.util.module_from_spec(spec)

    with (
        patch(
            "sys.argv",
            [
                "pii_regex_scan.py",
                "--files",
                str(clean),
                "--out",
                str(out),
                "--ems-url",
                "http://localhost:8000",
                "--run-id",
                "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "--commit-sha",
                "a" * 40,
            ],
        ),
        patch.object(sys.modules["ssid_autorunner.ems_reporter"], "post_result", side_effect=fake_post),
    ):
        spec.loader.exec_module(mod)
        with contextlib.suppress(SystemExit):
            mod.main()

    assert len(posted) == 1, "post_result must be called exactly once"
    assert posted[0]["ar_id"] == "AR-01"
    assert posted[0]["status"] == "PASS"
    assert posted[0]["ems_url"] == "http://localhost:8000"
