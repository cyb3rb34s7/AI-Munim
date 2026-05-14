from sqlmodel import Session, col, select

from munim.agents.rto_mitigator.agent import RTOMitigatorAgent
from munim.models import RunLog
from munim.modules.agent_runs.schemas import (
    AgentRunDetail,
    AgentRunListResponse,
    AgentRunSummary,
    TriggerAgentResponse,
)
from munim.shared.constants import AgentName, ErrorCode, RunLogKind
from munim.shared.errors import MunimError


class AgentUnknownError(MunimError):
    code = ErrorCode.AGENT_UNKNOWN.value
    http_status = 404
    message = "Unknown agent."


class AgentRunNotFoundError(MunimError):
    code = ErrorCode.RECORD_NOT_FOUND.value
    http_status = 404
    message = "Agent run not found."


_AGENTS: dict[AgentName, type[RTOMitigatorAgent]] = {
    AgentName.RTO_MITIGATOR: RTOMitigatorAgent,
}


def trigger_agent(
    session: Session, merchant_id: str, agent_name: AgentName
) -> TriggerAgentResponse:
    agent_cls = _AGENTS.get(agent_name)
    if agent_cls is None:
        raise AgentUnknownError(
            message=f"Agent {agent_name.value!r} is not registered.",
            details={"agent": agent_name.value},
        )
    agent = agent_cls()
    summary = agent.run(session, merchant_id)
    return TriggerAgentResponse(
        run=AgentRunSummary(
            run_log_id=summary.run_log_id,
            run_id=summary.run_id,
            agent=agent_name.value,
            orders_scanned=summary.orders_scanned,
            actions_proposed=summary.actions_proposed,
            started_at=summary.started_at,
            finished_at=summary.finished_at,
        )
    )


def list_agent_runs(session: Session, merchant_id: str, limit: int) -> AgentRunListResponse:
    effective_limit = max(1, min(limit, 200))
    rows = session.exec(
        select(RunLog)
        .where(RunLog.merchant_id == merchant_id)
        .where(RunLog.kind == RunLogKind.AGENT.value)
        .order_by(col(RunLog.started_at).desc())
        .limit(effective_limit)
    ).all()
    items = [
        AgentRunSummary(
            run_log_id=r.id if r.id is not None else 0,
            run_id=r.detail_json["run_id"],
            agent=r.detail_json["agent"],
            orders_scanned=r.detail_json["orders_scanned"],
            actions_proposed=r.detail_json["actions_proposed"],
            started_at=r.started_at,
            finished_at=r.finished_at if r.finished_at else r.started_at,
        )
        for r in rows
    ]
    return AgentRunListResponse(items=items)


def get_agent_run(session: Session, merchant_id: str, run_log_id: int) -> AgentRunDetail:
    row = session.exec(
        select(RunLog)
        .where(RunLog.id == run_log_id)
        .where(RunLog.merchant_id == merchant_id)
        .where(RunLog.kind == RunLogKind.AGENT.value)
    ).first()
    if row is None:
        raise AgentRunNotFoundError(
            message=f"Agent run {run_log_id} not found.",
            details={"run_log_id": run_log_id},
        )
    return AgentRunDetail(
        run_log_id=row.id if row.id is not None else 0,
        run_id=row.detail_json["run_id"],
        agent=row.detail_json["agent"],
        started_at=row.started_at,
        finished_at=row.finished_at if row.finished_at else row.started_at,
        orders_scanned=row.detail_json["orders_scanned"],
        actions_proposed=row.detail_json["actions_proposed"],
        decisions=row.detail_json["decisions"],
    )
