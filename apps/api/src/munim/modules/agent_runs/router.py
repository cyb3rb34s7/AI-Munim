from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from munim.modules.agent_runs.schemas import (
    AgentRunDetail,
    AgentRunListResponse,
    TriggerAgentResponse,
)
from munim.modules.agent_runs.service import (
    AgentUnknownError,
    get_agent_run,
    list_agent_runs,
    trigger_agent,
)
from munim.shared.constants import AgentName
from munim.shared.db import DEFAULT_MERCHANT_ID, get_session
from munim.shared.responses import SuccessEnvelope

router = APIRouter(tags=["agent-runs"])


@router.post(
    "/agents/{name}/run",
    response_model=SuccessEnvelope[TriggerAgentResponse],
)
def trigger_agent_endpoint(
    name: str,
    request: Request,
    session: Session = Depends(get_session),
) -> SuccessEnvelope[TriggerAgentResponse]:
    try:
        agent_name = AgentName(name)
    except ValueError as exc:
        raise AgentUnknownError(
            message=f"Agent {name!r} is not registered.",
            details={"agent": name},
        ) from exc
    result = trigger_agent(session, DEFAULT_MERCHANT_ID, agent_name)
    session.commit()
    return SuccessEnvelope(data=result, trace_id=request.state.trace_id)


@router.get(
    "/agent-runs",
    response_model=SuccessEnvelope[AgentRunListResponse],
)
def list_endpoint(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> SuccessEnvelope[AgentRunListResponse]:
    data = list_agent_runs(session, DEFAULT_MERCHANT_ID, limit)
    return SuccessEnvelope(data=data, trace_id=request.state.trace_id)


@router.get(
    "/agent-runs/{run_log_id}",
    response_model=SuccessEnvelope[AgentRunDetail],
)
def detail_endpoint(
    run_log_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> SuccessEnvelope[AgentRunDetail]:
    data = get_agent_run(session, DEFAULT_MERCHANT_ID, run_log_id)
    return SuccessEnvelope(data=data, trace_id=request.state.trace_id)
