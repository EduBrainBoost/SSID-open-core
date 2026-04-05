"""SystemPulse — standalone runtime health monitor for SSID-open-core.

Collects OS-level metrics (CPU, memory, disk, network) via psutil, checks
named service endpoints, and aggregates pulse data over a sliding window.
No database dependency; all persistence delegated to PulseStateStore.

Usage::

    pulse = SystemPulse()
    metrics = pulse.collect_metrics()
    health  = pulse.check_service_health(["http://localhost:8000/health"])
    status  = pulse.get_runtime_status()
    agg     = pulse.aggregate_pulse_data(timedelta(minutes=5))
"""

from __future__ import annotations

import logging
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class NetworkStats:
    bytes_sent: int = 0
    bytes_recv: int = 0
    packets_sent: int = 0
    packets_recv: int = 0


@dataclass
class PulseMetrics:
    """Point-in-time system resource snapshot."""

    timestamp: str = field(default_factory=_utcnow_iso)
    cpu_percent: float = 0.0
    cpu_count: int = 1
    memory_total_mb: float = 0.0
    memory_used_mb: float = 0.0
    memory_percent: float = 0.0
    disk_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    disk_percent: float = 0.0
    network: NetworkStats = field(default_factory=NetworkStats)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PulseMetrics:
        net_raw = data.pop("network", {})
        if isinstance(net_raw, dict):
            net = NetworkStats(**{k: net_raw.get(k, 0) for k in NetworkStats.__dataclass_fields__})
        else:
            net = NetworkStats()
        return cls(network=net, **data)


@dataclass
class ServiceHealth:
    name: str
    url: str
    status: str  # "healthy" | "degraded" | "unreachable"
    latency_ms: float | None = None
    http_status: int | None = None
    detail: str = ""


@dataclass
class HealthReport:
    timestamp: str = field(default_factory=_utcnow_iso)
    overall: str = "unknown"  # "healthy" | "degraded" | "unhealthy" | "unknown"
    services: list[ServiceHealth] = field(default_factory=list)
    healthy_count: int = 0
    total_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall": self.overall,
            "services": [asdict(s) for s in self.services],
            "healthy_count": self.healthy_count,
            "total_count": self.total_count,
        }


@dataclass
class RuntimeStatus:
    timestamp: str = field(default_factory=_utcnow_iso)
    status: str = "unknown"  # "operational" | "degraded" | "critical" | "unknown"
    cpu_status: str = "ok"
    memory_status: str = "ok"
    disk_status: str = "ok"
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    uptime_seconds: float = 0.0
    factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PulseAggregate:
    timestamp: str = field(default_factory=_utcnow_iso)
    window_seconds: float = 0.0
    sample_count: int = 0
    cpu_avg: float = 0.0
    cpu_max: float = 0.0
    memory_avg: float = 0.0
    memory_max: float = 0.0
    disk_avg: float = 0.0
    disk_max: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_CPU_WARN = 75.0
_CPU_CRIT = 90.0
_MEM_WARN = 80.0
_MEM_CRIT = 95.0
_DISK_WARN = 85.0
_DISK_CRIT = 95.0
_HTTP_TIMEOUT = 5  # seconds


# ---------------------------------------------------------------------------
# SystemPulse
# ---------------------------------------------------------------------------


class SystemPulse:
    """Collects runtime metrics and health signals for the SSID platform."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect_metrics(self) -> PulseMetrics:
        """Collect current OS resource metrics.

        Falls back gracefully when psutil is unavailable.
        """
        try:
            import psutil  # type: ignore

            cpu = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count(logical=True) or 1
            vm = psutil.virtual_memory()
            du = psutil.disk_usage("/")
            net = psutil.net_io_counters()

            return PulseMetrics(
                timestamp=_utcnow_iso(),
                cpu_percent=round(cpu, 2),
                cpu_count=cpu_count,
                memory_total_mb=round(vm.total / (1024**2), 1),
                memory_used_mb=round(vm.used / (1024**2), 1),
                memory_percent=round(vm.percent, 2),
                disk_total_gb=round(du.total / (1024**3), 2),
                disk_used_gb=round(du.used / (1024**3), 2),
                disk_percent=round(du.percent, 2),
                network=NetworkStats(
                    bytes_sent=net.bytes_sent,
                    bytes_recv=net.bytes_recv,
                    packets_sent=net.packets_sent,
                    packets_recv=net.packets_recv,
                ),
            )
        except ImportError:
            logger.warning("psutil not available — returning stub metrics")
            return self._stub_metrics()
        except Exception:
            logger.debug("Failed to collect metrics", exc_info=True)
            return self._stub_metrics()

    def check_service_health(self, services: list[str]) -> HealthReport:
        """Probe a list of service URLs and return a HealthReport.

        Each entry in *services* can be:
        - A plain URL string, e.g. "http://localhost:8000/health"
        - A dict with keys ``name`` and ``url``
        """
        report = HealthReport(timestamp=_utcnow_iso())
        for entry in services:
            if isinstance(entry, dict):
                name = str(entry.get("name", entry.get("url", "unknown")))
                url = str(entry.get("url", ""))
            else:
                url = str(entry)
                name = url.split("//")[-1].split("/")[0]

            svc = self._probe_url(name, url)
            report.services.append(svc)

        report.total_count = len(report.services)
        report.healthy_count = sum(1 for s in report.services if s.status == "healthy")
        report.overall = self._aggregate_health([s.status for s in report.services])
        return report

    def get_runtime_status(self) -> RuntimeStatus:
        """Derive a RuntimeStatus from current metrics."""
        metrics = self.collect_metrics()
        factors: list[str] = []

        cpu_status = self._threshold_status(metrics.cpu_percent, _CPU_WARN, _CPU_CRIT)
        mem_status = self._threshold_status(metrics.memory_percent, _MEM_WARN, _MEM_CRIT)
        disk_status = self._threshold_status(metrics.disk_percent, _DISK_WARN, _DISK_CRIT)

        if cpu_status == "critical":
            factors.append(f"cpu_critical={metrics.cpu_percent}%")
        elif cpu_status == "warning":
            factors.append(f"cpu_high={metrics.cpu_percent}%")

        if mem_status == "critical":
            factors.append(f"memory_critical={metrics.memory_percent}%")
        elif mem_status == "warning":
            factors.append(f"memory_high={metrics.memory_percent}%")

        if disk_status == "critical":
            factors.append(f"disk_critical={metrics.disk_percent}%")
        elif disk_status == "warning":
            factors.append(f"disk_high={metrics.disk_percent}%")

        statuses = [cpu_status, mem_status, disk_status]
        if "critical" in statuses:
            overall = "critical"
        elif "warning" in statuses:
            overall = "degraded"
        else:
            overall = "operational"

        uptime = self._get_uptime()

        return RuntimeStatus(
            timestamp=_utcnow_iso(),
            status=overall,
            cpu_status=cpu_status,
            memory_status=mem_status,
            disk_status=disk_status,
            cpu_percent=metrics.cpu_percent,
            memory_percent=metrics.memory_percent,
            disk_percent=metrics.disk_percent,
            uptime_seconds=uptime,
            factors=factors,
        )

    def aggregate_pulse_data(self, window: timedelta) -> PulseAggregate:
        """Aggregate pulse samples from PulseStateStore within *window*.

        Requires PulseStateStore to be available. Falls back to single
        live sample when the store is not importable.
        """
        try:
            from ssid_observability.runtime.pulse_state_store import PulseStateStore  # type: ignore

            store = PulseStateStore()
            history = store.get_pulse_history(count=500)
        except Exception:
            # Fallback: collect a single live sample
            history = [self.collect_metrics()]

        window_secs = window.total_seconds()
        cutoff_epoch = time.time() - window_secs

        samples: list[PulseMetrics] = []
        for item in history:
            if isinstance(item, PulseMetrics):
                m = item
            elif isinstance(item, dict):
                try:
                    m = PulseMetrics.from_dict(dict(item))
                except Exception:
                    continue
            else:
                continue

            # Parse timestamp to epoch for filtering
            try:
                ts = datetime.fromisoformat(m.timestamp).timestamp()
            except Exception:
                ts = 0.0

            if ts >= cutoff_epoch:
                samples.append(m)

        if not samples:
            # Always include at least one live reading
            samples = [self.collect_metrics()]

        cpu_vals = [s.cpu_percent for s in samples]
        mem_vals = [s.memory_percent for s in samples]
        disk_vals = [s.disk_percent for s in samples]

        return PulseAggregate(
            timestamp=_utcnow_iso(),
            window_seconds=window_secs,
            sample_count=len(samples),
            cpu_avg=round(sum(cpu_vals) / len(cpu_vals), 2),
            cpu_max=round(max(cpu_vals), 2),
            memory_avg=round(sum(mem_vals) / len(mem_vals), 2),
            memory_max=round(max(mem_vals), 2),
            disk_avg=round(sum(disk_vals) / len(disk_vals), 2),
            disk_max=round(max(disk_vals), 2),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _stub_metrics() -> PulseMetrics:
        return PulseMetrics(timestamp=_utcnow_iso())

    @staticmethod
    def _threshold_status(value: float, warn: float, crit: float) -> str:
        if value >= crit:
            return "critical"
        if value >= warn:
            return "warning"
        return "ok"

    @staticmethod
    def _aggregate_health(statuses: list[str]) -> str:
        if not statuses:
            return "unknown"
        if all(s == "unknown" for s in statuses):
            return "unknown"
        if any(s == "unreachable" for s in statuses):
            return "unhealthy"
        if any(s == "degraded" for s in statuses):
            return "degraded"
        if all(s == "healthy" for s in statuses):
            return "healthy"
        return "degraded"

    @staticmethod
    def _probe_url(name: str, url: str) -> ServiceHealth:
        """HTTP GET probe — returns ServiceHealth with latency."""
        if not url:
            return ServiceHealth(name=name, url=url, status="unknown", detail="No URL provided")
        try:
            t0 = time.monotonic()
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                latency_ms = round((time.monotonic() - t0) * 1000, 1)
                code = resp.status
                if code < 400:
                    return ServiceHealth(
                        name=name,
                        url=url,
                        status="healthy",
                        latency_ms=latency_ms,
                        http_status=code,
                        detail=f"HTTP {code}",
                    )
                return ServiceHealth(
                    name=name,
                    url=url,
                    status="degraded",
                    latency_ms=latency_ms,
                    http_status=code,
                    detail=f"HTTP {code}",
                )
        except Exception as exc:
            return ServiceHealth(
                name=name,
                url=url,
                status="unreachable",
                detail=str(exc)[:120],
            )

    @staticmethod
    def _get_uptime() -> float:
        """Return system uptime in seconds (best-effort)."""
        try:
            import psutil  # type: ignore

            return round(time.time() - psutil.boot_time(), 1)
        except Exception:
            return 0.0
