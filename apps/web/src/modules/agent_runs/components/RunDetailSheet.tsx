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
import { ApiError } from '@/shared/api';
import { inr, InvalidMoneyError } from '@/shared/utils/inr';
import { agentDisplayName } from '@/shared/constants/agents';

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

const ACTION_HEADLINE: Record<AgentAction, string> = {
  [AgentAction.CONVERT_TO_PREPAID]: 'Recommend converting to prepaid before shipping.',
  [AgentAction.CONFIRMATION_CALL]: 'Recommend a confirmation call before shipping.',
  [AgentAction.NO_ACTION]: 'No intervention needed — ship as planned.',
};

const SIGNAL_LABEL: Record<string, string> = {
  value: 'Order value',
  pincode: 'Delivery pincode',
  time: 'Time of order',
  customer: 'Customer history',
};

const CONVERT_THRESHOLD = 0.6;
const CALL_THRESHOLD = 0.4;

interface ValueDiagnostic {
  total_inr?: string;
  bucket?: 'low' | 'medium' | 'high';
}
interface PincodeDiagnostic {
  pincode?: string;
  in_high_risk_list?: boolean;
}
interface TimeDiagnostic {
  hour_ist?: number;
  hour_band?: 'late_night' | 'business_hours' | 'evening';
}
interface CustomerDiagnostic {
  history_count?: number;
  rto_count?: number;
  observed_rate?: number;
  rate_source?: 'customer_history' | 'population_baseline';
  confident?: boolean;
}

function renderSavings(value: string): string {
  try {
    return inr(value);
  } catch (err) {
    if (err instanceof InvalidMoneyError) return '—';
    throw err;
  }
}

function formatHour(hour: number): string {
  if (hour === 0) return 'midnight';
  if (hour === 12) return 'noon';
  if (hour < 12) return `${hour} am`;
  return `${hour - 12} pm`;
}

function buildOrderContext(decision: AgentRunDecision): string {
  const value = decision.signal_diagnostics.value as ValueDiagnostic | undefined;
  const pincode = decision.signal_diagnostics.pincode as PincodeDiagnostic | undefined;
  const time = decision.signal_diagnostics.time as TimeDiagnostic | undefined;

  const parts: string[] = [];
  if (value?.total_inr) {
    parts.push(`₹${Number(value.total_inr).toLocaleString('en-IN')} COD order`);
  } else {
    parts.push('COD order');
  }
  if (pincode?.pincode) {
    const flagged = pincode.in_high_risk_list ? ' (flagged high-RTO)' : '';
    parts.push(`to pincode ${pincode.pincode}${flagged}`);
  }
  if (typeof time?.hour_ist === 'number') {
    parts.push(`placed at ${formatHour(time.hour_ist)}`);
  }
  return parts.join(', ');
}

function buildReasoningSentences(decision: AgentRunDecision): string[] {
  const sentences: string[] = [];
  const customer = decision.signal_diagnostics.customer as CustomerDiagnostic | undefined;
  const pincode = decision.signal_diagnostics.pincode as PincodeDiagnostic | undefined;
  const time = decision.signal_diagnostics.time as TimeDiagnostic | undefined;
  const value = decision.signal_diagnostics.value as ValueDiagnostic | undefined;

  if (
    customer?.rate_source === 'customer_history' &&
    typeof customer.history_count === 'number' &&
    typeof customer.rto_count === 'number' &&
    customer.rto_count > 0
  ) {
    sentences.push(
      `This customer has returned ${customer.rto_count} of their last ${customer.history_count} deliveries — well above the 20% baseline.`,
    );
  } else if (customer?.rate_source === 'population_baseline') {
    sentences.push(
      `Not enough history on this customer yet; using the population baseline RTO rate (20%).`,
    );
  }

  if (pincode?.in_high_risk_list) {
    sentences.push(
      `Pincode ${pincode.pincode} is on our high-RTO watchlist — orders here historically RTO more often.`,
    );
  }

  if (time?.hour_band === 'late_night') {
    sentences.push(
      `Placed late at night (${formatHour(time.hour_ist ?? 0)} IST), where impulse-purchase RTO rates spike.`,
    );
  }

  if (value?.bucket === 'high') {
    sentences.push(
      `Order value is in the high bracket (>₹5,000) — a return would be especially costly.`,
    );
  }

  if (sentences.length === 0) {
    sentences.push(
      `All risk signals were within normal bounds; the order looks like any other COD shipment.`,
    );
  }
  return sentences;
}

function describeSignal(
  name: string,
  diagnostic: Record<string, unknown> | undefined,
): string {
  if (!diagnostic) return '—';
  if (name === 'value') {
    const total = diagnostic.total_inr as string | undefined;
    const bucket = diagnostic.bucket as string | undefined;
    const amount = total ? `₹${Number(total).toLocaleString('en-IN')}` : 'Unknown';
    const bracket =
      bucket === 'high' ? 'high bracket' : bucket === 'medium' ? 'medium bracket' : 'low bracket';
    return `${amount} — ${bracket}`;
  }
  if (name === 'pincode') {
    const pincode = diagnostic.pincode as string | null | undefined;
    const flagged = diagnostic.in_high_risk_list as boolean | undefined;
    if (!pincode) return 'No pincode on order';
    return flagged
      ? `Pincode ${pincode} — on high-RTO watchlist`
      : `Pincode ${pincode} — not flagged`;
  }
  if (name === 'time') {
    const hour = diagnostic.hour_ist as number | undefined;
    const band = diagnostic.hour_band as string | undefined;
    const bandLabel =
      band === 'late_night'
        ? 'late night'
        : band === 'business_hours'
          ? 'business hours'
          : 'evening';
    return typeof hour === 'number' ? `${formatHour(hour)} — ${bandLabel}` : bandLabel;
  }
  if (name === 'customer') {
    const rateSource = diagnostic.rate_source as string | undefined;
    const history = diagnostic.history_count as number | undefined;
    const rto = diagnostic.rto_count as number | undefined;
    if (
      rateSource === 'customer_history' &&
      typeof history === 'number' &&
      typeof rto === 'number'
    ) {
      return `${rto} of ${history} prior deliveries returned`;
    }
    if (typeof history === 'number' && history > 0) {
      return `Only ${history} prior deliveries — using 20% baseline`;
    }
    return 'No prior delivery history — using 20% baseline';
  }
  return '—';
}

function thresholdNote(score: number): string {
  if (score >= CONVERT_THRESHOLD) {
    return `Above 0.60 — strong enough to recommend converting to prepaid.`;
  }
  if (score >= CALL_THRESHOLD) {
    return `Above 0.40 — enough to recommend a confirmation call, below 0.60 (convert).`;
  }
  return `Below 0.40 — no action needed.`;
}

function totalEstimatedSaved(decisions: AgentRunDecision[]): string {
  let total = 0;
  for (const d of decisions) {
    if (d.action === AgentAction.NO_ACTION) continue;
    const n = Number(d.estimated_inr_saved);
    if (Number.isFinite(n)) total += n;
  }
  return inr(total);
}

function DecisionRow({ decision }: { decision: AgentRunDecision }) {
  const dimmed = decision.action === AgentAction.NO_ACTION;
  const orderContext = buildOrderContext(decision);
  const reasoning = buildReasoningSentences(decision);

  return (
    <motion.div
      variants={fadeUp}
      className={`rounded-lg border border-border bg-surface p-5 flex flex-col gap-4 ${dimmed ? 'opacity-60' : ''}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex flex-col gap-1">
          <Badge variant={ACTION_VARIANT[decision.action]} className="self-start">
            {ACTION_LABEL[decision.action]}
          </Badge>
          <div className="text-sm font-medium text-fg leading-snug">
            {ACTION_HEADLINE[decision.action]}
          </div>
        </div>
        {decision.action !== AgentAction.NO_ACTION && (
          <div className="text-right shrink-0">
            <div className="text-[11px] uppercase tracking-wider text-fg-subtle">Could save</div>
            <div className="text-base font-semibold text-fg">
              {renderSavings(decision.estimated_inr_saved)}
            </div>
          </div>
        )}
      </div>

      <div className="text-sm text-fg-muted leading-relaxed">
        <span className="text-fg-subtle">Order </span>
        <span className="font-mono text-fg">#{decision.source_id}</span>
        <span className="text-fg-subtle"> — </span>
        <span>{orderContext}</span>
      </div>

      <div className="flex flex-col gap-1.5">
        {reasoning.map((line, i) => (
          <div key={i} className="text-sm text-fg leading-relaxed flex gap-2">
            <span className="text-primary mt-0.5">•</span>
            <span>{line}</span>
          </div>
        ))}
      </div>

      <details className="group">
        <summary className="cursor-pointer text-xs text-fg-subtle hover:text-fg-muted transition-colors select-none">
          <span className="group-open:hidden">See how the score was built →</span>
          <span className="hidden group-open:inline">Hide the math ↑</span>
        </summary>
        <div className="mt-3 pt-3 border-t border-border flex flex-col gap-3">
          <div className="text-[11px] text-fg-muted leading-relaxed">
            Each risk signal scores 0–1; each carries a weight that sums to 1 across all signals.
            Contribution = signal × weight. The four contributions add up to the order's risk
            score, which is then compared to two thresholds.
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-fg-subtle">
                <th className="text-left py-1.5 font-medium">Signal</th>
                <th className="text-right py-1.5 font-medium">Contribution</th>
                <th className="text-left py-1.5 pl-4 font-medium">Why</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(decision.signal_scores).map(([name, scoreVal]) => {
                const weight = decision.weights[name] ?? 0;
                const contribution = scoreVal * weight;
                return (
                  <tr key={name} className="border-t border-border">
                    <td className="py-2 text-fg">{SIGNAL_LABEL[name] ?? name}</td>
                    <td className="py-2 text-right font-mono text-fg tabular-nums">
                      +{contribution.toFixed(2)}
                    </td>
                    <td className="py-2 pl-4 text-fg-muted">
                      {describeSignal(name, decision.signal_diagnostics[name])}
                    </td>
                  </tr>
                );
              })}
              <tr className="border-t-2 border-border-strong">
                <td className="py-2 text-fg font-semibold">Total</td>
                <td className="py-2 text-right font-mono text-fg font-semibold tabular-nums">
                  {decision.score.toFixed(2)}
                </td>
                <td className="py-2 pl-4 text-fg-muted text-[11px]">
                  {thresholdNote(decision.score)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>
    </motion.div>
  );
}

export function RunDetailSheet({ runLogId, onOpenChange }: Props) {
  const { data, isLoading, error } = useAgentRun(runLogId);

  const totalSaved = data ? totalEstimatedSaved(data.decisions) : null;
  const actionable = data ? data.decisions.filter((d) => d.action !== AgentAction.NO_ACTION) : [];

  return (
    <Sheet open={runLogId !== null} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>{data ? `Agent run #${data.run_log_id}` : 'Agent run'}</SheetTitle>
          <SheetDescription>
            {data
              ? `${agentDisplayName(data.agent)} · ${new Date(data.started_at).toLocaleString()}`
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
              <div>Couldn't load run: {error.message}</div>
              {error instanceof ApiError && (
                <div className="mt-1 font-mono text-[10px] text-fg-subtle">
                  trace: {error.traceId}
                </div>
              )}
            </div>
          )}

          {data && (
            <>
              <section className="rounded-lg border border-border bg-surface-subtle p-5">
                {totalSaved && Number(totalSaved.replace(/[^\d.-]/g, '')) > 0 ? (
                  <>
                    <div className="text-xs font-medium uppercase tracking-wider text-fg-subtle">
                      Estimated impact
                    </div>
                    <div className="mt-1 text-3xl font-semibold text-fg tracking-tight">
                      {totalSaved}
                    </div>
                    <div className="mt-1 text-sm text-fg-muted">
                      potential RTO loss avoided across {actionable.length}{' '}
                      {actionable.length === 1 ? 'order' : 'orders'} (of {data.orders_scanned}{' '}
                      scanned)
                    </div>
                  </>
                ) : (
                  <>
                    <div className="text-xs font-medium uppercase tracking-wider text-fg-subtle">
                      Result
                    </div>
                    <div className="mt-1 text-lg font-semibold text-fg">
                      No actions needed
                    </div>
                    <div className="mt-1 text-sm text-fg-muted">
                      Scanned {data.orders_scanned}{' '}
                      {data.orders_scanned === 1 ? 'order' : 'orders'}; nothing flagged this run.
                    </div>
                  </>
                )}
              </section>

              {data.decisions.length > 0 && (
                <section>
                  <div className="text-xs font-medium uppercase tracking-wider text-fg-subtle mb-3">
                    Breakdown
                  </div>
                  <ActionDonut decisions={data.decisions} />
                </section>
              )}

              {data.decisions.length > 0 && (
                <section>
                  <div className="text-xs font-medium uppercase tracking-wider text-fg-subtle mb-3">
                    Per-order recommendations
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
              )}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
