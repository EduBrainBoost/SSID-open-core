from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ems.auth import Identity, get_current_identity
from ems.schemas.sot_promotion import (
    ActiveBaselineStateResponse,
    CandidateActionRequest,
    CandidateActionResponse,
    CandidateDetailResponse,
    CandidateListResponse,
    ExecutionGatewayActionResponse,
    ExecutionGatewayBlockersResponse,
    ExecutionGatewayEvaluationResponse,
    ExecutionGatewayLiveStatusResponse,
    ExecutionGatewayRequest,
    ExecutionGatewayRunItem,
    ExecutionGatewayRunListResponse,
    FreezeEvaluateRequest,
    FreezeEvaluateResponse,
    FreezeStateResponse,
    FreezeStateUpdateRequest,
    OperatorApprovalListResponse,
    PromotionExecuteRequest,
    PromotionExecuteResponse,
    PromotionExecutionHistoryItem,
    PromotionExecutionHistoryListResponse,
    PromotionTimelineResponse,
    RollbackEvaluateRequest,
    RollbackEvaluateResponse,
    RollbackProposalCreateRequest,
    RollbackProposalCreateResponse,
    RollbackProposalDecisionRequest,
    RollbackProposalDecisionResponse,
    RollbackProposalDetailResponse,
    RollbackProposalListResponse,
    RollbackRecoveryExecuteRequest,
    RollbackRecoveryExecuteResponse,
)
from ems.services.execution_gateway import (
    abort_execution_run,
    defer_execution_run,
    evaluate_execution_run,
    get_execution_blockers,
    get_execution_live_status,
    get_gateway_run,
    list_gateway_runs,
    start_execution_run,
)
from ems.services.sot_incident_freeze_governance import (
    FreezeGovernanceError,
    evaluate_promotion_freeze_gate,
    evaluate_recovery_freeze_gate,
    load_freeze_state,
    write_freeze_state,
)
from ems.services.sot_promotion_execution_service import (
    ExecutionHandoffError,
    build_operator_audit_timeline,
    execute_promotion_handoff,
    get_execution_history_item,
    list_execution_history,
    validate_rollback_guard,
)
from ems.services.sot_promotion_service import (
    RegistryConsistencyError,
    approve_candidate,
    get_candidate,
    list_candidates,
    list_operator_approvals,
    load_active_baseline_state,
    reject_candidate,
)
from ems.services.sot_rollback_proposal_service import (
    decide_rollback_proposal,
    evaluate_and_build_rollback_proposal,
    get_rollback_proposal,
    list_rollback_proposals,
)
from ems.services.sot_rollback_recovery_service import execute_guarded_recovery_handoff

router = APIRouter(prefix="/api/sot/promotion", tags=["sot-promotion"])


def _repo_root(request: Request) -> Path:
    return Path(request.app.state.repo_root)


def _map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FreezeGovernanceError):
        return HTTPException(status_code=exc.http_status, detail=str(exc))
    if isinstance(exc, ExecutionHandoffError):
        return HTTPException(status_code=exc.http_status, detail=str(exc))
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    if isinstance(exc, RegistryConsistencyError):
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/active-state", response_model=ActiveBaselineStateResponse)
def get_active_state(
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> ActiveBaselineStateResponse:
    try:
        return ActiveBaselineStateResponse.model_validate(load_active_baseline_state(_repo_root(request)))
    except Exception as exc:  # fail-closed mapping
        raise _map_error(exc) from exc


@router.get("/freeze-state", response_model=FreezeStateResponse)
def get_freeze_state(
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> FreezeStateResponse:
    try:
        return FreezeStateResponse.model_validate(load_freeze_state(_repo_root(request)))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/freeze-state", response_model=FreezeStateResponse)
def set_freeze_state(
    body: FreezeStateUpdateRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> FreezeStateResponse:
    try:
        return FreezeStateResponse.model_validate(
            write_freeze_state(
                _repo_root(request),
                body.freeze_level,
                body.reason,
                body.set_by,
                body.incident_id,
                body.scope,
            )
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/freeze-evaluate", response_model=FreezeEvaluateResponse)
def evaluate_freeze_state(
    body: FreezeEvaluateRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> FreezeEvaluateResponse:
    try:
        if body.operation_type == "promotion_execute":
            decision = evaluate_promotion_freeze_gate(
                _repo_root(request),
                candidate_id=body.candidate_id or "unknown-candidate",
                reason=body.reason,
            )
        else:
            decision = evaluate_recovery_freeze_gate(
                _repo_root(request),
                operation_type=body.operation_type,
                proposal_id=body.proposal_id,
                target_baseline_version=body.target_baseline_version,
                reason=body.reason,
            )
        return FreezeEvaluateResponse.model_validate(
            {
                "operation_type": body.operation_type,
                "freeze_level": decision["freeze_state"]["freeze_level"],
                "decision": decision["decision"],
                "allowed": decision["allowed"],
                "candidate_id": body.candidate_id,
                "proposal_id": body.proposal_id,
                "findings": [],
            }
        )
    except FreezeGovernanceError as exc:
        return FreezeEvaluateResponse.model_validate(
            {
                "operation_type": body.operation_type,
                "freeze_level": load_freeze_state(_repo_root(request))["freeze_level"],
                "decision": "FAIL",
                "allowed": False,
                "candidate_id": body.candidate_id,
                "proposal_id": body.proposal_id,
                "findings": exc.findings,
            }
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/candidates", response_model=CandidateListResponse)
def get_candidates(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    _: Identity = Depends(get_current_identity),
) -> CandidateListResponse:
    try:
        return CandidateListResponse(items=list_candidates(_repo_root(request), status=status_filter))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/candidates/pending", response_model=CandidateListResponse)
def get_pending_candidates(
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> CandidateListResponse:
    try:
        return CandidateListResponse(items=list_candidates(_repo_root(request), status="pending"))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/candidates/{candidate_id}", response_model=CandidateDetailResponse)
def get_candidate_detail(
    candidate_id: str,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> CandidateDetailResponse:
    try:
        return CandidateDetailResponse.model_validate(get_candidate(_repo_root(request), candidate_id))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/approvals", response_model=OperatorApprovalListResponse)
def get_approvals(
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> OperatorApprovalListResponse:
    try:
        return OperatorApprovalListResponse(items=list_operator_approvals(_repo_root(request)))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/executions", response_model=PromotionExecutionHistoryListResponse)
def get_execution_history(
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> PromotionExecutionHistoryListResponse:
    try:
        return PromotionExecutionHistoryListResponse(items=list_execution_history(_repo_root(request)))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/executions/{execution_id}", response_model=PromotionExecutionHistoryItem)
def get_execution_history_detail(
    execution_id: str,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> PromotionExecutionHistoryItem:
    try:
        return PromotionExecutionHistoryItem.model_validate(
            get_execution_history_item(_repo_root(request), execution_id)
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/timeline", response_model=PromotionTimelineResponse)
def get_timeline(
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> PromotionTimelineResponse:
    try:
        return PromotionTimelineResponse(items=build_operator_audit_timeline(_repo_root(request)))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/candidates/{candidate_id}/approve", response_model=CandidateActionResponse)
def approve_candidate_route(
    candidate_id: str,
    body: CandidateActionRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> CandidateActionResponse:
    try:
        return CandidateActionResponse.model_validate(
            approve_candidate(_repo_root(request), candidate_id, body.approved_by, body.reason)
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/candidates/{candidate_id}/reject", response_model=CandidateActionResponse)
def reject_candidate_route(
    candidate_id: str,
    body: CandidateActionRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> CandidateActionResponse:
    try:
        return CandidateActionResponse.model_validate(
            reject_candidate(_repo_root(request), candidate_id, body.approved_by, body.reason)
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/candidates/{candidate_id}/execute", response_model=PromotionExecuteResponse)
def execute_candidate_route(
    candidate_id: str,
    body: PromotionExecuteRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> PromotionExecuteResponse:
    try:
        return PromotionExecuteResponse.model_validate(
            execute_promotion_handoff(
                _repo_root(request),
                candidate_id,
                body.executed_by,
                body.reason,
            )
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/execution/evaluate", response_model=ExecutionGatewayEvaluationResponse)
def evaluate_execution_gateway_route(
    body: ExecutionGatewayRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> ExecutionGatewayEvaluationResponse:
    try:
        return ExecutionGatewayEvaluationResponse.model_validate(
            evaluate_execution_run(
                repo_root=_repo_root(request),
                execution_target=body.execution_target,
                target_id=body.target_id,
                requested_by=body.requested_by,
                reason=body.reason,
            )
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/execution/start", response_model=ExecutionGatewayActionResponse)
def start_execution_gateway_route(
    body: ExecutionGatewayRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> ExecutionGatewayActionResponse:
    try:
        return ExecutionGatewayActionResponse.model_validate(
            start_execution_run(
                repo_root=_repo_root(request),
                execution_target=body.execution_target,
                target_id=body.target_id,
                requested_by=body.requested_by,
                reason=body.reason,
            )
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/execution/defer", response_model=ExecutionGatewayActionResponse)
def defer_execution_gateway_route(
    body: ExecutionGatewayRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> ExecutionGatewayActionResponse:
    try:
        return ExecutionGatewayActionResponse.model_validate(
            defer_execution_run(
                repo_root=_repo_root(request),
                execution_target=body.execution_target,
                target_id=body.target_id,
                requested_by=body.requested_by,
                reason=body.reason,
            )
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/execution/abort", response_model=ExecutionGatewayActionResponse)
def abort_execution_gateway_route(
    body: ExecutionGatewayRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> ExecutionGatewayActionResponse:
    try:
        return ExecutionGatewayActionResponse.model_validate(
            abort_execution_run(
                repo_root=_repo_root(request),
                execution_target=body.execution_target,
                target_id=body.target_id,
                requested_by=body.requested_by,
                reason=body.reason,
            )
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/execution/runs", response_model=ExecutionGatewayRunListResponse)
def get_execution_runs_route(
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> ExecutionGatewayRunListResponse:
    try:
        return ExecutionGatewayRunListResponse.model_validate({"items": list_gateway_runs(_repo_root(request))})
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/execution/runs/{run_id}", response_model=ExecutionGatewayRunItem)
def get_execution_run_detail_route(
    run_id: str,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> ExecutionGatewayRunItem:
    try:
        return ExecutionGatewayRunItem.model_validate(get_gateway_run(_repo_root(request), run_id))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/execution/live-status", response_model=ExecutionGatewayLiveStatusResponse)
def get_execution_live_status_route(
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> ExecutionGatewayLiveStatusResponse:
    try:
        return ExecutionGatewayLiveStatusResponse.model_validate(get_execution_live_status(_repo_root(request)))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/execution/blockers", response_model=ExecutionGatewayBlockersResponse)
def get_execution_blockers_route(
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> ExecutionGatewayBlockersResponse:
    try:
        return ExecutionGatewayBlockersResponse.model_validate(get_execution_blockers(_repo_root(request)))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/rollback-evaluate", response_model=RollbackEvaluateResponse)
def evaluate_rollback_route(
    body: RollbackEvaluateRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> RollbackEvaluateResponse:
    try:
        evaluate_recovery_freeze_gate(
            _repo_root(request),
            operation_type="rollback_evaluate",
            proposal_id=None,
            target_baseline_version=body.target_baseline_version,
            reason=body.reason,
        )
        return RollbackEvaluateResponse.model_validate(
            validate_rollback_guard(
                _repo_root(request),
                body.requested_by,
                body.target_baseline_version,
                body.reason,
            )
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/rollback-proposals", response_model=RollbackProposalListResponse)
def get_rollback_proposals(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    _: Identity = Depends(get_current_identity),
) -> RollbackProposalListResponse:
    try:
        return RollbackProposalListResponse(items=list_rollback_proposals(_repo_root(request), status_filter))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/rollback-proposals/{proposal_id}", response_model=RollbackProposalDetailResponse)
def get_rollback_proposal_detail(
    proposal_id: str,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> RollbackProposalDetailResponse:
    try:
        return RollbackProposalDetailResponse.model_validate(get_rollback_proposal(_repo_root(request), proposal_id))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/rollback-proposals", response_model=RollbackProposalCreateResponse)
def create_rollback_proposal_route(
    body: RollbackProposalCreateRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> RollbackProposalCreateResponse:
    try:
        return RollbackProposalCreateResponse.model_validate(
            evaluate_and_build_rollback_proposal(
                _repo_root(request),
                body.created_by,
                body.target_baseline_version,
                body.reason,
            )
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/rollback-proposals/{proposal_id}/approve",
    response_model=RollbackProposalDecisionResponse,
)
def approve_rollback_proposal_route(
    proposal_id: str,
    body: RollbackProposalDecisionRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> RollbackProposalDecisionResponse:
    try:
        return RollbackProposalDecisionResponse.model_validate(
            decide_rollback_proposal(
                _repo_root(request),
                proposal_id,
                body.approved_by,
                "approve",
                body.reason,
            )
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/rollback-proposals/{proposal_id}/reject",
    response_model=RollbackProposalDecisionResponse,
)
def reject_rollback_proposal_route(
    proposal_id: str,
    body: RollbackProposalDecisionRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> RollbackProposalDecisionResponse:
    try:
        return RollbackProposalDecisionResponse.model_validate(
            decide_rollback_proposal(
                _repo_root(request),
                proposal_id,
                body.approved_by,
                "reject",
                body.reason,
            )
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/rollback-proposals/{proposal_id}/execute",
    response_model=RollbackRecoveryExecuteResponse,
)
def execute_rollback_recovery_route(
    proposal_id: str,
    body: RollbackRecoveryExecuteRequest,
    request: Request,
    _: Identity = Depends(get_current_identity),
) -> RollbackRecoveryExecuteResponse:
    try:
        return RollbackRecoveryExecuteResponse.model_validate(
            execute_guarded_recovery_handoff(
                _repo_root(request),
                proposal_id,
                body.executed_by,
                body.reason,
            )
        )
    except Exception as exc:
        raise _map_error(exc) from exc
