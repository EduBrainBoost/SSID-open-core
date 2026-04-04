#!/usr/bin/env python3
"""Load Test Framework Stub — lightweight HTTP load testing for SSID endpoints.

Provides a simple, zero-external-dependency load test runner that measures
latency and error rates for SSID service endpoints.

Usage:
  python 12_tooling/cli/load_test_stub.py --target http://localhost:8080/health
  python 12_tooling/cli/load_test_stub.py --config scenarios.json
  python 12_tooling/cli/load_test_stub.py --target http://localhost:8080 --users 10 --duration 30

Exit codes:
  0 = all scenarios completed within thresholds
  1 = one or more scenarios exceeded error/latency thresholds
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class LoadTestScenario:
    """Definition of a single load test scenario."""

    name: str
    target_url: str
    concurrent_users: int = 5
    duration_seconds: int = 10
    method: str = "GET"
    timeout_seconds: float = 10.0
    max_error_rate: float = 0.05  # 5% threshold
    max_p95_latency_ms: float = 2000.0  # 2s threshold

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoadTestScenario:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class RequestResult:
    """Result of a single HTTP request."""

    status_code: int
    latency_ms: float
    error: str = ""
    timestamp: str = ""


@dataclass
class ScenarioResult:
    """Aggregate result of a load test scenario."""

    scenario_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    mean_latency_ms: float = 0.0
    median_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    duration_seconds: float = 0.0
    requests_per_second: float = 0.0
    passed: bool = True
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _make_request(url: str, method: str = "GET", timeout: float = 10.0) -> RequestResult:
    """Execute a single HTTP request and measure latency."""
    ts = datetime.now(UTC).isoformat()
    start = time.monotonic()
    try:
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _ = resp.read()
            elapsed = (time.monotonic() - start) * 1000
            return RequestResult(
                status_code=resp.status,
                latency_ms=round(elapsed, 2),
                timestamp=ts,
            )
    except urllib.error.HTTPError as exc:
        elapsed = (time.monotonic() - start) * 1000
        return RequestResult(
            status_code=exc.code,
            latency_ms=round(elapsed, 2),
            error=str(exc),
            timestamp=ts,
        )
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        return RequestResult(
            status_code=0,
            latency_ms=round(elapsed, 2),
            error=str(exc),
            timestamp=ts,
        )


def _percentile(data: list[float], pct: float) -> float:
    """Calculate the p-th percentile of a sorted list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (pct / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


class LoadTestRunner:
    """Runs load test scenarios and collects metrics."""

    def __init__(self, scenarios: list[LoadTestScenario] | None = None) -> None:
        self.scenarios: list[LoadTestScenario] = scenarios or []
        self.results: list[ScenarioResult] = []

    def add_scenario(self, scenario: LoadTestScenario) -> None:
        self.scenarios.append(scenario)

    def run_scenario(self, scenario: LoadTestScenario) -> ScenarioResult:
        """Run a single load test scenario."""
        request_results: list[RequestResult] = []
        start_time = time.monotonic()
        end_time = start_time + scenario.duration_seconds

        with ThreadPoolExecutor(max_workers=scenario.concurrent_users) as pool:
            futures = []
            while time.monotonic() < end_time:
                # Submit requests up to concurrent_users limit
                while len(futures) < scenario.concurrent_users:
                    fut = pool.submit(
                        _make_request,
                        scenario.target_url,
                        scenario.method,
                        scenario.timeout_seconds,
                    )
                    futures.append(fut)

                # Collect completed futures
                done = []
                for fut in futures:
                    if fut.done():
                        try:
                            request_results.append(fut.result())
                        except Exception as exc:
                            request_results.append(RequestResult(status_code=0, latency_ms=0, error=str(exc)))
                        done.append(fut)
                for d in done:
                    futures.remove(d)

                # Brief pause to avoid busy-loop
                time.sleep(0.01)

            # Collect remaining futures
            for fut in as_completed(futures, timeout=scenario.timeout_seconds):
                try:
                    request_results.append(fut.result())
                except Exception as exc:
                    request_results.append(RequestResult(status_code=0, latency_ms=0, error=str(exc)))

        actual_duration = time.monotonic() - start_time

        # Compute metrics
        total = len(request_results)
        successful = sum(1 for r in request_results if 200 <= r.status_code < 400)
        failed = total - successful
        latencies = [r.latency_ms for r in request_results if r.latency_ms > 0]
        errors = [r.error for r in request_results if r.error]

        error_rate = failed / total if total > 0 else 0.0

        result = ScenarioResult(
            scenario_name=scenario.name,
            total_requests=total,
            successful_requests=successful,
            failed_requests=failed,
            error_rate=round(error_rate, 4),
            min_latency_ms=round(min(latencies), 2) if latencies else 0.0,
            max_latency_ms=round(max(latencies), 2) if latencies else 0.0,
            mean_latency_ms=round(statistics.mean(latencies), 2) if latencies else 0.0,
            median_latency_ms=round(statistics.median(latencies), 2) if latencies else 0.0,
            p95_latency_ms=round(_percentile(latencies, 95), 2) if latencies else 0.0,
            p99_latency_ms=round(_percentile(latencies, 99), 2) if latencies else 0.0,
            duration_seconds=round(actual_duration, 2),
            requests_per_second=round(total / actual_duration, 2) if actual_duration > 0 else 0.0,
            passed=(
                error_rate <= scenario.max_error_rate
                and (_percentile(latencies, 95) <= scenario.max_p95_latency_ms if latencies else True)
            ),
            errors=errors[:10],  # cap error list
        )

        self.results.append(result)
        return result

    def run_all(self) -> list[ScenarioResult]:
        """Run all configured scenarios sequentially."""
        self.results.clear()
        for scenario in self.scenarios:
            self.run_scenario(scenario)
        return self.results

    def generate_report(self) -> dict[str, Any]:
        """Generate a JSON-serializable report of all results."""
        all_passed = all(r.passed for r in self.results)
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "overall_passed": all_passed,
            "scenarios_run": len(self.results),
            "scenarios_passed": sum(1 for r in self.results if r.passed),
            "results": [r.to_dict() for r in self.results],
        }


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SSID Load Test Stub — lightweight HTTP load testing")
    parser.add_argument("--target", type=str, default=None, help="Target URL to test")
    parser.add_argument("--users", type=int, default=5, help="Number of concurrent users (default: 5)")
    parser.add_argument("--duration", type=int, default=10, help="Test duration in seconds (default: 10)")
    parser.add_argument("--config", type=str, default=None, help="Path to JSON config with scenario definitions")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--output", type=str, default=None, help="Write report to file")
    args = parser.parse_args(argv)

    runner = LoadTestRunner()

    if args.config:
        config_path = Path(args.config)
        if not config_path.is_file():
            print(f"ERROR: config file not found: {args.config}", file=sys.stderr)
            return 1
        config = json.loads(config_path.read_text(encoding="utf-8"))
        scenarios = config.get("scenarios", [])
        for s in scenarios:
            runner.add_scenario(LoadTestScenario.from_dict(s))
    elif args.target:
        runner.add_scenario(
            LoadTestScenario(
                name="cli_scenario",
                target_url=args.target,
                concurrent_users=args.users,
                duration_seconds=args.duration,
            )
        )
    else:
        print("ERROR: provide --target or --config", file=sys.stderr)
        return 1

    print(f"Running {len(runner.scenarios)} scenario(s)...")
    runner.run_all()
    report = runner.generate_report()

    if args.json:
        output = json.dumps(report, indent=2)
    else:
        lines = [f"Load Test Report — {report['timestamp']}", ""]
        for r in report["results"]:
            status = "PASS" if r["passed"] else "FAIL"
            lines.append(f"  [{status}] {r['scenario_name']}")
            lines.append(
                f"    Requests: {r['total_requests']} total, "
                f"{r['successful_requests']} ok, {r['failed_requests']} failed"
            )
            lines.append(f"    Error rate: {r['error_rate'] * 100:.1f}%")
            lines.append(
                f"    Latency: min={r['min_latency_ms']}ms, "
                f"mean={r['mean_latency_ms']}ms, "
                f"p95={r['p95_latency_ms']}ms, "
                f"p99={r['p99_latency_ms']}ms"
            )
            lines.append(f"    Throughput: {r['requests_per_second']} req/s")
            lines.append("")
        lines.append(
            f"Overall: {'PASS' if report['overall_passed'] else 'FAIL'} "
            f"({report['scenarios_passed']}/{report['scenarios_run']} passed)"
        )
        output = "\n".join(lines)

    print(output)

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nReport written to {args.output}")

    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
