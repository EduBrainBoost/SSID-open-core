"""fairness_engine.py — Fairness evaluation, bias detection, and policy enforcement.

Compute-only: produces assessments and policy results, never stores individual data.
All evaluations produce SHA-256 evidence chains for audit traceability.
No PII is handled; inputs are expected to be anonymised numeric/categorical data.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


class FairnessError(Exception):
    pass


class PolicyViolationError(FairnessError):
    pass


def _sha256_dict(data: dict[str, Any]) -> str:
    serialised = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FairnessScore:
    gini_coefficient: float
    score: float          # 0.0 (perfectly unfair) – 1.0 (perfectly fair)
    verdict: str          # "fair" | "marginal" | "unfair"
    criteria_met: list[str]
    criteria_failed: list[str]
    evidence_hash: str
    input_hash: str


@dataclass(frozen=True)
class BiasReport:
    biased_attributes: list[str]
    disparity_scores: dict[str, float]   # attribute -> disparity ratio
    verdict: str                          # "no_bias" | "potential_bias" | "significant_bias"
    evidence_hash: str
    input_hash: str


@dataclass(frozen=True)
class PolicyResult:
    action: str
    allowed: bool
    constraints_evaluated: list[str]
    constraints_violated: list[str]
    evidence_hash: str
    input_hash: str


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class FairnessEngine:
    """
    Evaluates fairness of distributions, detects bias in datasets, and
    enforces fairness policies on proposed actions.

    All methods are deterministic and compute-only.
    """

    FAIR_THRESHOLD: float = 0.3
    MARGINAL_THRESHOLD: float = 0.5
    BIAS_DISPARITY_THRESHOLD: float = 0.2  # 20 % disparity triggers potential_bias
    SIGNIFICANT_BIAS_THRESHOLD: float = 0.4

    # ------------------------------------------------------------------
    # Gini coefficient
    # ------------------------------------------------------------------

    @staticmethod
    def gini_coefficient(values: list[float]) -> float:
        """
        Compute the Gini coefficient for a list of non-negative numeric values.

        Returns a float in [0.0, 1.0] where 0 = perfect equality.
        Uses the mean absolute difference formula for determinism.
        """
        if not values:
            raise FairnessError("values must not be empty")
        n = len(values)
        sorted_vals = sorted(values)
        total = sum(sorted_vals)
        if total == 0.0:
            return 0.0
        # G = (2 * sum(i * x_i)) / (n * sum(x_i)) - (n+1)/n
        numerator = sum((i + 1) * v for i, v in enumerate(sorted_vals))
        return (2.0 * numerator) / (n * total) - (n + 1) / n

    # ------------------------------------------------------------------
    # evaluate_fairness
    # ------------------------------------------------------------------

    def evaluate_fairness(
        self,
        distribution: dict[str, float],
        criteria: dict[str, Any] | None = None,
    ) -> FairnessScore:
        """
        Evaluate fairness of a distribution mapping participant_id -> amount.

        Args:
            distribution: Numeric allocations per participant.
            criteria: Optional dict of named thresholds, e.g.
                      {"max_gini": 0.35, "min_share": 0.05}.

        Returns:
            FairnessScore with Gini coefficient, normalised score, and
            verdict ("fair" | "marginal" | "unfair").
        """
        if not distribution:
            raise FairnessError("distribution must not be empty")

        criteria = criteria or {}
        input_payload: dict[str, Any] = {
            "distribution": {k: str(v) for k, v in distribution.items()},
            "criteria": criteria,
        }
        input_hash = _sha256_dict(input_payload)

        values = list(distribution.values())
        gini = self.gini_coefficient(values)
        fairness_score = max(0.0, 1.0 - gini)

        criteria_met: list[str] = []
        criteria_failed: list[str] = []
        total = sum(values) or 1.0

        if "max_gini" in criteria:
            if gini <= float(criteria["max_gini"]):
                criteria_met.append("max_gini")
            else:
                criteria_failed.append("max_gini")

        if "min_share" in criteria:
            min_share = float(criteria["min_share"])
            all_above = all(v / total >= min_share for v in values)
            if all_above:
                criteria_met.append("min_share")
            else:
                criteria_failed.append("min_share")

        if gini <= self.FAIR_THRESHOLD:
            verdict = "fair"
        elif gini <= self.MARGINAL_THRESHOLD:
            verdict = "marginal"
        else:
            verdict = "unfair"

        output_payload: dict[str, Any] = {
            "gini_coefficient": gini,
            "score": fairness_score,
            "verdict": verdict,
            "criteria_met": sorted(criteria_met),
            "criteria_failed": sorted(criteria_failed),
        }
        evidence_hash = _sha256_dict(output_payload)

        return FairnessScore(
            gini_coefficient=gini,
            score=fairness_score,
            verdict=verdict,
            criteria_met=criteria_met,
            criteria_failed=criteria_failed,
            evidence_hash=evidence_hash,
            input_hash=input_hash,
        )

    # ------------------------------------------------------------------
    # detect_bias
    # ------------------------------------------------------------------

    def detect_bias(
        self,
        data: list[dict[str, Any]],
        protected_attributes: list[str],
    ) -> BiasReport:
        """
        Detect potential bias in a dataset with respect to protected attributes.

        Each record in data must contain the protected attributes plus an
        'outcome' key with a numeric value.  The engine computes the mean
        outcome per group and the disparity ratio between groups.

        No individual-level data is retained in the returned BiasReport.

        Args:
            data: List of anonymised records (dicts).  Must contain 'outcome' key.
            protected_attributes: Attribute names to check for disparity.

        Returns:
            BiasReport with per-attribute disparity scores and overall verdict.
        """
        if not data:
            raise FairnessError("data must not be empty")
        if not protected_attributes:
            raise FairnessError("protected_attributes must not be empty")

        input_payload: dict[str, Any] = {
            "record_count": len(data),
            "protected_attributes": sorted(protected_attributes),
            "outcome_values_hash": _sha256_dict({"outcomes": [str(r.get("outcome", 0)) for r in data]}),
        }
        input_hash = _sha256_dict(input_payload)

        disparity_scores: dict[str, float] = {}
        biased_attributes: list[str] = []

        for attr in protected_attributes:
            groups: dict[Any, list[float]] = {}
            for record in data:
                group_key = record.get(attr)
                outcome = float(record.get("outcome", 0.0))
                groups.setdefault(group_key, []).append(outcome)

            if len(groups) < 2:
                disparity_scores[attr] = 0.0
                continue

            group_means = {k: sum(v) / len(v) for k, v in groups.items()}
            mean_values = list(group_means.values())
            max_mean = max(mean_values)
            min_mean = min(mean_values)
            if max_mean == 0.0:
                disparity = 0.0
            else:
                disparity = (max_mean - min_mean) / max_mean

            disparity_scores[attr] = round(disparity, 6)
            if disparity >= self.BIAS_DISPARITY_THRESHOLD:
                biased_attributes.append(attr)

        max_disparity = max(disparity_scores.values()) if disparity_scores else 0.0
        if max_disparity >= self.SIGNIFICANT_BIAS_THRESHOLD:
            verdict = "significant_bias"
        elif max_disparity >= self.BIAS_DISPARITY_THRESHOLD:
            verdict = "potential_bias"
        else:
            verdict = "no_bias"

        output_payload: dict[str, Any] = {
            "biased_attributes": sorted(biased_attributes),
            "disparity_scores": disparity_scores,
            "verdict": verdict,
        }
        evidence_hash = _sha256_dict(output_payload)

        return BiasReport(
            biased_attributes=sorted(biased_attributes),
            disparity_scores=disparity_scores,
            verdict=verdict,
            evidence_hash=evidence_hash,
            input_hash=input_hash,
        )

    # ------------------------------------------------------------------
    # enforce_policy
    # ------------------------------------------------------------------

    def enforce_policy(
        self,
        action: dict[str, Any],
        fairness_constraints: dict[str, Any],
    ) -> PolicyResult:
        """
        Determine whether a proposed action satisfies all fairness constraints.

        Args:
            action: Dict describing the proposed action, e.g.
                    {"type": "payout", "gini": 0.25, "min_share": 0.1}.
            fairness_constraints: Dict of named constraints and their thresholds,
                    e.g. {"max_gini": 0.35, "min_share": 0.05}.

        Returns:
            PolicyResult indicating allowed/denied with per-constraint details.
        """
        if not action:
            raise FairnessError("action must not be empty")

        input_payload: dict[str, Any] = {
            "action": action,
            "fairness_constraints": fairness_constraints,
        }
        input_hash = _sha256_dict(input_payload)

        constraints_evaluated: list[str] = []
        constraints_violated: list[str] = []

        for constraint_name, threshold in fairness_constraints.items():
            constraints_evaluated.append(constraint_name)
            action_value = action.get(constraint_name)
            if action_value is None:
                # Constraint not present in action — treat as violation.
                constraints_violated.append(constraint_name)
                continue

            # Convention: constraints prefixed "max_" are upper bounds,
            # constraints prefixed "min_" are lower bounds.
            if constraint_name.startswith("max_"):
                if float(action_value) > float(threshold):
                    constraints_violated.append(constraint_name)
            elif constraint_name.startswith("min_"):
                if float(action_value) < float(threshold):
                    constraints_violated.append(constraint_name)
            # Other named constraints: exact equality check.
            else:
                if str(action_value) != str(threshold):
                    constraints_violated.append(constraint_name)

        allowed = len(constraints_violated) == 0

        output_payload: dict[str, Any] = {
            "action_type": action.get("type", "unknown"),
            "allowed": allowed,
            "constraints_evaluated": sorted(constraints_evaluated),
            "constraints_violated": sorted(constraints_violated),
        }
        evidence_hash = _sha256_dict(output_payload)

        return PolicyResult(
            action=action.get("type", "unknown"),
            allowed=allowed,
            constraints_evaluated=constraints_evaluated,
            constraints_violated=constraints_violated,
            evidence_hash=evidence_hash,
            input_hash=input_hash,
        )
