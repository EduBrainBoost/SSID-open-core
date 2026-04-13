"""ssidctl worker: browser — Playwright/browser automation stub.

Usage:
    python -m ssidctl.commands.browser check --url <url>
    python -m ssidctl.commands.browser screenshot --url <url> --output <path>
    python -m ssidctl.commands.browser status
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime


def _check(args: argparse.Namespace) -> int:
    """Check if a URL is reachable via browser."""
    url = args.url
    timeout = args.timeout

    # Stub: In real implementation uses Playwright with Google Chrome channel
    output = {
        "command": "browser.check",
        "timestamp": datetime.now(UTC).isoformat(),
        "url": url,
        "timeout_ms": timeout,
        "browser": "Google Chrome",
        "channel": "chrome",
        "reachable": None,
        "status_code": None,
        "note": "Playwright not invoked in stub mode. Use --live for real check.",
    }

    if args.live:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(channel="chrome", headless=True)
                page = browser.new_page()
                response = page.goto(url, timeout=timeout)
                output["reachable"] = True
                output["status_code"] = response.status if response else None
                output["note"] = None
                browser.close()
        except ImportError:
            output["reachable"] = False
            output["note"] = "playwright not installed"
            print(json.dumps(output, indent=2), file=sys.stderr)
            return 1
        except Exception as exc:
            output["reachable"] = False
            output["error"] = str(exc)
            print(json.dumps(output, indent=2), file=sys.stderr)
            return 1

    print(json.dumps(output, indent=2))
    return 0


def _screenshot(args: argparse.Namespace) -> int:
    """Take a screenshot of a URL."""
    output = {
        "command": "browser.screenshot",
        "timestamp": datetime.now(UTC).isoformat(),
        "url": args.url,
        "output_path": args.output,
        "status": "stub",
        "note": "Screenshot requires --live flag and Playwright installation",
    }
    print(json.dumps(output, indent=2))
    return 0


def _status(args: argparse.Namespace) -> int:
    """Report browser worker status."""
    output = {
        "command": "browser.status",
        "timestamp": datetime.now(UTC).isoformat(),
        "playwright_installed": False,
        "chrome_available": False,
        "active_sessions": 0,
    }

    try:
        import playwright  # noqa: F401

        output["playwright_installed"] = True
    except ImportError:
        pass

    print(json.dumps(output, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ssidctl-browser",
        description="SSIDCTL Browser Worker — Playwright/browser automation",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    check_p = sub.add_parser("check", help="Check URL reachability")
    check_p.add_argument("--url", required=True, help="URL to check")
    check_p.add_argument("--timeout", type=int, default=30000, help="Timeout in ms")
    check_p.add_argument("--live", action="store_true", help="Actually launch browser")

    screenshot_p = sub.add_parser("screenshot", help="Take screenshot")
    screenshot_p.add_argument("--url", required=True, help="URL to screenshot")
    screenshot_p.add_argument("--output", required=True, help="Output file path")

    sub.add_parser("status", help="Browser worker status")

    args = parser.parse_args(argv)

    dispatch_map = {
        "check": _check,
        "screenshot": _screenshot,
        "status": _status,
    }

    try:
        return dispatch_map[args.action](args)
    except Exception as exc:
        error = {
            "command": f"browser.{args.action}",
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(exc),
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
