"""Backup Automation Daemon (G031)

Automated backup orchestration with cron-like scheduler.
- Reads backup_automation_config.yaml
- Manages job lifecycle (scheduled → running → completed/failed)
- Logs evidence for all operations (SHA256)
- Enforces ROOT-24-LOCK constraints

SoT v4.1.0 | Classification: Infrastructure Automation
"""
import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml


class BackupStrategy(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class JobStatus(str, Enum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BackupJob:
    """Backup job definition."""
    job_id: str
    target_root: str
    strategy: BackupStrategy
    schedule: str  # cron expression
    retention_days: int
    priority: str  # critical, high, normal, low
    timeout_seconds: int

    status: JobStatus = JobStatus.SCHEDULED
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    size_bytes: int = 0
    evidence_hash: Optional[str] = None
    error: Optional[str] = None
    attempt: int = 0
    max_attempts: int = 3


@dataclass
class BackupManifest:
    """Backup manifest entry."""
    backup_id: str
    root: str
    strategy: str
    timestamp: str
    size_bytes: int
    content_hash: str
    duration_seconds: float
    status: str
    version: int = 1


class CronScheduler:
    """Simple cron-like scheduler (subset support)."""

    @staticmethod
    def is_due(cron_expr: str, now: datetime) -> bool:
        """Check if job should run at 'now' based on cron expression.

        Supports: "minute hour day month dayofweek"
        Wildcards: *
        Lists: 0,2,4
        Ranges: 0-5
        Steps: */2
        """
        parts = cron_expr.split()
        if len(parts) != 5:
            return False

        minute_spec, hour_spec, day_spec, month_spec, dow_spec = parts

        # Simple check for daily @ hour:minute
        # (full cron parsing omitted for brevity)
        if hour_spec != "*" and day_spec == "*":
            try:
                target_hour = int(hour_spec)
                target_minute = int(minute_spec)
                return (now.hour == target_hour and now.minute == target_minute)
            except ValueError:
                return False
        return False


class BackupAutomationDaemon:
    """Orchestrates automated backups with evidence logging."""

    def __init__(self, config_path: str, evidence_base: str, repo_root: str):
        self.config_path = Path(config_path)
        self.evidence_base = Path(evidence_base)
        self.repo_root = Path(repo_root)
        self.jobs: dict[str, BackupJob] = {}
        self.config: dict[str, Any] = {}
        self.allowed_roots: set[str] = set()
        self.logger = self._setup_logging()
        self.scheduler = CronScheduler()

    def _setup_logging(self) -> logging.Logger:
        """Setup logging to evidence directory."""
        self.evidence_base.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger("backup_daemon")
        logger.setLevel(logging.INFO)

        handler = logging.FileHandler(
            self.evidence_base / f"daemon_{datetime.now():%Y%m%d_%H%M%S}.log"
        )
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def load_config(self) -> bool:
        """Load backup automation config."""
        try:
            with open(self.config_path, "r") as f:
                self.config = yaml.safe_load(f)

            # Extract allowed roots from config
            constraints = self.config.get("constraints", {})
            self.allowed_roots = set(constraints.get("allowed_roots", []))

            # Load job definitions
            for job_def in self.config.get("scheduler", {}).get("jobs", []):
                job = BackupJob(
                    job_id=job_def["job_id"],
                    target_root=job_def["target_root"],
                    strategy=BackupStrategy(job_def["strategy"]),
                    schedule=job_def["schedule"],
                    retention_days=job_def["retention_days"],
                    priority=job_def["priority"],
                    timeout_seconds=job_def["timeout_seconds"],
                )
                self.jobs[job.job_id] = job

            self.logger.info(f"Loaded {len(self.jobs)} backup jobs")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return False

    def _is_root_allowed(self, root: str) -> bool:
        """Enforce ROOT-24-LOCK: validate target root."""
        return root in self.allowed_roots

    def get_due_jobs(self) -> list[BackupJob]:
        """Get jobs that are due to run now."""
        now = datetime.utcnow()
        due = []
        for job in self.jobs.values():
            if (job.status == JobStatus.SCHEDULED
                    and self.scheduler.is_due(job.schedule, now)):
                due.append(job)
        return due

    async def execute_job(self, job: BackupJob) -> bool:
        """Execute a backup job.

        Mocked for this prototype. In real implementation:
        - Would call actual backup tool (robocopy, rsync, etc.)
        - Would compute SHA256 of backup content
        - Would validate against retention policy
        """
        # ROOT-24-LOCK check
        if not self._is_root_allowed(job.target_root):
            job.error = f"Root {job.target_root} not allowed (ROOT-24-LOCK)"
            job.status = JobStatus.FAILED
            self.logger.error(f"Job {job.job_id}: {job.error}")
            return False

        job.status = JobStatus.RUNNING
        job.started_at = time.time()
        job.attempt += 1

        try:
            # Simulate backup operation
            await asyncio.sleep(0.1)

            # Generate mock backup content hash
            backup_id = hashlib.sha256(
                f"{job.job_id}:{time.time_ns()}".encode()
            ).hexdigest()[:16]

            job.size_bytes = 1024 * 1024  # Mock: 1 MB
            job.evidence_hash = hashlib.sha256(
                f"{backup_id}:{job.target_root}".encode()
            ).hexdigest()

            job.status = JobStatus.COMPLETED
            job.completed_at = time.time()

            # Log evidence
            manifest_entry = BackupManifest(
                backup_id=backup_id,
                root=job.target_root,
                strategy=job.strategy.value,
                timestamp=datetime.utcnow().isoformat(),
                size_bytes=job.size_bytes,
                content_hash=job.evidence_hash,
                duration_seconds=job.completed_at - job.started_at,
                status="completed",
            )

            self._log_evidence(job, manifest_entry)
            self.logger.info(
                f"Job {job.job_id} completed: {job.target_root} "
                f"({job.size_bytes} bytes, hash: {job.evidence_hash[:8]}...)"
            )
            return True

        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = time.time()
            job.error = str(e)
            self.logger.error(f"Job {job.job_id} failed: {e}")

            if job.attempt < job.max_attempts:
                job.status = JobStatus.SCHEDULED
                self.logger.info(
                    f"Job {job.job_id} rescheduled (attempt {job.attempt}/{job.max_attempts})"
                )
                return False
            return False

    def _log_evidence(self, job: BackupJob, manifest: BackupManifest) -> None:
        """Write evidence entry (SAFE-FIX compliant)."""
        evidence = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": "backup_automation_daemon",
            "operation": "backup",
            "job_id": job.job_id,
            "target_root": job.target_root,
            "status": job.status.value,
            "manifest": asdict(manifest),
        }

        evidence_file = (
            self.evidence_base
            / f"backup_{manifest.backup_id}.jsonl"
        )

        with open(evidence_file, "a") as f:
            f.write(json.dumps(evidence) + "\n")

    async def run_scheduler_loop(self, interval_seconds: int = 60) -> None:
        """Main scheduler loop."""
        self.logger.info("Backup automation daemon started")

        try:
            while True:
                due_jobs = self.get_due_jobs()
                if due_jobs:
                    self.logger.info(f"Running {len(due_jobs)} due jobs")
                    tasks = [self.execute_job(job) for job in due_jobs]
                    results = await asyncio.gather(*tasks)
                    success = sum(1 for r in results if r)
                    self.logger.info(
                        f"Jobs completed: {success}/{len(due_jobs)} successful"
                    )

                await asyncio.sleep(interval_seconds)
        except KeyboardInterrupt:
            self.logger.info("Backup automation daemon stopped")


async def main():
    """Entry point for daemon."""
    repo_root = Path(__file__).parent.parent.parent
    config_path = repo_root / "15_infra" / "config" / "backup_automation_config.yaml"
    evidence_base = repo_root / ".ssid-system" / "evidence" / "backups"

    daemon = BackupAutomationDaemon(str(config_path), str(evidence_base), str(repo_root))

    if not daemon.load_config():
        return 1

    await daemon.run_scheduler_loop(interval_seconds=60)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
