import { motion } from 'framer-motion';
import { Badge, Card, Skeleton } from '@/shared/ui';
import { fadeUp, stagger } from '@/shared/utils/motion';
import { ApiError } from '@/shared/api';
import { agentDisplayName } from '@/shared/constants/agents';
import type { AgentRunSummary } from '@/modules/agent_runs/api/client';

interface Props {
  runs: AgentRunSummary[] | undefined;
  isLoading: boolean;
  error: Error | null;
  onOpenRun: (runLogId: number) => void;
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

function duration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function RunsTable({ runs, isLoading, error, onOpenRun }: Props) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Card className="p-6 text-sm text-destructive">
        <div>Couldn't load agent runs: {error.message}</div>
        {error instanceof ApiError && (
          <div className="mt-1 font-mono text-[10px] text-fg-subtle">
            trace: {error.traceId}
          </div>
        )}
      </Card>
    );
  }

  if (!runs?.length) {
    return (
      <Card className="p-10 text-center">
        <div className="text-base font-medium text-fg">No agent runs yet</div>
        <div className="mt-1 text-sm text-fg-muted">
          Trigger the agent above to scan your COD orders and propose actions.
        </div>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <table className="w-full text-sm">
        <thead className="border-b border-border bg-surface-subtle text-xs uppercase tracking-wide text-fg-subtle">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Run</th>
            <th className="px-4 py-3 text-left font-medium">Agent</th>
            <th className="px-4 py-3 text-right font-medium">Scanned</th>
            <th className="px-4 py-3 text-right font-medium">Proposed</th>
            <th className="px-4 py-3 text-left font-medium">Started</th>
            <th className="px-4 py-3 text-right font-medium">Duration</th>
          </tr>
        </thead>
        <motion.tbody variants={stagger} initial="hidden" animate="visible">
          {runs.map((run) => (
            <motion.tr
              variants={fadeUp}
              key={run.run_log_id}
              tabIndex={0}
              role="button"
              aria-label={`Open agent run ${run.run_log_id}`}
              onClick={() => onOpenRun(run.run_log_id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onOpenRun(run.run_log_id);
                }
              }}
              className="cursor-pointer border-t border-border transition-colors hover:bg-surface-subtle focus:outline-none focus:bg-surface-subtle"
            >
              <td className="px-4 py-3 font-mono text-xs text-fg-muted">
                #{run.run_log_id}
              </td>
              <td className="px-4 py-3 text-fg">{agentDisplayName(run.agent)}</td>
              <td className="px-4 py-3 text-right text-fg">{run.orders_scanned}</td>
              <td className="px-4 py-3 text-right">
                {run.actions_proposed > 0 ? (
                  <Badge variant="default">{run.actions_proposed}</Badge>
                ) : (
                  <Badge variant="outline">0</Badge>
                )}
              </td>
              <td className="px-4 py-3 text-fg-muted">{formatDateTime(run.started_at)}</td>
              <td className="px-4 py-3 text-right text-fg-muted">
                {duration(run.started_at, run.finished_at)}
              </td>
            </motion.tr>
          ))}
        </motion.tbody>
      </table>
    </Card>
  );
}
