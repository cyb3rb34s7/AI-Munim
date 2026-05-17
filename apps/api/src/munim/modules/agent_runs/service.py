from sqlmodel import Session, col, select

from munim.agents.daily_briefing.constants import Sector as BriefingSector
from munim.agents.daily_briefing.service import run_briefing
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


class AgentRunFailedError(MunimError):
    code = ErrorCode.AGENT_RUN_FAILED.value
    http_status = 500
    message = "Agent run failed."


class AgentRunNotFoundError(MunimError):
    code = ErrorCode.AGENT_RUN_NOT_FOUND.value
    http_status = 404
    message = "Agent run not found."


class SectorRequiredError(MunimError):
    code = ErrorCode.VALIDATION_MISSING_FIELD.value
    http_status = 400
    message = "sector is required for the daily-briefing agent."


_AGENTS: dict[AgentName, type[RTOMitigatorAgent]] = {
    AgentName.RTO_MITIGATOR: RTOMitigatorAgent,
}


async def trigger_agent(
    session: Session,
    merchant_id: str,
    agent_name: AgentName,
    *,
    sector: str | None = None,
    trace_id: str | None = None,
) -> TriggerAgentResponse:
    if agent_name is AgentName.DAILY_BRIEFING:
        if sector is None:
            raise SectorRequiredError(
                message="sector is required for the daily-briefing agent.",
                details={"agent": agent_name.value},
            )
        try:
            sector_enum = BriefingSector(sector)
        except ValueError as exc:
            raise SectorRequiredError(
                message=f"Unknown sector {sector!r}.",
                details={
                    "sector": sector,
                    "valid": [s.value for s in BriefingSector],
                },
            ) from exc
        briefing_summary = await run_briefing(session, merchant_id, sector_enum, trace_id=trace_id)
        return TriggerAgentResponse(
            run=AgentRunSummary(
                run_log_id=briefing_summary.run_log_id,
                run_id=briefing_summary.run_id,
                agent=agent_name.value,
                orders_scanned=briefing_summary.items_scanned,
                actions_proposed=briefing_summary.actions_proposed,
                started_at=briefing_summary.started_at,
                finished_at=briefing_summary.finished_at,
            )
        )

    agent_cls = _AGENTS.get(agent_name)
    if agent_cls is None:
        raise AgentUnknownError(
            message=f"Agent {agent_name.value!r} is not registered.",
            details={"agent": agent_name.value},
        )
    agent = agent_cls()
    try:
        summary = agent.run(session, merchant_id)
    except MunimError:
        raise
    except (KeyError, ValueError) as exc:
        raise AgentRunFailedError(
            message=f"Agent {agent_name.value!r} run failed on a malformed record.",
            details={"agent": agent_name.value, "reason": str(exc)},
        ) from exc
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
    detail = row.detail_json
    return AgentRunDetail(
        run_log_id=row.id if row.id is not None else 0,
        run_id=detail["run_id"],
        agent=detail["agent"],
        started_at=row.started_at,
        finished_at=row.finished_at if row.finished_at else row.started_at,
        orders_scanned=detail["orders_scanned"],
        actions_proposed=detail["actions_proposed"],
        decisions=detail.get("decisions", []),
        sector=detail.get("sector"),
        narrative=detail.get("narrative"),
        proposed_actions=detail.get("proposed_actions"),
        citations=detail.get("citations"),
    )
