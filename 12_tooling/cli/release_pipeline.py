#!/usr/bin/env python3
"""Release Pipeline Manager — formal release lifecycle with promotion gates.

Manages release manifests through environment stages (dev -> staging -> production)
with cryptographic evidence at every promotion and rollback.

Usage:
  python 12_tooling/cli/release_pipeline.py create --version 4.1.0 --sha abc123
  python 12_tooling/cli/release_pipeline.py promote --manifest release.json --to staging
  python 12_tooling/cli/release_pipeline.py rollback --manifest release.json
  python 12_tooling/cli/release_pipeline.py verify --manifest release.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional
from uuid import uuid4

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENVIRONMENTS = ("dev", "staging", "production")
PROMOTION_ORDER = {
    "dev": "staging",
    "staging": "production",
}
VALID_STATUSES = ("draft", "candidate", "staging", "production", "rolled_back")

EXIT_PASS = 0
EXIT_FAIL = 2

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

DEFAULT_EVIDENCE_DIR = "02_audit_logging/evidence/releases"
DEFAULT_MANIFEST_DIR = "04_deployment/releases"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_str(s: str) -> str:
    return _sha256_bytes(s.encode("utf-8"))


def _json_sha256(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return _sha256_bytes(data)


def _new_id() -> str:
    return uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ReleaseManifest:
    """Immutable record of a release through its lifecycle."""

    version: str
    sha: str
    timestamp: str
    artifacts: List[str] = field(default_factory=list)
    evidence_hashes: List[str] = field(default_factory=list)
    sbom_ref: str = ""
    status: str = "draft"
    release_id: str = ""
    promotion_history: List[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.release_id:
            self.release_id = _new_id()
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{self.status}'; must be one of {VALID_STATUSES}")

    def integrity_hash(self) -> str:
        """SHA256 over the canonical JSON of core fields."""
        core = {
            "version": self.version,
            "sha": self.sha,
            "timestamp": self.timestamp,
            "artifacts": sorted(self.artifacts),
            "sbom_ref": self.sbom_ref,
            "status": self.status,
            "release_id": self.release_id,
        }
        return _json_sha256(core)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ReleaseManifest":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PromotionGate:
    """A single gate check that must pass before promotion."""

    name: str
    description: str
    required: bool = True

    def check(self, manifest: ReleaseManifest, context: dict | None = None) -> "GateResult":
        raise NotImplementedError("Subclasses must implement check()")


@dataclass
class GateResult:
    """Result of a single gate check."""

    gate_name: str
    passed: bool
    detail: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _utc_now_iso()


@dataclass
class PromotionResult:
    """Outcome of a promotion attempt."""

    success: bool
    from_env: str
    to_env: str
    manifest_version: str
    gate_results: List[dict] = field(default_factory=list)
    evidence_hash: str = ""
    timestamp: str = ""
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _utc_now_iso()


@dataclass
class RollbackRecord:
    """Evidence record for a rollback."""

    release_id: str
    version: str
    previous_status: str
    rollback_reason: str
    evidence_hash: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _utc_now_iso()


# ---------------------------------------------------------------------------
# Built-in gate implementations
# ---------------------------------------------------------------------------


class TestsGreenGate(PromotionGate):
    """Verifies that tests have passed (checks context for test results)."""

    def __init__(self) -> None:
        super().__init__(name="tests_green", description="All tests must pass")

    def check(self, manifest: ReleaseManifest, context: dict | None = None) -> GateResult:
        ctx = context or {}
        passed = ctx.get("tests_green", False)
        return GateResult(
            gate_name=self.name,
            passed=bool(passed),
            detail="Tests passed" if passed else "Tests not confirmed as green",
        )


class EvidenceCompleteGate(PromotionGate):
    """Verifies that evidence hashes are present."""

    def __init__(self) -> None:
        super().__init__(name="evidence_complete", description="Evidence chain must be present")

    def check(self, manifest: ReleaseManifest, context: dict | None = None) -> GateResult:
        passed = len(manifest.evidence_hashes) > 0
        return GateResult(
            gate_name=self.name,
            passed=passed,
            detail=f"{len(manifest.evidence_hashes)} evidence hash(es)" if passed else "No evidence hashes",
        )


class SecretScanCleanGate(PromotionGate):
    """Verifies no secrets detected in artifacts."""

    def __init__(self) -> None:
        super().__init__(name="secret_scan_clean", description="Secret scan must be clean")

    def check(self, manifest: ReleaseManifest, context: dict | None = None) -> GateResult:
        ctx = context or {}
        passed = ctx.get("secret_scan_clean", False)
        return GateResult(
            gate_name=self.name,
            passed=bool(passed),
            detail="Secret scan clean" if passed else "Secret scan not confirmed",
        )


class NoPiiGate(PromotionGate):
    """Verifies no PII present in release artifacts."""

    def __init__(self) -> None:
        super().__init__(name="no_pii", description="No PII in artifacts")

    def check(self, manifest: ReleaseManifest, context: dict | None = None) -> GateResult:
        ctx = context or {}
        passed = ctx.get("no_pii", False)
        return GateResult(
            gate_name=self.name,
            passed=bool(passed),
            detail="No PII detected" if passed else "PII check not confirmed",
        )


# ---------------------------------------------------------------------------
# Default gate set
# ---------------------------------------------------------------------------

def default_gates() -> List[PromotionGate]:
    """Return the standard promotion gate set."""
    return [
        TestsGreenGate(),
        EvidenceCompleteGate(),
        SecretScanCleanGate(),
        NoPiiGate(),
    ]


# ---------------------------------------------------------------------------
# ReleasePipeline
# ---------------------------------------------------------------------------


class ReleasePipeline:
    """Manages the release lifecycle: create, promote, rollback, verify."""

    def __init__(
        self,
        repo_root: Path | None = None,
        gates: List[PromotionGate] | None = None,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root else REPO_ROOT
        self.gates = gates if gates is not None else default_gates()

    # -- create ---------------------------------------------------------------

    def create_release(self, version: str, sha: str, artifacts: List[str] | None = None) -> ReleaseManifest:
        """Create a new release manifest in draft status."""
        manifest = ReleaseManifest(
            version=version,
            sha=sha,
            timestamp=_utc_now_iso(),
            artifacts=list(artifacts) if artifacts else [],
            status="draft",
        )
        # Compute artifact integrity hashes
        for artifact_path in manifest.artifacts:
            full = self.repo_root / artifact_path
            if full.is_file():
                content = full.read_bytes()
                manifest.evidence_hashes.append(_sha256_bytes(content))
        # Add manifest self-hash as evidence
        manifest.evidence_hashes.append(manifest.integrity_hash())
        return manifest

    # -- verify gates ---------------------------------------------------------

    def verify_promotion_gates(
        self,
        manifest: ReleaseManifest,
        context: dict | None = None,
    ) -> List[GateResult]:
        """Run all promotion gates and return results."""
        results: List[GateResult] = []
        for gate in self.gates:
            result = gate.check(manifest, context)
            results.append(result)
        return results

    # -- promote --------------------------------------------------------------

    def promote(
        self,
        manifest: ReleaseManifest,
        from_env: str,
        to_env: str,
        context: dict | None = None,
    ) -> PromotionResult:
        """Promote a release from one environment to the next.

        Validates promotion order and runs all gates before allowing promotion.
        """
        # Validate environments
        if from_env not in PROMOTION_ORDER:
            return PromotionResult(
                success=False,
                from_env=from_env,
                to_env=to_env,
                manifest_version=manifest.version,
                detail=f"Cannot promote from '{from_env}'; no further promotion path",
            )

        expected_next = PROMOTION_ORDER[from_env]
        if to_env != expected_next:
            return PromotionResult(
                success=False,
                from_env=from_env,
                to_env=to_env,
                manifest_version=manifest.version,
                detail=f"Invalid promotion: {from_env} -> {to_env}; expected {from_env} -> {expected_next}",
            )

        # Run gates
        gate_results = self.verify_promotion_gates(manifest, context)
        gate_dicts = [asdict(gr) for gr in gate_results]

        all_passed = all(gr.passed for gr in gate_results if gr.gate_name in
                         {g.name for g in self.gates if g.required})

        if not all_passed:
            failed = [gr.gate_name for gr in gate_results if not gr.passed]
            return PromotionResult(
                success=False,
                from_env=from_env,
                to_env=to_env,
                manifest_version=manifest.version,
                gate_results=gate_dicts,
                detail=f"Gate(s) failed: {', '.join(failed)}",
            )

        # Promote
        manifest.status = self._env_to_status(to_env)
        promotion_entry = {
            "from": from_env,
            "to": to_env,
            "timestamp": _utc_now_iso(),
            "gate_results_hash": _json_sha256(gate_dicts),
        }
        manifest.promotion_history.append(promotion_entry)

        evidence_hash = _json_sha256({
            "action": "promote",
            "release_id": manifest.release_id,
            "version": manifest.version,
            "from_env": from_env,
            "to_env": to_env,
            "gate_results": gate_dicts,
            "timestamp": promotion_entry["timestamp"],
        })
        manifest.evidence_hashes.append(evidence_hash)

        return PromotionResult(
            success=True,
            from_env=from_env,
            to_env=to_env,
            manifest_version=manifest.version,
            gate_results=gate_dicts,
            evidence_hash=evidence_hash,
        )

    # -- rollback -------------------------------------------------------------

    def rollback(self, manifest: ReleaseManifest, reason: str = "manual rollback") -> RollbackRecord:
        """Roll back a release, recording evidence."""
        previous_status = manifest.status
        manifest.status = "rolled_back"

        rollback_entry = {
            "action": "rollback",
            "from_status": previous_status,
            "reason": reason,
            "timestamp": _utc_now_iso(),
        }
        manifest.promotion_history.append(rollback_entry)

        evidence_hash = _json_sha256({
            "action": "rollback",
            "release_id": manifest.release_id,
            "version": manifest.version,
            "previous_status": previous_status,
            "reason": reason,
            "timestamp": rollback_entry["timestamp"],
        })
        manifest.evidence_hashes.append(evidence_hash)

        return RollbackRecord(
            release_id=manifest.release_id,
            version=manifest.version,
            previous_status=previous_status,
            rollback_reason=reason,
            evidence_hash=evidence_hash,
        )

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _env_to_status(env: str) -> str:
        mapping = {
            "dev": "candidate",
            "staging": "staging",
            "production": "production",
        }
        return mapping.get(env, env)

    # -- serialization --------------------------------------------------------

    @staticmethod
    def save_manifest(manifest: ReleaseManifest, path: Path) -> None:
        """Write manifest JSON to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @staticmethod
    def load_manifest(path: Path) -> ReleaseManifest:
        """Load manifest from JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return ReleaseManifest.from_dict(data)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SSID Release Pipeline Manager")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="Repository root")
    sub = parser.add_subparsers(dest="command")

    # create
    p_create = sub.add_parser("create", help="Create a new release manifest")
    p_create.add_argument("--version", required=True, help="Semantic version (e.g. 4.1.0)")
    p_create.add_argument("--sha", required=True, help="Git commit SHA")
    p_create.add_argument("--artifacts", nargs="*", default=[], help="Artifact paths relative to repo root")
    p_create.add_argument("--output", help="Output manifest path")

    # promote
    p_promote = sub.add_parser("promote", help="Promote a release")
    p_promote.add_argument("--manifest", required=True, help="Path to release manifest JSON")
    p_promote.add_argument("--from-env", required=True, choices=ENVIRONMENTS, dest="from_env")
    p_promote.add_argument("--to", required=True, choices=ENVIRONMENTS, dest="to_env")

    # rollback
    p_rollback = sub.add_parser("rollback", help="Roll back a release")
    p_rollback.add_argument("--manifest", required=True, help="Path to release manifest JSON")
    p_rollback.add_argument("--reason", default="manual rollback", help="Rollback reason")

    # verify
    p_verify = sub.add_parser("verify", help="Verify promotion gates")
    p_verify.add_argument("--manifest", required=True, help="Path to release manifest JSON")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return EXIT_FAIL

    pipeline = ReleasePipeline(repo_root=Path(args.repo))

    if args.command == "create":
        manifest = pipeline.create_release(args.version, args.sha, args.artifacts)
        out = json.dumps(manifest.to_dict(), indent=2)
        if args.output:
            p = Path(args.output)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(out + "\n", encoding="utf-8")
            print(f"PASS: release manifest written to {p}")
        else:
            print(out)
        return EXIT_PASS

    if args.command == "verify":
        manifest = ReleasePipeline.load_manifest(Path(args.manifest))
        results = pipeline.verify_promotion_gates(manifest)
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            print(f"  [{status}] {r.gate_name}: {r.detail}")
        all_ok = all(r.passed for r in results)
        print(f"\nOverall: {'PASS' if all_ok else 'FAIL'}")
        return EXIT_PASS if all_ok else EXIT_FAIL

    if args.command == "promote":
        manifest = ReleasePipeline.load_manifest(Path(args.manifest))
        result = pipeline.promote(manifest, args.from_env, args.to_env)
        if result.success:
            ReleasePipeline.save_manifest(manifest, Path(args.manifest))
            print(f"PASS: promoted {manifest.version} from {result.from_env} to {result.to_env}")
            print(f"  evidence_hash: {result.evidence_hash}")
        else:
            print(f"FAIL: {result.detail}")
        return EXIT_PASS if result.success else EXIT_FAIL

    if args.command == "rollback":
        manifest = ReleasePipeline.load_manifest(Path(args.manifest))
        record = pipeline.rollback(manifest, args.reason)
        ReleasePipeline.save_manifest(manifest, Path(args.manifest))
        print(f"PASS: rolled back {record.version} (was {record.previous_status})")
        print(f"  evidence_hash: {record.evidence_hash}")
        return EXIT_PASS

    parser.print_help()
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
