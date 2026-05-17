import { type ReactNode } from 'react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui';
import type { RowCitation } from '@/modules/chat/api/client';

interface Props {
  citations: RowCitation[];
  children: ReactNode;
}

const ENTITY_LABEL: Record<string, string> = {
  order: 'Order',
  shipment: 'Shipment',
  ad_spend: 'Ad spend',
};

function entityLabel(type: string): string {
  return ENTITY_LABEL[type] ?? type;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null;
}

function rupee(value: unknown): string | null {
  if (typeof value !== 'string' && typeof value !== 'number') return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return `₹${n.toLocaleString('en-IN')}`;
}

function intValue(value: unknown): number | null {
  const n = Number(value);
  return Number.isFinite(n) ? Math.round(n) : null;
}

function shortDate(value: unknown): string | null {
  const s = asString(value);
  if (!s) return null;
  try {
    return new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
  } catch {
    return null;
  }
}

const PAYMENT_LABEL: Record<string, string> = {
  cod: 'COD',
  prepaid: 'Prepaid',
  partial: 'Partial',
};

const FULFILLMENT_LABEL: Record<string, string> = {
  fulfilled: 'Delivered',
  rto: 'RTO',
  pending: 'Pending',
  in_transit: 'In transit',
  cancelled: 'Cancelled',
};

function factsFor(type: string, excerpt: Record<string, unknown>): string[] {
  const facts: string[] = [];
  if (type === 'order') {
    const total = rupee(excerpt.total_inr);
    if (total) facts.push(total);
    const payment = asString(excerpt.payment_method);
    if (payment) facts.push(PAYMENT_LABEL[payment] ?? payment);
    const pincode = asString(excerpt.pincode);
    if (pincode) facts.push(`pincode ${pincode}`);
    return facts;
  }
  if (type === 'shipment') {
    const status = asString(excerpt.fulfillment_status);
    if (status) facts.push(FULFILLMENT_LABEL[status] ?? status);
    const courier = asString(excerpt.courier_name);
    if (courier) facts.push(courier);
    const date = shortDate(excerpt.placed_at);
    if (date) facts.push(date);
    return facts;
  }
  if (type === 'ad_spend') {
    const campaign = asString(excerpt.campaign_name);
    if (campaign) facts.push(campaign);
    const spend = rupee(excerpt.spend_inr);
    if (spend) facts.push(`${spend} spend`);
    const purchases = intValue(excerpt.purchases_attributed);
    if (purchases !== null && purchases > 0) {
      facts.push(`${purchases} ${purchases === 1 ? 'purchase' : 'purchases'}`);
    }
    const date = shortDate(excerpt.date);
    if (date) facts.push(date);
    return facts;
  }
  return facts;
}

export function CitationBadge({ citations, children }: Props) {
  if (citations.length === 0) return <>{children}</>;
  const label = citations.length === 1 ? '1 source' : `${citations.length} sources`;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-help border-b border-dotted border-primary/50 hover:border-primary transition-colors">
          {children}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm">
        <div className="text-xs flex flex-col gap-2">
          <div className="text-[10px] uppercase tracking-wider text-fg-subtle font-medium">
            {label}
          </div>
          <div className="flex flex-col gap-2">
            {citations.map((c) => {
              const facts = factsFor(c.entity_type, c.excerpt ?? {});
              return (
                <div key={c.record_id} className="flex flex-col gap-0.5">
                  <div className="flex items-baseline gap-2">
                    <span className="text-fg font-medium">{entityLabel(c.entity_type)}</span>
                    <span className="font-mono text-fg-muted text-[10px]">{c.source_id}</span>
                  </div>
                  {facts.length > 0 && (
                    <div className="text-fg-muted text-[11px]">{facts.join(' · ')}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
