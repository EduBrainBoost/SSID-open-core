import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "secret_scanner.py"


def run_scan(file_content, filename="test.py"):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / filename
        p.write_text(file_content)
        r = subprocess.run(
            ["python", str(SCRIPT), "--repo-root", tmp, "--scan-all", "true"], capture_output=True, text=True
        )
        return r.returncode, json.loads(r.stdout) if r.stdout.strip() else {}


def test_clean_file_passes():
    code, result = run_scan("print('hello world')")
    assert code == 0
    assert result["total_secrets"] == 0


def test_aws_key_detected():
    code, result = run_scan("key = 'AKIAIOSFODNN7EXAMPLE1234'")
    assert code == 1
    assert result["total_secrets"] >= 1
    assert any("aws" in s.get("pattern_name", "").lower() for s in result["secrets"])


def test_github_pat_detected():
    code, result = run_scan("token = 'ghp_" + "a" * 36 + "'")
    assert code == 1


def test_private_key_detected():
    code, result = run_scan("-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----")
    assert code == 1


def test_slack_token_detected():
    code, result = run_scan("slack_token = 'xoxb-123456789-abcdefg'")
    assert code == 1


def test_hash_in_comment_not_secret():
    code, result = run_scan("# sha256: " + "a" * 64)
    assert code == 0
