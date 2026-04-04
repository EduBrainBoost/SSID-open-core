"""Tests for SSID CLI."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ssid_cli import SSIDCLI


def test_commands():
    cli = SSIDCLI()
    r = cli.execute("version")
    assert r["cli_version"] == "1.0.0"
    r = cli.execute("health")
    assert r["status"] == "healthy"
    r = cli.execute("status")
    assert r["roots"] == 24
    r = cli.execute("did:create", key_type="EC-P256")
    assert r["did"].startswith("did:ssid:")
    r = cli.execute("unknown_cmd")
    assert "error" in r
    assert cli.history_count == 5
    print("PASS: test_commands")


if __name__ == "__main__":
    test_commands()
    print("\nALL TESTS PASSED")
