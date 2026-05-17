import { EmptyState } from '@/shared/components';
import { fmtIST } from '@/shared/utils/fmtIST';

import type { RecordSummary } from '../types/record.types';

const SOURCE_LABEL = {
  shopify: 'Shopify',
  meta_ads: 'Meta Ads',
  shiprocket: 'Shiprocket',
} as const;

const SOURCE_DOT_CLASS = {
  shopify: 'bg-primary',
  meta_ads: 'bg-pop',
  shiprocket: 'bg-success',
} as const;

const ENTITY_LABEL = {
  order: 'Order',
  shipment: 'Shipment',
  ad_spend: 'Ad spend',
} as const;

function sourceLabel(source: string): string {
  return SOURCE_LABEL[source as keyof typeof SOURCE_LABEL] ?? source;
}

function sourceDotClass(source: string): string {
  return SOURCE_DOT_CLASS[source as keyof typeof SOURCE_DOT_CLASS] ?? 'bg-fg-subtle';
}

function entityLabel(entity: string): string {
  return ENTITY_LABEL[entity as keyof typeof ENTITY_LABEL] ?? entity;
}

interface RecordsTableProps {
  items: RecordSummary[];
  onRowClick: (id: number) => void;
}

export function RecordsTable({ items, onRowClick }: RecordsTableProps) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="Your demo workspace is empty"
        hint="Run onboarding to load demo data."
        action={{ label: 'Go to onboarding', href: '/onboarding' }}
      />
    );
  }
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-fg-subtle">
          <tr>
            <th className="px-4 py-3 font-medium">Source</th>
            <th className="px-4 py-3 font-medium">Source ID</th>
            <th className="px-4 py-3 font-medium">Entity</th>
            <th className="px-4 py-3 font-medium">Fetched (IST)</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              className="cursor-pointer border-t border-border transition-colors hover:bg-surface-subtle"
              onClick={() => onRowClick(item.id)}
            >
              <td className="px-4 py-2.5 text-fg">
                <span className="inline-flex items-center gap-2">
                  <span
                    aria-hidden
                    className={`h-2 w-2 rounded-full ${sourceDotClass(item.source_system)}`}
                  />
                  {sourceLabel(item.source_system)}
                </span>
              </td>
              <td className="px-4 py-2.5 font-mono text-xs text-fg">{item.source_id}</td>
              <td className="px-4 py-2.5 text-fg">{entityLabel(item.entity_type)}</td>
              <td className="px-4 py-2.5 text-xs text-fg-muted">{fmtIST(item.fetched_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
