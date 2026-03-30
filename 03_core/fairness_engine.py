#!/usr/bin/env python3
"""Fairness Engine for SSID Ecosystem.

Provides bias detection, demographic parity checks, and equal opportunity
validation for scoring models used across the SSID identity and reputation
infrastructure. All audit evidence is hash-only -- no PII is stored or logged.

SoT v4.1.0 | ROOT-24-LOCK | Module: 03_core
Evidence strategy: hash_manifest_only
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Sequence


class FairnessMetric(Enum):
    """Supported fairness evaluation metrics."""
    DEMOGRAPHIC_PARITY = "demographic_parity"
    EQUAL_OPPORTUNITY = "equal_opportunity"
    DISPARATE_IMPACT = "disparate_impact"


class FairnessVerdict(Enum):
    """Overall verdict of a fairness evaluation."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class GroupOutcome:
    """Aggregated outcome statistics for a single demographic group.

    Attributes:
        group_id: Opaque, hashed identifier for the group.
        total: Number of individuals evaluated.
        positive: Number receiving a positive outcome.
        negative: Number receiving a negative outcome.
    """
    group_id: str
    total: int
    positive: int
    negative: int

    @property
    def positive_rate(self) -> float:
        """Fraction of individuals with a positive outcome."""
        if self.total == 0:
            return 0.0
        return self.positive / self.total


@dataclass(frozen=True)
class MetricResult:
    """Result of evaluating a single fairness metric."""
    metric: FairnessMetric
    value: float
    threshold: float
    passed: bool
    detail: str


@dataclass(frozen=True)
class FairnessReport:
    """Complete fairness evaluation report.

    Contains metric results and a hash-only evidence digest.
    """
    report_id: str
    timestamp: str
    model_id: str
    metric_results: tuple  # tuple[MetricResult, ...]
    verdict: FairnessVerdict
    evidence_hash: str


class FairnessEngine:
    """Evaluates scoring models for fairness and bias.

    The engine accepts pre-aggregated ``GroupOutcome`` objects (no raw PII)
    and computes standard fairness metrics.  All outputs include a SHA-256
    evidence hash for immutable audit trails.

    Design principles:
        * Hash-only evidence: no PII enters or leaves the engine.
        * Deterministic: same inputs always produce the same verdict.
        * Configurable thresholds per metric.
    """

    # Default thresholds (can be overridden)
    DEFAULT_THRESHOLDS: Dict[FairnessMetric, float] = {
        FairnessMetric.DEMOGRAPHIC_PARITY: 0.10,   # max allowed diff
        FairnessMetric.EQUAL_OPPORTUNITY: 0.10,     # max allowed diff
        FairnessMetric.DISPARATE_IMPACT: 0.80,      # min ratio (4/5 rule)
    }

    def __init__(
        self,
        thresholds: Optional[Dict[FairnessMetric, float]] = None,
    ) -> None:
        self._thresholds = dict(self.DEFAULT_THRESHOLDS)
        if thresholds:
            self._thresholds.update(thresholds)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        model_id: str,
        group_outcomes: Sequence[GroupOutcome],
        metrics: Optional[List[FairnessMetric]] = None,
    ) -> FairnessReport:
        """Run fairness evaluation on *group_outcomes*.

        Args:
            model_id: Identifier (or hash) of the scoring model being evaluated.
            group_outcomes: Per-group aggregated statistics.
            metrics: Which metrics to evaluate. Defaults to all supported.

        Returns:
            A ``FairnessReport`` with per-metric results and overall verdict.

        Raises:
            ValueError: If fewer than 2 groups are provided.
        """
        if len(group_outcomes) < 2:
            raise ValueError("At least 2 groups required for fairness evaluation")

        if metrics is None:
            metrics = list(FairnessMetric)

        results: List[MetricResult] = []
        for metric in metrics:
            result = self._evaluate_metric(metric, group_outcomes)
            results.append(result)

        verdict = self._compute_verdict(results)
        report_id = uuid.uuid4().hex[:16]
        ts = datetime.now(timezone.utc).isoformat()

        evidence_hash = self._hash_evidence(report_id, ts, model_id, results, verdict)

        return FairnessReport(
            report_id=report_id,
            timestamp=ts,
            model_id=model_id,
            metric_results=tuple(results),
            verdict=verdict,
            evidence_hash=evidence_hash,
        )

    # ------------------------------------------------------------------
    # Metric implementations
    # ------------------------------------------------------------------

    def _evaluate_metric(
        self, metric: FairnessMetric, groups: Sequence[GroupOutcome]
    ) -> MetricResult:
        dispatch = {
            FairnessMetric.DEMOGRAPHIC_PARITY: self._demographic_parity,
            FairnessMetric.EQUAL_OPPORTUNITY: self._equal_opportunity,
            FairnessMetric.DISPARATE_IMPACT: self._disparate_impact,
        }
        return dispatch[metric](groups)

    def _demographic_parity(self, groups: Sequence[GroupOutcome]) -> MetricResult:
        """Max absolute difference in positive rates across groups."""
        rates = [g.positive_rate for g in groups]
        diff = max(rates) - min(rates)
        threshold = self._thresholds[FairnessMetric.DEMOGRAPHIC_PARITY]
        passed = diff <= threshold
        return MetricResult(
            metric=FairnessMetric.DEMOGRAPHIC_PARITY,
            value=round(diff, 6),
            threshold=threshold,
            passed=passed,
            detail=(
                f"Max positive-rate spread: {diff:.4f} "
                f"(threshold: {threshold})"
            ),
        )

    def _equal_opportunity(self, groups: Sequence[GroupOutcome]) -> MetricResult:
        """Difference in true-positive rates across groups.

        Uses positive_rate as a proxy for TPR when ground-truth labels
        equal actual positives (pre-aggregated assumption).
        """
        rates = [g.positive_rate for g in groups]
        diff = max(rates) - min(rates)
        threshold = self._thresholds[FairnessMetric.EQUAL_OPPORTUNITY]
        passed = diff <= threshold
        return MetricResult(
            metric=FairnessMetric.EQUAL_OPPORTUNITY,
            value=round(diff, 6),
            threshold=threshold,
            passed=passed,
            detail=(
                f"Equal-opportunity spread: {diff:.4f} "
                f"(threshold: {threshold})"
            ),
        )

    def _disparate_impact(self, groups: Sequence[GroupOutcome]) -> MetricResult:
        """Ratio of the lowest positive rate to the highest (4/5 rule)."""
        rates = [g.positive_rate for g in groups if g.total > 0]
        if not rates or max(rates) == 0:
            ratio = 0.0
        else:
            ratio = min(rates) / max(rates)
        threshold = self._thresholds[FairnessMetric.DISPARATE_IMPACT]
        passed = ratio >= threshold
        return MetricResult(
            metric=FairnessMetric.DISPARATE_IMPACT,
            value=round(ratio, 6),
            threshold=threshold,
            passed=passed,
            detail=(
                f"Disparate impact ratio: {ratio:.4f} "
                f"(threshold: {threshold})"
            ),
        )

    # ------------------------------------------------------------------
    # Verdict & evidence
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_verdict(results: List[MetricResult]) -> FairnessVerdict:
        if all(r.passed for r in results):
            return FairnessVerdict.PASS
        failed = [r for r in results if not r.passed]
        # If disparate impact fails, it's a hard FAIL
        if any(r.metric == FairnessMetric.DISPARATE_IMPACT for r in failed):
            return FairnessVerdict.FAIL
        # Other metric failures are warnings unless more than half fail
        if len(failed) > len(results) / 2:
            return FairnessVerdict.FAIL
        return FairnessVerdict.WARN

    @staticmethod
    def _hash_evidence(
        report_id: str,
        ts: str,
        model_id: str,
        results: List[MetricResult],
        verdict: FairnessVerdict,
    ) -> str:
        payload = {
            "report_id": report_id,
            "timestamp": ts,
            "model_id": model_id,
            "metrics": [
                {
                    "metric": r.metric.value,
                    "value": r.value,
                    "threshold": r.threshold,
                    "passed": r.passed,
                }
                for r in results
            ],
            "verdict": verdict.value,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
