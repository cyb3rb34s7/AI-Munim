import { EmptyState } from '@/shared/components';

import type { RecordSummary } from '../types/record.types';

interface RecordsTableProps {
  items: RecordSummary[];
  onRowClick: (id: number) => void;
}

export function RecordsTable({ items, onRowClick }: RecordsTableProps) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="No records yet"
        hint="Go to Connectors, hit Connect (demo), then Sync now."
      />
    );
  }
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-bg-subtle text-xs uppercase text-muted">
          <tr>
            <th className="px-4 py-2 font-medium">Source</th>
            <th className="px-4 py-2 font-medium">Source ID</th>
            <th className="px-4 py-2 font-medium">Entity</th>
            <th className="px-4 py-2 font-medium">Fetched</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              className="cursor-pointer border-t border-border hover:bg-bg-subtle/50"
              onClick={() => onRowClick(item.id)}
            >
              <td className="px-4 py-2">{item.source_system}</td>
              <td className="px-4 py-2 font-mono text-xs">{item.source_id}</td>
              <td className="px-4 py-2">{item.entity_type}</td>
              <td className="px-4 py-2 text-xs text-muted">{item.fetched_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
