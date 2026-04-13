from typing import Any

from pydantic import BaseModel, Field


class ActiveBaselineStateResponse(BaseModel):
    active_baseline_version: str
    source_promotion_id: str
    source_approval_id: str
    decision: str
    consistency_status: str
    updated_at_utc: str


class FreezeStateResponse(BaseModel):
    state_id: str
    updated_at_utc: str
    freeze_level: str
    incident_id: str
    reason: str
    set_by: str
    scope: str
    evidence_hash: str


class FreezeStateUpdateRequest(BaseModel):
    freeze_level: str
    reason: str
    set_by: str
    incident_id: str
    scope: str


class FreezeEvaluateRequest(BaseModel):
    operation_type: str
    candidate_id: str | None = None
    proposal_id: str | None = None
    requested_by: str
    reason: str
    target_baseline_version: str | None = None


class FreezeEvaluateResponse(BaseModel):
    operation_type: str
    freeze_level: str
    decision: str
    allowed: bool
    candidate_id: str | None = None
    proposal_id: str | None = None
    findings: list[dict[str, str]] = Field(default_factory=list)


class CandidateItem(BaseModel):
    candidate_id: str
    created_at_utc: str
    status: str
    source_convergence_report: str
    source_convergence_evidence_hash: str
    source_active_baseline_version: str
    target_baseline_version: str
    approval_scope: str
    reason: str
    candidate_evidence_hash: str


class CandidateDetailResponse(CandidateItem):
    history: list[dict[str, Any]] = Field(default_factory=list)


class CandidateListResponse(BaseModel):
    items: list[CandidateItem]


class OperatorApprovalItem(BaseModel):
    decision_id: str
    candidate_id: str
    decided_at_utc: str
    decided_by: str
    decision: str
    reason: str
    approval_file: str | None = None
    decision_evidence_hash: str


class OperatorApprovalListResponse(BaseModel):
    items: list[OperatorApprovalItem]


class CandidateActionRequest(BaseModel):
    approved_by: str
    reason: str


class CandidateActionResponse(BaseModel):
    decision: str
    candidate_id: str
    approval_file: str | None = None
    status_after: str
    decision_id: str


class PromotionExecuteRequest(BaseModel):
    executed_by: str
    reason: str


class PromotionExecutionFinding(BaseModel):
    finding_code: str
    severity: str
    path: str
    detail: str


class PromotionExecuteResponse(BaseModel):
    execution_id: str | None = None
    candidate_id: str
    execution_status: str
    promotion_id: str | None = None
    approval_file: str | None = None
    promotion_report: str | None = None
    active_baseline_version_after: str | None = None
    release_block_status: str
    findings: list[PromotionExecutionFinding] = Field(default_factory=list)


class PromotionExecutionHistoryItem(BaseModel):
    execution_id: str
    executed_at_utc: str
    executed_by: str
    candidate_id: str
    approval_id: str
    promotion_id: str | None = None
    baseline_version_before: str
    baseline_version_after: str
    release_block_status_after: str
    execution_status: str
    reason: str
    approval_file: str | None = None
    promotion_report: str | None = None
    execution_evidence_hash: str


class PromotionExecutionHistoryListResponse(BaseModel):
    items: list[PromotionExecutionHistoryItem]


class PromotionTimelineItem(BaseModel):
    timestamp_utc: str | None = None
    event_type: str
    status: str | None = None
    detail: str | None = None
    candidate_id: str | None = None
    decision_id: str | None = None
    execution_id: str | None = None
    promotion_id: str | None = None
    approval_id: str | None = None
    active_baseline_version: str | None = None
    approval_file: str | None = None


class PromotionTimelineResponse(BaseModel):
    items: list[PromotionTimelineItem]


class RollbackEvaluateRequest(BaseModel):
    requested_by: str
    target_baseline_version: str
    reason: str


class RollbackEvaluateResponse(BaseModel):
    allowed: bool
    guard_decision: str
    current_active_version: str | None = None
    target_baseline_version: str
    findings: list[PromotionExecutionFinding] = Field(default_factory=list)


class RollbackProposalCreateRequest(BaseModel):
    created_by: str
    target_baseline_version: str
    reason: str


class RollbackProposalItem(BaseModel):
    proposal_id: str
    created_at_utc: str
    created_by: str
    source_execution_id: str
    current_active_version: str
    target_baseline_version: str
    guard_decision: str
    guard_allowed: bool
    reason: str
    status: str
    proposal_evidence_hash: str


class RollbackProposalDetailResponse(RollbackProposalItem):
    history: list[dict[str, Any]] = Field(default_factory=list)


class RollbackProposalListResponse(BaseModel):
    items: list[RollbackProposalItem]


class RollbackProposalCreateResponse(BaseModel):
    proposal_id: str
    guard_decision: str
    guard_allowed: bool
    status: str
    current_active_version: str
    target_baseline_version: str


class RollbackProposalDecisionRequest(BaseModel):
    approved_by: str
    reason: str


class RollbackProposalDecisionResponse(BaseModel):
    decision: str
    proposal_id: str
    status_after: str


class RollbackRecoveryExecuteRequest(BaseModel):
    executed_by: str
    reason: str


class RollbackRecoveryExecuteResponse(BaseModel):
    recovery_id: str | None = None
    recovery_status: str
    baseline_version_after: str | None = None
    release_block_status_after: str | None = None
    findings: list[PromotionExecutionFinding] = Field(default_factory=list)


class ExecutionGatewayRequest(BaseModel):
    execution_target: str
    target_id: str
    requested_by: str
    reason: str


class ExecutionGatewayContextResponse(BaseModel):
    execution_target: str
    target_id: str
    freeze_level: str
    release_block_status: str
    runtime_dependency_status: str
    approval_status: str
    active_run_id: str | None = None


class ExecutionGatewayRunItem(BaseModel):
    run_id: str
    created_at_utc: str
    execution_target: str
    target_id: str
    status: str
    decision: str
    blocker_codes: list[str] = Field(default_factory=list)
    requested_by: str
    reason: str
    evidence_hash: str
    handoff_execution_id: str | None = None
    handoff_status: str | None = None


class ExecutionGatewayEvaluationResponse(BaseModel):
    decision: str
    blocker_codes: list[str] = Field(default_factory=list)
    context: ExecutionGatewayContextResponse


class ExecutionGatewayActionResponse(BaseModel):
    decision: str
    blocker_codes: list[str] = Field(default_factory=list)
    run: ExecutionGatewayRunItem
    handoff: dict[str, Any] | None = None


class ExecutionGatewayRunListResponse(BaseModel):
    items: list[ExecutionGatewayRunItem]


class ExecutionGatewayLiveStatusResponse(BaseModel):
    decision: str
    latest_run: ExecutionGatewayRunItem | None = None
    active_blockers: list[str] = Field(default_factory=list)
    run_count: int


class ExecutionGatewayBlockersResponse(BaseModel):
    blocker_codes: list[str] = Field(default_factory=list)
