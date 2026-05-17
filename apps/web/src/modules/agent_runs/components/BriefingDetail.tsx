import { Badge } from '@/shared/ui';
import { CitedText } from '@/modules/chat/components/CitedText';
import { SECTOR_LABEL, type Sector } from '@/shared/constants/sectors';
import type {
  AgentRunDetail,
  ProposedAction,
  RowCitation,
} from '@/modules/agent_runs/api/client';

interface Props {
  detail: AgentRunDetail;
}

function sectorLabelFor(value: string | null | undefined): string | null {
  if (!value) return null;
  return SECTOR_LABEL[value as Sector] ?? value;
}

export function BriefingDetail({ detail }: Props) {
  const citations: RowCitation[] = detail.citations ?? [];
  const sectorLabel = sectorLabelFor(detail.sector ?? null);
  const actions: ProposedAction[] = detail.proposed_actions ?? [];

  return (
    <>
      <section className="rounded-lg border border-border bg-surface-subtle p-5">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-fg-subtle">
          {sectorLabel && <Badge variant="outline">{sectorLabel}</Badge>}
          <span>weekly briefing</span>
        </div>
        <div className="mt-3 text-sm text-fg leading-relaxed">
          <CitedText text={detail.narrative ?? ''} citations={citations} />
        </div>
      </section>

      {actions.length > 0 && (
        <section>
          <div className="text-xs font-medium uppercase tracking-wider text-fg-subtle mb-3">
            Proposed actions
          </div>
          <div className="flex flex-col gap-3">
            {actions.map((a, i) => (
              <div key={i} className="rounded-lg border border-border bg-surface p-4">
                <div className="text-sm font-medium text-fg">{a.action_type}</div>
                <div className="mt-1.5 text-sm text-fg-muted leading-relaxed">
                  <CitedText text={a.reasoning} citations={citations} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
