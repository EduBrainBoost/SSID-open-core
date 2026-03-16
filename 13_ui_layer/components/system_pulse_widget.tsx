/**
 * SystemPulseWidget — displays live runtime health metrics from /api/runtime/pulse.
 *
 * Shows: CPU %, Memory %, Disk %, active service count, overall status badge,
 * and a "Last updated" timestamp. Colour-coded by threshold (green/yellow/red).
 *
 * Props:
 *   apiBase     — base URL for the EMS backend (default: "")
 *   pollMs      — polling interval in ms (default: 15000)
 *   className   — optional CSS class applied to the root element
 */

import React, { useCallback, useEffect, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ResourceStatus = "ok" | "warning" | "critical" | "unknown";
type OverallStatus = "operational" | "degraded" | "critical" | "unknown";

interface NetworkStats {
  bytes_sent: number;
  bytes_recv: number;
  packets_sent: number;
  packets_recv: number;
}

interface PulseData {
  timestamp: string;
  cpu_percent: number | null;
  cpu_count: number | null;
  memory_percent: number | null;
  memory_total_mb: number | null;
  memory_used_mb: number | null;
  disk_percent: number | null;
  disk_total_gb: number | null;
  disk_used_gb: number | null;
  network: NetworkStats | null;
  cpu_status: ResourceStatus;
  memory_status: ResourceStatus;
  disk_status: ResourceStatus;
  psutil_available: boolean;
}

interface ServiceEntry {
  name: string;
  url: string;
  status: "healthy" | "degraded" | "unreachable" | "unknown";
  latency_ms: number | null;
  http_status: number | null;
  detail: string;
}

interface HealthData {
  timestamp: string;
  overall: string;
  services: ServiceEntry[];
  healthy_count: number;
  total_count: number;
}

interface SystemPulseWidgetProps {
  apiBase?: string;
  pollMs?: number;
  className?: string;
}

// ---------------------------------------------------------------------------
// Colour helpers
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  ok: "#22c55e",          // green-500
  warning: "#eab308",     // yellow-500
  critical: "#ef4444",    // red-500
  operational: "#22c55e",
  degraded: "#eab308",
  unhealthy: "#ef4444",
  healthy: "#22c55e",
  unreachable: "#ef4444",
  unknown: "#94a3b8",     // slate-400
};

function statusColor(status: string): string {
  return STATUS_COLORS[status] ?? STATUS_COLORS.unknown;
}

const BADGE_STYLE: React.CSSProperties = {
  display: "inline-block",
  padding: "2px 8px",
  borderRadius: "9999px",
  fontSize: "0.75rem",
  fontWeight: 600,
  color: "#fff",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span style={{ ...BADGE_STYLE, background: statusColor(status) }}>
      {status.toUpperCase()}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Gauge bar
// ---------------------------------------------------------------------------

interface GaugeBarProps {
  label: string;
  percent: number | null;
  status: ResourceStatus;
  detail?: string;
}

function GaugeBar({ label, percent, status, detail }: GaugeBarProps) {
  const displayPct = percent ?? 0;
  const barColor = statusColor(status);

  return (
    <div style={{ marginBottom: "0.75rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", marginBottom: "2px" }}>
        <span style={{ color: "#94a3b8" }}>{label}</span>
        <span style={{ color: barColor, fontWeight: 600 }}>
          {percent !== null ? `${displayPct.toFixed(1)}%` : "N/A"}
          {detail ? ` — ${detail}` : ""}
        </span>
      </div>
      <div
        style={{
          height: "6px",
          background: "#1e293b",
          borderRadius: "3px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${Math.min(100, displayPct)}%`,
            background: barColor,
            borderRadius: "3px",
            transition: "width 0.4s ease",
          }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main widget
// ---------------------------------------------------------------------------

export function SystemPulseWidget({
  apiBase = "",
  pollMs = 15_000,
  className,
}: SystemPulseWidgetProps) {
  const [pulse, setPulse] = useState<PulseData | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [pulseRes, healthRes] = await Promise.allSettled([
        fetch(`${apiBase}/api/runtime/pulse`),
        fetch(`${apiBase}/api/runtime/health`),
      ]);

      if (pulseRes.status === "fulfilled" && pulseRes.value.ok) {
        setPulse(await pulseRes.value.json());
      }
      if (healthRes.status === "fulfilled" && healthRes.value.ok) {
        setHealth(await healthRes.value.json());
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fetch failed");
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    fetchData();
    timerRef.current = setInterval(fetchData, pollMs);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [fetchData, pollMs]);

  // Derive overall widget status
  const overallStatus: string = (() => {
    if (!pulse) return "unknown";
    const statuses = [pulse.cpu_status, pulse.memory_status, pulse.disk_status];
    if (statuses.includes("critical")) return "critical";
    if (statuses.includes("warning")) return "degraded";
    return "operational";
  })();

  const lastUpdated = pulse?.timestamp
    ? new Date(pulse.timestamp).toLocaleTimeString()
    : "—";

  const containerStyle: React.CSSProperties = {
    background: "#0f172a",
    border: `1px solid ${statusColor(overallStatus)}33`,
    borderRadius: "0.75rem",
    padding: "1.25rem",
    color: "#e2e8f0",
    fontFamily: "Inter, system-ui, sans-serif",
    minWidth: "280px",
    maxWidth: "400px",
    boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
  };

  return (
    <div style={containerStyle} className={className} data-testid="system-pulse-widget">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <div>
          <div style={{ fontSize: "0.7rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em" }}>
            System Pulse
          </div>
          <div style={{ fontSize: "1rem", fontWeight: 700, color: "#f1f5f9" }}>
            Runtime Health
          </div>
        </div>
        <StatusBadge status={overallStatus} />
      </div>

      {/* Error banner */}
      {error && (
        <div style={{ background: "#450a0a", border: "1px solid #b91c1c", borderRadius: "6px", padding: "0.5rem 0.75rem", marginBottom: "0.75rem", fontSize: "0.75rem", color: "#fca5a5" }}>
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && !pulse && (
        <div style={{ color: "#64748b", fontSize: "0.8rem", textAlign: "center", padding: "1rem 0" }}>
          Collecting metrics…
        </div>
      )}

      {/* Resource gauges */}
      {pulse && (
        <>
          <GaugeBar
            label="CPU"
            percent={pulse.cpu_percent}
            status={pulse.cpu_status}
            detail={pulse.cpu_count !== null ? `${pulse.cpu_count} cores` : undefined}
          />
          <GaugeBar
            label="Memory"
            percent={pulse.memory_percent}
            status={pulse.memory_status}
            detail={
              pulse.memory_used_mb !== null && pulse.memory_total_mb !== null
                ? `${(pulse.memory_used_mb / 1024).toFixed(1)} / ${(pulse.memory_total_mb / 1024).toFixed(1)} GB`
                : undefined
            }
          />
          <GaugeBar
            label="Disk"
            percent={pulse.disk_percent}
            status={pulse.disk_status}
            detail={
              pulse.disk_used_gb !== null && pulse.disk_total_gb !== null
                ? `${pulse.disk_used_gb} / ${pulse.disk_total_gb} GB`
                : undefined
            }
          />
        </>
      )}

      {/* Services */}
      {health && (
        <div style={{ marginTop: "0.75rem", borderTop: "1px solid #1e293b", paddingTop: "0.75rem" }}>
          <div style={{ fontSize: "0.7rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "0.5rem" }}>
            Services
          </div>
          {health.services.map((svc) => (
            <div
              key={svc.url}
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem", fontSize: "0.78rem" }}
            >
              <span style={{ color: "#94a3b8" }}>{svc.name}</span>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                {svc.latency_ms !== null && (
                  <span style={{ color: "#64748b", fontSize: "0.7rem" }}>{svc.latency_ms}ms</span>
                )}
                <StatusBadge status={svc.status} />
              </div>
            </div>
          ))}
          <div style={{ marginTop: "0.35rem", fontSize: "0.7rem", color: "#475569" }}>
            {health.healthy_count}/{health.total_count} services healthy
          </div>
        </div>
      )}

      {/* Footer */}
      <div style={{ marginTop: "0.75rem", borderTop: "1px solid #1e293b", paddingTop: "0.5rem", display: "flex", justifyContent: "space-between", fontSize: "0.68rem", color: "#475569" }}>
        <span>Last updated</span>
        <span>{lastUpdated}</span>
      </div>

      {pulse && !pulse.psutil_available && (
        <div style={{ marginTop: "0.35rem", fontSize: "0.65rem", color: "#475569", textAlign: "center" }}>
          psutil unavailable — metrics may be incomplete
        </div>
      )}
    </div>
  );
}

export default SystemPulseWidget;
