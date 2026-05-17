import { useSearchParams } from 'react-router-dom';
import { useAgentRuns } from '@/modules/agent_runs/hooks/useAgentRuns';
import { RunsTable } from './components/RunsTable';
import { RunDetailSheet } from './components/RunDetailSheet';
import { TriggerAgentButton } from './components/TriggerAgentButton';
import { RunBriefingButton } from './components/RunBriefingButton';

const RUN_PARAM = 'run';

export function AgentRunsPage() {
  const { data, isLoading, error } = useAgentRuns(50);
  const [searchParams, setSearchParams] = useSearchParams();

  const runParam = searchParams.get(RUN_PARAM);
  const runLogId = runParam ? Number.parseInt(runParam, 10) : null;
  const activeRunLogId = Number.isFinite(runLogId) ? runLogId : null;

  const openRun = (id: number) => {
    const next = new URLSearchParams(searchParams);
    next.set(RUN_PARAM, String(id));
    setSearchParams(next, { replace: false });
  };

  const closeRun = (open: boolean) => {
    if (open) return;
    const next = new URLSearchParams(searchParams);
    next.delete(RUN_PARAM);
    setSearchParams(next, { replace: false });
  };

  return (
    <div className="mx-auto max-w-5xl p-8 flex flex-col gap-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">Agent runs</h1>
          <p className="mt-1 text-sm text-fg-muted">
            Audit log of every agent run. Click a row to see the full reasoning.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <TriggerAgentButton />
          <RunBriefingButton />
        </div>
      </header>

      <RunsTable runs={data?.items} isLoading={isLoading} error={error} onOpenRun={openRun} />

      <RunDetailSheet runLogId={activeRunLogId} onOpenChange={closeRun} />
    </div>
  );
}
