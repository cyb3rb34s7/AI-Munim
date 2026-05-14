import { motion } from 'framer-motion';
import {
  Badge,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Skeleton,
} from '@/shared/ui';
import { useAgentRun } from '@/modules/agent_runs/hooks/useAgentRun';
import { AgentAction, type AgentRunDecision } from '@/modules/agent_runs/api/client';
import { ActionDonut } from './ActionDonut';
import { fadeUp, stagger } from '@/shared/utils/motion';

interface Props {
  runLogId: number | null;
  onOpenChange: (open: boolean) => void;
}

const ACTION_VARIANT: Record<AgentAction, 'default' | 'warning' | 'outline'> = {
  [AgentAction.CONVERT_TO_PREPAID]: 'default',
  [AgentAction.CONFIRMATION_CALL]: 'warning',
  [AgentAction.NO_ACTION]: 'outline',
};

const ACTION_LABEL: Record<AgentAction, string> = {
  [AgentAction.CONVERT_TO_PREPAID]: 'Convert to prepaid',
  [AgentAction.CONFIRMATION_CALL]: 'Confirmation call',
  [AgentAction.NO_ACTION]: 'No action',
};

function formatINR(value: string): string {
  const num = Number(value);
  if (!Number.isFinite(num)) return `Rs ${value}`;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(num);
}

function DecisionRow({ decision }: { decision: AgentRunDecision }) {
  return (
    <motion.div
      variants={fadeUp}
      className="rounded-lg border border-border bg-surface p-4 flex flex-col gap-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={ACTION_VARIANT[decision.action]}>{ACTION_LABEL[decision.action]}</Badge>
            <span className="text-xs text-fg-subtle">score {decision.score.toFixed(2)}</span>
          </div>
          <div className="mt-1.5 font-mono text-xs text-fg-muted truncate">
            {decision.source_id}
          </div>
        </div>
        {decision.action !== AgentAction.NO_ACTION && (
          <div className="text-right">
            <div className="text-[11px] uppercase tracking-wider text-fg-subtle">Est. saved</div>
            <div className="text-sm font-semibold text-fg">
              {formatINR(decision.estimated_inr_saved)}
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {Object.entries(decision.signal_scores).map(([key, value]) => (
          <span
            key={key}
            className="inline-flex items-center gap-1 rounded-md bg-surface-elevated px-2 py-0.5 text-[11px] text-fg-muted"
          >
            <span className="font-medium text-fg">{key}</span>
            <span className="text-fg-subtle">{value.toFixed(2)}</span>
          </span>
        ))}
      </div>

      <div className="text-sm leading-relaxed text-fg-muted">{decision.reasoning}</div>
    </motion.div>
  );
}

export function RunDetailSheet({ runLogId, onOpenChange }: Props) {
  const { data, isLoading, error } = useAgentRun(runLogId);

  return (
    <Sheet open={runLogId !== null} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>{data ? `Run #${data.run_log_id}` : 'Agent run'}</SheetTitle>
          <SheetDescription>
            {data
              ? `${data.agent} · started ${new Date(data.started_at).toLocaleString()}`
              : 'Loading run details…'}
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6">
          {isLoading && (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-[200px] w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          )}

          {error && (
            <div className="text-sm text-destructive">
              Couldn't load run: {error.message}
            </div>
          )}

          {data && (
            <>
              <section>
                <div className="text-xs font-medium uppercase tracking-wider text-fg-subtle mb-2">
                  Action distribution
                </div>
                <ActionDonut decisions={data.decisions} />
                <div className="mt-2 grid grid-cols-3 gap-3 text-center text-xs">
                  <div>
                    <div className="font-semibold text-fg">{data.orders_scanned}</div>
                    <div className="text-fg-subtle">scanned</div>
                  </div>
                  <div>
                    <div className="font-semibold text-fg">{data.actions_proposed}</div>
                    <div className="text-fg-subtle">proposed</div>
                  </div>
                  <div>
                    <div className="font-semibold text-fg">{data.decisions.length}</div>
                    <div className="text-fg-subtle">decisions</div>
                  </div>
                </div>
              </section>

              <section>
                <div className="text-xs font-medium uppercase tracking-wider text-fg-subtle mb-3">
                  Per-order decisions
                </div>
                <motion.div
                  variants={stagger}
                  initial="hidden"
                  animate="visible"
                  className="flex flex-col gap-3"
                >
                  {data.decisions.map((decision) => (
                    <DecisionRow key={decision.record_id} decision={decision} />
                  ))}
                </motion.div>
              </section>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
